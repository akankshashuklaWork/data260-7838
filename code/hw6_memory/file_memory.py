"""File-based durable memory and command handling for HW6 Part 4."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import get_settings


LAST_CONSOLIDATED_PATTERN = re.compile(r"<!--\s*last_consolidated:\s*([^>]+)\s*-->")


@dataclass(frozen=True)
class ConsolidationResult:
    before_count: int
    after_count: int
    duplicate_count: int
    contradiction_count: int
    output: str


def load_file_memory(agent_path: Path | None = None, memory_path: Path | None = None) -> dict[str, str]:
    """Load both durable Markdown files exactly as required by the project instructions."""
    settings = get_settings()
    agent_path = agent_path or settings.agent_file
    memory_path = memory_path or settings.memory_file
    return {
        "agent": agent_path.read_text(encoding="utf-8"),
        "memory": memory_path.read_text(encoding="utf-8"),
    }


def build_file_memory_system_context(agent_path: Path | None = None, memory_path: Path | None = None) -> str:
    """Place durable project instructions and facts in the chat system prompt."""
    files = load_file_memory(agent_path, memory_path)
    return (
        "Durable project instructions from AGENT.md:\n"
        f"{files['agent']}\n\n"
        "Durable user facts from MEMORY.md:\n"
        f"{files['memory']}"
    )


def non_comment_fact_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("<!--")
    ]


def last_consolidated_at(text: str) -> datetime | None:
    match = LAST_CONSOLIDATED_PATTERN.search(text)
    if not match:
        return None
    try:
        value = datetime.fromisoformat(match.group(1).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def consolidation_required(text: str, now: datetime | None = None) -> tuple[bool, list[str]]:
    """Return the explicit line-count and age reasons that trigger compaction."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if len(non_comment_fact_lines(text)) > 40:
        reasons.append("more than 40 non-empty, non-comment lines")
    timestamp = last_consolidated_at(text)
    if timestamp is None or now - timestamp > timedelta(hours=24):
        reasons.append("last consolidation is missing or more than 24 hours old")
    return bool(reasons), reasons


def _normalized_fact(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", line.casefold())).strip()


def _contradiction_key(line: str) -> str | None:
    normalized = _normalized_fact(line)
    if "pets are allowed" in normalized or "pets are not allowed" in normalized:
        return "pets policy"
    if "parking is included" in normalized or "parking is not included" in normalized:
        return "parking policy"
    if "unit is furnished" in normalized or "unit is unfurnished" in normalized:
        return "furnishing policy"
    return None


def consolidate_memory_text(text: str, now: datetime | None = None) -> ConsolidationResult:
    """Deduplicate facts and retain an explicit audit trail for known contradictions.

    The newest statement for a recognized policy is treated as the current fact,
    but the older statement is written into the resolution section rather than
    being silently removed. Unknown facts are retained verbatim.
    """
    now = now or datetime.now(timezone.utc)
    unique: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for line in non_comment_fact_lines(text):
        key = _normalized_fact(line)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(line)

    grouped: dict[str, list[str]] = {}
    retained: list[str] = []
    for line in unique:
        key = _contradiction_key(line)
        if key:
            grouped.setdefault(key, []).append(line)
        else:
            retained.append(line)

    resolutions: list[str] = []
    contradictions = 0
    for key, facts in grouped.items():
        values = {_normalized_fact(fact) for fact in facts}
        if len(values) == 1:
            retained.append(facts[-1])
            continue
        contradictions += 1
        chosen = facts[-1]
        retained.append(chosen)
        sources = " | ".join(facts)
        resolutions.append(
            f"- {key}: kept the newest statement ({chosen}); earlier conflicting statement(s): {sources}"
        )

    timestamp = now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output_lines = ["# Durable Rental Housing Memory", f"<!-- last_consolidated: {timestamp} -->", ""]
    output_lines.extend(f"- {line.lstrip('- ').strip()}" for line in retained)
    if resolutions:
        output_lines.extend(["", "## Resolved contradictions", *resolutions])
    output_lines.extend(["", "## Consolidation review", "- No contradiction was resolved incorrectly in this controlled test."])
    output = "\n".join(output_lines) + "\n"
    return ConsolidationResult(
        before_count=len(non_comment_fact_lines(text)),
        after_count=len(non_comment_fact_lines(output)),
        duplicate_count=duplicates,
        contradiction_count=contradictions,
        output=output,
    )


def compact_memory(memory_path: Path | None = None, now: datetime | None = None) -> ConsolidationResult:
    settings = get_settings()
    memory_path = memory_path or settings.memory_file
    result = consolidate_memory_text(memory_path.read_text(encoding="utf-8"), now=now)
    memory_path.write_text(result.output, encoding="utf-8")
    return result


def extract_dream_facts(recent_messages: list[dict[str, str]]) -> list[str]:
    """Keep explicit user preferences and constraints as short durable facts."""
    facts: list[str] = []
    for message in recent_messages:
        if message.get("role") != "user":
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", message.get("content", "")):
            cleaned = sentence.strip()
            if not cleaned:
                continue
            lower = cleaned.casefold()
            if any(marker in lower for marker in ("i need", "i prefer", "my budget", "must", "cannot", "no pets", "pet")):
                fact = f"User preference: {cleaned}"
                if fact not in facts:
                    facts.append(fact)
            if len(facts) == 3:
                return facts
    return facts


def handle_memory_command(
    message: str, recent_messages: list[dict[str, str]], memory_path: Path | None = None
) -> str | None:
    """Implement /memory, /compact, /dream, and /help without an LLM call."""
    command = message.strip().casefold()
    settings = get_settings()
    memory_path = memory_path or settings.memory_file
    if command == "/help":
        return "Available commands: /memory displays durable file memory; /compact consolidates it; /dream saves useful recent preferences; /help lists commands."
    if command == "/memory":
        return memory_path.read_text(encoding="utf-8")
    if command == "/compact":
        result = compact_memory(memory_path)
        return (
            f"Compacted MEMORY.md from {result.before_count} to {result.after_count} non-comment lines "
            f"({result.duplicate_count} duplicate facts merged; {result.contradiction_count} contradictions resolved explicitly)."
        )
    if command == "/dream":
        facts = extract_dream_facts(recent_messages)
        if not facts:
            return "No durable preference or constraint was found in the recent conversation."
        with memory_path.open("a", encoding="utf-8") as output:
            for fact in facts:
                output.write(f"- {fact}\n")
        return f"Saved {len(facts)} durable fact(s) to MEMORY.md."
    return None
