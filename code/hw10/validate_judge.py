"""Part 3.2 and 3.3: compare the judge with the human labels and test its repeatability.

Refuses to run until the evaluation cases and the human labels exist, are complete (20 labels,
1-5), and are committed with no later edits. The labels are the reference: they are never
regenerated or changed here.

    PYTHONPATH=code python -m hw10.validate_judge                 # documented settings, 3 runs
    PYTHONPATH=code python -m hw10.validate_judge --sensitivity   # plus 3 runs at temperature 0.7
    PYTHONPATH=code python -m hw10.validate_judge --skip-git-check   # development only
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import time

from hw8.common import log, utc_iso

from .config import (
    EVAL_CASES,
    HUMAN_LABELS,
    RAW_DIR,
    ROOT,
)
from .judge import LocalJudge, OllamaJudge, warm_up
from .validation_stats import mean_absolute_difference, repeatability, spearman

RUNS = 3
SENSITIVITY_TEMPERATURE = 0.7


def load_inputs() -> tuple[list[dict], dict[str, int]]:
    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8"))
    with open(HUMAN_LABELS, newline="", encoding="utf-8") as handle:
        labels = {row["case_id"]: int(row["human_score"]) for row in csv.DictReader(handle)}
    ids = [c["case_id"] for c in cases]
    if len(cases) != 20 or set(labels) != set(ids):
        raise SystemExit(f"need exactly 20 cases with a label each; have {len(labels)} labels")
    if any(not 1 <= v <= 5 for v in labels.values()):
        raise SystemExit("every human label must be an integer from 1 to 5")
    return cases, labels


def git_commit_of(path) -> str:
    """Hash of the commit that last touched the file; fails if it is untracked or modified."""
    relative = str(path.relative_to(ROOT))
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True, text=True
    )
    if tracked.returncode != 0:
        raise SystemExit(f"{relative} is not committed yet. Commit it before running the judge.")
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT)
    if dirty.returncode != 0:
        raise SystemExit(f"{relative} has uncommitted changes. Commit it (no edits after judging).")
    return subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", relative],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


def run_judge(judge: LocalJudge, cases: list[dict], run_no: int, label: str) -> list[dict]:
    results = []
    for case in cases:
        score = judge.helpfulness("writer", case["question"], case["draft"], case["context"])
        results.append(
            {
                "run": run_no,
                "case_id": case["case_id"],
                "score": score.score,
                "reason": score.reason,
                "judge_ms": round(score.judge_ms, 1),
            }
        )
    log("JUDGE", f"{label} run {run_no}: {[r['score'] for r in results]}")
    return results


def summarize(human: list[int], runs: list[list[int]]) -> dict:
    mean_scores = [sum(case) / len(case) for case in zip(*runs, strict=True)]
    return {
        "per_run": [
            {
                "run": i + 1,
                **{f"spearman_{k}": v for k, v in spearman(human, run).items()},
                "mean_abs_diff": mean_absolute_difference(human, run),
            }
            for i, run in enumerate(runs)
        ],
        "mean_of_runs": {
            **spearman(human, mean_scores),
            "mean_abs_diff": mean_absolute_difference(human, mean_scores),
        },
        "repeatability": repeatability(runs),
    }


def main() -> int:
    skip_git = "--skip-git-check" in sys.argv
    sensitivity = "--sensitivity" in sys.argv
    if not EVAL_CASES.exists() or not HUMAN_LABELS.exists():
        raise SystemExit("eval_cases.json and human_labels.csv must exist first (label_drafts).")
    cases, labels = load_inputs()
    commits = {}
    if not skip_git:
        commits = {p.name: git_commit_of(p) for p in (EVAL_CASES, HUMAN_LABELS)}
    human = [labels[c["case_id"]] for c in cases]

    judge = LocalJudge()
    log("JUDGE", f"warm-up {warm_up(judge):.0f} ms; settings={judge.settings()}")
    started = time.time()
    all_rows: list[dict] = []
    runs: list[list[int]] = []
    for run_no in range(1, RUNS + 1):
        rows = run_judge(judge, cases, run_no, "documented settings")
        all_rows += rows
        runs.append([r["score"] for r in rows])

    output: dict = {
        "created": utc_iso(),
        "criterion": "Writer Helpfulness (1-5) on the Writer draft",
        "judge_settings": judge.settings(),
        "frozen_files_committed_at": commits,
        "human_labels": dict(zip([c["case_id"] for c in cases], human, strict=True)),
        "runs": RUNS,
        "documented": summarize(human, runs),
        "seconds": round(time.time() - started, 1),
    }

    if sensitivity:
        hot = LocalJudge(OllamaJudge(temperature=SENSITIVITY_TEMPERATURE, seed=0))
        hot_runs = []
        for run_no in range(1, RUNS + 1):
            hot.llm.seed = (
                run_no * 1000
            )  # a different seed each run, as an unpinned deployment would
            rows = run_judge(hot, cases, run_no, f"temperature {SENSITIVITY_TEMPERATURE}")
            for r in rows:
                r["run"] = f"T{SENSITIVITY_TEMPERATURE}-{run_no}"
            all_rows += rows
            hot_runs.append([r["score"] for r in rows])
        output["sensitivity"] = {
            "temperature": SENSITIVITY_TEMPERATURE,
            "note": "seed changed each run; shows how repeatability degrades when sampling is on",
            **summarize(human, hot_runs),
        }
        runs_for_csv = runs + hot_runs
    else:
        runs_for_csv = runs

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_DIR / "judge_validation_cases.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        header = ["case_id", "human"] + [f"judge_run{i + 1}" for i in range(RUNS)]
        header += ["judge_mean"] + (
            [f"judge_T{SENSITIVITY_TEMPERATURE}_run{i + 1}" for i in range(RUNS)]
            if sensitivity
            else []
        )
        writer.writerow(header)
        for index, case in enumerate(cases):
            values = [runs_for_csv[i][index] for i in range(len(runs_for_csv))]
            mean_doc = sum(values[:RUNS]) / RUNS
            writer.writerow(
                [case["case_id"], human[index], *values[:RUNS], round(mean_doc, 3), *values[RUNS:]]
            )
    with open(RAW_DIR / "judge_validation_reasons.jsonl", "w", encoding="utf-8") as handle:
        for row in all_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (RAW_DIR / "judge_validation.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )

    doc = output["documented"]
    first = doc["per_run"][0]
    log("JUDGE", f"human vs judge run 1: spearman={first['spearman_rho']:.3f} "
        f"(p={first['spearman_p_value']:.4f}) MAD={first['mean_abs_diff']:.2f}")  # fmt: skip
    log("JUDGE", f"repeatability: {doc['repeatability']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
