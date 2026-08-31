#!/usr/bin/env python3
"""
Part 3: Run 40 non-determinism tests
20 runs at temperature 0.7
20 runs at temperature 0.0

Saves results to reports/hw01/raw/nondeterminism_results.json
"""

import json
import subprocess
import sys
from pathlib import Path

def run_test(temperature: float, run_num: int) -> dict:
    """Run a single test and return the result."""
    print(f"  Running test {run_num}/40 at temperature {temperature}...", end=" ", flush=True)

    try:
        result = subprocess.run(
            [sys.executable, "agents_demo.py", "../reports/hw01/cases/nondeterminism_input.json", str(temperature)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print("FAILED")
            print(f"Error: {result.stderr}")
            return None

        # Parse output
        output = result.stdout.strip()
        data = json.loads(output)
        print(f"{data['latency_ms']:.0f}ms")
        return data

    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON PARSE ERROR: {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def main():
    """Run all 40 tests."""
    print("Part 3: Non-Determinism Testing (40 runs total)")
    print()

    # Verify input file exists
    input_file = Path("../reports/hw01/cases/nondeterminism_input.json")
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)

    print(f"Input file: {input_file}")
    print()

    all_results = []

    # Run 20 tests at temperature 0.7
    print("Running 20 tests at temperature 0.7 (creative)...")
    for i in range(1, 21):
        result = run_test(0.7, i)
        if result:
            result["temperature"] = 0.7
            result["run"] = i
            all_results.append(result)
        else:
            print(f"Test {i} failed, skipping...")
    print()

    # Run 20 tests at temperature 0.0
    print("Running 20 tests at temperature 0.0 (deterministic)...")
    for i in range(1, 21):
        result = run_test(0.0, i + 20)
        if result:
            result["temperature"] = 0.0
            result["run"] = i
            all_results.append(result)
        else:
            print(f"Test {i} failed, skipping...")
    print()

    # Save results
    output_file = Path("../reports/hw01/raw/nondeterminism_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"Results saved to: {output_file}")
    print(f"Total runs completed: {len(all_results)}")
    print()

    # Print summary
    print("Next steps:")
    print("1. Run: python analyze_nondeterminism.py")
    print("2. Check reports/hw01/METRICS.md for results")
    print()

if __name__ == "__main__":
    main()
