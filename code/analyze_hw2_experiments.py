#!/usr/bin/env python3
"""Summarize raw Part 4 experiment results into reports/hw02/METRICS.md."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports" / "hw02" / "raw"
OUTPUT = ROOT / "reports" / "hw02" / "METRICS.md"


def read_json(name: str) -> Any:
    with open(RAW / name, encoding="utf-8") as handle:
        return json.load(handle)


def mean_latency(rows: Iterable[dict[str, Any]]) -> float:
    values = [row["latency_ms"] for row in rows if "latency_ms" in row]
    return round(mean(values), 2) if values else 0.0


def completion_rate(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "0.00%"
    return f"{100 * sum(row.get('completed', False) for row in rows) / len(rows):.2f}%"


def outcome_table(rows: list[dict[str, Any]]) -> str:
    counts = Counter(row.get("outcome", "error") for row in rows)
    return "\n".join(
        f"| {label} | {counts.get(key, 0)} | {mean_latency([r for r in rows if r.get('outcome') == key]):.2f} |"
        for label, key in [
            ("Valid first attempt", "valid_first_attempt"),
            ("Valid after 1 retry", "valid_after_one_retry"),
            ("Valid after 2+ retries", "valid_after_two_or_more_retries"),
            ("Abandoned at ceiling", "abandoned_at_ceiling"),
            ("Error", "error"),
        ]
    )


def main() -> None:
    schema = read_json("schema_validation_results.json")
    ceilings = read_json("ceiling_comparison_results.json")
    adversarial = read_json("adversarial_results.json")

    lines = [
        "# HW2 Part 4 Metrics",
        "",
        "These values are generated from the raw JSON files by `code/analyze_hw2_experiments.py`.",
        "",
        "## Schema Validation Over 30 Runs",
        "",
        "| Outcome | Count | Mean latency (ms) |",
        "|---|---:|---:|",
        outcome_table(schema),
        "",
        "## Turn Ceiling Comparison",
        "",
        "| Ceiling | Runs | Completion rate | Mean latency (ms) |",
        "|---:|---:|---:|---:|",
    ]
    for ceiling in (2, 10):
        rows = ceilings.get(str(ceiling), [])
        lines.append(f"| {ceiling} | {len(rows)} | {completion_rate(rows)} | {mean_latency(rows):.2f} |")

    lines.extend(
        [
            "",
            "## Adversarial Input",
            "",
            f"Runs: {len(adversarial)}",
            "",
            f"Completion rate: {completion_rate(adversarial)}",
            "",
            f"Runs abandoned at ceiling: {sum(row.get('outcome') == 'abandoned_at_ceiling' for row in adversarial)}",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
