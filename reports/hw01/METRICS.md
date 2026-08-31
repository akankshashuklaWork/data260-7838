# Part 3: Measuring Non-Determinism - Results

**Domain**: Rental Housing Listings (DOMAIN_ID 6)
**Input**: Spacious 2BR Apartment in Downtown San Jose
**Model**: qwen2:7b
**Total Runs**: 40 (20 at temp 0.7, 20 at temp 0.0)

---

## Metrics Table

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| Distinct tag sets | 1 | 14 |
| Tags in all 20 runs | 3 | 0 |
| Tags in exactly 1 run | 0 | 6 |

---

## Latency Analysis

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| p50 (ms) | 3879.1 | 4289.1 |
| p95 (ms) | 4143.3 | 5573.2 |
| p99 (ms) | 4241.4 | 5874.8 |

---

## Detailed Analysis

### Temperature 0.0 (Deterministic)

**Distinct tag sets**: 1

**Tags appearing in ALL 20 runs**:
- Downtown San Jose
- Pet-friendly
- Spacious 2BR

**Tags appearing in EXACTLY 1 run**:
- None

---

### Temperature 0.7 (Creative/Non-Deterministic)

**Distinct tag sets**: 14

**Tags appearing in ALL 20 runs**:
- None

**Tags appearing in EXACTLY 1 run**:
- CityViews
- FlexibleLease
- Rooftop Garden
- Spacious 2-bedroom apartment
- Spacious Apartment
- SpaciousApartment

---

## Raw Data

All run-by-run results saved to: `raw/nondeterminism_results.json`

Each entry contains:
- `tags`: The 3 final tags produced
- `summary`: The generated summary
- `latency_ms`: Time to complete (in milliseconds)
- `temperature`: Test temperature (0.0 or 0.7)
- `run`: Run number within that temperature (1-20)
