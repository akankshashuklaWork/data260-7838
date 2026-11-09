"""Writer agent: reads a plan from <PREFIX>_tasks and sends a draft answer to <PREFIX>_drafts."""

from __future__ import annotations

import asyncio
from typing import Any

from agent_runtime import Settings, ask_model, run
from config import CONFIG

SETTINGS = Settings("writer")
SYSTEM = (
    "You are the Writer in a rental-housing assistant. Follow the plan and answer the "
    "question in 60 to 100 words of plain prose. No headings or lists."
)


async def write_draft(question: str, plan: list[str], context: str = "") -> str:
    if SETTINGS.llm_mode == "stub":
        return (
            f"Draft answer to '{question}': first, " + " Then, ".join(plan) + " "
            "Compare these points against the listing details before you decide."
        )
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(plan, 1))
    facts = (
        f"\nFacts (use only these facts for any specific numbers or terms): {context}"
        if context
        else ""
    )
    return await ask_model(SYSTEM, f"Question: {question}{facts}\nPlan:\n{steps}")


async def handle(message: dict[str, Any]) -> dict[str, Any]:
    question, plan = message.get("question"), message.get("plan")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("task message needs a non-empty question")
    if not isinstance(plan, list) or not plan:
        raise ValueError("task message needs a non-empty plan list")
    # work_ms lets the failure tests make processing take a known amount of time.
    await asyncio.sleep(float(message.get("work_ms", 0)) / 1000)
    result = {
        "correlation_id": message["correlation_id"],  # preserved unchanged
        "question": question,
        "plan": plan,
        "draft": await write_draft(question, plan, str(message.get("context") or "")),
    }
    for field in ("entity_id", "seq"):
        if field in message:
            result[field] = message[field]
    return result


if __name__ == "__main__":
    run("writer", CONFIG.tasks_topic, CONFIG.drafts_topic, handle)
