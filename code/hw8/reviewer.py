"""Reviewer agent: reads a draft from <PREFIX>_drafts and sends an approval to <PREFIX>_final."""

from __future__ import annotations

from typing import Any

from agent_runtime import run
from config import CONFIG

MIN_WORDS = 15


async def handle(message: dict[str, Any]) -> dict[str, Any]:
    draft = message.get("draft")
    if not isinstance(draft, str):
        raise ValueError("draft message needs a draft string")
    # Objective review rule: a usable answer is non-empty prose with at least MIN_WORDS words.
    approved = len(draft.split()) >= MIN_WORDS
    return {
        "correlation_id": message["correlation_id"],  # preserved unchanged
        "status": "approved" if approved else "rejected",
        "answer": draft,
    }


if __name__ == "__main__":
    run("reviewer", CONFIG.drafts_topic, CONFIG.final_topic, handle)
