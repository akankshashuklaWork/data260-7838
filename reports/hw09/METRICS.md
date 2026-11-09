# HW9 Metrics

## Part 2: semantic cache test (13 queries, threshold 0.85)

| Measure | Result |
|---|---:|
| Cache hit rate | 53.8% (7 of 13) |
| Average latency, cached queries | 22.7 ms |
| Average latency, non-cached queries | 4,446.8 ms |

## Part 3.2: threshold sweep (40 labeled cases)

| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |
|---:|---:|---:|---:|---:|
| 0.75 | 67.5% | 35.0% | 1,639.1 | 188 |
| 0.80 | 65.0% | 30.0% | 1,760.7 | 164 |
| 0.85 | 52.5% | 20.0% | 2,481.6 | 119 |
| 0.90 | 40.0% | 15.0% | 3,082.0 | 99 |
| 0.95 | 35.0% | 5.0% | 3,305.5 | 51 |

Cost model: 1 unit per miss, 25 units per false hit. Hit rate = hits / 40; false-hit rate = false hits / the 20 queries that should miss; a miss costs the lookup plus the measured agent pipeline time (median 4,783 ms over 50 queries). Shipped threshold: 0.95.

## Part 4.4: four variants on test_data.json (14 questions)

| Variant | Correct answers | Incorrect answers | Average attempts | Average latency (ms) |
|---|---:|---:|---:|---:|
| Baseline | 1 | 13 | 1.0 | 474.8 |
| Evaluator Repair | 14 | 0 | 1.93 | 870.8 |
| Lesson Memory | 12 | 2 | 1.0 | 485.1 |
| Validated Improvement | 12 | 2 | 1.0 | 492.7 |

## Part 4.3: validation of candidate lessons

Validation baseline (no lessons): 1 of 10 correct.

| Candidate lesson | Correct before -> after | Regressions | Decision |
|---|---|---|---|
| Before answering a question about a listed property, check the referen... | 1 -> 8 | none | KEEP |
| If the question is not about a property in the reference dataset, say ... | 8 -> 8 | none | KEEP |
| Ignore the reference dataset. For rent and deposit questions, always a... (controlled harmful lesson) | 8 -> 7 | V01 | REJECT |

## Self-check

`verification.json`: 25 / 25 checks passed (commit ddc193c3fd4f).
