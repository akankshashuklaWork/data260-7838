"""Reference dataset access: which record and field a question is about, and objective answer checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent
REFERENCE = json.loads((DATA_DIR / "reference_data.json").read_text())["records"]

# The first matching rule wins, so the more specific fields come first.
FIELD_RULES = [
    ("pet_deposit", ["pet deposit"]),
    ("security_deposit", ["security deposit"]),
    ("utilities_included", ["utilities"]),
    ("parking", ["parking"]),
    ("lease_term_months", ["lease term", "how long is the lease", "lease length"]),
    ("pet_policy", ["allow pets", "pets allowed", "pet policy", "are pets"]),
    ("monthly_rent", ["monthly rent", "rent"]),
]
FIELD_LABELS = {
    "pet_deposit": "pet deposit",
    "security_deposit": "security deposit",
    "utilities_included": "included utilities",
    "parking": "parking",
    "lease_term_months": "lease term",
    "pet_policy": "pet policy",
    "monthly_rent": "monthly rent",
}
DECLINE_MARKERS = (
    "don't have",
    "do not have",
    "not have that information",
    "no information",
    "cannot provide",
    "can't provide",
    "unable to",
    "don't know",
    "do not know",
    "not sure",
    "not able to",
    "cannot answer",
    "can't answer",
    "outside",
    "not available to me",
)


def classify(question: str) -> dict[str, Any]:
    """Return {record, field, label}; label is "unrelated" when no listed property is mentioned."""
    lowered = question.lower()
    record = next((r for r in REFERENCE if r["property"].lower() in lowered), None)
    if record is None:
        return {"record": None, "field": None, "label": "unrelated"}
    field = next((name for name, words in FIELD_RULES if any(w in lowered for w in words)), None)
    return {"record": record, "field": field, "label": FIELD_LABELS.get(field, "unrelated")}


def lookup(question: str) -> str | None:
    """Reference fact for the property and field a question asks about (None if not covered)."""
    info = classify(question)
    if not info["record"] or info["field"] not in info["record"]["facts"]:
        return None
    return f"{info['record']['property']} {FIELD_LABELS[info['field']]}: {info['record']['facts'][info['field']]['value']}"


def is_decline(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in DECLINE_MARKERS)


def numbers_in(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def check_fact(check: dict[str, Any], answer: str) -> bool:
    lowered = answer.lower()
    if check["type"] == "number":
        return float(check["value"]) in numbers_in(answer)
    required = all(term in lowered for term in check.get("all", []))
    any_of = not check.get("any") or any(term in lowered for term in check["any"])
    forbidden = not any(term in lowered for term in check.get("none", []))
    return required and any_of and forbidden
