"""Objective HW8 smoke test: start the system, check the basics, write verification.json.

It only talks to the running services and writes temporary files plus
reports/hw08/verification.json; it never edits application code.

    PYTHONPATH=code python -m hw8.verify_hw8
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from aiokafka.admin import AIOKafkaAdminClient

from .config import CONFIG, KAFKA_BOOTSTRAP, TOPIC_PLAN
from .failure_tests import run_all
from .harness import HW8_DIR, ROOT
from .run_pipeline import run_pipeline

REPORT = ROOT / "reports/hw08"
API = f"http://127.0.0.1:{CONFIG.port}/listings"
COMPOSE = ["docker", "compose", "-f", str(HW8_DIR / "docker-compose.yml")]

LISTING = {
    "propertyTitle": "Verification listing",
    "propertyLocation": "Sunnyvale, CA",
    "submitterEmail": "verify@example.com",
    "propertyDescription": "Smoke-test listing with a description longer than 25 characters.",
    "propertyCategory": "Condo",
    "termsAccepted": "true",
}


def check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **({"detail": detail} if detail else {})}


def ensure_stack() -> None:
    """Start the Docker services if needed and wait until the API and worker are ready."""
    subprocess.run([*COMPOSE, "up", "-d", "--build"], check=True, capture_output=True, text=True)
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            ready = httpx.get(f"http://127.0.0.1:{CONFIG.port}/", timeout=2).status_code == 200
            logs = subprocess.run(
                ["docker", "logs", "s7838_worker"], capture_output=True, text=True
            )
            if ready and "Consumer is ready and listening..." in logs.stdout + logs.stderr:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("Docker services did not become ready")


def call(operation: str, data: dict, correlation_id: str) -> dict[str, Any]:
    body = {"operation": operation, "data": data, "correlation_id": correlation_id}
    return httpx.post(API, json=body, timeout=30).json()


async def topic_partitions() -> dict[str, int]:
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        described = await admin.describe_topics([topic for topic, _ in TOPIC_PLAN])
    finally:
        await admin.close()
    return {item["topic"]: len(item["partitions"]) for item in described if not item["error_code"]}


def main() -> int:
    ensure_stack()
    checks: list[dict[str, Any]] = []

    partitions = asyncio.run(topic_partitions())
    expected = dict(TOPIC_PLAN)
    checks.append(
        check(
            "All seven PREFIX topics exist (tasks has 2 partitions)",
            partitions == expected,
            json.dumps(partitions),
        )
    )

    # Part 1: CREATE_LISTING then GET_LISTING must round-trip through Kafka.
    correlation_id = str(uuid.uuid4())
    created = call("CREATE_LISTING", LISTING, correlation_id)
    listing_id = created.get("listing_id")
    fetched = call("GET_LISTING", {"listing_id": listing_id}, correlation_id)
    stored = fetched.get("listing") or {}
    checks.append(
        check(
            "CREATE_LISTING returns success, a UUID listing_id, and the same correlation_id",
            created.get("success") is True
            and created.get("message") == "Listing created"
            and created.get("correlation_id") == correlation_id
            and bool(listing_id)
            and str(uuid.UUID(listing_id)) == listing_id,
        )
    )
    checks.append(
        check(
            "GET_LISTING returns the created listing with the same correlation_id",
            fetched.get("success") is True
            and fetched.get("correlation_id") == correlation_id
            and all(stored.get(k) == v for k, v in LISTING.items() if k != "termsAccepted")
            and stored.get("listing_id") == listing_id,
        )
    )
    missing = call("GET_LISTING", {"listing_id": "does-not-exist"}, "verify-missing")
    checks.append(
        check(
            "Unknown listing_id gives success=false, an error, and the same correlation_id",
            missing.get("success") is False
            and bool(missing.get("error"))
            and missing.get("correlation_id") == "verify-missing",
        )
    )
    unknown = call("DELETE_LISTING", {}, "verify-unknown")
    checks.append(
        check(
            "Unknown operation is rejected with a clean error and the same correlation_id",
            unknown.get("success") is False
            and unknown.get("error") == "Unknown operation"
            and unknown.get("correlation_id") == "verify-unknown",
        )
    )
    bad_inputs = [
        {**LISTING, "propertyTitle": ""},
        {**LISTING, "propertyDescription": "too short"},
        {**LISTING, "propertyCategory": "Castle"},
        {**LISTING, "submitterEmail": "not-an-email"},
        {**LISTING, "termsAccepted": "false"},
        {k: v for k, v in LISTING.items() if k != "propertyLocation"},
    ]
    rejected = [call("CREATE_LISTING", bad, f"verify-bad-{i}") for i, bad in enumerate(bad_inputs)]
    checks.append(
        check(
            "Missing, empty, and invalid fields are rejected",
            all(r.get("success") is False and r.get("error") for r in rejected),
        )
    )
    worker_logs = subprocess.run(["docker", "logs", "s7838_worker"], capture_output=True, text=True)
    checks.append(
        check(
            "Worker container logged 'Consumer is ready and listening...'",
            "Consumer is ready and listening..." in worker_logs.stdout + worker_logs.stderr,
        )
    )

    # Part 2: one question travels inbox -> tasks -> drafts -> final (offline stand-in model).
    with tempfile.TemporaryDirectory() as tmp:
        journey = run_pipeline(stub=True, workdir=Path(tmp), unique_groups=True)
    final = journey["final"] or {}
    stages = ["PLANNER", "WRITER", "REVIEWER"]
    checks.append(
        check(
            "Pipeline returns an approved answer on s7838_final with the same correlation_id",
            final.get("status") == "approved"
            and bool(final.get("answer"))
            and final.get("correlation_id") == journey["correlation_id"]
            and all(
                any(f"[{s}]" in line and "received" in line for line in journey["journey"])
                for s in stages
            ),
        )
    )

    # Part 3: the fixed behavior (after-fix runs only).
    results = run_all(raw_dir=None, include_before=False)
    dup, death = results["duplicate:after"], results["death:after"]
    poison, order = results["poison:after"], results["ordering:after"]
    checks.append(
        check(
            "Replayed message causes no extra side effect (idempotency)",
            dup["processed"] == 1
            and dup["duplicates_skipped"] == 1
            and dup["drafts_published"] == 1,
        )
    )
    checks.append(
        check(
            "Killed Writer's message is redelivered and offset is committed only after processing",
            death["received_by_restarted_writer"]
            and death["completed_after_restart"]
            and death["committed_offset_after_kill"] == death["message_offset"]
            and death["committed_offset_after_restart"] == death["message_offset"] + 1
            and death["commit_after_processing"],
        )
    )
    checks.append(
        check(
            "Poison message is retried up to the limit, dead-lettered, and does not block the next",
            poison["poison_attempts"] == 3
            and poison["moved_to_dead_letter"] == 1
            and poison["good_message_processed"],
        )
    )
    checks.append(
        check(
            "Keyed 20-message VERIFY_SEED run keeps each entity in one partition, in order",
            order["messages"] == 20 and order["all_in_order"] and order["all_in_one_partition"],
        )
    )

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "code/hw8"], cwd=ROOT, text=True
        ).strip()
    )
    result = {
        "homework": 8,
        "SID4": CONFIG.sid4,
        "commit_hash": commit,
        "uncommitted_changes_in_code_hw8": dirty,
        "model": f"{CONFIG.model} (live Part 2 run); offline stub model inside this self-check",
        "hardware": CONFIG.hardware,
        "seed": CONFIG.seed,
        "verify_seed": CONFIG.verify_seed,
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
