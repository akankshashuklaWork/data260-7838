"""Fixed configuration required for DATA 260 HW8 (shared by every HW8 module)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HomeworkConfig:
    sid4: int = 7838
    port: int = 8638
    prefix: str = "s7838"
    seed: int = 7838
    verify_seed: int = 267838
    domain_id: int = 6
    model: str = "qwen2:7b"
    hardware: str = "MacBook Pro (Apple M4 Pro, 48 GB unified memory)"

    # Part 1: request/response topics (exactly two).
    @property
    def request_topic(self) -> str:
        return f"{self.prefix}_entity_requests"

    @property
    def response_topic(self) -> str:
        return f"{self.prefix}_entity_responses"

    # Part 2: three-agent pipeline topics.
    @property
    def inbox_topic(self) -> str:
        return f"{self.prefix}_inbox"

    @property
    def tasks_topic(self) -> str:
        return f"{self.prefix}_tasks"

    @property
    def drafts_topic(self) -> str:
        return f"{self.prefix}_drafts"

    @property
    def final_topic(self) -> str:
        return f"{self.prefix}_final"

    # Part 3: dead-letter topic.
    @property
    def dead_letter_topic(self) -> str:
        return f"{self.prefix}_dead_letter"

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


CONFIG = HomeworkConfig()

# Host processes reach the broker on localhost:9092; containers use kafka:19092.
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# (topic, partitions) for every topic the homework uses.
TOPIC_PLAN = [
    (CONFIG.request_topic, 1),
    (CONFIG.response_topic, 1),
    (CONFIG.inbox_topic, 1),
    (CONFIG.tasks_topic, 2),
    (CONFIG.drafts_topic, 1),
    (CONFIG.final_topic, 1),
    (CONFIG.dead_letter_topic, 1),
]
