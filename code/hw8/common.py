"""Small helpers shared by the HW8 worker, API, and agents."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def log(component: str, message: str) -> None:
    """One timestamped line per event so logs from many processes can be merged by time."""
    print(f"{utc_iso()} [{component}] {message}", flush=True)


def to_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


async def start_with_retry(client: Any, name: str, attempts: int = 30) -> None:
    """Kafka may still be starting when a container boots, so retry the connection."""
    for attempt in range(1, attempts + 1):
        try:
            await client.start()
            return
        except Exception as exc:  # noqa: BLE001 - any connection failure means "try again"
            log(name, f"waiting for Kafka (attempt {attempt}): {exc!r}")
            await asyncio.sleep(2)
    raise RuntimeError(f"{name} could not connect to Kafka")
