"""Helpers for running the agents as real processes and inspecting Kafka from the outside."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient

from .config import KAFKA_BOOTSTRAP

HW8_DIR = Path(__file__).resolve().parent
ROOT = HW8_DIR.parents[1]


class AgentProcess:
    """One agent script (planner.py, writer.py, reviewer.py) running as its own process."""

    def __init__(self, script: str, env: dict[str, str], log_path: Path) -> None:
        self.script = script
        self.log_path = log_path
        self.log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - closed in stop()
        self.proc = subprocess.Popen(
            [sys.executable, "-u", script],
            cwd=HW8_DIR,
            env={**os.environ, **env, "PYTHONUNBUFFERED": "1"},
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )

    def kill(self) -> None:
        """SIGKILL: the process dies mid-work and cannot commit or leave its group politely."""
        self.proc.send_signal(signal.SIGKILL)
        self.proc.wait()
        self.log_file.close()

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if not self.log_file.closed:
            self.log_file.close()

    def lines(self) -> list[str]:
        return self.log_path.read_text(encoding="utf-8").splitlines()


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def wait_until(condition: Callable[[], bool], timeout: float, what: str, poll: float = 0.2) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return
        time.sleep(poll)
    raise TimeoutError(f"timed out after {timeout}s waiting for {what}")


def event_exists(path: Path, **match: Any) -> Callable[[], bool]:
    def check() -> bool:
        return any(
            all(event.get(key) == value for key, value in match.items())
            for event in read_events(path)
        )

    return check


async def end_offsets(topic: str) -> dict[int, int]:
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    try:
        partitions = sorted(await producer.partitions_for(topic))
    finally:
        await producer.stop()
    consumer = AIOKafkaConsumer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await consumer.start()
    try:
        tps = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(tps)  # a consumer with no assignment fails to stop cleanly
        ends = await consumer.end_offsets(tps)
        return {tp.partition: offset for tp, offset in ends.items()}
    finally:
        await consumer.stop()


async def prime_group(group_id: str, topic: str) -> None:
    """Give a fresh consumer group a committed offset at the end of the topic.

    Tests then start from a known point (old messages are never replayed) and a
    restarted consumer has a committed offset to resume from.
    """
    ends = await end_offsets(topic)
    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP, group_id=group_id, enable_auto_commit=False
    )
    await consumer.start()
    try:
        offsets = {TopicPartition(topic, p): end for p, end in ends.items()}
        consumer.assign(list(offsets))
        await consumer.commit(offsets)
    finally:
        await consumer.stop()


async def committed_offsets(group_id: str, topic: str) -> dict[int, int]:
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        found = await admin.list_consumer_group_offsets(group_id)
    finally:
        await admin.close()
    return {tp.partition: meta.offset for tp, meta in found.items() if tp.topic == topic}


async def messages_since(
    topic: str, start: dict[int, int], quiet_seconds: float = 1.5
) -> list[dict[str, Any]]:
    """Read every message appended to `topic` after the `start` offsets, as dicts."""
    consumer = AIOKafkaConsumer(bootstrap_servers=KAFKA_BOOTSTRAP, enable_auto_commit=False)
    await consumer.start()
    try:
        tps = [TopicPartition(topic, p) for p in start]
        consumer.assign(tps)
        for tp in tps:
            consumer.seek(tp, start[tp.partition])
        found: list[dict[str, Any]] = []
        while True:
            batch = await consumer.getmany(timeout_ms=int(quiet_seconds * 1000))
            if not batch:
                return found
            for records in batch.values():
                for record in records:
                    try:
                        value = json.loads(record.value.decode())
                    except ValueError:
                        value = {"raw": record.value.decode(errors="replace")}
                    found.append(
                        {**value, "_partition": record.partition, "_offset": record.offset}
                    )
    finally:
        await consumer.stop()


async def send_raw(
    topic: str, value: bytes, key: bytes | None = None, partition: int | None = None
) -> Any:
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    try:
        return await producer.send_and_wait(topic, value, key=key, partition=partition)
    finally:
        await producer.stop()
