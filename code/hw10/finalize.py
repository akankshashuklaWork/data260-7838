"""Copy the evidence behind the reported numbers into reports/hw10/raw and write METRICS.md.

    PYTHONPATH=code python -m hw10.finalize

Raw files written (all machine-readable, so every reported statistic can be recomputed):
    spans_reported.jsonl        every span of the 50-miss run, its 15 hit checks, and the 3 example traces
    eval_results_reported.jsonl the evaluator records for those traces (scores, reasons, messages)
    stage_latency*.json|csv     written earlier by hw10.analyze_latency
    judge_validation*.csv|json  written earlier by hw10.validate_judge
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from hw8.tracing import read_spans

from .config import CONFIG, EVAL_RESULTS, JUDGE_MODEL, RAW_DIR, REPORT_DIR
from .metrics import mean


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def export_raw() -> dict[str, int]:
    run = load(RAW_DIR / "latency_run.json")
    examples = load(RAW_DIR / "example_traces.json")
    if not run or not examples:
        return {}
    wanted = {m["trace_id"] for m in run["misses"]} | {h["trace_id"] for h in run["hits"]}
    wanted |= {run["warmup_trace_id"]} | {v["trace_id"] for v in examples.values()}
    spans = [s for s in read_spans() if s["trace_id"] in wanted]
    with open(RAW_DIR / "spans_reported.jsonl", "w", encoding="utf-8") as handle:
        for span in sorted(spans, key=lambda s: s["start"]):
            handle.write(json.dumps(span) + "\n")
    records = []
    if EVAL_RESULTS.exists():
        for line in EVAL_RESULTS.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["trace_id"] in wanted:
                records.append(record)
    with open(RAW_DIR / "eval_results_reported.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"spans": len(spans), "eval_records": len(records)}


def fmt(value: float, digits: int = 1) -> str:
    return (
        "n/a"
        if value is None or (isinstance(value, float) and math.isnan(value))
        else f"{value:,.{digits}f}"
    )


def write_metrics() -> None:
    lines = ["# HW10 Metrics", ""]
    run = load(RAW_DIR / "latency_run.json")
    miss_ids = {m["trace_id"] for m in run["misses"]} if run else set()
    reported = RAW_DIR / "eval_results_reported.jsonl"
    records = (
        [json.loads(line) for line in reported.read_text(encoding="utf-8").splitlines()]
        if reported.exists()
        else []
    )
    scored = [r for r in records if r["trace_id"] in miss_ids and r["status"] == "ok"]

    lines += ["## Part 2: automated evaluation of the Kafka pipeline", ""]
    if scored:
        lines += [
            f"Evaluated traces: {len(scored)} of {len(miss_ids)} cache-miss requests (judge {JUDGE_MODEL}, 1-5 scale).",
            "",
            "| Stage / criterion | Mean | Min | Max |",
            "|---|---:|---:|---:|",
        ]
        for key, label in (
            ("plan_quality", "Plan Quality (Planner)"),
            ("writer_helpfulness", "Writer Helpfulness (draft)"),
            ("final_helpfulness", "Final Answer Helpfulness (Reviewer output)"),
        ):
            values = [r["scores"][key]["score"] for r in scored]
            lines.append(f"| {label} | {mean(values):.2f} | {min(values)} | {max(values)} |")
        diffs = [r["improvement"]["difference"] for r in scored]
        identical = sum(1 for r in scored if r["improvement"]["text_identical"])
        lines += [
            "",
            f"Final minus draft: mean {mean(diffs):+.2f}, min {min(diffs):+d}, max {max(diffs):+d}; "
            f"the final answer was word-for-word the draft in {identical} of {len(scored)} cases.",
            "",
        ]
    else:
        lines += ["Not run yet.", ""]

    validation = load(RAW_DIR / "judge_validation.json")
    lines += ["## Part 3: judge validation (20 frozen drafts, Writer Helpfulness)", ""]
    if validation:
        doc = validation["documented"]
        lines += [
            "| Run | Spearman rho | p-value | Mean absolute difference |",
            "|---:|---:|---:|---:|",
        ]
        for r in doc["per_run"]:
            lines.append(
                f"| {r['run']} | {r['spearman_rho']:.3f} | {r['spearman_p_value']:.4f} | {r['mean_abs_diff']:.2f} |"
            )
        mr = doc["mean_of_runs"]
        lines.append(
            f"| mean of 3 runs | {mr['rho']:.3f} | {mr['p_value']:.4f} | {mr['mean_abs_diff']:.2f} |"
        )
        rep = doc["repeatability"]
        lines += [
            "",
            "| Repeatability over 3 runs | Value |",
            "|---|---:|",
            f"| Cases whose score changed in at least one run | {100 * rep['cases_changed']:.1f}% |",
            f"| (case, run-pair) comparisons that differ | {100 * rep['pairs_changed']:.1f}% |",
            f"| Mean absolute change (points) | {rep['mean_abs_change']:.3f} |",
            f"| Maximum absolute change (points) | {rep['max_abs_change']:.0f} |",
            "",
        ]
        if "sensitivity" in validation:
            s = validation["sensitivity"]
            lines.append(
                f"Sensitivity (temperature {s['temperature']}, new seed per run): cases changed "
                f"{100 * s['repeatability']['cases_changed']:.1f}%, mean / max absolute change "
                f"{s['repeatability']['mean_abs_change']:.3f} / {s['repeatability']['max_abs_change']:.0f}."
            )
            lines.append("")
    else:
        lines += ["Not run yet: needs the committed human labels (`make validate-hw10`).", ""]

    examples = load(RAW_DIR / "example_traces.json")
    lines += ["## Part 4.2: example traces", ""]
    if examples:
        lines += ["| Trace | trace_id | Detail |", "|---|---|---|"]
        e = examples
        lines += [
            f"| Cache hit | `{e['cache_hit']['trace_id']}` | similarity {e['cache_hit']['similarity']}, {e['cache_hit']['latency_ms']:.1f} ms |",
            f"| Cache miss (success) | `{e['cache_miss']['trace_id']}` | {e['cache_miss']['latency_ms']:.0f} ms (first request after start) |",
            f"| Failed | `{e['failed']['trace_id']}` | stage `{e['failed']['failed_stage']}`: {e['failed']['error']} |",
            "",
        ]

    table = load(RAW_DIR / "stage_latency.json")
    lines += ["## Part 4.3: stage latency on 50 confirmed cache misses", ""]
    if table:
        lines += [
            "| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |",
            "|---|---:|---:|---:|",
        ]
        for row in table["rows"]:
            lines.append(
                f"| {row['stage']} | {fmt(row['p50_ms'])} | {fmt(row['p95_ms'])} | {fmt(row['pct_of_e2e'])}% |"
            )
        e2e, req, hit = table["e2e"], table["request"], table["cache_hit"]
        lines += [
            "",
            f"End-to-end (cache lookup start to evaluation end): p50 {fmt(e2e['p50_ms'])} ms, p95 {fmt(e2e['p95_ms'])} ms. "
            f"User-facing (request span, answer returned): p50 {fmt(req['p50_ms'])} ms, p95 {fmt(req['p95_ms'])} ms. "
            f"Time outside any span: {fmt(table['unaccounted_pct_of_e2e'])}% of end-to-end. Dominant stage: {table['dominant']}.",
            "",
            f"Cache-hit latency (separate, {hit['n']} repeated questions, all served from cache: {hit['all_cached']}): "
            f"request p50 {fmt(hit['request_p50_ms'])} ms, p95 {fmt(hit['request_p95_ms'])} ms; "
            f"cache lookup p50 {fmt(hit['lookup_p50_ms'])} ms, p95 {fmt(hit['lookup_p95_ms'])} ms.",
            "",
            f"All 50 responses reported is_cached=false: {table['confirmed_misses']}.",
            "",
        ]
    else:
        lines += ["Not run yet.", ""]

    verification = load(REPORT_DIR / "verification.json")
    lines += ["## Self-check", ""]
    if verification:
        passed = sum(1 for c in verification["checks"] if c["passed"])
        lines.append(
            f"`verification.json`: {passed} / {len(verification['checks'])} checks passed (commit {verification['commit_hash'][:12]})."
        )
    else:
        lines.append("Not run yet.")
    (REPORT_DIR / "METRICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_DIR / 'METRICS.md'} (sid4={CONFIG.sid4})")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("exported:", export_raw())
    write_metrics()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
