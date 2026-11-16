"""Join the Planner plan, Writer draft, and Reviewer final that share one correlation_id.

Used by the evaluator (live scoring), by the frozen-case builder, and by the latency experiment.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from aiokafka import AIOKafkaConsumer
from hw8.common import log

from .config import CONFIG, EVAL_EVENTS, JOIN_TIMEOUT_S, KAFKA_BOOTSTRAP, MAX_BUFFERED_TRACES

TOPIC_ROLE = {
    CONFIG.tasks_topic: "plan",
    CONFIG.drafts_topic: "draft",
    CONFIG.final_topic: "final",
}


@dataclass
class Bundle:
    """The three messages that belong to one trace_id."""

    trace_id: str
    created: float = field(default_factory=time.time)
    plan: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    final: dict[str, Any] | None = None

    def complete(self) -> bool:
        return None not in (self.plan, self.draft, self.final)

    def missing(self) -> list[str]:
        return [role for role in ("plan", "draft", "final") if getattr(self, role) is None]


def record_event(kind: str, **fields: Any) -> None:
    """Append one line to the evaluator event log (joins, timeouts, malformed messages)."""
    from hw8.common import utc_iso

    EVAL_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with open(EVAL_EVENTS, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": utc_iso(), "event": kind, **fields}) + "\n")


class Collector:
    """Buffers messages from the three pipeline topics, keyed by correlation_id."""

    def __init__(self) -> None:
        self.bundles: OrderedDict[str, Bundle] = OrderedDict()

    def add(self, topic: str, raw: bytes) -> Bundle | None:
        """File one message under its correlation_id; malformed input is logged and skipped."""
        try:
            payload = json.loads(raw.decode())
            if not isinstance(payload, dict):
                raise ValueError("message is not a JSON object")
            trace_id = payload["correlation_id"]
            if not isinstance(trace_id, str) or not trace_id:
                raise ValueError("correlation_id missing or not a string")
        except (ValueError, KeyError, UnicodeDecodeError) as exc:
            record_event("malformed_message", topic=topic, error=repr(exc)[:160])
            log("EVALUATOR", f"skipped malformed message on {topic}: {exc!r}")
            return None
        bundle = self.bundles.get(trace_id)
        if bundle is None:
            bundle = self.bundles[trace_id] = Bundle(trace_id)
            while len(self.bundles) > MAX_BUFFERED_TRACES:  # bounded memory
                self.bundles.popitem(last=False)
        setattr(bundle, TOPIC_ROLE[topic], payload)
        return bundle

    async def wait_for_all(self, bundle: Bundle, timeout: float = JOIN_TIMEOUT_S) -> bool:
        """True once plan, draft, and final are all present; False when the wait is capped."""
        deadline = time.time() + timeout
        while not bundle.complete():
            if time.time() > deadline:
                return False
            await asyncio.sleep(0.05)
        return True


async def open_consumer() -> AIOKafkaConsumer:
    """A fresh consumer group on the three topics, starting from new messages only."""
    consumer = AIOKafkaConsumer(
        *TOPIC_ROLE,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"{CONFIG.prefix}_hw10_{uuid.uuid4().hex[:8]}",
        auto_offset_reset="latest",
    )
    await consumer.start()
    return consumer
