"""Objective HW10 smoke test: writes reports/hw10/verification.json.

It starts its own Planner/Writer/Reviewer processes in stub mode (no language model), runs the
evaluator in-process with a fake judge, and sends requests through the real ingress logic, the
real Kafka topics, and the real Redis cache. It checks behavior (spans, trace propagation, bounded
evaluator, statistics, dashboard pages), not exact wording. Temporary files go to a temp folder, the
cache entries it creates carry a unique marker and are removed, and application code is never edited.

The live stack must be stopped first (`python -m hw10.stack down`) so no other agent consumes the
test messages.

    PYTHONPATH=code python -m hw10.verify_hw10
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import math
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import hw8.tracing as tracing
from aiokafka import AIOKafkaProducer
from hw8.harness import AgentProcess, wait_until
from hw8.tracing import new_trace_id, read_spans, span, write_span
from hw9.ingress import QueryHandler
from hw9.listing_db import ListingDatabase
from hw9.pipeline_client import PipelineClient
from hw9.semantic_cache import KEY_PREFIX, SemanticCache

from . import stack
from .collector import Bundle, Collector
from .config import (
    CONFIG,
    EVAL_CASES,
    HUMAN_LABELS,
    JUDGE_MODEL,
    KAFKA_BOOTSTRAP,
    RAW_DIR,
    REPORT_DIR,
    ROOT,
)
from .evaluator import Evaluator, interpret_improvement
from .judge import Score
from .metrics import percentile, request_rows, stage_latency_table, summarize_requests
from .validation_stats import mean_absolute_difference, repeatability, spearman

PIPELINE_STAGES = {
    "request",
    "cache_lookup",
    "queue_inbox",
    "planner",
    "queue_tasks",
    "writer",
    "queue_drafts",
    "reviewer",
    "queue_final",
    "evaluation",
}


def check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **({"detail": detail} if detail else {})}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


class FakeJudge:
    """Stands in for the local model: instant, deterministic, and able to fail on demand."""

    def __init__(self) -> None:
        self.fail = False
        self.llm = SimpleNamespace(model_name="fake-judge", generate=lambda prompt: "ready")

    def settings(self) -> dict[str, Any]:
        return {"judge_model": "fake-judge"}

    def _maybe_fail(self) -> None:
        if self.fail:
            raise ConnectionError("judge unavailable (simulated)")

    def plan_quality(self, question: str, plan: list[str]) -> Score:
        self._maybe_fail()
        return Score("Plan Quality", 4, "plan is relevant", 1.0)

    def helpfulness(self, which: str, question: str, answer: str, context: str = "") -> Score:
        self._maybe_fail()
        return Score(f"{which} helpfulness", 3 if which == "writer" else 3, "fine", 1.0)


# ---------------------------------------------------------------------------------------------
# A. Checks that need no services
# ---------------------------------------------------------------------------------------------
def offline_checks() -> list[dict[str, Any]]:
    checks = []
    with (
        tempfile.TemporaryDirectory() as tmp,
        patch.object(tracing, "SPAN_FILE", Path(tmp) / "s.jsonl"),
    ):
        trace = new_trace_id()
        write_span(trace, "planner", 100.0, 100.5, service="planner", attempt=1)
        try:
            with span(trace, "writer", service="writer"):
                raise ValueError("boom")
        except ValueError:
            pass
        ignored = write_span(None, "planner", 1.0, 2.0)
        spans = read_spans()
        first, second = spans[0], spans[1]
        checks.append(
            check(
                "Span has trace_id, stage, start, end, status, error and a duration",
                all(k in first for k in ("trace_id", "stage", "start", "end", "status", "error"))
                and first["duration_ms"] == 500.0
                and first["status"] == "ok"
                and first["error"] is None,
            )
        )
        checks.append(
            check(
                "A failing block is recorded as status=error with the exception text, then re-raised",
                second["status"] == "error" and "boom" in second["error"],
            )
        )
        checks.append(
            check("A span without a trace_id is not written", ignored is None and len(spans) == 2)
        )

    values = [float(v) for v in range(1, 101)]
    summaries = [
        {
            "e2e_ms": 200.0,
            "request_ms": 60.0,
            "stage_ms": {
                "cache_lookup": 10,
                "planner": 40,
                "writer": 30,
                "queue_inbox": 1,
                "evaluation": 35,
            },
        },
        {
            "e2e_ms": 240.0,
            "request_ms": 70.0,
            "stage_ms": {
                "cache_lookup": 12,
                "planner": 44,
                "writer": 34,
                "queue_inbox": 2,
                "evaluation": 40,
            },
        },
    ]
    table = stage_latency_table(summaries)
    shares = {r["stage"]: r["pct_of_e2e"] for r in table["rows"]}
    checks.append(
        check(
            "Percentiles use linear interpolation (p50 of 1..100 is 50.5, p95 is 95.05)",
            math.isclose(percentile(values, 50), 50.5)
            and math.isclose(percentile(values, 95), 95.05),
        )
    )
    checks.append(
        check(
            "Stage table: % of end-to-end is mean stage / mean end-to-end and the shares total <= 100",
            math.isclose(shares["Planner"], 100 * 42 / 220)
            and sum(shares.values()) <= 100.0
            and table["dominant"] == "Planner",
            f"planner share={shares['Planner']:.2f}",
        )
    )

    human = [1, 2, 3, 4, 5]
    runs = [[3, 4, 5], [3, 4, 5], [3, 5, 5]]
    rep = repeatability(runs)
    checks.append(
        check(
            "Spearman is +1 for the same order, -1 for the reverse order, and NaN for a constant judge",
            math.isclose(spearman(human, [10, 20, 30, 40, 50])["rho"], 1.0)
            and math.isclose(spearman(human, [5, 4, 3, 2, 1])["rho"], -1.0)
            and math.isnan(spearman(human, [3, 3, 3, 3, 3])["rho"]),
        )
    )
    checks.append(
        check(
            "Mean absolute difference and repeatability match a hand-computed example",
            math.isclose(mean_absolute_difference([1, 2, 3], [1, 3, 5]), 1.0)
            and math.isclose(rep["cases_changed"], 1 / 3)
            and math.isclose(rep["pairs_changed"], 2 / 9)
            and rep["max_abs_change"] == 1,
            json.dumps({k: round(v, 3) for k, v in rep.items()}),
        )
    )

    collector = Collector()
    with (
        tempfile.TemporaryDirectory() as tmp,
        patch("hw10.collector.EVAL_EVENTS", Path(tmp) / "e.jsonl"),
    ):
        bad_json = collector.add(f"{CONFIG.prefix}_tasks", b"{not json")
        bad_shape = collector.add(f"{CONFIG.prefix}_tasks", b'["a list"]')
        no_id = collector.add(f"{CONFIG.prefix}_tasks", b'{"plan": []}')
        partial = Bundle("t-partial", plan={"a": 1})
        started = time.time()
        completed = asyncio.run(collector.wait_for_all(partial, timeout=0.2))
        waited = time.time() - started
    checks.append(
        check(
            "Malformed evaluator input is skipped and an incomplete join gives up after its timeout",
            bad_json is None
            and bad_shape is None
            and no_id is None
            and completed is False
            and waited < 2,
            f"waited {waited:.2f}s",
        )
    )
    note = interpret_improvement("same text", "same text", 4, 4, "approved")
    checks.append(
        check(
            "Final-vs-draft interpretation states plainly when the final answer is the draft",
            "word-for-word" in note and "+0" in note,
        )
    )
    return checks


# ---------------------------------------------------------------------------------------------
# B. Live checks: Kafka + Redis + stub agents + in-process evaluator with a fake judge
# ---------------------------------------------------------------------------------------------
async def wait_async(condition, timeout: float, poll: float = 0.1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        await asyncio.sleep(poll)
    return False


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def live_checks(tmp: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    spans_file, eval_file, events_file = (
        tmp / "spans.jsonl",
        tmp / "eval.jsonl",
        tmp / "events.jsonl",
    )
    marker = f"verify10-{uuid.uuid4().hex[:6]}"
    run_id = uuid.uuid4().hex[:6]
    agents = [
        AgentProcess(
            f"{name}.py",
            {
                "AGENT_LLM": "stub",
                "AUTO_OFFSET_RESET": "latest",
                "GROUP_ID": f"{CONFIG.prefix}_{name}_verify10_{run_id}",
                "PROCESSED_DB": str(tmp / f"{name}.db"),
                "TRACE_FILE": str(spans_file),
            },
            tmp / f"{name}.log",
        )
        for name in ("planner", "writer", "reviewer")
    ]
    judge = FakeJudge()
    evaluator = Evaluator(judge)  # type: ignore[arg-type]
    eval_task: asyncio.Task | None = None
    pipeline = PipelineClient()
    cache = SemanticCache()
    db = ListingDatabase()
    state: dict[str, Any] = {}
    try:
        with (
            patch.object(tracing, "SPAN_FILE", spans_file),
            patch("hw10.evaluator.EVAL_RESULTS", eval_file),
            patch("hw10.collector.EVAL_EVENTS", events_file),
            patch("hw10.dashboard.SPANS", spans_file, create=True),
        ):
            for agent in agents:
                wait_until(
                    lambda a=agent: any("Consumer is ready" in x for x in a.lines()),
                    60,
                    f"{agent.script} ready",
                )
            await pipeline.start()
            handler = QueryHandler(cache, db, pipeline)
            eval_task = asyncio.create_task(evaluator.run())
            await asyncio.sleep(4)  # let the evaluator join its consumer group

            # A malformed message on the final topic must be skipped without stopping the evaluator.
            producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
            await producer.start()
            await producer.send_and_wait(CONFIG.final_topic, b"{this is not json")
            await producer.stop()

            question = f"[{marker}] What is a security deposit used for in a rental lease?"
            miss = await handler.handle(question)
            hit = await handler.handle(question)
            failed = await handler.handle("   ")
            await wait_async(
                lambda: any(r["trace_id"] == miss["trace_id"] for r in read_jsonl(eval_file)), 40
            )

            judge.fail = (
                True  # the judge goes away: the evaluator must record the failure and move on
            )
            miss_dead_judge = await handler.handle(
                f"[{marker}] Which utilities does a landlord usually pay for?"
            )
            await wait_async(
                lambda: any(
                    r["trace_id"] == miss_dead_judge["trace_id"] for r in read_jsonl(eval_file)
                ),
                40,
            )
            judge.fail = False
            miss_after = await handler.handle(
                f"[{marker}] How should a tenant report a broken window?"
            )
            await wait_async(
                lambda: any(r["trace_id"] == miss_after["trace_id"] for r in read_jsonl(eval_file)),
                40,
            )
            await asyncio.sleep(0.5)

            spans = read_spans(spans_file)
            records = {r["trace_id"]: r for r in read_jsonl(eval_file)}
            by_trace: dict[str, list[dict[str, Any]]] = {}
            for s in spans:
                by_trace.setdefault(s["trace_id"], []).append(s)
            stages = lambda t: {s["stage"] for s in by_trace.get(t, [])}  # noqa: E731

            checks.append(
                check(
                    "Cache miss: one trace_id has spans for the cache lookup, every queue, all three agents, and the evaluation",
                    miss["is_cached"] is False and PIPELINE_STAGES <= stages(miss["trace_id"]),
                    f"stages={sorted(stages(miss['trace_id']))}",
                )
            )
            services = {s["service"].split("-")[0] for s in by_trace[miss["trace_id"]]}
            checks.append(
                check(
                    "The spans come from separate processes (ingress, PLANNER, WRITER, REVIEWER, evaluator)",
                    {"ingress", "PLANNER", "WRITER", "REVIEWER", "evaluator"} <= services,
                    f"services={sorted(services)}",
                )
            )
            record = records.get(miss["trace_id"], {})
            messages = record.get("messages", {})
            checks.append(
                check(
                    "The Planner plan, Writer draft and Reviewer final all carry the same correlation_id as the trace_id",
                    len(messages) == 3
                    and all(
                        m and m.get("correlation_id") == miss["trace_id"] for m in messages.values()
                    ),
                )
            )
            queue = [s for s in by_trace[miss["trace_id"]] if s["stage"].startswith("queue_")]
            checks.append(
                check(
                    "Queue-wait spans exist for all four topics with non-negative, sane durations",
                    len(queue) == 4 and all(0 <= s["duration_ms"] < 5000 for s in queue),
                    f"{[(s['stage'], round(s['duration_ms'], 1)) for s in queue]}",
                )
            )
            lookup = next(s for s in by_trace[hit["trace_id"]] if s["stage"] == "cache_lookup")
            checks.append(
                check(
                    "Cache hit: cache_lookup says hit, the request is marked cached, and no agent ran",
                    hit["is_cached"] is True
                    and lookup["attrs"]["result"] == "hit"
                    and stages(hit["trace_id"]) == {"cache_lookup", "request"},
                    f"stages={sorted(stages(hit['trace_id']))}",
                )
            )
            fail_spans = by_trace[failed["trace_id"]]
            planner_errors = [
                s for s in fail_spans if s["stage"] == "planner" and s["status"] == "error"
            ]
            dead = [s for s in fail_spans if s["stage"] == "dead_letter"]
            req = next(s for s in fail_spans if s["stage"] == "request")
            checks.append(
                check(
                    "Failed trace: the Planner span shows the error, a dead_letter span follows, and the request names the failing stage",
                    failed.get("failed_stage") == "planner"
                    and len(planner_errors) >= 1
                    and "non-empty question" in (planner_errors[0]["error"] or "")
                    and len(dead) == 1
                    and req["status"] == "error"
                    and req["attrs"].get("failed_stage") == "planner",
                    f"planner error attempts={len(planner_errors)}",
                )
            )

            scores = record.get("scores", {})
            valid = all(
                isinstance(scores.get(k, {}).get("score"), int) and 1 <= scores[k]["score"] <= 5
                for k in ("plan_quality", "writer_helpfulness", "final_helpfulness")
            )
            imp = record.get("improvement", {})
            checks.append(
                check(
                    "Evaluator saves Plan Quality, Writer Helpfulness (with trace_id), Final Helpfulness (with final answer) on a 1-5 scale",
                    record.get("status") == "ok"
                    and valid
                    and scores["writer_helpfulness"].get("trace_id") == miss["trace_id"]
                    and bool(scores["final_helpfulness"].get("final_answer")),
                )
            )
            checks.append(
                check(
                    "Final-vs-draft improvement stores both scores, their difference, and an interpretation",
                    imp.get("difference") == imp.get("final_score", 0) - imp.get("draft_score", 0)
                    and bool(imp.get("interpretation"))
                    and "text_identical" in imp,
                )
            )
            events = read_jsonl(events_file)
            dead_judge_record = records.get(miss_dead_judge["trace_id"], {})
            after_record = records.get(miss_after["trace_id"], {})
            checks.append(
                check(
                    "A malformed message and an unavailable judge are recorded and do not stop the evaluator",
                    any(e["event"] == "malformed_message" for e in events)
                    and dead_judge_record.get("status") == "error"
                    and "unavailable" in (dead_judge_record.get("error") or "")
                    and after_record.get("status") == "ok"
                    and any(
                        s["stage"] == "evaluation" and s["status"] == "error"
                        for s in by_trace[miss_dead_judge["trace_id"]]
                    ),
                )
            )

            all_rows = request_rows(spans)
            summary = summarize_requests(all_rows)
            checks.append(
                check(
                    "Summary metrics from spans: 5 requests, 1 hit, 1 error, and hit rate / error rate follow from the counts",
                    summary["requests"] == 5
                    and summary["hits"] == 1
                    and summary["errors"] == 1
                    and math.isclose(summary["hit_rate"], 0.2)
                    and math.isclose(summary["error_rate"], 0.2),
                    json.dumps({k: summary[k] for k in ("requests", "hits", "misses", "errors")}),
                )
            )
            state = {
                "miss": miss["trace_id"],
                "hit": hit["trace_id"],
                "failed": failed["trace_id"],
                "summary": summary,
            }
            checks.extend(dashboard_checks(spans_file, eval_file, state))
    finally:
        if eval_task:
            eval_task.cancel()
            await asyncio.gather(eval_task, return_exceptions=True)
        await pipeline.stop()
        for agent in agents:
            agent.stop()
        # Remove only the cache entries this test created (their text carries the unique marker).
        for key in cache.client.scan_iter(match=f"{KEY_PREFIX}*", count=500):
            query = cache.client.hget(key, "query")
            if query and marker.encode() in query:
                cache.client.delete(key)
        db.close()
    return checks, state


# ---------------------------------------------------------------------------------------------
# C. Dashboard pages render and show the numbers computed from the data
# ---------------------------------------------------------------------------------------------
def _run_page(page: str, trace_id: str = "") -> None:
    import streamlit as st

    from hw10 import dashboard

    if trace_id:
        st.session_state["trace_id"] = trace_id
    getattr(dashboard, page)()


def dashboard_checks(
    spans_file: Path, eval_file: Path, state: dict[str, Any]
) -> list[dict[str, Any]]:
    from streamlit.testing.v1 import AppTest

    checks = []
    with (
        patch("hw10.dashboard.SPANS", spans_file),
        patch("hw10.dashboard.EVAL_RESULTS", eval_file),
    ):
        summary = AppTest.from_function(_run_page, args=("summary_page",)).run(timeout=120)
        metrics = {m.label: m.value for m in summary.metric}
        checks.append(
            check(
                "Summary page renders without an error and shows request count, hit rate, and error rate",
                not summary.exception
                and metrics.get("Requests") == "5"
                and metrics.get("Semantic-cache hit rate") == "20.0%"
                and metrics.get("Error rate") == "20.0%",
                f"metrics={metrics}",
            )
        )
        evaluation = AppTest.from_function(_run_page, args=("evaluation_page",)).run(timeout=120)
        checks.append(
            check(
                "Evaluation page renders without an error",
                not evaluation.exception,
                str([e.value for e in evaluation.exception][:1]),
            )
        )
        outcomes = {}
        for key, expected in (("miss", "CACHE MISS"), ("hit", "CACHE HIT"), ("failed", "FAILED")):
            page = AppTest.from_function(_run_page, args=("trace_page", state[key])).run(
                timeout=120
            )
            texts = [e.value for e in (*page.info, *page.success, *page.error)]
            outcomes[key] = (not page.exception) and any(expected in t for t in texts)
        checks.append(
            check(
                "Trace page labels the cache-hit, cache-miss, and failed paths differently for the right trace_id",
                all(outcomes.values()),
                json.dumps(outcomes),
            )
        )
    return checks


# ---------------------------------------------------------------------------------------------
# D. Frozen evaluation artifacts
# ---------------------------------------------------------------------------------------------
def artifact_checks() -> list[dict[str, Any]]:
    checks = []
    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8")) if EVAL_CASES.exists() else []
    ids = [c.get("case_id") for c in cases]
    checks.append(
        check(
            "eval_cases.json holds 20 distinct Writer drafts, each with its trace_id and question",
            len(cases) == 20
            and len(set(ids)) == 20
            and all(c.get("draft") and c.get("trace_id") and c.get("question") for c in cases),
        )
    )
    if HUMAN_LABELS.exists():
        with open(HUMAN_LABELS, newline="", encoding="utf-8") as handle:
            labels = {r["case_id"]: r["human_score"] for r in csv.DictReader(handle)}
        checks.append(
            check(
                "human_labels.csv has one whole-number 1-5 label for each of the 20 cases",
                set(labels) == set(ids)
                and all(v in {"1", "2", "3", "4", "5"} for v in labels.values()),
            )
        )
        result_file = RAW_DIR / "judge_validation.json"
        if result_file.exists():
            created = json.loads(result_file.read_text(encoding="utf-8"))["created"]
            label_commit_time = git(
                "log", "-1", "--format=%cI", "--", str(HUMAN_LABELS.relative_to(ROOT))
            )
            from datetime import datetime

            before = datetime.fromisoformat(label_commit_time) < datetime.fromisoformat(
                created.replace("Z", "+00:00")
            )
            checks.append(
                check(
                    "The human labels were committed before the judge scores were produced", before
                )
            )
    return checks


def main() -> int:
    running = {n: p for n, p in stack.status().items() if p and n != "ingress_http"}
    if running:
        raise SystemExit("Stop the live stack first: PYTHONPATH=code python -m hw10.stack down")
    checks = offline_checks()
    with tempfile.TemporaryDirectory() as tmp:
        live, _ = asyncio.run(live_checks(Path(tmp)))
    checks += live + artifact_checks()

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "code/hw10", "code/hw8", "code/hw9"))
    result = {
        "homework": 10,
        "SID4": CONFIG.sid4,
        "commit_hash": commit,
        "uncommitted_changes_in_code": dirty,
        "model": f"{CONFIG.model} (agents, via Ollama); stub agents and a fake judge inside this self-check",
        "configuration": {
            "judge_model": JUDGE_MODEL,
            "judge_temperature": 0,
            "judge_scale": "1-5",
            "kafka": KAFKA_BOOTSTRAP,
            "redis": "redis-stack-server 7.4",
        },
        "hardware": CONFIG.hardware,
        "seed": CONFIG.seed,
        "verify_seed": CONFIG.verify_seed,
        "eval_cases_sha256": hashlib.sha256(EVAL_CASES.read_bytes()).hexdigest()[:16]
        if EVAL_CASES.exists()
        else None,
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
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    raise SystemExit(main())
