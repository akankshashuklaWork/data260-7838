"""Settings shared by the HW3 RAG scripts."""

from pathlib import Path


SID4 = 7838
SEED = 7838
VERIFY_SEED = 267838
DOMAIN_ID = 6
DOMAIN_NAME = "Rental housing"

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "hw03" / "corpus"
REPORT_DIR = REPO_ROOT / "reports" / "hw03"
RAW_DIR = REPORT_DIR / "raw"
QUESTIONS_PATH = REPORT_DIR / "questions.yaml"
MANIFEST_PATH = REPORT_DIR / "CORPUS_MANIFEST.json"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TOKEN_CHUNK_SIZE = 512
TOKEN_CHUNK_OVERLAP = 50

SEMANTIC_BUFFER_SIZE = 1
SEMANTIC_BREAKPOINT_PERCENTILE = 95

SENTENCE_WINDOW_SIZE = 3

PREVIEW_LENGTH = 160
