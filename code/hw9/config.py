"""Fixed configuration for DATA 260 HW9 (the Section 0 values are shared with HW8)."""

from __future__ import annotations

from pathlib import Path

from hw8.config import CONFIG, KAFKA_BOOTSTRAP

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/hw9"
REPORT_DIR = ROOT / "reports/hw09"
RAW_DIR = REPORT_DIR / "raw"

PREFIX = CONFIG.prefix  # every Redis key starts with this prefix
REDIS_HOST = "localhost"
REDIS_PORT = 6379
DB_PATH = DATA_DIR / f"{PREFIX}_rel.db"  # relational store for the listing rows

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
DEFAULT_THRESHOLD = 0.85
SWEEP_THRESHOLDS = [0.75, 0.80, 0.85, 0.90, 0.95]

# Cost model (units are "one avoidable model run"); see the report for the justification.
COST_MISS = 1.0
COST_FALSE_HIT = 25.0

__all__ = [
    "CONFIG",
    "KAFKA_BOOTSTRAP",
    "ROOT",
    "DATA_DIR",
    "REPORT_DIR",
    "RAW_DIR",
    "PREFIX",
    "REDIS_HOST",
    "REDIS_PORT",
    "DB_PATH",
    "EMBED_MODEL",
    "EMBED_DIM",
    "DEFAULT_THRESHOLD",
    "SWEEP_THRESHOLDS",
    "COST_MISS",
    "COST_FALSE_HIT",
]
