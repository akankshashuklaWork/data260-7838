# HW6 Memory Cost Metrics

The 30-message conversation and five fixed probes were run in fresh sessions for each setting. Token counts use the HW1 adapter's documented four-characters-per-token estimate.

| Setting | Mean prompt tokens/turn | Mean completion tokens/turn | Mean latency (ms) | Probe quality (1-5) | Estimated cost for 10,000 30-turn conversations |
| --- | ---: | ---: | ---: | ---: | ---: |
| short_term_n_4 | 1644.63 | 108.00 | 2317.32 | 4.60 | $655.39 |
| short_term_n_12 | 1908.83 | 82.97 | 2527.91 | 5.00 | $697.10 |
| short_term_n_30 | 2007.63 | 44.53 | 2430.65 | 5.00 | $669.09 |
| summary_first_eviction | 1526.23 | 47.07 | 1287.85 | 5.00 | $528.47 |

Best setting: **summary_first_eviction**. It had the highest mean probe quality; cost breaks ties among equally accurate settings.
Worst setting: **short_term_n_12**. It had the highest modeled 10,000-conversation cost; probe quality breaks cost ties.

The summary_first_eviction policy keeps the latest four prior messages in the short-term window after summaries are available. Older detail remains in session/lifetime summaries and episodic facts, reducing prompt tokens while preserving durable requirements.
