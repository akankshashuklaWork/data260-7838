"""Send one question through the HW8 Planner -> Writer -> Reviewer pipeline and wait for the answer."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from hw8.common import to_bytes

from .config import CONFIG, KAFKA_BOOTSTRAP


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
            final = json.loads(msg.value.decode())
            future = self.pending.pop(final.get("correlation_id"), None)
            if future and not future.done():
                future.set_result(final)

    async def ask(
        self, question: str, context: str = "", timeout: float = 300
    ) -> tuple[str, float]:
        """Return (answer, pipeline_ms). Raises TimeoutError when the agents are not running."""
        correlation_id = str(uuid.uuid4())
        message: dict = {"correlation_id": correlation_id, "question": question}
        if context:
            message["context"] = context
        future = asyncio.get_running_loop().create_future()
        self.pending[correlation_id] = future
        started = time.perf_counter()
        await self.producer.send_and_wait(  # type: ignore[union-attr]
            CONFIG.inbox_topic, to_bytes(message), key=correlation_id.encode()
        )
        final = await asyncio.wait_for(future, timeout=timeout)
        return final["answer"], (time.perf_counter() - started) * 1000
