# HW10 Metrics

## Part 2: automated evaluation of the Kafka pipeline

Evaluated traces: 50 of 50 cache-miss requests (judge qwen3:8b, 1-5 scale).

| Stage / criterion | Mean | Min | Max |
|---|---:|---:|---:|
| Plan Quality (Planner) | 3.64 | 2 | 5 |
| Writer Helpfulness (draft) | 4.66 | 2 | 5 |
| Final Answer Helpfulness (Reviewer output) | 4.66 | 2 | 5 |

Final minus draft: mean +0.00, min +0, max +0; the final answer was word-for-word the draft in 50 of 50 cases.

## Part 3: judge validation (20 frozen drafts, Writer Helpfulness)

| Run | Spearman rho | p-value | Mean absolute difference |
|---:|---:|---:|---:|
| 1 | 0.290 | 0.2155 | 1.50 |
| 2 | 0.290 | 0.2155 | 1.50 |
| 3 | 0.290 | 0.2155 | 1.50 |
| mean of 3 runs | 0.290 | 0.2155 | 1.50 |

| Repeatability over 3 runs | Value |
|---|---:|
| Cases whose score changed in at least one run | 0.0% |
| (case, run-pair) comparisons that differ | 0.0% |
| Mean absolute change (points) | 0.000 |
| Maximum absolute change (points) | 0 |

Sensitivity (temperature 0.7, new seed per run): cases changed 35.0%, mean / max absolute change 0.233 / 1.

## Part 4.2: example traces

| Trace | trace_id | Detail |
|---|---|---|
| Cache hit | `75c73fce-e6ac-4c1e-bba9-de1bf5b177e4` | similarity 0.972, 41.9 ms |
| Cache miss (success) | `eeea390f-2c98-4419-8a46-c449443e2da6` | 6523 ms (first request after start) |
| Failed | `17a9d205-17bb-4870-a1f9-061524259f9e` | stage `planner`: ValueError('inbox message needs a non-empty question') |

## Part 4.3: stage latency on 50 confirmed cache misses

| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |
|---|---:|---:|---:|
| Cache lookup | 41.3 | 75.2 | 0.3% |
| Planner | 1,708.0 | 3,630.6 | 14.0% |
| Writer | 3,898.5 | 6,384.9 | 29.4% |
| Reviewer | 0.0 | 0.0 | 0.0% |
| Queue wait (total) | 16.2 | 56.5 | 0.2% |
| Evaluation | 7,488.6 | 10,773.8 | 56.0% |

End-to-end (cache lookup start to evaluation end): p50 13,562.7 ms, p95 20,094.8 ms. User-facing (request span, answer returned): p50 5,943.3 ms, p95 9,825.6 ms. Time outside any span: 0.0% of end-to-end. Dominant stage: Evaluation.

Cache-hit latency (separate, 15 repeated questions, all served from cache: True): request p50 9.5 ms, p95 18.8 ms; cache lookup p50 9.1 ms, p95 18.4 ms.

All 50 responses reported is_cached=false: True.

## Self-check

`verification.json`: 23 / 23 checks passed (commit 6dc5cb3da032).
