"""Planner agent: reads a question from <PREFIX>_inbox and sends a plan to <PREFIX>_tasks."""

from __future__ import annotations

import re
from typing import Any

from agent_runtime import Settings, ask_model, run
from config import CONFIG

SETTINGS = Settings("planner")
SYSTEM = (
    "You are the Planner in a rental-housing assistant. Reply with exactly three short "
    "numbered steps (1., 2., 3.) that a writer should follow to answer the question. "
    "No other text."
)


async def plan_steps(question: str) -> list[str]:
    if SETTINGS.llm_mode == "stub":
        return [
            "State the key facts a renter must check.",
            "Explain why each fact matters.",
            "Give one clear recommendation.",
        ]
    reply = await ask_model(SYSTEM, question)
    # Keep only the numbered lines ("1. ...") so extra chatter from the model is ignored.
    numbered = (re.match(r"^\s*\d+[.)]\s*(.+)", line) for line in reply.splitlines())
    return [match.group(1).strip() for match in numbered if match]


async def handle(message: dict[str, Any]) -> dict[str, Any]:
    question = message.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("inbox message needs a non-empty question")
    steps = await plan_steps(question)
    if len(steps) < 2:
        raise ValueError(f"model returned fewer than two plan steps: {steps}")
    result = {
        "correlation_id": message["correlation_id"],  # preserved unchanged
        "question": question,
        "plan": steps[:3],
    }
    if message.get("entity_id"):
        result["entity_id"] = message["entity_id"]
    return result


if __name__ == "__main__":
    run("planner", CONFIG.inbox_topic, CONFIG.tasks_topic, handle)
