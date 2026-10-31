"""Part 3 fixes: idempotency, offset commit, bounded retry + dead letter, and partition key.

Each fix is a small function so the failure tests can switch it off to show the
"before" behavior and on to show the "after" behavior.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaConsumer, TopicPartition


# --- Duplicate delivery: remember which correlation_ids were already handled -------------
class IdempotencyStore:
    """Durable set of processed correlation_ids (SQLite file, so restarts keep it)."""

    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS processed (correlation_id TEXT PRIMARY KEY)")
        self.db.commit()

    def seen(self, correlation_id: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM processed WHERE correlation_id = ?", (correlation_id,)
        ).fetchone()
        return row is not None

    def mark(self, correlation_id: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO processed VALUES (?)", (correlation_id,))
        self.db.commit()


# --- Consumer death: commit the offset only after the work is finished -------------------
async def commit_offset(consumer: AIOKafkaConsumer, msg: Any) -> None:
    """Commit "next message to read" for this message's partition."""
    await consumer.commit({TopicPartition(msg.topic, msg.partition): msg.offset + 1})


# --- Poison message: retry a bounded number of times, then give up ----------------------
async def run_with_retries(
    attempt_once: Callable[[], Awaitable[Any]],
    retry_mode: str,
    max_attempts: int,
    emit: Callable[..., None],
    backoff: float = 0.3,
) -> tuple[bool, Any, int]:
    """Return (ok, output_or_error, attempts).

    bounded:   stop after max_attempts so the caller can dead-letter the message.
    unbounded: never gives up (the "before" behavior that blocks the partition).
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return True, await attempt_once(), attempt
        except Exception as exc:  # noqa: BLE001 - any failure counts as a failed attempt
            will_retry = retry_mode != "bounded" or attempt < max_attempts
            emit("attempt_failed", attempt=attempt, error=repr(exc)[:160], will_retry=will_retry)
            if not will_retry:
                return False, repr(exc)[:160], attempt
            await asyncio.sleep(backoff)


def dead_letter_record(msg: Any, error: str, attempts: int, instance: str) -> dict[str, Any]:
    """What goes to <PREFIX>_dead_letter: enough to find and replay the bad message."""
    raw = msg.value.decode(errors="replace")
    try:
        correlation_id = json.loads(raw).get("correlation_id")
    except (ValueError, AttributeError):
        correlation_id = None
    return {
        "correlation_id": correlation_id,
        "source_topic": msg.topic,
        "partition": msg.partition,
        "offset": msg.offset,
        "attempts": attempts,
        "error": error,
        "original": raw,
        "failed_by": instance,
    }


# --- Ordering: related messages share a key, so they share a partition -------------------
def partition_key(message: dict[str, Any]) -> bytes:
    """Key by the entity the messages are about (falling back to the journey's correlation_id)."""
    return str(message.get("entity_id") or message["correlation_id"]).encode()
