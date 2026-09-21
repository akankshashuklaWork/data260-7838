# HW3 Part 2 Retrieval Metrics

All scores below come from retrieval only; no answer-generation model was used. Recall@5 is source-based: a question receives 1 when its expected PDF appears anywhere in the five retrieved results and 0 otherwise.

## Aggregate comparison

| Technique | Chunks | Avg chunk chars | Mean top-1 cosine | Mean@5 cosine | Recall@5 | Top-1 source accuracy | Mean latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| token | 337 | 1598.85 | 0.737837 | 0.685544 | 1.00 | 0.80 | 6.74 |
| semantic | 436 | 1157.87 | 0.748664 | 0.685382 | 1.00 | 0.80 | 7.35 |
| sentence_window | 3851 | 131.09 | 0.772652 | 0.714652 | 0.60 | 0.60 | 32.12 |

## Per-question source retrieval

| Technique | Question | Expected-source first rank | Recall@5 | Top-1 cosine | Mean@5 cosine | Latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| token | q1 | 1 | 1 | 0.721816 | 0.685978 | 7.46 |
| token | q2 | 1 | 1 | 0.751856 | 0.678113 | 6.61 |
| token | q3 | 1 | 1 | 0.796959 | 0.705701 | 6.63 |
| token | q4 | 2 | 1 | 0.676165 | 0.639231 | 6.67 |
| token | q5 | 1 | 1 | 0.742388 | 0.718699 | 6.31 |
| semantic | q1 | 1 | 1 | 0.709581 | 0.675888 | 7.90 |
| semantic | q2 | 1 | 1 | 0.749611 | 0.650973 | 7.18 |
| semantic | q3 | 1 | 1 | 0.734426 | 0.688609 | 7.18 |
| semantic | q4 | 3 | 1 | 0.747219 | 0.666824 | 7.50 |
| semantic | q5 | 1 | 1 | 0.802486 | 0.744618 | 7.01 |
| sentence_window | q1 | miss | 0 | 0.730907 | 0.691617 | 32.18 |
| sentence_window | q2 | 1 | 1 | 0.722435 | 0.681228 | 31.53 |
| sentence_window | q3 | 1 | 1 | 0.760806 | 0.729913 | 32.73 |
| sentence_window | q4 | miss | 0 | 0.791594 | 0.709400 | 32.97 |
| sentence_window | q5 | 1 | 1 | 0.857518 | 0.761102 | 31.20 |

## Confident retrieval failure

For q1, sentence-window retrieval assigned cosine 0.730907 to its rank-1 result from `california_landlord_tenant_guide_2026.pdf`. The expected source was `san_jose_apartment_rent_ordinance_fact_sheet.pdf`, which did not appear anywhere in the top five.

> Other city ordinances allow a certain percentage increase in rent each year.

Neither that retrieved sentence nor its stored surrounding window states the required answer: a 5 percent regular rent increase once during a 12-month period. This demonstrates that a comparatively high cosine score reflects semantic similarity, not factual answer completeness.

## Observations

- Token and semantic chunking both achieved Recall@5 of 1.00 and rank-1 expected-source accuracy of 0.80.
- Semantic chunking produced more, shorter chunks than token chunking while retaining the same source-level recall.
- Sentence-window retrieval produced far more candidate nodes, had lower Recall@5 (0.60), and had substantially higher mean retrieval latency.
- Sentence-window had the highest mean cosine values despite lower source recall, showing that cosine magnitude alone should not be treated as correctness.
- The independently computed cosine values agree with the vector-store scores to within floating-point tolerance.

## Conclusion

For this five-document rental-housing corpus, token and semantic chunking were more reliable than sentence-window retrieval at top-5 source recovery. Semantic chunking provided the strongest mean top-1 cosine with perfect Recall@5, while token chunking was slightly faster. Sentence-window retrieval was less suitable for this corpus because its many short nodes increased latency and sometimes matched generic rental-law sentences instead of the specific authoritative fact sheet.
