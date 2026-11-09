"""Part 2 demo: 13 queries (new, exact duplicates, paraphrases) through the ingress endpoint.

Needs the ingress API (make run-hw09) and the three HW8 agents running.
"""

from __future__ import annotations

import json
import sys

import httpx

from .config import CONFIG, RAW_DIR

URL = f"http://127.0.0.1:{CONFIG.port}/ask"

QUERIES = [
    ("new", "What is a security deposit used for?"),
    ("exact duplicate", "What is a security deposit used for?"),
    ("paraphrase", "What is a security deposit meant to cover?"),
    ("new", "How many days does a landlord have to return a security deposit after move-out?"),
    (
        "exact duplicate",
        "How many days does a landlord have to return a security deposit after move-out?",
    ),
    ("paraphrase", "Within how many days must a landlord give back my deposit once I move out?"),
    ("new", "What is a month-to-month lease?"),
    ("paraphrase", "What does a month to month lease mean?"),
    ("new", "What is the capital of France?"),
    ("new", "Can a landlord enter my apartment without notice?"),
    ("paraphrase", "Is a landlord allowed to enter my apartment without giving me notice?"),
    ("new", "What does a lease renewal clause mean?"),
    ("exact duplicate", "What is the capital of France?"),
]


def main() -> int:
    print(f"=== Semantic cache test: {len(QUERIES)} queries, threshold 0.85 ===\n")
    rows = []
    with httpx.Client(timeout=400) as client:
        client.post(URL.replace("/ask", "/reset"))  # start from an empty cache
        for number, (kind, question) in enumerate(QUERIES, 1):
            reply = client.post(URL, json={"question": question, "threshold": 0.85}).json()
            rows.append({"n": number, "type": kind, "question": question, **reply})
            print(
                f"#{number:<2} [{kind:<15}] is_cached={str(reply['is_cached']):<5} "
                f"similarity={reply['similarity']:.4f} latency_ms={reply['latency_ms']:>9.1f}  {question}"
            )
    cached = [r for r in rows if r["is_cached"]]
    live = [r for r in rows if not r["is_cached"]]
    hit_rate = 100 * len(cached) / len(rows)
    avg = lambda items: sum(r["latency_ms"] for r in items) / len(items) if items else 0.0  # noqa: E731
    print(f"\nCache hit rate: {hit_rate:.1f}% ({len(cached)} of {len(rows)} queries)")
    print(f"Average latency, cached queries:     {avg(cached):,.1f} ms ({len(cached)} queries)")
    print(f"Average latency, non-cached queries: {avg(live):,.1f} ms ({len(live)} queries)")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "threshold": 0.85,
        "queries": len(rows),
        "hits": len(cached),
        "hit_rate_percent": round(hit_rate, 1),
        "avg_latency_ms_cached": round(avg(cached), 1),
        "avg_latency_ms_not_cached": round(avg(live), 1),
        "rows": rows,
    }
    (RAW_DIR / "part2_queries.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
