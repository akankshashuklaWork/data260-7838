"""Pure functions that turn span files into the numbers shown on the dashboard and in the report.

The dashboard, the latency analysis, and the verification script all import from here, so a number
cannot differ between the screenshot and the report.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from hw8.tracing import QUEUE_STAGES

# Rows of the Part 4.3 table: (label, span stage(s)).
STAGE_ROWS: list[tuple[str, list[str]]] = [
    ("Cache lookup", ["cache_lookup"]),
    ("Planner", ["planner"]),
    ("Writer", ["writer"]),
    ("Reviewer", ["reviewer"]),
    ("Queue wait (total)", QUEUE_STAGES),
    ("Evaluation", ["evaluation"]),
]


def percentile(values: list[float], q: float) -> float:
    """Percentile with linear interpolation between ranks (same as numpy's default)."""
    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def group_by_trace(spans: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in spans:
        grouped[span["trace_id"]].append(span)
    return grouped


def trace_summary(trace_spans: list[dict[str, Any]]) -> dict[str, Any]:
    """One row per trace: per-stage milliseconds, queue total, and end-to-end time.

    * stage_ms uses the last *successful* span of each stage (a retried stage keeps its final try).
    * queue_ms is the sum of the four queue-wait spans.
    * e2e_ms is first span start -> last span end: from the cache lookup to the evaluation result.
    """
    stage_ms: dict[str, float] = {}
    for span in sorted(trace_spans, key=lambda s: s["start"]):
        if span["status"] == "ok":
            stage_ms[span["stage"]] = span["duration_ms"]
    queue_ms = sum(stage_ms.get(stage, 0.0) for stage in QUEUE_STAGES)
    request = next((s for s in trace_spans if s["stage"] == "request"), None)
    start = min(s["start"] for s in trace_spans)
    end = max(s["end"] for s in trace_spans)
    attrs = request["attrs"] if request else {}
    return {
        "trace_id": trace_spans[0]["trace_id"],
        "start": start,
        "end": end,
        "stage_ms": stage_ms,
        "queue_ms": queue_ms,
        "e2e_ms": (end - start) * 1000,
        "request_ms": request["duration_ms"] if request else math.nan,
        "path": attrs.get("path", "unknown"),
        "status": request["status"] if request else "no_request_span",
        "error": request["error"] if request else None,
        "failed_stage": attrs.get("failed_stage"),
        "has_evaluation": "evaluation" in stage_ms,
    }


def request_rows(spans: list[dict[str, Any]], since: float | None = None) -> list[dict[str, Any]]:
    """One row per ingress request (a trace that has a `request` span), oldest first."""
    rows = []
    for trace_spans in group_by_trace(spans).values():
        if not any(s["stage"] == "request" for s in trace_spans):
            continue
        row = trace_summary(trace_spans)
        if since is None or row["start"] >= since:
            rows.append(row)
    return sorted(rows, key=lambda r: r["start"])


def summarize_requests(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts and latencies for the Summary page, with hits and misses kept apart."""
    hits = [r for r in rows if r["path"] == "cache_hit"]
    misses = [r for r in rows if r["path"] == "cache_miss"]
    errors = [r for r in rows if r["status"] == "error"]
    ok_misses = [r for r in misses if r["status"] == "ok"]

    def lat(items: list[dict[str, Any]]) -> dict[str, float]:
        values = [r["request_ms"] for r in items]
        return {
            "n": len(values),
            "mean": mean(values),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
        }

    total = len(rows)
    return {
        "requests": total,
        "hits": len(hits),
        "misses": len(misses),
        "errors": len(errors),
        "hit_rate": len(hits) / total if total else math.nan,
        "error_rate": len(errors) / total if total else math.nan,
        "latency_hit": lat(hits),
        "latency_miss": lat(ok_misses),
        "latency_all_ok": lat([r for r in rows if r["status"] == "ok"]),
    }


def stage_latency_table(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """The Part 4.3 table for a set of cache-miss traces.

    % of cache-miss end-to-end = mean stage time / mean end-to-end time, where end-to-end runs from
    the start of the cache lookup to the end of the evaluation. The remainder is time not inside any
    span (HTTP handling, Kafka produce, thread hand-off). `pct_of_request` repeats the share of the
    user-facing time (the `request` span) for the stages that happen before the answer returns.
    """
    e2e = [s["e2e_ms"] for s in summaries]
    request = [s["request_ms"] for s in summaries]
    rows = []
    for label, stages in STAGE_ROWS:
        values = [sum(s["stage_ms"].get(stage, 0.0) for stage in stages) for s in summaries]
        row = {
            "stage": label,
            "n": len(values),
            "mean_ms": mean(values),
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "max_ms": max(values) if values else math.nan,
            "pct_of_e2e": 100 * mean(values) / mean(e2e) if e2e else math.nan,
        }
        row["pct_of_request"] = (
            math.nan if label == "Evaluation" else 100 * mean(values) / mean(request)
        )
        rows.append(row)
    accounted = sum(r["mean_ms"] for r in rows)
    return {
        "n_traces": len(summaries),
        "rows": rows,
        "e2e": {
            "mean_ms": mean(e2e),
            "p50_ms": percentile(e2e, 50),
            "p95_ms": percentile(e2e, 95),
        },
        "request": {
            "mean_ms": mean(request),
            "p50_ms": percentile(request, 50),
            "p95_ms": percentile(request, 95),
        },
        "unaccounted_pct_of_e2e": 100 * (mean(e2e) - accounted) / mean(e2e) if e2e else math.nan,
        "dominant": max(rows, key=lambda r: r["pct_of_e2e"])["stage"] if rows else None,
    }
