"""Objective smoke test that starts the HW6 API and writes reports/hw06/verification.json."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from .config import REPOSITORY_ROOT, get_settings
from .db import episodes_collection, messages_collection, summaries_collection
from .file_memory import compact_memory, load_file_memory


REPORT_PATH = REPOSITORY_ROOT / "reports" / "hw06" / "verification.json"
RUN_LOG_PATH = REPOSITORY_ROOT / "reports" / "hw06" / "RUN_LOG.txt"


def _git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _start_server() -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "code")
    environment["HW6_USE_DETERMINISTIC_MODEL"] = "true"
    environment["HW6_TELEMETRY_PATH"] = str(Path(tempfile.gettempdir()) / "hw6_verify_telemetry.jsonl")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "hw6_memory.main:app", "--host", "127.0.0.1", "--port", "8638"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_health(client: httpx.Client, process: subprocess.Popen[str]) -> dict[str, Any]:
    for _ in range(50):
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"API exited before health check: {output}")
        try:
            response = client.get("/")
            if response.status_code == 200:
                return response.json()
        except httpx.ConnectError:
            pass
        time.sleep(0.2)
    raise RuntimeError("API did not become ready within 10 seconds")


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "passed": passed, "detail": detail})
    if not passed:
        raise AssertionError(f"{name}: {detail}")


def run_verification() -> dict[str, Any]:
    settings = get_settings()
    checks: list[dict[str, Any]] = []
    for collection in (messages_collection(), summaries_collection(), episodes_collection()):
        collection.delete_many({"user_id": "verify-7838"})
    process = _start_server()
    listing_id = ""
    try:
        with httpx.Client(base_url="http://127.0.0.1:8638", timeout=30) as client:
            health = _wait_for_health(client, process)
            _check(checks, "FastAPI health endpoint", health["status"] == "ok", json.dumps(health))
            _check(checks, "configured MongoDB database", health["database"] == "s7838_doc", health["database"])

            create = client.post(
                "/api/rental-listings",
                json={
                    "property_title": "Verify Willow Glen two-bedroom",
                    "property_description": "Temporary smoke-test record with garage parking.",
                    "listing_status": "available",
                    "property_category": "Apartment",
                    "available_on": "2026-11-01T09:00:00Z",
                },
            )
            _check(checks, "POST rental listing", create.status_code == 201, create.text)
            listing_id = create.json()["id"]
            _check(checks, "GET one rental listing", client.get(f"/api/rental-listings/{listing_id}").status_code == 200, listing_id)
            update = client.put(f"/api/rental-listings/{listing_id}", json={"listing_status": "pending"})
            _check(checks, "PUT rental listing", update.status_code == 200 and update.json()["listing_status"] == "pending", update.text)
            _check(checks, "GET all rental listings", client.get("/api/rental-listings").status_code == 200, "response received")
            _check(checks, "Pydantic missing-field validation", client.post("/api/rental-listings", json={}).status_code == 422, "422 expected")
            _check(checks, "invalid ObjectId handling", client.get("/api/rental-listings/not-an-id").status_code == 400, "400 expected")

            chat = client.post(
                "/api/chat",
                json={"user_id": "verify-7838", "session_id": "verify-267838", "message": "My budget is $2,800 and I need two bedrooms."},
            )
            chat_body = chat.json() if chat.status_code == 200 else {}
            _check(checks, "POST /api/chat returns a reply", chat.status_code == 200 and bool(chat_body.get("reply")), chat.text)
            _check(checks, "chat returns memory evidence", "memory_used" in chat_body and "token_usage" in chat_body, json.dumps(chat_body))
            _check(checks, "GET /api/memory", client.get("/api/memory/verify-7838").status_code == 200, "response received")
            _check(checks, "GET /api/aggregate", client.get("/api/aggregate/verify-7838").status_code == 200, "response received")
            _check(checks, "DELETE rental listing", client.delete(f"/api/rental-listings/{listing_id}").status_code == 204, listing_id)

        with tempfile.TemporaryDirectory(prefix="hw6-memory-") as temporary_directory:
            temporary_memory = Path(temporary_directory) / "MEMORY.md"
            original = REPOSITORY_ROOT / "memory" / "MEMORY.original.md"
            temporary_memory.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
            result = compact_memory(temporary_memory)
            _check(checks, "55-line memory consolidation", result.before_count == 55 and result.after_count < 40, f"{result.before_count} -> {result.after_count}")
            _check(checks, "duplicate facts merged", result.duplicate_count >= 3, str(result.duplicate_count))
            _check(checks, "contradictions kept explicitly", result.contradiction_count >= 3 and "Resolved contradictions" in result.output, str(result.contradiction_count))

        source = inspect.getsource(load_file_memory)
        agent_text = (REPOSITORY_ROOT / "AGENT.md").read_text(encoding="utf-8")
        required_categories = ["Project description", "Technology stack", "Coding conventions", "Testing approach", "Prohibited actions"]
        _check(checks, "AGENT.md contains five durable instructions", all(item in agent_text for item in required_categories), "five categories checked")
        _check(checks, "load_file_memory follows AGENT.md", source.count("read_text") >= 2, "function loads both Markdown files")

        return {
            "homework": "hw06",
            "sid4": 7838,
            "commit_hash_at_run": _git_hash(),
            "model_configuration": "deterministic local smoke-test adapter; production default is qwen2:7b through src/model_client.py",
            "seed": 7838,
            "verify_seed": 267838,
            "checks": checks,
            "all_checks_passed": all(item["passed"] for item in checks),
        }
    finally:
        if listing_id:
            try:
                with httpx.Client(base_url="http://127.0.0.1:8638", timeout=5) as client:
                    client.delete(f"/api/rental-listings/{listing_id}")
            except Exception:
                pass
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_verification()
    except Exception as error:
        result = {
            "homework": "hw06",
            "sid4": 7838,
            "commit_hash_at_run": _git_hash(),
            "all_checks_passed": False,
            "error": str(error),
        }
    REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with RUN_LOG_PATH.open("a", encoding="utf-8") as run_log:
        run_log.write(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] make verify-hw06: "
            f"{'PASS' if result.get('all_checks_passed') else 'FAIL'}\n"
        )
    print(json.dumps(result, indent=2))
    if not result.get("all_checks_passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
