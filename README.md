# DATA 260 Homework 1 to 4

Rental Housing Listings - Akanksha Shukla

## HW4: Full-Stack CRUD, Database Performance, and Grounded RAG

HW4 extends the rental-housing application from the earlier assignments. It
adds a FastAPI and MySQL backend, a React frontend, protected CRUD routes,
database measurements, and a grounded question-answering experiment that uses
the HW3 document corpus.

### Configuration

| Value | Result | Calculation |
|---|---|---|
| SID4 | 7838 | Last four digits of student ID |
| PORT_BASE | 8638 | 8000 + (7838 mod 900) |
| PREFIX | s7838 | `s` + SID4 |
| SEED | 7838 | SID4 |
| VERIFY_SEED | 267838 | 260000 + SID4 |
| DOMAIN_ID | 6 | 7838 mod 8 (Rental Housing Listings) |

Experiments were run on a MacBook Pro with an Apple M4 Pro processor and 48 GB
of RAM. The local generation model is `qwen2:7b` through Ollama. The RAG
embedding model is `sentence-transformers/all-MiniLM-L6-v2`.

### Part 1: Full-Stack Rental Listings Application

The backend is in `code/hw4_backend/` and uses FastAPI, SQLAlchemy, MySQL,
Pydantic validation, PBKDF2 password hashing, and opaque HTTP-only server-side
sessions. The frontend is in `code/hw4_frontend/` and uses React, React Router,
Axios, `useState`, and `useEffect`.

The React application passes listing data and callback functions as props to the
create, update, and delete components. Protected routes show `Login required`
when a user is not authenticated.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Create a user account |
| POST | `/auth/login` | Start an HTTP-only session |
| POST | `/auth/logout` | End the current session |
| GET | `/auth/me` | Check the current session |
| GET | `/listings` | Return listings with related rows loaded efficiently |
| GET | `/listings/{id}` | Return one listing |
| POST | `/listings` | Create a listing |
| PUT | `/listings/{id}` | Update a listing |
| DELETE | `/listings/{id}` | Delete a listing |

### Part 2: N+1 Query Measurement

The database is seeded with 5,000 listings and 200 related amenity rows using
`SEED=7838`. The `naive` endpoint loads related rows one listing at a time. The
`fixed` endpoint uses SQLAlchemy eager loading so the number of SQL statements
stays constant as the page grows.

The measurement script makes 30 requests for each version at page sizes 10, 50,
and 200. The detailed results are in `reports/hw04/METRICS.md` and the raw
records are in `reports/hw04/raw/n_plus_one.json`.

| Page size | Version | SQL statements/request |
|---:|---|---:|
| 10 | naive | 11 |
| 10 | fixed | 1 |
| 50 | naive | 51 |
| 50 | fixed | 1 |
| 200 | naive | 201 |
| 200 | fixed | 1 |

### Part 3: Grounded RAG Question Answering

The RAG experiment reuses the five-document rental-housing corpus from HW3.
It creates normalized embeddings, searches a FAISS index, and compares three
answer configurations:

1. `no_rag`: asks the local model without retrieved documents.
2. `basic_rag`: gives the model retrieved text without source labels.
3. `context_rag`: gives labelled sources and requires citations or a refusal.

The six questions include domain questions and two questions that should be
refused because the corpus does not contain enough information. Raw retrieval,
comparison, and evaluation artifacts are in `reports/hw04/raw/`.

### HW4 Setup and Verification

Prerequisites:

- Python 3.11 or 3.12
- MySQL running locally, with database `s7838_rel`
- Ollama with the `qwen2:7b` model for the RAG experiment
- Node.js and npm for the React frontend

From the repository root:

```bash
source .venv/bin/activate
export MYSQL_PASSWORD="replace-with-your-mysql-password"
export DATABASE_URL="mysql+pymysql://root:${MYSQL_PASSWORD}@127.0.0.1:3306/s7838_rel"

PYTHONPATH=code python -m hw4_backend.seed_hw4
PYTHONPATH=code python -m uvicorn hw4_backend.main:app \
  --host 127.0.0.1 --port 8638
```

In another terminal, start the frontend:

```bash
cd code/hw4_frontend
npm install
npm run dev -- --host 127.0.0.1
```

Run the backend verification from the repository root while the API is
running:

```bash
PYTHONPATH=code python -m hw4_backend.verify_hw4
```

Run the N+1 experiment:

```bash
PYTHONPATH=code python -m hw4_backend.measure_n_plus_one
```

Run the local RAG experiment after starting Ollama and pulling the model:

```bash
ollama serve
ollama pull qwen2:7b
PYTHONPATH=code python -m hw4_rag.rag
```

HW4 evidence is stored in `reports/hw04/`, including the DOCX report,
`METRICS.md`, `RUN_LOG.txt`, `verification.json`, raw experiment files, and
`AI_USE.md`.

