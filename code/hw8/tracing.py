"""HW10 Part 4: structured span tracing shared by the ingress, the agents, and the evaluator.

The HW8 correlation_id *is* the trace_id: it is never replaced by a second identifier. Every
process appends one JSON line per span to a single file (an O_APPEND write of one short line is
atomic on a local file system, so several processes can share it). Tracing is best effort: a
failure to write a span must never break the request path.

A span looks like::

    {"trace_id": "...", "span_id": "ab12cd34", "stage": "planner", "service": "planner",
     "start": 1.7e9, "end": 1.7e9, "start_iso": "...Z", "end_iso": "...Z",
     "duration_ms": 1234.5, "status": "ok" | "error" | "skipped", "error": null, "attrs": {...}}
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPAN_FILE = Path(os.getenv("TRACE_FILE") or ROOT / "data/hw10/spans.jsonl")

# Stage names used everywhere (dashboard, latency table, tests).
STAGES = [
    "request",
    "cache_lookup",
    "queue_inbox",
    "planner",
    "queue_tasks",
    "writer",
    "queue_drafts",
    "reviewer",
    "queue_final",
    "cache_store",
    "evaluation",
    "dead_letter",
]
QUEUE_STAGES = ["queue_inbox", "queue_tasks", "queue_drafts", "queue_final"]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_trace_id() -> str:
    return str(uuid.uuid4())


def write_span(
    trace_id: str | None,
    stage: str,
    start: float,
    end: float,
    status: str = "ok",
    error: str | None = None,
    service: str | None = None,
    **attrs: Any,
) -> dict[str, Any] | None:
    """Append one span. Returns the record (or None when there is no trace_id to attach it to)."""
    if not trace_id:
        return None
    record = {
        "trace_id": trace_id,
        "span_id": uuid.uuid4().hex[:8],
        "stage": stage,
        "service": service or stage,
        "start": round(start, 6),
        "end": round(end, 6),
        "start_iso": _iso(start),
        "end_iso": _iso(end),
        "duration_ms": round((end - start) * 1000, 3),
        "status": status,
        "error": error,
        "attrs": attrs,
    }
    try:
        SPAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record, separators=(",", ":"), default=str) + "\n").encode()
        fd = os.open(SPAN_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError:
        pass  # tracing is best effort
    return record


@contextmanager
def span(
    trace_id: str | None, stage: str, service: str | None = None, **attrs: Any
) -> Iterator[dict[str, Any]]:
    """Time a block. The body may add attributes with `extra["key"] = value`.

    An exception marks the span status "error" with the exception text and is re-raised.
    """
    extra: dict[str, Any] = dict(attrs)
    start = time.time()
    try:
        yield extra
    except BaseException as exc:
        write_span(
            trace_id,
            stage,
            start,
            time.time(),
            status="error",
            error=f"{type(exc).__name__}: {exc}"[:300],
            service=service,
            **extra,
        )
        raise
    write_span(trace_id, stage, start, time.time(), service=service, **extra)


def read_spans(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load every span, skipping any half-written or corrupt line."""
    target = Path(path) if path else SPAN_FILE
    if not target.exists():
        return []
    spans: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            try:
                spans.append(json.loads(line))
            except ValueError:
                continue
    return spans


def spans_for(trace_id: str, path: str | Path | None = None) -> list[dict[str, Any]]:
    """All spans of one trace in pipeline stage order (retries of one stage in start order).

    Stage order, not raw start time, because Kafka record timestamps are whole milliseconds and a
    queue span can otherwise sort a hair ahead of the agent span that produced its message.
    """
    return sorted(
        (s for s in read_spans(path) if s.get("trace_id") == trace_id), key=stage_sort_key
    )


def stage_sort_key(span: dict[str, Any]) -> tuple[int, float]:
    order = {name: i for i, name in enumerate(STAGES)}
    return order.get(span["stage"], 99), span["start"]
