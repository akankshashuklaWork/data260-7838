"""Objective HW5 smoke verification; writes reports/hw05/verification.json."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(name: str, passed: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "passed": passed, **({"detail": detail} if detail else {})}


def api_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'verify.sqlite'}"
        sys.path.insert(0, str(ROOT / "code"))
        from fastapi.testclient import TestClient
        from hw4_backend.main import app

        client = TestClient(app)
        assert client.post("/auth/register", json={"name": "Verify", "email": "verify@example.com", "password": "password123"}).status_code == 200
        assert client.post("/auth/login", json={"email": "verify@example.com", "password": "password123"}).status_code == 200
        owner = client.post("/owners", json={"first_name": "Verify", "last_name": "Owner", "email": "owner@example.com"})
        assert owner.status_code == 201
        listing = client.post("/listings", json={"listing_code": "VERIFY-1", "property_title": "Verification listing", "property_location": "San Jose", "submitter_email": "submitter@example.com", "property_description": "A long enough verification description.", "property_category": "Apartment", "available_units": 1, "owner_id": owner.json()["id"], "terms_accepted": True})
        assert listing.status_code == 200
        assert client.get(f"/owners/{owner.json()['id']}/listings").status_code == 200


def main() -> int:
    sys.path.insert(0, str(ROOT / "code"))
    checks = []
    test_process = subprocess.run([sys.executable, str(ROOT / "code/run_hw5_tests.py")], cwd=ROOT, capture_output=True, text=True)
    checks.append(check("offline Part 4–5 tests", test_process.returncode == 0, test_process.stdout[-500:]))
    fault_process = subprocess.run([sys.executable, str(ROOT / "code/run_hw5_fault_injection.py")], cwd=ROOT, capture_output=True, text=True)
    checks.append(check("150 fault-injection records", fault_process.returncode == 0 and len(json.loads((ROOT / "reports/hw05/raw/fault_injection_records.json").read_text())) == 150))
    try:
        api_smoke()
        checks.append(check("SQLite API relationship smoke", True))
    except Exception as exc:
        checks.append(check("SQLite API relationship smoke", False, str(exc)))
    checks.append(check("MCP server source files", (ROOT / "code/hw5_mcp/meals_server.py").exists() and (ROOT / "code/hw5_mcp/domain_server.py").exists()))
    checks.append(check("Redux client source files", (ROOT / "code/hw4_frontend/src/store/store.js").exists() and (ROOT / "code/hw4_frontend/src/features/listings/listingsSlice.js").exists()))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {"homework": 5, "SID4": 7838, "PORT_BASE": 8638, "PREFIX": "s7838", "DOMAIN_ID": 6, "commit_hash": commit, "model": os.getenv("OLLAMA_MODEL", "qwen2:7b"), "SEED": 7838, "VERIFY_SEED": 267838, "checks": checks, "passed": all(item["passed"] for item in checks)}
    target = ROOT / "reports/hw05/verification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

