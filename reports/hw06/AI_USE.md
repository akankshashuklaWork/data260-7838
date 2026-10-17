# AI Use Record

AI assistance was used as a coding and editing aid for this homework. I reviewed, ran, and verified the resulting code and evidence locally.

1. **Question:** How can a FastAPI service structure MongoDB configuration, Pydantic schemas, and route modules without duplicating the existing project?
   **How it was used:** I used the suggested separation of concerns to organize the HW6 modules under `code/hw6_memory/`, then adapted it to the repository's existing `code/` layout.
   **Source attribution:** None; this was general implementation guidance.

2. **Question:** How can I log prompt tokens, completion tokens, component token estimates, and latency for every memory-aware chat turn?
   **How it was used:** I used the suggested telemetry fields, validated them against the existing HW1 model adapter's four-characters-per-token convention, and wrote raw JSONL and CSV exports.
   **Source attribution:** `src/model_client.py` in this repository for the existing adapter/token-estimation convention.

3. **Question:** What is a reproducible way to compare short-term context windows and a summary-first eviction policy?
   **How it was used:** I used the suggested fixed 30-message conversation and five fixed probes, then ran each setting in a fresh MongoDB session with the local Qwen model.
   **Source attribution:** None; the conversation, probes, criteria, and scores are original to this homework.

4. **Question:** How can duplicate and contradictory durable facts be compacted without silently deleting information?
   **How it was used:** I implemented explicit contradiction records, preserved the original 55-line memory file, and verified the compacted result is under 40 non-comment lines.
   **Source attribution:** None; the memory facts and reconciliation test are original to this homework.
