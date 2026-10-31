"""Terminal 4: send one question to <PREFIX>_inbox and print the answer from <PREFIX>_final."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from common import log, to_bytes
from config import CONFIG, KAFKA_BOOTSTRAP

DEFAULT_QUESTION = (
    "What should a renter check before signing a lease for a two-bedroom apartment in San Jose?"
)
TIMEOUT_SECONDS = 240


async def main(question: str) -> int:
    correlation_id = str(uuid.uuid4())  # created once; every agent must preserve it
    # Start listening on the final topic first so the answer cannot be missed.
    consumer = AIOKafkaConsumer(
        CONFIG.final_topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"{CONFIG.prefix}_asker_{uuid.uuid4().hex[:8]}",
        auto_offset_reset="latest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await consumer.start()
    await producer.start()
    try:
        message = {"correlation_id": correlation_id, "question": question}
        metadata = await producer.send_and_wait(
            CONFIG.inbox_topic, to_bytes(message), key=correlation_id.encode()
        )
        log(
            "YOU",
            f"sent to {metadata.topic} partition={metadata.partition} offset={metadata.offset} "
            f"correlation_id={correlation_id}",
        )
        log("YOU", f"question message={json.dumps(message, separators=(',', ':'))}")

        async def wait_for_answer() -> dict:
            async for msg in consumer:
                final = json.loads(msg.value.decode())
                if final.get("correlation_id") == correlation_id:
                    log(
                        "YOU",
                        f"received from {msg.topic} partition={msg.partition} offset={msg.offset} "
                        f"correlation_id={correlation_id}",
                    )
                    return final
            raise RuntimeError("consumer stopped")

        try:
            final = await asyncio.wait_for(wait_for_answer(), timeout=TIMEOUT_SECONDS)
        except TimeoutError:
            log("YOU", f"no answer within {TIMEOUT_SECONDS}s for correlation_id={correlation_id}")
            return 1
        print(json.dumps(final, indent=2))
        return 0
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(" ".join(sys.argv[1:]) or DEFAULT_QUESTION)))
