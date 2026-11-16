"""Part 4.3: turn the 50-miss run into the stage-latency table (p50, p95, % of end-to-end).

Reads ``reports/hw10/raw/latency_run.json`` (written by hw10.loadtest) and the span file, and writes
``stage_latency.json`` plus a per-trace CSV so every number can be recomputed.

    PYTHONPATH=code python -m hw10.analyze_latency
"""

from __future__ import annotations

import csv
import json

from hw8.tracing import read_spans

from .config import RAW_DIR
from .metrics import STAGE_ROWS, group_by_trace, percentile, stage_latency_table, trace_summary


def main() -> int:
    run = json.loads((RAW_DIR / "latency_run.json").read_text(encoding="utf-8"))
    by_trace = group_by_trace(read_spans())
    miss_ids = [m["trace_id"] for m in run["misses"]]
    summaries = [trace_summary(by_trace[t]) for t in miss_ids]
    assert all(s["path"] == "cache_miss" and s["status"] == "ok" for s in summaries)
    table = stage_latency_table(summaries)

    hit_ms = [by_trace[h["trace_id"]] for h in run["hits"]]
    hit_summaries = [trace_summary(t) for t in hit_ms]
    hit_request = [s["request_ms"] for s in hit_summaries]
    hit_lookup = [s["stage_ms"].get("cache_lookup", float("nan")) for s in hit_summaries]
    table["cache_hit"] = {
        "n": len(hit_request),
        "all_cached": all(s["path"] == "cache_hit" for s in hit_summaries),
        "request_p50_ms": percentile(hit_request, 50),
        "request_p95_ms": percentile(hit_request, 95),
        "lookup_p50_ms": percentile(hit_lookup, 50),
        "lookup_p95_ms": percentile(hit_lookup, 95),
    }
    table["confirmed_misses"] = all(not m["is_cached"] for m in run["misses"])
    table["run"] = {k: run[k] for k in ("started", "finished", "judge_model")}
    (RAW_DIR / "stage_latency.json").write_text(
        json.dumps(table, indent=2) + "\n", encoding="utf-8"
    )

    columns = ["trace_id", "e2e_ms", "request_ms", "queue_ms"] + [label for label, _ in STAGE_ROWS]
    with open(RAW_DIR / "stage_latency_per_trace.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for s in summaries:
            stage_values = []
            for _label, stages in STAGE_ROWS:
                stage_values.append(round(sum(s["stage_ms"].get(x, 0.0) for x in stages), 3))
            writer.writerow(
                [
                    s["trace_id"],
                    round(s["e2e_ms"], 3),
                    round(s["request_ms"], 3),
                    round(s["queue_ms"], 3),
                ]
                + stage_values
            )

    print(f"{'Stage':20s} {'p50 ms':>10s} {'p95 ms':>10s} {'% of e2e':>9s}")
    for row in table["rows"]:
        print(
            f"{row['stage']:20s} {row['p50_ms']:10.1f} {row['p95_ms']:10.1f} {row['pct_of_e2e']:8.1f}%"
        )
    print(f"end-to-end p50={table['e2e']['p50_ms']:.0f}ms p95={table['e2e']['p95_ms']:.0f}ms; "
          f"unaccounted={table['unaccounted_pct_of_e2e']:.1f}%; dominant={table['dominant']}")  # fmt: skip
    print(f"cache-hit: {table['cache_hit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
