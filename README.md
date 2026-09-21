# DATA 260 Homework 1 to 3

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
Local model used (HW1 and HW2 agents): qwen2:7b, served through Ollama
Embedding model (HW3 RAG): sentence-transformers/all-MiniLM-L6-v2 (no generative model)

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

## HW3

### Part 1: FastAPI Authentication with Bootstrap

Login, logout, a session-protected dashboard, and Bootstrap pages, in `code/web_application/auth.py` and `code/web_application/templates/`.

How to run (Python 3.11 or 3.12). Set a private session-signing secret and, optionally, override the demonstration login credentials:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
export SESSION_SECRET_KEY="replace-with-a-long-random-value"
export APP_LOGIN_USERNAME="akanksha"
export APP_LOGIN_PASSWORD="data260"
cd code
uvicorn web_application.app:app --host 127.0.0.1 --port 8638
```

Open http://localhost:8638. Sessions use a signed cookie with `Secure`, `HttpOnly`, and `SameSite=Lax`, are also tracked on the server, and expire after 15 idle minutes. The listing interface from HW2 is at http://localhost:8638/listings.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/` | Show the domain welcome page and session-aware navigation |
| GET/POST | `/login` | Show and process the Bootstrap login form |
| GET | `/dashboard` | Show the protected user dashboard |
| GET | `/logout` | Clear the session and redirect to the home page |
| GET | `/listings` | Open the cumulative rental listing interface |

Run the authentication checks:

```bash
python code/test_auth.py
```

### Part 2: Retrieval-Only RAG Chunking Comparison

Compares three LlamaIndex chunking techniques (token, semantic, sentence-window) on a rental housing corpus. Each technique gets its own in-memory `VectorStoreIndex`. Only retrieval is measured, so no model writes or grades answers.

- Corpus: 5 public PDFs in `data/hw03/corpus/` (10,496,158 bytes). Sources and access dates are in `reports/hw03/SOURCES.md`, and file sizes and SHA-256 hashes are in `reports/hw03/CORPUS_MANIFEST.json`.
- Questions: five domain questions with expected answers and expected source files in `reports/hw03/questions.yaml` (committed before the results).
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), top_k = 5.
- Code: `code/hw3_rag/` (`ingestion.py`, `chunkers.py`, `indexing.py`, `retrieval.py`, `run_experiment.py`, `metrics.py`, `verify.py`).

How to run (from the repository root, Python 3.11 or 3.12, after `pip install -r code/requirements.txt`):

```bash
PYTHONPATH=code python -m hw3_rag.run_experiment
PYTHONPATH=code python -m hw3_rag.metrics
PYTHONPATH=code python -m hw3_rag.verify
```

If the embedding model is already cached and you are offline, put `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` in front of each command. To print the query embedding and the ranked results table for the shared query, run `PYTHONPATH=code python -m hw3_rag.retrieval`.

Results (`reports/hw03/METRICS.md`):

| Technique | Chunks | Avg chunk chars | Mean top-1 cosine | Mean@5 cosine | Recall@5 |
|---|---:|---:|---:|---:|---:|
| Token | 337 | 1598.85 | 0.7378 | 0.6855 | 1.00 |
| Semantic | 436 | 1157.87 | 0.7487 | 0.6854 | 1.00 |
| Sentence window | 3851 | 131.09 | 0.7727 | 0.7147 | 0.60 |

Raw per-question output is in `reports/hw03/raw/`.

## HW2

### Parts 1 and 2: Responsive Listing Page and FastAPI Backend

The HW1 listing form is styled to stay usable at 375px, with loading, empty, and error states. A FastAPI backend on port 8638 adds, updates, deletes, and searches listings.

Files: `code/web_application/` (`app.py`, `index.html`, `script.js`, `styles.css`)

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/listings` | List all records |
| GET | `/api/listings?search=San Jose` | Search title or location |
| POST | `/api/listings` | Add a record and redirect to `/listings` |
| PUT | `/api/listings/1` | Update record ID 1 and redirect to `/listings` |
| DELETE | `/api/listings/highest` | Delete highest ID and redirect to `/listings` |

Run the browser application checks:

```bash
node code/web_application/tests/run-tests.js
```

Build and run with Docker:

```bash
docker build -f code/Dockerfile -t hw2-rental-listings .
docker run --rm --publish 8638:8638 hw2-rental-listings
```

Open http://localhost:8638 in a browser.

### Part 3: Stateful Agent Graph

The stateful Planner/Reviewer graph is implemented in `code/stateful_agent_graph.py`.
It follows the required Supervisor flow: a missing proposal routes to Planner, an
existing proposal routes to Reviewer, Reviewer issues route back through Supervisor
to Planner, and an approved review ends the graph. All model calls use the HW1
`src/model_client.py` adapter with the documented `qwen2:7b` local model.

Run the graph with:

```bash
python code/stateful_agent_graph.py
```

Run the offline routing and correction-loop check with:

```bash
python code/test_stateful_agent_graph.py
```

Part 4 (Pydantic output validation, turn-ceiling comparison, adversarial input) experiments:

```bash
python code/run_hw2_experiments.py
python code/analyze_hw2_experiments.py
```

Results: `reports/hw02/METRICS.md`

## HW1

### Part 1: Web Form

A form for submitting rental property listings, with client-side validation and JSON handling in JavaScript.

Files: `code/web_application/index.html`, `code/web_application/script.js`

### Part 2: Agentic AI Pipeline

A Planner -> Reviewer -> Finalizer pipeline that reads a listing's title and content and produces exactly 3 tags and a summary (at most 25 words) as JSON.

Files: `code/agents_demo.py`

How to run:

```bash
cd code
source venv/bin/activate
python agents_demo.py
```

### Part 3: Non-Determinism Testing

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

### Part 4: Model Client and Token Accounting

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

Each homework has its own folder under `reports/`:

- `reports/hw01/`, `reports/hw02/`, `reports/hw03/`

Each folder holds:

- `report.pdf` - full write-up with screenshots and answers (HW3 also has `Shukla_HW3.pdf`)
- `METRICS.md` - results tables
- `RUN_LOG.txt` - real console output from the runs
- `verification.json` - self-check results
- `AI_USE.md` - AI use disclosure
- `raw/` - raw experiment data

HW3 also has `SOURCES.md`, `CORPUS_MANIFEST.json`, and `questions.yaml`.