## HW3: Authentication and Retrieval-Only RAG

### Part 1: FastAPI Authentication with Bootstrap

Login, logout, a session-protected dashboard, and Bootstrap pages are in
`code/web_application/auth.py` and `code/web_application/templates/`.

How to run:

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

Open http://localhost:8638. Sessions use a signed cookie with `Secure`,
`HttpOnly`, and `SameSite=Lax`, are tracked on the server, and expire after 15
idle minutes. The listing interface from HW2 is at
http://localhost:8638/listings.

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

HW3 compares token, semantic, and sentence-window chunking with LlamaIndex on
five rental-housing PDFs in `data/hw03/corpus/`. Each technique uses its own
in-memory vector index, and only retrieval is measured.

- Corpus sources and access dates: `reports/hw03/SOURCES.md`
- File sizes and SHA-256 hashes: `reports/hw03/CORPUS_MANIFEST.json`
- Questions and expected sources: `reports/hw03/questions.yaml`
- Code: `code/hw3_rag/`
- Results: `reports/hw03/METRICS.md`
- Raw output: `reports/hw03/raw/`

Run the experiment and checks from the repository root:

```bash
PYTHONPATH=code python -m hw3_rag.run_experiment
PYTHONPATH=code python -m hw3_rag.metrics
PYTHONPATH=code python -m hw3_rag.verify
```

The embedding model is `sentence-transformers/all-MiniLM-L6-v2` with 384
dimensions and `top_k=5`.

## HW2: Responsive Listings, Stateful Agents, and Validation

### Parts 1 and 2: Responsive Listing Page and FastAPI Backend

The HW1 listing form was extended for 375px screens with loading, empty, and
error states. The FastAPI backend adds, updates, deletes, and searches listings.
The files are in `code/web_application/`.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/listings` | List all records |
| GET | `/api/listings?search=San Jose` | Search title or location |
| POST | `/api/listings` | Add a record and redirect to `/listings` |
| PUT | `/api/listings/1` | Update record ID 1 and redirect to `/listings` |
| DELETE | `/api/listings/highest` | Delete the highest ID and redirect to `/listings` |

Run the browser application checks:

```bash
node code/web_application/tests/run-tests.js
```

Build and run with Docker:

```bash
docker build -f code/Dockerfile -t hw2-rental-listings .
docker run --rm --publish 8638:8638 hw2-rental-listings
```

### Part 3: Stateful Agent Graph

The Planner/Reviewer graph is implemented in
`code/stateful_agent_graph.py`. A missing proposal routes to Planner, an
existing proposal routes to Reviewer, a rejected review returns through the
Supervisor to Planner, and an approved review ends the graph. Model calls use
the HW1 `src/model_client.py` adapter with the local `qwen2:7b` model.

```bash
python code/stateful_agent_graph.py
python code/test_stateful_agent_graph.py
```

### Part 4: Validation and Loop-Safety Experiments

These experiments cover Pydantic output validation, turn-ceiling comparison,
and adversarial input handling:

```bash
python code/run_hw2_experiments.py
python code/analyze_hw2_experiments.py
```

Results are in `reports/hw02/METRICS.md`.

## HW1: Web Form, Agent Pipeline, and Token Accounting

### Part 1: Web Form

The original form for submitting rental property listings, with client-side
validation and JSON handling, is in `code/web_application/index.html` and
`code/web_application/script.js`.

### Part 2: Agentic AI Pipeline

The Planner, Reviewer, and Finalizer pipeline reads a listing title and content
and produces exactly three tags and a summary of at most 25 words as JSON. The
implementation is in `code/agents_demo.py`.

```bash
cd code
source venv/bin/activate
python agents_demo.py
```

### Part 3: Non-Determinism Testing

The test runs the Part 2 pipeline 40 times on one fixed input: 20 runs at
temperature 0.7 and 20 runs at temperature 0.0.

```bash
cd code
source venv/bin/activate
python run_nondeterminism_tests.py
python analyze_nondeterminism.py
```

Results are in `reports/hw01/METRICS.md`.

### Part 4: Model Client and Token Accounting

`src/model_client.py` contains the reusable `ModelClient.complete()` adapter.
The interactive client in `code/hw1_client.py` prints token usage after each
turn. Type `/stats` for cumulative statistics or `/exit` to quit.

```bash
cd code
source venv/bin/activate
python hw1_client.py
```

## Reports and Reproducibility

Each assignment has its own folder under `reports/`:

- `reports/hw04/` - HW4 report, measurements, RAG artifacts, and verification
- `reports/hw03/` - HW3 report, retrieval evidence, and verification
- `reports/hw02/` - HW2 report, experiment results, and verification
- `reports/hw01/` - HW1 report, experiment results, and verification

The report folders contain the relevant write-up, metrics, real console output,
verification results, screenshots, raw experiment data, and AI-use disclosure.
