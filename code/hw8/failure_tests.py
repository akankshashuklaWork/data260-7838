"""Part 3 failure experiments: each runs "before fix" and "after fix" against real Kafka.

The Writer is started as a real process with the relevant fix switched off (before) or
on (after). Its machine-readable event log (received / processed / committed / ...) is
the evidence; the topics are read back from Kafka to confirm what was published.

    PYTHONPATH=code python -m hw8.failure_tests
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaProducer

from .common import log, to_bytes, utc_iso
from .config import CONFIG, KAFKA_BOOTSTRAP
from .harness import (
    ROOT,
    AgentProcess,
    committed_offsets,
    end_offsets,
    event_exists,
    messages_since,
    prime_group,
    read_events,
    wait_until,
)
from .reliability import partition_key

RAW = ROOT / "reports/hw08/raw"
ENTITIES = ["listing-1", "listing-2", "listing-3", "listing-6"]  # ids hash to both partitions


def task(correlation_id: str, entity_id: str, seq: int, work_ms: int = 0, **extra: Any) -> dict:
    return {
        "correlation_id": correlation_id,
        "entity_id": entity_id,
        "seq": seq,
        "question": f"Summarize what a renter should know about {entity_id}.",
        "plan": ["Check the price.", "Check the lease terms.", "Check the neighborhood."],
        "work_ms": work_ms,
        **extra,
    }


async def produce(items: list[tuple[dict | bytes, bytes | None, int | None]]) -> None:
    """Send (message, key, partition) tuples to the tasks topic, in order, from one producer."""
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    try:
        for message, key, partition in items:
            value = message if isinstance(message, bytes) else to_bytes(message)
            await producer.send_and_wait(CONFIG.tasks_topic, value, key=key, partition=partition)
    finally:
        await producer.stop()


class WriterRun:
    """A Writer process plus the paths of its logs, for one scenario."""

    def __init__(self, workdir: Path, scenario: str, group: str, flags: dict[str, str]) -> None:
        self.workdir, self.scenario, self.group, self.flags = workdir, scenario, group, flags
        self.events = workdir / f"{scenario}_events.jsonl"
        self.processes: list[AgentProcess] = []
        self.notes: list[str] = []

    def start(self, instance: str) -> AgentProcess:
        env = {
            "AGENT_LLM": "stub",
            "GROUP_ID": self.group,
            "INSTANCE": instance,
            "EVENT_LOG": str(self.events),
            "PROCESSED_DB": str(self.workdir / f"{self.scenario}_idempotency.db"),
            **self.flags,
        }
        process = AgentProcess(
            "writer.py", env, self.workdir / f"{self.scenario}_writer{instance}.log"
        )
        self.processes.append(process)
        wait_until(
            event_exists(self.events, event="ready", instance=instance), 60, f"writer {instance}"
        )
        return process

    def stop(self) -> None:
        for process in self.processes:
            process.stop()

    def console(self) -> list[str]:
        return sorted(
            [line for p in self.processes for line in p.lines() if line[:2] == "20"] + self.notes
        )

    def events_for(self, correlation_id: str | None = None, **match: Any) -> list[dict]:
        return [
            event
            for event in read_events(self.events)
            if (correlation_id is None or event.get("correlation_id") == correlation_id)
            and all(event.get(k) == v for k, v in match.items())
        ]


def new_run(
    workdir: Path, scenario: str, variant: str, flags: dict[str, str]
) -> tuple[WriterRun, str]:
    group = f"{CONFIG.prefix}_test_{scenario}_{variant}_{uuid.uuid4().hex[:6]}"
    asyncio.run(prime_group(group, CONFIG.tasks_topic))
    return WriterRun(workdir, f"{scenario}_{variant}", group, flags), group


def finish(run: WriterRun, result: dict[str, Any], raw_dir: Path | None) -> dict[str, Any]:
    """Stop the writers, keep their console lines in the result, and archive the event log."""
    run.stop()
    result["writer_console"] = run.console()
    if raw_dir:
        events_dir = raw_dir / "part3_events"
        events_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(run.events, events_dir / run.events.name)
    return result


# --- I. Duplicate delivery ---------------------------------------------------------------
def duplicate_delivery(workdir: Path, fixed: bool, raw_dir: Path | None) -> dict[str, Any]:
    variant = "after" if fixed else "before"
    run, _ = new_run(workdir, "duplicate", variant, {"IDEMPOTENT": "1" if fixed else "0"})
    drafts_start = asyncio.run(end_offsets(CONFIG.drafts_topic))
    run.start("1")
    correlation_id = f"dup-{variant}-{uuid.uuid4().hex[:6]}"
    message = task(correlation_id, "listing-1", 1, work_ms=200)
    key = partition_key(message)
    # Replay: the exact same message (same correlation_id) is delivered twice.
    asyncio.run(produce([(message, key, None), (message, key, None)]))
    wait_until(
        lambda: len(run.events_for(correlation_id, event="committed")) == 2, 30, "both deliveries"
    )
    published = [
        d
        for d in asyncio.run(messages_since(CONFIG.drafts_topic, drafts_start))
        if d.get("correlation_id") == correlation_id
    ]
    result = {
        "scenario": "duplicate_delivery",
        "variant": variant,
        "correlation_id": correlation_id,
        "deliveries": 2,
        "processed": len(run.events_for(correlation_id, event="processed")),
        "duplicates_skipped": len(run.events_for(correlation_id, event="duplicate_skipped")),
        "drafts_published": len(published),
        "side_effect_repeated": len(published) > 1,
    }
    return finish(run, result, raw_dir)


# --- II. Consumer death ------------------------------------------------------------------
def consumer_death(workdir: Path, fixed: bool, raw_dir: Path | None) -> dict[str, Any]:
    variant = "after" if fixed else "before"
    run, group = new_run(workdir, "death", variant, {"COMMIT_MODE": "late" if fixed else "early"})
    drafts_start = asyncio.run(end_offsets(CONFIG.drafts_topic))
    writer = run.start("1")
    correlation_id = f"kill-{variant}-{uuid.uuid4().hex[:6]}"
    asyncio.run(produce([(task(correlation_id, "listing-1", 1, work_ms=4000), b"listing-1", None)]))
    wait_until(
        event_exists(run.events, event="received", correlation_id=correlation_id), 30, "receive"
    )
    received = run.events_for(correlation_id, event="received")[0]
    time.sleep(0.5)
    writer.kill()  # terminate Writer mid-processing (it is inside the 4 s work step)
    log("TEST", f"Writer killed mid-processing correlation_id={correlation_id}")
    run.notes.append(
        f"{utc_iso()} [TEST] SIGKILL sent to WRITER-1 mid-processing correlation_id={correlation_id}"
    )
    partition, offset = received["partition"], received["offset"]
    committed_at_kill = asyncio.run(committed_offsets(group, CONFIG.tasks_topic)).get(partition)

    run.start("2")  # restart: same group, new process
    redelivered = False
    try:
        wait_until(
            event_exists(run.events, event="processed", correlation_id=correlation_id),
            45 if fixed else 20,
            "redelivery and completion",
        )
        redelivered = True
    except TimeoutError:
        pass
    time.sleep(1.5)
    committed_final = asyncio.run(committed_offsets(group, CONFIG.tasks_topic)).get(partition)
    drafts = [
        d
        for d in asyncio.run(messages_since(CONFIG.drafts_topic, drafts_start))
        if d.get("correlation_id") == correlation_id
    ]
    processed_events = run.events_for(correlation_id, event="processed")
    committed_events = run.events_for(correlation_id, event="committed")
    result = {
        "scenario": "consumer_death",
        "variant": variant,
        "correlation_id": correlation_id,
        "partition": partition,
        "message_offset": offset,
        "committed_offset_after_kill": committed_at_kill,
        "committed_offset_after_restart": committed_final,
        "received_by_restarted_writer": any(
            e["instance"] == "2" for e in run.events_for(correlation_id, event="received")
        ),
        "completed_after_restart": redelivered,
        "drafts_published": len(drafts),
        "commit_after_processing": bool(
            processed_events
            and committed_events
            and max(e["ts"] for e in committed_events) > min(e["ts"] for e in processed_events)
        ),
        "message_lost": len(drafts) == 0,
    }
    return finish(run, result, raw_dir)


# --- III. Poison message -----------------------------------------------------------------
def poison_message(workdir: Path, fixed: bool, raw_dir: Path | None) -> dict[str, Any]:
    variant = "after" if fixed else "before"
    run, _ = new_run(
        workdir,
        "poison",
        variant,
        {"RETRY_MODE": "bounded" if fixed else "unbounded", "MAX_ATTEMPTS": "3"},
    )
    drafts_start = asyncio.run(end_offsets(CONFIG.drafts_topic))
    dlq_start = asyncio.run(end_offsets(CONFIG.dead_letter_topic))
    run.start("1")
    poison_id = f"poison-{variant}-{uuid.uuid4().hex[:6]}"
    good_id = f"good-{variant}-{uuid.uuid4().hex[:6]}"
    poison = task(poison_id, "listing-poison", 1)
    del poison["question"]  # a task with no question can never be written; it always fails
    good = task(good_id, "listing-poison", 2)  # same key, so it queues behind the poison message
    key = b"listing-poison"
    asyncio.run(produce([(poison, key, None), (good, key, None)]))
    if fixed:
        wait_until(
            event_exists(run.events, event="processed", correlation_id=good_id), 30, "good message"
        )
    else:
        time.sleep(12)  # observe: does the bad message ever stop blocking the good one?
    time.sleep(1)
    dead = [
        d
        for d in asyncio.run(messages_since(CONFIG.dead_letter_topic, dlq_start))
        if d.get("correlation_id") == poison_id
    ]
    drafts = [
        d
        for d in asyncio.run(messages_since(CONFIG.drafts_topic, drafts_start))
        if d.get("correlation_id") == good_id
    ]
    failed_attempts = run.events_for(poison_id, event="attempt_failed")
    result = {
        "scenario": "poison_message",
        "variant": variant,
        "poison_correlation_id": poison_id,
        "good_correlation_id": good_id,
        "poison_attempts": len(failed_attempts),
        "retry_limit": 3 if fixed else None,
        "moved_to_dead_letter": len(dead),
        "dead_letter_record": dead[0] if dead else None,
        "good_message_processed": len(drafts) == 1,
        "good_message_blocked": len(drafts) == 0,
    }
    return finish(run, result, raw_dir)


# --- IV. Ordering ------------------------------------------------------------------------
def make_ordering_messages() -> list[dict[str, Any]]:
    """20 related messages generated from VERIFY_SEED (same list for both runs)."""
    rng = random.Random(CONFIG.verify_seed)
    next_seq = dict.fromkeys(ENTITIES, 0)
    messages = []
    for index in range(20):
        entity = rng.choice(ENTITIES)
        next_seq[entity] += 1
        correlation_id = f"order-{index:02d}-{rng.getrandbits(24):06x}"
        messages.append(
            task(correlation_id, entity, next_seq[entity], work_ms=rng.choice([100, 300, 500, 700]))
        )
    return messages


def ordering(workdir: Path, fixed: bool, raw_dir: Path | None) -> dict[str, Any]:
    variant = "keyed" if fixed else "unkeyed"
    run, _ = new_run(workdir, "ordering", variant, {})
    run.start("A")
    run.start("B")
    # Wait for the group to settle: one partition for each of the two Writers.

    def settled() -> bool:
        latest: dict[str, list[int]] = {}
        for event in read_events(run.events):
            if event["event"] == "assigned":
                latest[event["instance"]] = event["partitions"]
        return len(latest) == 2 and sorted(sum(latest.values(), [])) == [0, 1]

    wait_until(settled, 60, "two Writers to split the two partitions")
    messages = make_ordering_messages()
    partition_rng = random.Random(CONFIG.verify_seed + 1)
    if fixed:
        items = [(m, partition_key(m), None) for m in messages]  # key = entity_id
    else:
        # No key: spread messages over both partitions like a keyless producer would.
        items = [(m, None, partition_rng.randrange(2)) for m in messages]
    asyncio.run(produce(items))
    wait_until(lambda: len(run.events_for(event="processed")) >= 20, 120, "all 20 messages")
    time.sleep(1)

    processed = sorted(run.events_for(event="processed"), key=lambda e: e["ts"])
    sent_index = {m["correlation_id"]: i for i, m in enumerate(messages)}
    rows = [
        {
            "processing_order": order,
            "sent_index": sent_index[e["correlation_id"]],
            "writer": e["instance"],
            "partition": e["partition"],
            "offset": e["offset"],
            "entity_id": e["entity_id"],
            "seq": e["seq"],
            "correlation_id": e["correlation_id"],
        }
        for order, e in enumerate(processed, 1)
    ]
    per_entity = {}
    for entity in ENTITIES:
        entity_rows = [r for r in rows if r["entity_id"] == entity]
        seqs = [r["seq"] for r in entity_rows]
        per_entity[entity] = {
            "messages": len(seqs),
            "partitions_used": sorted({r["partition"] for r in entity_rows}),
            "processed_seq_order": seqs,
            "in_order": seqs == sorted(seqs),
        }
    result = {
        "scenario": "ordering",
        "variant": variant,
        "verify_seed": CONFIG.verify_seed,
        "messages": len(messages),
        "per_entity": per_entity,
        "entities_out_of_order": [e for e, v in per_entity.items() if not v["in_order"]],
        "entities_split_across_partitions": [
            e for e, v in per_entity.items() if len(v["partitions_used"]) > 1
        ],
        "all_in_order": all(v["in_order"] for v in per_entity.values()),
        "all_in_one_partition": all(len(v["partitions_used"]) == 1 for v in per_entity.values()),
        "rows": rows,
    }
    if raw_dir:
        with open(
            raw_dir / f"part3_ordering_{variant}.csv", "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return finish(run, result, raw_dir)


SCENARIOS = {
    "duplicate": duplicate_delivery,
    "death": consumer_death,
    "poison": poison_message,
    "ordering": ordering,
}


def run_all(raw_dir: Path | None, include_before: bool = True) -> dict[str, Any]:
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for name, scenario in SCENARIOS.items():
            variants = [False, True] if include_before else [True]
            for fixed in variants:
                label = f"{name}:{'after' if fixed else 'before'}"
                log("TEST", f"=== {label} ===")
                result = scenario(workdir, fixed, raw_dir)
                results[label] = result
                for line in result["writer_console"]:
                    print(line, flush=True)
                brief = {k: v for k, v in result.items() if k not in ("writer_console", "rows")}
                log("TEST", f"{label} result: {json.dumps(brief, default=str)}")
    return results


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    results = run_all(RAW)
    for name, filename in {
        "duplicate": "part3_duplicate_delivery.json",
        "death": "part3_consumer_death.json",
        "poison": "part3_poison_message.json",
        "ordering": "part3_ordering.json",
    }.items():
        payload = {v["variant"]: v for k, v in results.items() if k.startswith(name + ":")}
        (RAW / filename).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
