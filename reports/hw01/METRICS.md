# Part 3: Measuring Non-Determinism - Results

**Domain**: Rental Housing Listings (DOMAIN_ID 6)
**Input**: Spacious 2BR Apartment in Downtown San Jose
**Model**: qwen2:7b
**Total Runs**: 40 (20 at temp 0.7, 20 at temp 0.0)

---

## Metrics Table

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| Distinct tag sets | 1 | 13 |
| Tags in all 20 runs | 3 | 1 |
| Tags in exactly 1 run | 0 | 5 |

---

## Latency Analysis

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| p50 (ms) | 3699.6 | 4256.5 |
| p95 (ms) | 3764.5 | 6412.0 |
| p99 (ms) | 3768.1 | 7579.7 |

---

## Detailed Analysis

### Temperature 0.0 (Deterministic)

**Distinct tag sets**: 1

**Tags appearing in ALL 20 runs**:
- Downtown San Jose
- Pet-friendly
- Spacious 2BR Apartment

**Tags appearing in EXACTLY 1 run**:
- None

---

### Temperature 0.7 (Creative/Non-Deterministic)

**Distinct tag sets**: 13

**Tags appearing in ALL 20 runs**:
- Downtown San Jose

**Tags appearing in EXACTLY 1 run**:
- High-end Amenities
- Renovated Apartment
- Spacious
- Spacious 2-bedroom
- Spacious Apartment

---

## Interpretation

### What Two Users Sending Identical Input Might See

With temperature 0.7 (non-deterministic):
- User A might receive tags: ["2BR Apartment", "Downtown San Jose", "Pet-friendly"]
- User B might receive tags: ["Spacious Unit", "Downtown Location", "Animal-Friendly"]

The differences arise because the LLM uses randomness (temperature > 0) to generate slightly different word choices while expressing similar concepts.

At temperature 0.0 (deterministic):
- Both users will receive identical tags: ["2BR Apartment", "Downtown San Jose", "Pet-friendly"]
- Results are 100% reproducible

### When Run-to-Run Variation is ACCEPTABLE

**Example 1 - Content Summarization**:
- "Summarize this rental listing in one sentence"
- Minor wording variations are fine ("spacious unit" vs "large apartment")
- Users understand the meaning is the same
- Slight variation actually helps discover different perspectives

**Example 2 - Creative Content Generation**:
- "Write marketing copy for this apartment"
- Different phrasings and emphases are expected
- Variation is a feature, not a bug

### When Run-to-Run Variation is NOT ACCEPTABLE

**Example 1 - Financial Calculations**:
- "Calculate the monthly rent with a 10% increase"
- MUST always return the same numerical result
- Variation would violate contract/legal requirements
- Deterministic (temp 0.0) is required

**Example 2 - Medical Diagnosis**:
- "Classify this symptom as symptom A or symptom B"
- Inconsistent classifications are dangerous
- Must be deterministic for patient safety
- Requires temperature 0.0

---

## Raw Data

All run-by-run results saved to: `raw/nondeterminism_results.json`

Each entry contains:
- `tags`: The 3 final tags produced
- `summary`: The generated summary
- `latency_ms`: Time to complete (in milliseconds)
- `temperature`: Test temperature (0.0 or 0.7)
- `run`: Run number within that temperature (1-20)
