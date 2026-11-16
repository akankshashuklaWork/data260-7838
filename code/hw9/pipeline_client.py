"""Send one question through the HW8 Planner -> Writer -> Reviewer pipeline and wait for the answer.

HW10 additions: the caller may supply the trace_id (it becomes the HW8 correlation_id, so no
second identifier exists), the client also listens to the dead-letter topic so a poisoned request
fails fast with the failing stage instead of waiting for the full timeout, and it records the
``queue_final`` span (final message created -> received here).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from hw8.common import to_bytes
from hw8.tracing import write_span

from .config import CONFIG, KAFKA_BOOTSTRAP


class PipelineError(RuntimeError):
    """The pipeline gave up on a request (the message was dead-lettered)."""

    def __init__(self, stage: str, error: str, trace_id: str) -> None:
        super().__init__(f"{stage} failed: {error}")
        self.stage, self.error, self.trace_id = stage, error, trace_id


class PipelineClient:
    def __init__(self) -> None:
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        self.consumer = AIOKafkaConsumer(
            CONFIG.final_topic,
            CONFIG.dead_letter_topic,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=f"{CONFIG.prefix}_cache_{uuid.uuid4().hex[:8]}",
            auto_offset_reset="latest",  # only answers produced after this client started
        )
        await self.producer.start()
        await self.consumer.start()
        self.task = asyncio.create_task(self._read_answers())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def _read_answers(self) -> None:
        async for msg in self.consumer:  # type: ignore[union-attr]
            received_at = time.time()
            try:
                payload = json.loads(msg.value.decode())
            except ValueError:
                continue
            correlation_id = payload.get("correlation_id")
            future = self.pending.pop(correlation_id, None)
            if msg.topic == CONFIG.dead_letter_topic:
                if future and not future.done():
                    future.set_exception(
                        PipelineError(
                            str(payload.get("failed_by", "unknown")).split("-")[0].lower(),
                            str(payload.get("error", "unknown error")),
                            correlation_id,
                        )
                    )
                continue
            if future and not future.done():
                if msg.timestamp and msg.timestamp > 0:
                    write_span(
                        correlation_id, "queue_final", min(msg.timestamp / 1000, received_at),
                        received_at, service="ingress", topic=msg.topic, partition=msg.partition,
                    )  # fmt: skip
                future.set_result(payload)

    async def ask(
        self,
        question: str,
        context: str = "",
        timeout: float = 300,
        trace_id: str | None = None,
    ) -> tuple[str, float]:
        """Return (answer, pipeline_ms).

        Raises PipelineError when the pipeline dead-letters the request and TimeoutError when
        the agents are not running.
        """
        correlation_id = trace_id or str(uuid.uuid4())  # the trace_id IS the correlation_id
        message: dict = {"correlation_id": correlation_id, "question": question}
        if context:
            message["context"] = context
        future = asyncio.get_running_loop().create_future()
        self.pending[correlation_id] = future
        started = time.perf_counter()
        await self.producer.send_and_wait(  # type: ignore[union-attr]
            CONFIG.inbox_topic, to_bytes(message), key=correlation_id.encode()
        )
        try:
            final = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.pending.pop(correlation_id, None)
        return final["answer"], (time.perf_counter() - started) * 1000
