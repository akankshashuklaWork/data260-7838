#!/usr/bin/env python3
"""
Part 3: Analyze non-determinism results
Computes metrics and generates METRICS.md
"""

import json
from pathlib import Path
from collections import Counter
from statistics import median, quantiles

def analyze_temperature(results: list, temperature: float) -> dict:
    """Analyze results for a specific temperature."""
    temp_results = [r for r in results if r["temperature"] == temperature]

    if not temp_results:
        return {}

    # Extract tags
    all_tags = [r["tags"] for r in temp_results]

    # Convert to tag sets for comparison
    tag_sets = [tuple(sorted(tags)) for tags in all_tags]
    distinct_tag_sets = len(set(tag_sets))

    # Count tag occurrences
    tag_counts = Counter()
    for tags in all_tags:
        for tag in tags:
            tag_counts[tag] += 1

    # Tags appearing in all 20 runs
    tags_in_all = [tag for tag, count in tag_counts.items() if count == 20]

    # Tags appearing in exactly 1 run
    tags_in_one = [tag for tag, count in tag_counts.items() if count == 1]

    # Calculate latency stats (in ms)
    latencies = sorted([r["latency_ms"] for r in temp_results])
    p50 = median(latencies)
    # For p95 and p99, use quantiles
    quantile_results = quantiles(latencies, n=100)
    p95 = quantile_results[94]  # 95th percentile (index 94 for 100 points)
    p99 = quantile_results[98]  # 99th percentile (index 98 for 100 points)

    # Two real, distinct example tag sets actually produced at this temperature,
    # used to illustrate what two different users might genuinely see.
    distinct_examples = []
    seen = set()
    for tags in all_tags:
        key = tuple(sorted(tags))
        if key not in seen:
            seen.add(key)
            distinct_examples.append(tags)
        if len(distinct_examples) == 2:
            break

    return {
        "temperature": temperature,
        "distinct_tag_sets": distinct_tag_sets,
        "tags_in_all_20": sorted(tags_in_all),
        "tags_in_exactly_1": sorted(tags_in_one),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "latency_p99_ms": round(p99, 1),
        "total_runs": len(temp_results),
        "example_tag_sets": distinct_examples
    }

def main():
    """Analyze results and generate METRICS.md."""
    results_file = Path("../reports/hw01/raw/nondeterminism_results.json")

    if not results_file.exists():
        print(f"ERROR: Results file not found: {results_file}")
        print("Run: python run_nondeterminism_tests.py")
        return

    # Load results
    with open(results_file, "r") as f:
        results = json.load(f)

    print(f"Loaded {len(results)} results")

    # Analyze each temperature
    analysis_07 = analyze_temperature(results, 0.7)
    analysis_00 = analyze_temperature(results, 0.0)

    # Generate METRICS.md
    metrics_file = Path("../reports/hw01/METRICS.md")
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    metrics_content = f"""# Part 3: Measuring Non-Determinism - Results

**Domain**: Rental Housing Listings (DOMAIN_ID 6)
**Input**: Spacious 2BR Apartment in Downtown San Jose
**Model**: qwen2:7b
**Total Runs**: 40 (20 at temp 0.7, 20 at temp 0.0)

---

## Metrics Table

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| Distinct tag sets | {analysis_00['distinct_tag_sets']} | {analysis_07['distinct_tag_sets']} |
| Tags in all 20 runs | {len(analysis_00['tags_in_all_20'])} | {len(analysis_07['tags_in_all_20'])} |
| Tags in exactly 1 run | {len(analysis_00['tags_in_exactly_1'])} | {len(analysis_07['tags_in_exactly_1'])} |

---

## Latency Analysis

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| p50 (ms) | {analysis_00['latency_p50_ms']} | {analysis_07['latency_p50_ms']} |
| p95 (ms) | {analysis_00['latency_p95_ms']} | {analysis_07['latency_p95_ms']} |
| p99 (ms) | {analysis_00['latency_p99_ms']} | {analysis_07['latency_p99_ms']} |

---

## Detailed Analysis

### Temperature 0.0 (Deterministic)

**Distinct tag sets**: {analysis_00['distinct_tag_sets']}

**Tags appearing in ALL 20 runs**:
{chr(10).join([f"- {tag}" for tag in analysis_00['tags_in_all_20']]) if analysis_00['tags_in_all_20'] else "- None"}

**Tags appearing in EXACTLY 1 run**:
{chr(10).join([f"- {tag}" for tag in analysis_00['tags_in_exactly_1']]) if analysis_00['tags_in_exactly_1'] else "- None"}

---

### Temperature 0.7 (Creative/Non-Deterministic)

**Distinct tag sets**: {analysis_07['distinct_tag_sets']}

**Tags appearing in ALL 20 runs**:
{chr(10).join([f"- {tag}" for tag in analysis_07['tags_in_all_20']]) if analysis_07['tags_in_all_20'] else "- None"}

**Tags appearing in EXACTLY 1 run**:
{chr(10).join([f"- {tag}" for tag in analysis_07['tags_in_exactly_1']]) if analysis_07['tags_in_exactly_1'] else "- None"}

---

## Raw Data

All run-by-run results saved to: `raw/nondeterminism_results.json`

Each entry contains:
- `tags`: The 3 final tags produced
- `summary`: The generated summary
- `latency_ms`: Time to complete (in milliseconds)
- `temperature`: Test temperature (0.0 or 0.7)
- `run`: Run number within that temperature (1-20)
"""

    with open(metrics_file, "w") as f:
        f.write(metrics_content)

    print(f"Results saved to: {metrics_file}")
    print()
    print("Analysis complete.")
    print("Metrics file: reports/hw01/METRICS.md")
    print("Raw data: reports/hw01/raw/nondeterminism_results.json")
    print()

if __name__ == "__main__":
    main()
