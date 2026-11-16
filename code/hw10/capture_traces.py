"""Part 4.2: capture one cache-hit trace, one successful cache-miss trace, and one failed trace.

Needs the full stack (`python -m hw10.stack up`). The three trace IDs are saved to
``reports/hw10/raw/example_traces.json`` so the dashboard and the report can use them.

    PYTHONPATH=code python -m hw10.capture_traces
"""

from __future__ import annotations

import json
import time

import httpx
from hw8.common import log
from hw8.tracing import spans_for

from .config import EVAL_RESULTS, INGRESS_URL, RAW_DIR

MISS_QUESTION = "What should I look for in the pet clauses of a rental lease?"
# Candidates tried in order; the first one that the semantic cache matches becomes the hit trace.
PARAPHRASES = [
    "Which things should I check in the pet clauses of a rental lease?",
    "What should I look for in a lease's pet clauses?",
    "What should I look for in the pet policy of a rental lease?",
]
FAILING_QUESTION = "   "  # blank: the Planner rejects it, retries 3 times, then dead-letters it


def ask(client: httpx.Client, question: str) -> dict:
    reply = client.post(f"{INGRESS_URL}/ask", json={"question": question}, timeout=320)
    return {"http_status": reply.status_code, **reply.json()}


def wait_for_evaluation(trace_id: str, timeout: float = 300) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if EVAL_RESULTS.exists() and trace_id in EVAL_RESULTS.read_text(encoding="utf-8"):
            return True
        time.sleep(1)
    return False


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as client:
        client.post(f"{INGRESS_URL}/reset", timeout=30)

        miss = ask(client, MISS_QUESTION)
        assert miss["is_cached"] is False and miss["http_status"] == 200, miss
        log("TRACES", f"cache-miss trace_id={miss['trace_id']} latency_ms={miss['latency_ms']}")
        evaluated = wait_for_evaluation(miss["trace_id"])

        hit = None
        for question in PARAPHRASES:
            candidate = ask(client, question)
            log("TRACES", f"paraphrase {question!r}: is_cached={candidate['is_cached']} "
                f"similarity={candidate['similarity']}")  # fmt: skip
            if candidate["is_cached"]:
                hit, hit["question"] = candidate, question
                break
        assert hit, "no paraphrase reached the cache threshold"
        log("TRACES", f"cache-hit trace_id={hit['trace_id']} latency_ms={hit['latency_ms']}")

        failed = ask(client, FAILING_QUESTION)
        assert failed["http_status"] == 502, failed
        log("TRACES", f"failed trace_id={failed['trace_id']} stage={failed['failed_stage']} "
            f"error={failed['error']}")  # fmt: skip
        time.sleep(1)

    summary = {
        "cache_hit": {
            "trace_id": hit["trace_id"],
            "question": hit["question"],
            "matched_query": hit["matched_query"],
            "similarity": hit["similarity"],
            "latency_ms": hit["latency_ms"],
        },
        "cache_miss": {
            "trace_id": miss["trace_id"],
            "question": MISS_QUESTION,
            "latency_ms": miss["latency_ms"],
            "evaluated": evaluated,
        },
        "failed": {
            "trace_id": failed["trace_id"],
            "question": FAILING_QUESTION,
            "failed_stage": failed["failed_stage"],
            "error": failed["error"],
        },
    }
    for name in ("cache_hit", "cache_miss", "failed"):
        summary[name]["stages"] = [s["stage"] for s in spans_for(summary[name]["trace_id"])]
    (RAW_DIR / "example_traces.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
