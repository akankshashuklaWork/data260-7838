"""Part 3.2 - 3.4: threshold sweep over the 40 labeled cases, one false hit, and the cost model.

Step 1 runs every distinct query through the live HW8 pipeline once (answer + measured pipeline time,
saved so the sweep can be repeated). Step 2 replays the 40 cases against a cache pre-loaded with the
20 seed answers at each threshold; a miss costs the measured pipeline time for that query. Misses are
not stored during the sweep, so every case sees the same cache.
"""

from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path

import yaml

from .config import COST_FALSE_HIT, COST_MISS, RAW_DIR, SWEEP_THRESHOLDS
from .pipeline_client import PipelineClient
from .semantic_cache import SemanticCache

CASES_FILE = Path(__file__).with_name("cache_cases.yaml")
ANSWERS_FILE = RAW_DIR / "part3_pipeline_answers.json"


async def collect_pipeline_answers(queries: list[str], refresh: bool) -> dict[str, dict]:
    """Run each distinct query through the agents once; reuse the saved results when they exist."""
    if ANSWERS_FILE.exists() and not refresh:
        return json.loads(ANSWERS_FILE.read_text())
    client = PipelineClient()
    await client.start()
    try:
        print("warm-up run (model loading, not recorded)...", flush=True)
        await client.ask("What is a lease?")
        answers: dict[str, dict] = {}
        for number, query in enumerate(queries, 1):
            answer, ms = await client.ask(query)
            answers[query] = {"answer": answer, "pipeline_ms": round(ms, 1)}
            print(f"  [{number}/{len(queries)}] {ms:8.0f} ms  {query[:70]}", flush=True)
    finally:
        await client.stop()
    ANSWERS_FILE.write_text(json.dumps(answers, indent=2) + "\n")
    return answers


def run_threshold(
    cache: SemanticCache, spec: dict, answers: dict, seed_vectors: dict, threshold: float
):
    cache.clear()
    seed_key = {}
    for seed in spec["seed_queries"]:
        key = cache.put(
            seed["query"],
            seed_vectors[seed["id"]],
            answers[seed["query"]]["answer"],
            "static",
            "none",
        )
        seed_key[key] = seed["id"]
    seed_by_query = {s["query"]: s["id"] for s in spec["seed_queries"]}
    rows = []
    for case in spec["cases"]:
        started = time.perf_counter()
        vector = cache.embed(case["query"])
        best = cache.nearest(vector)
        lookup_ms = (time.perf_counter() - started) * 1000
        similarity = best["similarity"]
        is_cached = similarity >= threshold
        matched_seed = seed_by_query.get(best["query"])
        pipeline_ms = answers[case["query"]]["pipeline_ms"]
        if is_cached:
            correct = case["expect"] == "hit" and matched_seed == case["seed_id"]
            outcome = "true_hit" if correct else "false_hit"
            latency = lookup_ms
        else:
            outcome = "missed_hit" if case["expect"] == "hit" else "true_miss"
            latency = lookup_ms + pipeline_ms
        rows.append(
            {
                "threshold": threshold,
                "case_id": case["id"],
                "category": case["category"],
                "expect": case["expect"],
                "similarity": round(similarity, 4),
                "matched_seed": matched_seed,
                "is_cached": is_cached,
                "outcome": outcome,
                "latency_ms": round(latency, 1),
            }
        )
    cache.clear()
    return rows


def summarise(rows: list[dict], threshold: float, c_miss: float, c_false: float) -> dict:
    hits = sum(r["is_cached"] for r in rows)
    false_hits = sum(r["outcome"] == "false_hit" for r in rows)
    misses = len(rows) - hits
    should_miss = sum(r["expect"] == "miss" for r in rows)
    return {
        "threshold": threshold,
        "queries": len(rows),
        "hits": hits,
        "misses": misses,
        "false_hits": false_hits,
        "missed_hits": sum(r["outcome"] == "missed_hit" for r in rows),
        "hit_rate": round(hits / len(rows), 4),
        "false_hit_rate": round(false_hits / should_miss, 4),  # of the 20 queries that should miss
        "false_hit_share_of_hits": round(false_hits / hits, 4) if hits else 0.0,
        "mean_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows), 1),
        "total_cost": round(misses * c_miss + false_hits * c_false, 2),
    }


async def main(refresh: bool = False) -> int:
    spec = yaml.safe_load(CASES_FILE.read_text())
    distinct = list(
        dict.fromkeys(
            [s["query"] for s in spec["seed_queries"]] + [c["query"] for c in spec["cases"]]
        )
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    answers = await collect_pipeline_answers(distinct, refresh)
    cache = SemanticCache()
    seed_vectors = {s["id"]: cache.embed(s["query"]) for s in spec["seed_queries"]}

    all_rows, table = [], []
    for threshold in SWEEP_THRESHOLDS:
        rows = run_threshold(cache, spec, answers, seed_vectors, threshold)
        all_rows += rows
        table.append(summarise(rows, threshold, COST_MISS, COST_FALSE_HIT))

    print("\nThreshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost")
    for r in table:
        print(
            f"  {r['threshold']:.2f}    |  {r['hit_rate'] * 100:5.1f}%  |    {r['false_hit_rate'] * 100:5.1f}%     "
            f"|   {r['mean_latency_ms']:10.1f}    | {r['total_cost']:7.2f}"
        )

    # Cost sensitivity: how the best threshold moves when a false hit is cheaper or dearer.
    sensitivity = {}
    for c_false in (5, 25, 100):
        costs = {
            t["threshold"]: round(t["misses"] * COST_MISS + t["false_hits"] * c_false, 2)
            for t in table
        }
        sensitivity[str(c_false)] = {"costs": costs, "best_threshold": min(costs, key=costs.get)}
    print(
        "\nCost sensitivity (cost of a false hit -> best threshold):",
        {k: v["best_threshold"] for k, v in sensitivity.items()},
    )

    # 3.3: the false hit with the highest similarity at the starting threshold of 0.85 (else the lowest threshold).
    for probe in (0.85, SWEEP_THRESHOLDS[0]):
        candidates = [
            r for r in all_rows if r["threshold"] == probe and r["outcome"] == "false_hit"
        ]
        if candidates:
            worst = max(candidates, key=lambda r: r["similarity"])
            break
    case = next(c for c in spec["cases"] if c["id"] == worst["case_id"])
    seed = next(s for s in spec["seed_queries"] if s["id"] == worst["matched_seed"])
    false_hit = {
        "threshold": worst["threshold"],
        "case_id": case["id"],
        "category": case["category"],
        "cached_query": seed["query"],
        "incoming_query": case["query"],
        "similarity": worst["similarity"],
        "cached_answer_returned": answers[seed["query"]]["answer"],
        "correct_answer": answers[case["query"]]["answer"],
    }
    print(
        f"\nFalse hit shown for 3.3 (threshold {worst['threshold']}): {case['id']} vs {seed['id']}, "
        f"similarity {worst['similarity']}"
    )

    (RAW_DIR / "part3_threshold_table.json").write_text(
        json.dumps(
            {
                "cost_per_miss": COST_MISS,
                "cost_per_false_hit": COST_FALSE_HIT,
                "table": table,
                "sensitivity": sensitivity,
            },
            indent=2,
        )
        + "\n"
    )
    (RAW_DIR / "part3_false_hit.json").write_text(json.dumps(false_hit, indent=2) + "\n")
    with open(RAW_DIR / "part3_sweep_cases.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(asyncio.run(main(refresh="--refresh" in sys.argv)))
