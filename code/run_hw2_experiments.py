#!/usr/bin/env python3
"""Run the Part 4 schema, ceiling, and adversarial experiments.

This script uses the same local ModelClient-backed graph for every run and
writes machine-readable results under reports/hw02/raw/.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

from stateful_agent_graph import initial_state, run_graph


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "hw02"
CASES = REPORTS / "cases"
RAW = REPORTS / "raw"


def load_case(name: str) -> Dict[str, str]:
    with open(CASES / name, encoding="utf-8") as handle:
        return json.load(handle)


def run_one(case: Dict[str, str], max_turns: int, run_number: int) -> Dict[str, Any]:
    started = time.perf_counter()
    state = initial_state(case["title"], case["content"], max_turns=max_turns)
    try:
        result = run_graph(state, show_stream=False)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        planner_attempts = sum(entry["node"] == "planner" for entry in result.get("trace", []))
        completed = bool(result.get("planner_proposal")) and result.get("reviewer_feedback", {}).get("approved") is True
        if not completed:
            outcome = "abandoned_at_ceiling" if result.get("turn_count", 0) >= max_turns else "incomplete"
        elif planner_attempts == 1:
            outcome = "valid_first_attempt"
        elif planner_attempts == 2:
            outcome = "valid_after_one_retry"
        else:
            outcome = "valid_after_two_or_more_retries"
        return {
            "run": run_number,
            "max_turns": max_turns,
            "outcome": outcome,
            "completed": completed,
            "planner_attempts": planner_attempts,
            "turn_count": result.get("turn_count"),
            "latency_ms": latency_ms,
            "planner_proposal": result.get("planner_proposal", {}),
            "reviewer_feedback": result.get("reviewer_feedback", {}),
            "trace": result.get("trace", []),
        }
    except Exception as error:
        return {
            "run": run_number,
            "max_turns": max_turns,
            "outcome": "error",
            "completed": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(error),
        }


def write_json(filename: str, payload: Any) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / filename, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HW2 Part 4 experiments")
    parser.add_argument("--runs", type=int, default=30, help="Number of schema runs")
    parser.add_argument("--ceiling-runs", type=int, default=20)
    parser.add_argument("--adversarial-runs", type=int, default=5)
    args = parser.parse_args()

    schema_case = load_case("schema_input.json")
    schema_results = [run_one(schema_case, 10, i) for i in range(1, args.runs + 1)]
    write_json("schema_validation_results.json", schema_results)

    ceiling_results = {
        str(ceiling): [
            run_one(schema_case, ceiling, i) for i in range(1, args.ceiling_runs + 1)
        ]
        for ceiling in (2, 10)
    }
    write_json("ceiling_comparison_results.json", ceiling_results)

    adversarial_case = load_case("adversarial_input.json")
    adversarial_results = [run_one(adversarial_case, 10, i) for i in range(1, args.adversarial_runs + 1)]
    write_json("adversarial_results.json", adversarial_results)

    print("Wrote schema_validation_results.json, ceiling_comparison_results.json, and adversarial_results.json")


if __name__ == "__main__":
    main()
