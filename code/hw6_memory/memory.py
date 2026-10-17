"""MongoDB short-, long-, and episodic-memory operations for the HW6 chat API."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, DESCENDING

from .config import get_settings
from .db import episodes_collection, messages_collection, summaries_collection
from .embedding import cosine_similarity, embed_text
from .file_memory import build_file_memory_system_context, handle_memory_command
from .model_adapter import get_model_client
from .utils import estimate_tokens, message_text, serialize_document, utc_now


SYSTEM_PRIMER = """You are a concise rental-housing assistant for the Rental Housing Listings project.
Use only the available memory when referring to prior preferences. If a detail is absent,
say that it was not provided. Do not invent listings, prices, availability, or legal advice.
For this experiment, answer in one sentence and keep the answer under 30 words."""


def save_message(user_id: str, session_id: str, role: str, content: str) -> dict[str, Any]:
    document = {
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": utc_now(),
    }
    result = messages_collection().insert_one(document)
    document["_id"] = result.inserted_id
    return document


def recent_messages(user_id: str, session_id: str | None = None, limit: int = 16) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"user_id": user_id}
    if session_id is not None:
        query["session_id"] = session_id
    documents = list(messages_collection().find(query).sort("created_at", DESCENDING).limit(limit))
    return list(reversed(documents))


def load_short_term(user_id: str, session_id: str, current_message_id: Any, limit: int) -> list[dict[str, Any]]:
    """Return the last N prior messages; the current message is added separately to the prompt."""
    query = {"user_id": user_id, "session_id": session_id, "_id": {"$ne": current_message_id}}
    documents = list(messages_collection().find(query).sort("created_at", DESCENDING).limit(limit))
    return list(reversed(documents))


def latest_summary(user_id: str, scope: str, session_id: str | None = None) -> dict[str, Any] | None:
    query: dict[str, Any] = {"user_id": user_id, "scope": scope}
    if scope == "session":
        query["session_id"] = session_id
    else:
        query["session_id"] = None
    return summaries_collection().find_one(query, sort=[("created_at", DESCENDING)])


def extract_episode_facts(message: str) -> list[dict[str, Any]]:
    """Extract up to three short, reviewable user facts without an additional model call."""
    candidates = [part.strip(" -") for part in re.split(r"(?<=[.!?])\s+|;", message) if part.strip()]
    facts: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = candidate.casefold()
        importance = 0.45
        if any(term in normalized for term in ("budget", "must", "need", "cannot", "no pets", "move", "available")):
            importance = 0.9
        elif any(term in normalized for term in ("prefer", "parking", "bedroom", "neighborhood", "pet")):
            importance = 0.7
        fact = candidate[:220]
        if fact and not any(existing["fact"].casefold() == fact.casefold() for existing in facts):
            facts.append({"fact": fact, "importance": importance})
        if len(facts) == 3:
            break
    return facts


def store_episodes(user_id: str, session_id: str, message: str) -> list[dict[str, Any]]:
    settings = get_settings()
    stored: list[dict[str, Any]] = []
    for item in extract_episode_facts(message):
        document = {
            "user_id": user_id,
            "session_id": session_id,
            "fact": item["fact"],
            "importance": item["importance"],
            "embedding": embed_text(item["fact"], settings.embedding_dimensions),
            "created_at": utc_now(),
        }
        episodes_collection().insert_one(document)
        stored.append(document)
    return stored


def retrieve_episodes(user_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    settings = get_settings()
    query_embedding = embed_text(query, settings.embedding_dimensions)
    candidates = list(episodes_collection().find({"user_id": user_id}))
    ranked = []
    for candidate in candidates:
        score = cosine_similarity(query_embedding, candidate.get("embedding", []))
        ranked.append({**candidate, "similarity": round(score, 6)})
    ranked.sort(key=lambda item: (item["similarity"], item["importance"]), reverse=True)
    return ranked[:top_k]


def summarize_session(user_id: str, session_id: str) -> dict[str, Any]:
    """Persist a concise session summary made from the latest user statements."""
    user_messages = list(
        messages_collection()
        .find({"user_id": user_id, "session_id": session_id, "role": "user"})
        .sort("created_at", DESCENDING)
        .limit(8)
    )
    user_messages.reverse()
    bullets = [f"- {message['content'][:180]}" for message in user_messages[-5:]]
    document = {
        "user_id": user_id,
        "session_id": session_id,
        "scope": "session",
        "text": "\n".join(bullets) or "- No user messages available for summary.",
        "created_at": utc_now(),
    }
    summaries_collection().insert_one(document)
    return document


def refresh_lifetime_summary(user_id: str) -> dict[str, Any]:
    """Condense recent session summaries into one lifetime summary with session_id null."""
    session_summaries = list(
        summaries_collection()
        .find({"user_id": user_id, "scope": "session"})
        .sort("created_at", DESCENDING)
        .limit(6)
    )
    session_summaries.reverse()
    lines = []
    for summary in session_summaries:
        lines.extend(summary["text"].splitlines()[:2])
    document = {
        "user_id": user_id,
        "session_id": None,
        "scope": "user",
        "text": "\n".join(lines[-10:]) or "- No session summaries available.",
        "created_at": utc_now(),
    }
    summaries_collection().insert_one(document)
    return document


def maybe_summarize(user_id: str, session_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    settings = get_settings()
    user_count = messages_collection().count_documents(
        {"user_id": user_id, "session_id": session_id, "role": "user"}
    )
    if user_count == 0 or user_count % settings.summarize_every_user_msgs != 0:
        return None, None
    session_summary = summarize_session(user_id, session_id)
    session_summary_count = summaries_collection().count_documents({"user_id": user_id, "scope": "session"})
    lifetime_summary = refresh_lifetime_summary(user_id) if session_summary_count % 2 == 0 else None
    return session_summary, lifetime_summary


def build_prompt(
    short_term: list[dict[str, Any]],
    session_summary: dict[str, Any] | None,
    lifetime_summary: dict[str, Any] | None,
    episodic: list[dict[str, Any]],
    current_message: str,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    durable_context = build_file_memory_system_context()
    system = f"{SYSTEM_PRIMER}\n\n{durable_context}"
    long_term = "\n".join(
        item["text"] for item in (session_summary, lifetime_summary) if item is not None
    ) or "(no long-term summary)"
    short_text = "\n".join(message_text(item["role"], item["content"]) for item in short_term) or "(no prior session messages)"
    episodic_text = "\n".join(f"- {item['fact']} (relevance {item['similarity']:.3f})" for item in episodic) or "(no episodic facts retrieved)"
    user_context = (
        f"Long-term summaries:\n{long_term}\n\n"
        f"Short-term window:\n{short_text}\n\n"
        f"Relevant episodic facts:\n{episodic_text}\n\n"
        f"Current user message:\n{current_message}"
    )
    tokens = {
        "system_primer": estimate_tokens(system),
        "long_term_summary": estimate_tokens(long_term),
        "short_term_window": estimate_tokens(short_text),
        "episodic_facts": estimate_tokens(episodic_text),
        "current_message": estimate_tokens(current_message),
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": user_context}], tokens


def _append_telemetry(record: dict[str, Any]) -> None:
    path: Path = get_settings().telemetry_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, default=str, sort_keys=True) + "\n")


def run_chat(user_id: str, session_id: str | None, message: str) -> dict[str, Any]:
    """Perform one persisted memory-aware turn and return the required memory evidence."""
    settings = get_settings()
    session_id = session_id or str(uuid.uuid4())
    prior_for_commands = recent_messages(user_id, session_id, limit=16)
    command_reply = handle_memory_command(message, [serialize_document(item) for item in prior_for_commands])
    user_document = save_message(user_id, session_id, "user", message)

    if command_reply is not None:
        assistant_document = save_message(user_id, session_id, "assistant", command_reply)
        return {
            "reply": command_reply,
            "session_id": session_id,
            "memory_used": {"short_term_count": 0, "short_term_messages": [], "session_summary": None, "lifetime_summary": None, "episodic_facts": []},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": estimate_tokens(command_reply), "components": {}},
            "message_ids": {"user": str(user_document["_id"]), "assistant": str(assistant_document["_id"])},
        }

    session_summary = latest_summary(user_id, "session", session_id)
    window_limit = min(settings.short_term_n, 4) if settings.memory_policy == "summary_first_eviction" and session_summary else settings.short_term_n
    short_term = load_short_term(user_id, session_id, user_document["_id"], window_limit)
    lifetime_summary = latest_summary(user_id, "user")
    episodic = retrieve_episodes(user_id, message, settings.episodic_top_k)
    prompt, component_tokens = build_prompt(short_term, session_summary, lifetime_summary, episodic, message)

    started = time.perf_counter()
    result = get_model_client().complete(prompt)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    reply = result["content"].strip()
    assistant_document = save_message(user_id, session_id, "assistant", reply)
    stored_episodes = store_episodes(user_id, session_id, message)
    generated_session_summary, generated_lifetime_summary = maybe_summarize(user_id, session_id)

    telemetry = {
        "timestamp": utc_now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "short_term_n": settings.short_term_n,
        "memory_policy": settings.memory_policy,
        "prompt_tokens": result["input_tokens"],
        "completion_tokens": result["output_tokens"],
        "component_tokens": component_tokens,
        "latency_ms": latency_ms,
        "episodic_retrieved": len(episodic),
    }
    _append_telemetry(telemetry)
    return {
        "reply": reply,
        "session_id": session_id,
        "memory_used": {
            "short_term_count": len(short_term),
            "short_term_messages": [serialize_document(item) for item in short_term],
            "session_summary": serialize_document(session_summary) if session_summary else None,
            "lifetime_summary": serialize_document(lifetime_summary) if lifetime_summary else None,
            "episodic_facts": [serialize_document(item) for item in episodic],
        },
        "token_usage": {"prompt_tokens": result["input_tokens"], "completion_tokens": result["output_tokens"], "components": component_tokens, "latency_ms": latency_ms},
        "generated": {"session_summary": serialize_document(generated_session_summary) if generated_session_summary else None, "lifetime_summary": serialize_document(generated_lifetime_summary) if generated_lifetime_summary else None, "episodes_stored": [serialize_document(item) for item in stored_episodes]},
        "message_ids": {"user": str(user_document["_id"]), "assistant": str(assistant_document["_id"])},
    }


def memory_snapshot(user_id: str) -> dict[str, Any]:
    return {
        "messages": [serialize_document(item) for item in recent_messages(user_id, limit=16)],
        "session_summary": serialize_document(
            summaries_collection().find_one({"user_id": user_id, "scope": "session"}, sort=[("created_at", DESCENDING)])
        ),
        "lifetime_summary": serialize_document(latest_summary(user_id, "user")),
        "episodes": [
            serialize_document(item)
            for item in episodes_collection().find({"user_id": user_id}).sort("created_at", DESCENDING).limit(20)
        ],
    }


def aggregate_snapshot(user_id: str) -> dict[str, Any]:
    daily = list(
        messages_collection().aggregate(
            [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "message_count": {"$sum": 1}}},
                {"$sort": {"_id": ASCENDING}},
            ]
        )
    )
    summaries = list(summaries_collection().find({"user_id": user_id}).sort("created_at", DESCENDING).limit(6))
    return {
        "daily_message_counts": [{"date": item["_id"], "message_count": item["message_count"]} for item in daily],
        "recent_summaries": [serialize_document(item) for item in summaries],
    }
