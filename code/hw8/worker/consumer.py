"""Part 1 worker: consumes requests from Kafka, applies the domain logic, and replies.

The worker is the only place that touches listing data. It reads
`s7838_entity_requests`, validates CREATE_LISTING / GET_LISTING, stores listings in a
plain dict, and answers on the topic named by `reply_to`, always echoing the
request's correlation_id unchanged.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from common import log, start_with_retry, to_bytes
from config import CONFIG, KAFKA_BOOTSTRAP

WORKER_GROUP = f"{CONFIG.prefix}_entity_worker_group"
CATEGORIES = {"Apartment", "House", "Condo", "Townhouse"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TRUE_VALUES = {"true", "on", "yes", "1"}

# Entities live in a plain dictionary for this Kafka exercise: listing_id -> listing.
listings: dict[str, dict[str, Any]] = {}


def validate_listing(data: Any) -> str | None:
    """Return an error message for missing, empty, or invalid fields, else None."""
    if not isinstance(data, dict):
        return "data must be an object"
    for field in ("propertyTitle", "propertyLocation", "submitterEmail", "propertyDescription"):
        value = data.get(field)
        if value is None:
            return f"{field} is required"
        if not isinstance(value, str) or not value.strip():
            return f"{field} must be a non-empty string"
    if not EMAIL_PATTERN.match(data["submitterEmail"].strip()):
        return "submitterEmail must be a valid email address"
    if len(data["propertyDescription"].strip()) <= 25:
        return "propertyDescription must contain more than 25 characters"
    if "propertyCategory" not in data:
        return "propertyCategory is required"
    if data["propertyCategory"] not in CATEGORIES:
        return f"propertyCategory must be one of {sorted(CATEGORIES)}"
    if "termsAccepted" not in data:
        return "termsAccepted is required"
    if str(data["termsAccepted"]).strip().lower() not in TRUE_VALUES:
        return "termsAccepted must be accepted (true)"
    return None


def process_request(request: dict[str, Any]) -> dict[str, Any]:
    """Run one operation and return the response body (without correlation_id)."""
    operation = request.get("operation")
    data = request.get("data")

    if operation == "CREATE_LISTING":
        error = validate_listing(data)
        if error:
            return {"success": False, "error": error}
        listing_id = str(uuid.uuid4())  # the worker, not the client, generates the id
        listings[listing_id] = {
            "listing_id": listing_id,
            "propertyTitle": data["propertyTitle"].strip(),
            "propertyLocation": data["propertyLocation"].strip(),
            "submitterEmail": data["submitterEmail"].strip(),
            "propertyDescription": data["propertyDescription"].strip(),
            "propertyCategory": data["propertyCategory"],
            "termsAccepted": "true",
            "submissionDate": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        return {"success": True, "listing_id": listing_id, "message": "Listing created"}

    if operation == "GET_LISTING":
        listing_id = data.get("listing_id") if isinstance(data, dict) else None
        if not isinstance(listing_id, str) or not listing_id:
            return {"success": False, "error": "listing_id is required"}
        if listing_id not in listings:
            return {"success": False, "error": "Listing not found"}
        return {"success": True, "listing": listings[listing_id]}

    return {"success": False, "error": "Unknown operation"}


async def main() -> None:
    consumer = AIOKafkaConsumer(
        CONFIG.request_topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=WORKER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # commit only after the reply was sent
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await start_with_retry(consumer, "WORKER")
    await start_with_retry(producer, "WORKER")
    log("WORKER", f"Consumer is ready and listening... topic={CONFIG.request_topic}")

    try:
        async for msg in consumer:
            try:
                request = json.loads(msg.value.decode())
                if not isinstance(request, dict):
                    raise ValueError("message must be a JSON object")
            except ValueError as exc:
                log("WORKER", f"skipped unreadable message offset={msg.offset}: {exc}")
                await consumer.commit({TopicPartition(msg.topic, msg.partition): msg.offset + 1})
                continue

            correlation_id = request.get("correlation_id")
            reply_to = request.get("reply_to") or CONFIG.response_topic
            operation = request.get("operation")
            log(
                "WORKER",
                f"received topic={msg.topic} partition={msg.partition} offset={msg.offset} "
                f"correlation_id={correlation_id} operation={operation} reply_to={reply_to}",
            )
            log("WORKER", f"request message={json.dumps(request, separators=(',', ':'))}")
            log("WORKER", f"processing correlation_id={correlation_id} operation={operation}")

            try:
                body = process_request(request)
            except Exception as exc:  # noqa: BLE001 - never leave the client waiting
                body = {"success": False, "error": f"Internal error: {type(exc).__name__}"}
            response = {"correlation_id": correlation_id, **body}

            log(
                "WORKER",
                f"sending response topic={reply_to} correlation_id={correlation_id} "
                f"success={response['success']}",
            )
            log("WORKER", f"response message={json.dumps(response, separators=(',', ':'))}")
            await producer.send_and_wait(reply_to, to_bytes(response))
            await consumer.commit({TopicPartition(msg.topic, msg.partition): msg.offset + 1})
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
