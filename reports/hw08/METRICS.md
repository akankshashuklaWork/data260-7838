# HW8 Metrics

## Failure table (before / after evidence)

| Failure scenario | Before fix | After fix |
| --- | --- | --- |
| Duplicate delivery | Same correlation_id delivered twice: processed=2, drafts published=2 (extra side effect). | Idempotency store: processed=1, duplicates skipped=1, drafts published=1. |
| Consumer killed mid-work | Offset committed on receipt: after SIGKILL committed offset=6 (message at 5); restarted Writer never saw it; drafts published=0 - message lost. | Offset committed after processing: committed offset after kill=6; restarted Writer received offset 6 again, finished it, and committed 7; drafts published=1. |
| Poison message | Unlimited retries: 54 failed attempts in 12 s, never dead-lettered; the next message was blocked (processed=False). | 3 attempts, then 1 record in s7838_dead_letter (count=1); the next message was processed (processed=True). |
| Two partitions / two consumers | No key: related messages split across both partitions; entities processed out of order: listing-1. | Key = entity_id: every entity stayed in one partition and in order (all_in_order=True, all_in_one_partition=True). |

## Ordering run (20 messages generated from VERIFY_SEED=267838, two partitions, two Writers)

| Run | Entities out of order | Entities split across partitions | All in order | All in one partition |
|---|---|---|---|---|
| unkeyed | listing-1 | listing-1, listing-2, listing-6 | False | False |
| keyed | none | none | True | True |

## Part 2 live pipeline

| Item | Result |
|---|---|
| Model | qwen2:7b |
| Stages | inbox -> tasks -> drafts -> final (Planner, Writer, Reviewer) |
| End-to-end time | about 6-10 s per run (6.6 s in raw/part2_pipeline_live.json) |
| Final status | approved |
| correlation_id preserved | True |

## Self-check

`verification.json`: 12 / 12 checks passed (commit c811a5eb3ec8).
