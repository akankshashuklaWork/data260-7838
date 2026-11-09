"""Objective HW9 smoke test: writes reports/hw09/verification.json.

It talks to Redis and uses stand-in agents instead of the language model, so it is quick and checks
behavior only. It creates temporary files and cache entries (all under my prefix) and never edits
application code.

    PYTHONPATH=code python -m hw9.verify_hw9
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from .config import (
    CONFIG,
    DEFAULT_THRESHOLD,
    EMBED_MODEL,
    PREFIX,
    RAW_DIR,
    REPORT_DIR,
    ROOT,
    SWEEP_THRESHOLDS,
)
from .ingress import QueryHandler
from .listing_db import ListingDatabase
from .part4 import run_part4
from .part4.answering_agent import AnsweringAgent
from .part4.evaluator_agent import EvaluatorAgent
from .part4.lessons import LESSONS_FILE, LessonStore
from .semantic_cache import INDEX_NAME, SemanticCache

CASES = ROOT / "code/hw9/cache_cases.yaml"
PART4 = ROOT / "code/hw9/part4"


def check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **({"detail": detail} if detail else {})}


class FakePipeline:
    """Stands in for the HW8 agents: returns a numbered answer and counts how often it is called."""

    def __init__(self) -> None:
        self.calls = 0

    async def ask(self, question: str, context: str = "") -> tuple[str, float]:
        self.calls += 1
        return f"answer {self.calls} for: {question} | {context}", 5.0


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


async def handler_checks(cache: SemanticCache, db: ListingDatabase) -> list[dict[str, Any]]:
    checks = []
    pipeline = FakePipeline()
    handler = QueryHandler(cache, db, pipeline)  # type: ignore[arg-type]
    cache.clear()
    question = "What is a security deposit used for?"
    miss = await handler.handle(question)
    hit = await handler.handle(question)
    calls_after_hit = pipeline.calls
    paraphrase = await handler.handle("What is a security deposit meant to cover?")
    unrelated = await handler.handle("What is the capital of France?")
    checks.append(
        check(
            "Miss runs the agent pipeline, stores the answer, and returns is_cached=false",
            miss["is_cached"] is False and pipeline.calls >= 1 and "latency_ms" in miss,
        )
    )
    checks.append(
        check(
            "Exact duplicate is a hit: is_cached=true, similarity ~1.0, pipeline not run again",
            hit["is_cached"] is True
            and hit["similarity"] >= 0.99
            and hit["answer"] == miss["answer"]
            and calls_after_hit == 1
            and "latency_ms" in hit,
            f"pipeline calls after the hit={calls_after_hit}",
        )
    )
    checks.append(
        check(
            "Paraphrase hits at threshold 0.85 and unrelated question misses",
            paraphrase["is_cached"] is True and unrelated["is_cached"] is False,
            f"paraphrase similarity={paraphrase['similarity']}, unrelated={unrelated['similarity']}",
        )
    )
    checks.append(
        check(
            "Stored entries have a data-version marker",
            cache.nearest(cache.embed(question))["data_version"] == "static",
        )
    )

    # Stale answer: change the record, show the stale hit, then the version check invalidates it.
    cache.clear()
    db.restore_seed(1)
    ask = "What is the monthly rent for the Maple Court two-bedroom apartment?"
    handler.check_data_version = False
    first = await handler.handle(ask)
    db.update_listing(1, monthly_rent=2650)
    stale = await handler.handle(ask)
    handler.check_data_version = True
    fresh = await handler.handle(ask)
    again = await handler.handle(ask)
    db.restore_seed(1)
    cache.clear()
    checks.append(
        check(
            "Without invalidation the cache returns the stale answer after the record changed",
            stale["is_cached"] is True and stale["answer"] == first["answer"],
        )
    )
    checks.append(
        check(
            "Version-marker invalidation recomputes the answer, then the new answer is cached",
            fresh["is_cached"] is False
            and fresh["data_version"] == "2"
            and again["is_cached"] is True,
        )
    )
    return checks


def part4_checks() -> list[dict[str, Any]]:
    checks = []
    evaluator = EvaluatorAgent()
    right = evaluator.evaluate("What is the monthly rent for Cedar Heights?", "The rent is $2,900.")
    wrong = evaluator.evaluate("What is the monthly rent for Cedar Heights?", "About $2,000.")
    refuse = evaluator.evaluate("What is the capital of France?", "I don't have that information.")
    guess = evaluator.evaluate("What is the capital of France?", "Paris.")
    checks.append(
        check(
            "Evaluator returns PASS/REVISE against the reference dataset, with feedback only on REVISE",
            right["result"] == "PASS"
            and right["feedback"] is None
            and wrong["result"] == "REVISE"
            and bool(wrong["feedback"])
            and bool(wrong["explanation"]),
        )
    )
    checks.append(
        check(
            "Unrelated questions: a refusal passes and an unsupported answer must be revised",
            refuse["result"] == "PASS" and guess["result"] == "REVISE",
        )
    )

    datasets = {
        n: json.loads((PART4 / n).read_text())
        for n in ("training_data.json", "validation_data.json", "test_data.json")
    }
    only_questions = all(
        set(item) == {"id", "question"} for rows in datasets.values() for item in rows
    )
    checks.append(
        check(
            "Training, validation, and test files contain only questions (no expected answers)",
            only_questions,
        )
    )
    questions = [item["question"] for rows in datasets.values() for item in rows]
    checks.append(
        check("The three question files do not overlap", len(questions) == len(set(questions)))
    )

    class AlwaysWrong(AnsweringAgent):
        def _chat(
            self, system: str, prompt: str
        ) -> str:  # a stand-in model that never gets it right
            return "About $2,000."

    run = run_part4.run_workflow(
        "What is the monthly rent for Cedar Heights?", AlwaysWrong(None), evaluator, repair=True
    )
    checks.append(
        check(
            "Stops after the second attempt and reports the final result",
            run["n_attempts"] == 2 and run["final_result"] == "REVISE",
        )
    )
    controlled = run_part4.run_workflow(
        "What is the monthly rent for Cedar Heights?",
        AnsweringAgent(None),
        evaluator,
        repair=False,
        initial_answer="About $2,000.",
    )
    checks.append(
        check(
            "A controlled flawed initial answer is detected as REVISE",
            controlled["attempts"][0]["evaluation"]["result"] == "REVISE",
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lessons.json"
        store = LessonStore(path, [])
        store.add(
            "The answer is wrong when asked about listed property facts.",
            "Check the reference dataset.",
        )
        store.save()
        seen: dict[str, str] = {}

        class Spy(AnsweringAgent):
            def _chat(self, system: str, prompt: str) -> str:
                seen["system"], seen["prompt"] = system, prompt
                return "The monthly rent is $2,900."

        Spy(LessonStore(path), track_usage=True).answer(
            "What is the monthly rent for Cedar Heights?"
        )
        reloaded = json.loads(path.read_text())[0]
        checks.append(
            check(
                "A saved lesson is loaded before answering and its use_count increases",
                "Check the reference dataset." in seen["system"] and reloaded["use_count"] == 1,
            )
        )
        fields = {"lesson_id", "failure_pattern", "correction", "created_at", "use_count"}
        checks.append(
            check(
                "lessons.json entries have the five required fields",
                all(set(item) == fields for item in json.loads(LESSONS_FILE.read_text()))
                and bool(json.loads(LESSONS_FILE.read_text())),
            )
        )

    # Validation gate: a lesson that breaks a previously correct answer must be rejected.
    class Harmful(AnsweringAgent):
        def _chat(self, system: str, prompt: str) -> str:
            return "About $3,000." if "HARM" in system else "The monthly rent is $2,900."

    validation = [{"id": "V1", "question": "What is the monthly rent for Cedar Heights?"}]
    before = run_part4.run_set(validation, Harmful(LessonStore(None, [])), evaluator)
    bad = {"failure_pattern": "wrong about listed property facts.", "correction": "HARM"}
    with patch.object(run_part4, "AnsweringAgent", Harmful):
        decision = run_part4.validate_candidate(
            bad, LessonStore(None, []), evaluator, validation, before
        )
    checks.append(
        check(
            "Validation gate rejects a lesson that causes a regression",
            decision["decision"] == "REJECT",
        )
    )
    return checks


def main() -> int:
    db_dir = tempfile.mkdtemp()
    db = ListingDatabase(db_path=str(Path(db_dir) / "verify.db"))
    cache = SemanticCache(DEFAULT_THRESHOLD)
    checks: list[dict[str, Any]] = []

    checks.append(
        check(
            "Redis is reachable and the vector index exists",
            cache.client.ping()
            and INDEX_NAME.encode()
            in [
                i if isinstance(i, bytes) else i.encode()
                for i in cache.client.execute_command("FT._LIST")
            ],
        )
    )

    # Part 1: counter increments on every access and syncs to the database on every 10th.
    db.reset_views(2)
    counts, synced = [], []
    for _ in range(25):
        counts.append(db.increment_listing_views(2))
        synced.append(db.last_synced)
    checks.append(
        check(
            "Counter returns 1..25 and keys start with the PREFIX",
            counts == list(range(1, 26))
            and db.redis_client.exists(f"{PREFIX}:views:listing:2") == 1,
        )
    )
    checks.append(
        check(
            "Database is written exactly on the 10th and 20th access",
            [i + 1 for i, s in enumerate(synced) if s] == [10, 20]
            and db.stored_view_count(2) == 20,
        )
    )
    db.reset_views(2)

    # Part 2 and 3.5 with a stand-in pipeline.
    checks += asyncio.run(handler_checks(cache, db))
    stray = [
        k.decode() for k in cache.client.scan_iter("*") if not k.decode().startswith(f"{PREFIX}")
    ]
    checks.append(
        check("Every Redis key starts with the PREFIX", not stray, f"stray keys: {stray[:3]}")
    )

    # Part 3 evidence.
    spec = yaml.safe_load(CASES.read_text())
    categories = {
        c: sum(1 for x in spec["cases"] if x["category"] == c)
        for c in ("exact_duplicate", "paraphrase", "superficially_similar", "unrelated")
    }
    checks.append(
        check(
            "cache_cases.yaml has 40 labeled cases: 10 of each category",
            len(spec["cases"]) == 40 and set(categories.values()) == {10},
            json.dumps(categories),
        )
    )
    history = git("log", "--format=%H %ct", "--", "code/hw9/cache_cases.yaml").splitlines()
    sweep = RAW_DIR / "part3_threshold_table.json"
    committed_first = int(history[-1].split()[1]) if history else None
    checks.append(
        check(
            "cache_cases.yaml was committed once, before the sweep results, and is unmodified",
            len(history) == 1
            and sweep.exists()
            and committed_first is not None
            and committed_first <= sweep.stat().st_mtime
            and git("status", "--porcelain", "code/hw9/cache_cases.yaml") == "",
        )
    )
    table = json.loads(sweep.read_text())["table"] if sweep.exists() else []
    checks.append(
        check(
            "Threshold table covers 0.75, 0.80, 0.85, 0.90, 0.95 with hit rate, false-hit rate, latency, cost",
            [r["threshold"] for r in table] == SWEEP_THRESHOLDS
            and all(
                {"hit_rate", "false_hit_rate", "mean_latency_ms", "total_cost"} <= set(r)
                for r in table
            ),
        )
    )
    false_hit = RAW_DIR / "part3_false_hit.json"
    checks.append(
        check(
            "One false hit is recorded in full (both queries, similarity, both answers)",
            false_hit.exists()
            and {
                "cached_query",
                "incoming_query",
                "similarity",
                "cached_answer_returned",
                "correct_answer",
            }
            <= set(json.loads(false_hit.read_text())),
        )
    )

    # Part 4.
    checks += part4_checks()
    variants = RAW_DIR / "part4_variants.json"
    names = (
        [r["variant"] for r in json.loads(variants.read_text())["table"]]
        if variants.exists()
        else []
    )
    checks.append(
        check(
            "Four variants were evaluated on the test set",
            names == ["Baseline", "Evaluator Repair", "Lesson Memory", "Validated Improvement"],
        )
    )
    candidates = RAW_DIR / "part4_validation.json"
    checks.append(
        check(
            "Lessons were created from training data only",
            candidates.exists()
            and all(
                str(i).startswith("T")
                for d in json.loads(candidates.read_text())["decisions"]
                for i in d.get("evidence_training_ids", [])
            ),
        )
    )

    cache.clear()
    db.close()
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "code/hw9"))
    result = {
        "homework": 9,
        "SID4": CONFIG.sid4,
        "commit_hash": commit,
        "uncommitted_changes_in_code_hw9": dirty,
        "model": f"{CONFIG.model} (agents, via Ollama); stand-in agents inside this self-check",
        "configuration": {
            "embedding_model": EMBED_MODEL,
            "default_threshold": DEFAULT_THRESHOLD,
            "sweep_thresholds": SWEEP_THRESHOLDS,
            "redis": "redis-stack-server 7.4 (vector index, COSINE)",
        },
        "hardware": CONFIG.hardware,
        "seed": CONFIG.seed,
        "verify_seed": CONFIG.verify_seed,
        "test_data_sha256": hashlib.sha256((PART4 / "test_data.json").read_bytes()).hexdigest()[
            :16
        ],
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, indent=2))
    for item in checks:
        print(
            ("PASS  " if item["passed"] else "FAIL  ")
            + item["name"]
            + (f"  [{item['detail']}]" if item.get("detail") and not item["passed"] else "")
        )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
