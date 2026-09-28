# HW4 measurements

Run `PYTHONPATH=code python -m hw4_backend.measure_n_plus_one` against a seeded and authenticated server. The command wrote 180 request records to `reports/hw04/raw/n_plus_one.json` (30 requests for each page-size/version combination).

| Page size | Version | SQL statements/request | p50 (ms) | p95 (ms) | p99 (ms) |
|---:|---|---:|---:|---:|---:|
| 10 | naive | 11 | 5.061 | 6.152 | 7.992 |
| 10 | fixed | 1 | 2.109 | 3.626 | 3.855 |
| 50 | naive | 51 | 15.319 | 17.754 | 17.852 |
| 50 | fixed | 1 | 3.537 | 4.679 | 4.773 |
| 200 | naive | 201 | 55.428 | 58.508 | 69.813 |
| 200 | fixed | 1 | 8.541 | 9.794 | 18.130 |

The Postman endpoint checks independently confirmed the same SQL-count pattern: naive requests used `page_size + 1` statements, while fixed requests used one statement for page sizes 10, 50, and 200. The fixed implementation removes the per-listing related-row query, so its statement count remains constant as the page grows.
