"""Client side of the request/response pattern: send a request, wait for its reply.

The API wrapper never talks to the worker directly. It publishes a request message
to Kafka and waits for the response message that carries the same correlation_id.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from common import log, start_with_retry, to_bytes
from config import CONFIG, KAFKA_BOOTSTRAP

TIMEOUT_SECONDS = 10


class KafkaRPC:
    def __init__(self) -> None:
        # aiokafka clients must be created inside the running event loop, so start() builds them.
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.consumer_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        # A unique group per API process means this process sees every response,
        # so the reply for a pending request cannot be taken by another instance.
        self.consumer = AIOKafkaConsumer(
            CONFIG.response_topic,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=f"{CONFIG.prefix}_api_{uuid.uuid4().hex[:8]}",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await start_with_retry(self.producer, "FASTAPI")
        await start_with_retry(self.consumer, "FASTAPI")
        self.consumer_task = asyncio.create_task(self.consume_responses())

    async def stop(self) -> None:
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        await self.consumer.stop()
        await self.producer.stop()

    async def consume_responses(self) -> None:
        async for msg in self.consumer:
            response = json.loads(msg.value.decode())
            correlation_id = response.get("correlation_id")
            log(
                "FASTAPI",
                f"received response topic={msg.topic} partition={msg.partition} "
                f"offset={msg.offset} correlation_id={correlation_id}",
            )
            future = self.pending.pop(correlation_id, None)
            if future is None:
                log("FASTAPI", f"no pending request for correlation_id={correlation_id}")
            elif not future.done():
                future.set_result(response)

    async def call(
        self, operation: Any, data: Any, correlation_id: str | None = None
    ) -> dict[str, Any]:
        # The correlation_id is created once; every later hop must preserve it.
        correlation_id = correlation_id or str(uuid.uuid4())
        request = {
            "correlation_id": correlation_id,
            "reply_to": CONFIG.response_topic,
            "operation": operation,
            "data": data,
        }
        future = asyncio.get_running_loop().create_future()
        self.pending[correlation_id] = future

        # Log before publishing: the worker can reply before send_and_wait even returns.
        log(
            "FASTAPI",
            f"sending request topic={CONFIG.request_topic} correlation_id={correlation_id} "
            f"operation={operation}",
        )
        log("FASTAPI", f"request message={json.dumps(request, separators=(',', ':'))}")
        await self.producer.send_and_wait(CONFIG.request_topic, to_bytes(request))
        try:
            response = await asyncio.wait_for(future, timeout=TIMEOUT_SECONDS)
        except TimeoutError:
            self.pending.pop(correlation_id, None)
            return {
                "correlation_id": correlation_id,
                "success": False,
                "error": "Timed out waiting for the worker",
            }
        log(
            "FASTAPI",
            f"returned to caller correlation_id={correlation_id} success={response.get('success')}",
        )
        return response
