"""Fixed configuration for DATA 260 HW10 (the Section 0 values are shared with HW8 and HW9)."""

from __future__ import annotations

import os
from pathlib import Path

from hw8.config import CONFIG, KAFKA_BOOTSTRAP
from hw8.tracing import SPAN_FILE

ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "code/hw10"
DATA_DIR = ROOT / "data/hw10"
REPORT_DIR = ROOT / "reports/hw10"
RAW_DIR = REPORT_DIR / "raw"

PREFIX = CONFIG.prefix
# The Streamlit dashboard is the HW10 app and takes PORT_BASE (8638). The HW9 ingress API moves one
# port up (override with INGRESS_PORT) so both can run together.
DASHBOARD_PORT = CONFIG.port
INGRESS_PORT = int(os.getenv("INGRESS_PORT", CONFIG.port + 1))
INGRESS_URL = f"http://127.0.0.1:{INGRESS_PORT}"

# --- Part 3: frozen evaluation cases and human labels (committed before any judge score) ---
EVAL_CASES = CODE_DIR / "eval_cases.json"
HUMAN_LABELS = CODE_DIR / "human_labels.csv"

# --- Where the evaluator and the dashboard read and write ------------------------------------
SPANS = SPAN_FILE  # data/hw10/spans.jsonl, written by ingress, agents, and evaluator
EVAL_RESULTS = DATA_DIR / "eval_results.jsonl"  # one record per evaluated trace
EVAL_EVENTS = DATA_DIR / "evaluator_events.jsonl"  # joins, timeouts, malformed messages

# --- Judge (Part 2.1: a local judge model, documented) ---------------------------------------
# A different local model from the generator (qwen2:7b) so the judge does not grade its own
# writing style. Temperature 0 and the HW seed make runs as repeatable as the runtime allows.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen3:8b")
GENERATOR_MODEL = CONFIG.model
JUDGE_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
JUDGE_TEMPERATURE = float(os.getenv("JUDGE_TEMPERATURE", "0"))
JUDGE_SEED = CONFIG.seed
JUDGE_NUM_CTX = 4096

# --- Bounds so a malformed message or an unavailable judge cannot hang the run ----------------
JUDGE_CALL_TIMEOUT_S = float(os.getenv("JUDGE_CALL_TIMEOUT_S", "120"))  # one judge call
JUDGE_CASE_TIMEOUT_S = float(os.getenv("JUDGE_CASE_TIMEOUT_S", "300"))  # all criteria of one trace
JOIN_TIMEOUT_S = float(os.getenv("JOIN_TIMEOUT_S", "30"))  # wait for plan+draft+final to arrive
MAX_BUFFERED_TRACES = 500  # evaluator memory bound

# --- Part 4.3 ---------------------------------------------------------------------------------
LATENCY_REQUESTS = 50
SCORE_MIN, SCORE_MAX = 1, 5  # one 1-5 scale for the judge and for the human labels

__all__ = [
    "CONFIG",
    "KAFKA_BOOTSTRAP",
    "ROOT",
    "CODE_DIR",
    "DATA_DIR",
    "REPORT_DIR",
    "RAW_DIR",
    "PREFIX",
    "DASHBOARD_PORT",
    "INGRESS_PORT",
    "INGRESS_URL",
    "EVAL_CASES",
    "HUMAN_LABELS",
    "SPANS",
    "EVAL_RESULTS",
    "EVAL_EVENTS",
    "JUDGE_MODEL",
    "GENERATOR_MODEL",
    "JUDGE_HOST",
    "JUDGE_TEMPERATURE",
    "JUDGE_SEED",
    "JUDGE_NUM_CTX",
    "JUDGE_CALL_TIMEOUT_S",
    "JUDGE_CASE_TIMEOUT_S",
    "JOIN_TIMEOUT_S",
    "MAX_BUFFERED_TRACES",
    "LATENCY_REQUESTS",
    "SCORE_MIN",
    "SCORE_MAX",
]
