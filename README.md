# DATA 260 Homework 1

Rental Housing Listings - Akanksha Shukla

## Configuration

| Value | Result | Calculation |
|---|---|---|
| SID4 | 7838 | Last four digits of student ID |
| PORT_BASE | 8638 | 8000 + (7838 mod 900) |
| PREFIX | s7838 | "s" + SID4 |
| SEED | 7838 | SID4 |
| VERIFY_SEED | 267838 | 260000 + SID4 |
| DOMAIN_ID | 6 | 7838 mod 8 (Rental Housing Listings) |

Hardware: MacBook Pro, Apple M4 Pro, 48 GB RAM
Local model used (Parts 2-4): qwen2:7b, served through Ollama

## Setup Instructions

Prerequisites:

- Python 3.11 or 3.12
- Ollama (https://ollama.ai) with qwen2:7b pulled
- Docker (for Part 1 deployment)

```bash
ollama serve
ollama pull qwen2:7b

cd code
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Part 1: Web Form

Created a web form for submitting rental property listings, with client-side validation and JSON handling in JavaScript.

Files: `code/web_application/`

How to run:

```bash
open code/web_application/index.html
```

Run the automated tests:

```bash
node code/web_application/tests/run-tests.js
```

Build and run with Docker:

```bash
docker build -f code/Dockerfile -t hw1-rental-listings:1.0 .
docker run --detach --name s7838-rental-housing --publish 8638:80 hw1-rental-listings:1.0
```

Open http://localhost:8638 in a browser.

## Part 2: Agentic AI Pipeline

A Planner -> Reviewer -> Finalizer pipeline that reads a listing's title and content and produces exactly 3 tags and a summary (at most 25 words) as JSON.

Files: `code/agents_demo.py`

How to run:

```bash
cd code
source venv/bin/activate
python agents_demo.py
```

## Part 3: Non-Determinism Testing

Runs the Part 2 pipeline 40 times on one fixed input (20 runs at temperature 0.7, 20 at temperature 0.0) and reports how consistent the output is at each temperature.

Files: `code/run_nondeterminism_tests.py`, `code/analyze_nondeterminism.py`

How to run:

```bash
cd code
source venv/bin/activate
python run_nondeterminism_tests.py
python analyze_nondeterminism.py
```

Results: `reports/hw01/METRICS.md`

## Part 4: Model Client and Token Accounting

A reusable model-adapter class (`ModelClient.complete(messages, tools=None)`) and an interactive command-line chat client that prints token usage after every turn.

Files: `src/model_client.py`, `code/hw1_client.py`

How to run:

```bash
cd code
source venv/bin/activate
python hw1_client.py
```

Type a message and press Enter to chat. Type `/stats` to see turn count and cumulative token usage. Type `/exit` to quit.

## Reports

All homework evidence and the final report are in `reports/hw01/`:

- `report.pdf` - full write-up with screenshots and answers
- `METRICS.md` - Part 3 results tables
- `RUN_LOG.txt` - real console output from the runs
- `verification.json` - self-check results
- `AI_USE.md` - AI use disclosure
- `raw/` - raw experiment data
