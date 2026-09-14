# HW2 Part 4 Metrics

These values are generated from the raw JSON files by `code/analyze_hw2_experiments.py`.

## Schema Validation Over 30 Runs

| Outcome | Count | Mean latency (ms) |
|---|---:|---:|
| Valid first attempt | 30 | 2747.47 |
| Valid after 1 retry | 0 | 0.00 |
| Valid after 2+ retries | 0 | 0.00 |
| Abandoned at ceiling | 0 | 0.00 |
| Error | 0 | 0.00 |

## Turn Ceiling Comparison

| Ceiling | Runs | Completion rate | Mean latency (ms) |
|---:|---:|---:|---:|
| 2 | 20 | 0.00% | 2641.17 |
| 10 | 20 | 100.00% | 6270.58 |

## Adversarial Input

Runs: 5

Completion rate: 0.00%

Runs abandoned at ceiling: 5
