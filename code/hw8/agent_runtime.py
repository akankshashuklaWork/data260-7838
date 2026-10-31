"""Shared Kafka loop for the Planner, Writer, and Reviewer processes.

Every agent reads one topic, handles one message at a time, publishes its result to
the next topic, and only then commits the offset. Environment variables switch the
Part 3 fixes off for the "before" experiments; the defaults are the fixed behavior.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRebalanceListener
from common import log, start_with_retry, to_bytes, utc_iso
from config import CONFIG, KAFKA_BOOTSTRAP
from reliability import (
    IdempotencyStore,
    commit_offset,
    dead_letter_record,
    partition_key,
    run_with_retries,
)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    agent: str
    instance: str = os.getenv("INSTANCE", "")
    group_id: str = ""
    offset_reset: str = os.getenv("AUTO_OFFSET_RESET", "earliest")
    commit_mode: str = os.getenv("COMMIT_MODE", "late")  # late = after processing (fixed)
    idempotent: bool = os.getenv("IDEMPOTENT", "1") == "1"
    retry_mode: str = os.getenv("RETRY_MODE", "bounded")  # bounded = retry limit + dead letter
    max_attempts: int = int(os.getenv("MAX_ATTEMPTS", "3"))
    llm_mode: str = os.getenv("AGENT_LLM", "ollama")  # ollama = qwen2:7b, stub = offline
    event_log: str = os.getenv("EVENT_LOG", "")
    processed_db: str = ""
    label: str = field(init=False)

    def __post_init__(self) -> None:
        self.group_id = os.getenv("GROUP_ID") or f"{CONFIG.prefix}_{self.agent}_group"
        self.processed_db = os.getenv("PROCESSED_DB") or str(
            ROOT / f"data/hw8/idempotency_{self.agent}.db"
        )
        suffix = f"-{self.instance}" if self.instance else ""
        self.label = f"{self.agent.upper()}{suffix}"


class AssignmentLogger(ConsumerRebalanceListener):
    """Records which partitions this process owns after every rebalance."""

    def __init__(self, settings: Settings, emit: Any) -> None:
        self.settings = settings
        self.emit = emit

    def on_partitions_revoked(self, revoked: Any) -> None:
        pass

    def on_partitions_assigned(self, assigned: Any) -> None:
        partitions = sorted(tp.partition for tp in assigned)
        log(self.settings.label, f"assigned partitions={partitions}")
        self.emit("assigned", partitions=partitions)


async def ask_model(system: str, prompt: str) -> str:
    """One chat call to the local qwen2:7b model (temperature 0, fixed SEED)."""
    from ollama import AsyncClient

    reply = await AsyncClient(host="http://localhost:11434").chat(
        model=CONFIG.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        options={"temperature": 0, "seed": CONFIG.seed},
    )
    return reply["message"]["content"].strip()


async def run_agent(agent: str, in_topic: str, out_topic: str, handler: Any) -> None:
    s = Settings(agent)
    store = IdempotencyStore(s.processed_db) if s.idempotent else None

    def emit(event: str, **fields: Any) -> None:
        """Append one machine-readable event; the failure tests read these."""
        if not s.event_log:
            return
        record = {"ts": time.time(), "iso": utc_iso(), "agent": agent, "instance": s.instance}
        with open(s.event_log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, "event": event, **fields}) + "\n")

    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=s.group_id,
        auto_offset_reset=s.offset_reset,
        enable_auto_commit=False,  # offsets are committed explicitly, see commit_offset
        session_timeout_ms=6000,
        heartbeat_interval_ms=2000,
    )
    consumer.subscribe([in_topic], listener=AssignmentLogger(s, emit))
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await start_with_retry(consumer, s.label)
    await start_with_retry(producer, s.label)
    log(s.label, f"Consumer is ready and listening... topic={in_topic} group={s.group_id}")
    emit("ready", topic=in_topic, group=s.group_id)

    try:
        async for msg in consumer:
            detail = {"topic": msg.topic, "partition": msg.partition, "offset": msg.offset}
            try:
                payload = json.loads(msg.value.decode())
                correlation_id = payload.get("correlation_id")
                entity_id, seq = payload.get("entity_id"), payload.get("seq")
            except (ValueError, AttributeError):
                correlation_id = entity_id = seq = None
            detail.update(correlation_id=correlation_id, entity_id=entity_id, seq=seq)
            log(
                s.label,
                f"received {in_topic} partition={msg.partition} offset={msg.offset} "
                f"correlation_id={correlation_id}",
            )
            emit("received", **detail)

            if s.commit_mode == "early":  # "before": commit on receipt, work not done yet
                await commit_offset(consumer, msg)
                emit("committed", **detail)

            if store and correlation_id and store.seen(correlation_id):
                log(s.label, f"duplicate skipped correlation_id={correlation_id}")
                emit("duplicate_skipped", **detail)
            else:

                async def attempt_once() -> dict[str, Any] | None:
                    message = json.loads(msg.value.decode())
                    if not isinstance(message, dict):
                        raise ValueError("message must be a JSON object")
                    log(s.label, f"processing correlation_id={correlation_id}")
                    result = await handler(message)
                    if result is not None:
                        log(s.label, f"sending to {out_topic} correlation_id={correlation_id}")
                        await producer.send_and_wait(
                            out_topic, to_bytes(result), key=partition_key(result)
                        )
                    return result

                def emit_attempt(event: str, **fields: Any) -> None:
                    log(s.label, f"{event} correlation_id={correlation_id} {fields}")
                    emit(event, **detail, **fields)

                ok, outcome, attempts = await run_with_retries(
                    attempt_once, s.retry_mode, s.max_attempts, emit_attempt
                )
                if ok:
                    if store and correlation_id:
                        store.mark(correlation_id)  # remember before committing the offset
                    log(
                        s.label,
                        f"processed correlation_id={correlation_id} -> "
                        f"{out_topic if outcome is not None else '(no output)'}",
                    )
                    emit("processed", **detail, attempts=attempts)
                else:
                    record = dead_letter_record(msg, outcome, attempts, s.label)
                    await producer.send_and_wait(CONFIG.dead_letter_topic, to_bytes(record))
                    log(
                        s.label,
                        f"moved to {CONFIG.dead_letter_topic} after {attempts} attempts "
                        f"correlation_id={correlation_id}",
                    )
                    emit("dead_letter", **detail, attempts=attempts, error=outcome)

            if s.commit_mode == "late":  # "after": commit only once the work is done
                await commit_offset(consumer, msg)
                emit("committed", **detail)
    finally:
        await consumer.stop()
        await producer.stop()


def run(agent: str, in_topic: str, out_topic: str, handler: Any) -> None:
    try:
        asyncio.run(run_agent(agent, in_topic, out_topic, handler))
    except KeyboardInterrupt:
        pass
