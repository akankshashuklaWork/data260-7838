"""Generate deterministic HW7 report evidence from local fixtures and checks."""

from __future__ import annotations

import csv
import json
import os
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .agent import (
    ScriptedModel,
    action,
    final,
    run_agent,
    run_fixed_benchmark,
)
from .bike_agent import (
    PRICING_URL,
    BikeTools,
    ReActBikeAgent,
    attack_results,
    hostile_pricing_fixture,
    sha256_file,
)
from .config import CONFIG
from .file_tools import run_safety_demo
from .reflexion import run_reflexion_comparison

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/hw07"
RAW = REPORT / "raw"
PRICING = REPORT / "pricing"
FIXTURES = REPORT / "fixtures"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_pricing_snapshot() -> Path:
    """Store the small official-price excerpt used by the local policy retriever."""
    PRICING.mkdir(parents=True, exist_ok=True)
    target = PRICING / "citibike_pricing_snapshot.txt"
    target.write_text(
        "Source: https://citibikenyc.com/plans-and-pricing\n"
        "Access date: 2026-10-22\n"
        "Citi Bike: $239/year. Bike unlocks: free. Ride times: 45 min. Ebike prices: $0.27/min.\n"
        "Single Ride: $4.99 for 30 mins. Bike unlocks: $4.99. Ebike prices: $0.41/min. Ride times: 30 min.\n"
        "Single rides include one classic bike ride up to 30 minutes. $0.41/min for every minute thereafter.\n"
        "Annual members get unlimited 45-minute rides on classic bikes; longer classic rides have extra-time charges.\n",
        encoding="utf-8",
    )
    metadata = {
        "url": PRICING_URL,
        "access_date": "2026-10-22",
        "sha256": sha256_file(target),
        "notes": "Captured pricing facts used for fixed local scenarios; re-check the official page before a real purchase.",
    }
    _write_json(PRICING / "citibike_pricing_snapshot.json", metadata)
    return target


def _write_trips(path: Path, count: int, start: date, span_days: int, long_rides: bool) -> None:
    rng = random.Random(CONFIG.seed + count + span_days)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["ride_id", "started_at", "duration_minutes", "bike_type"]
        )
        writer.writeheader()
        for index in range(count):
            offset = round(index * (span_days - 1) / max(count - 1, 1))
            duration = rng.uniform(28, 65) if long_rides else rng.uniform(7, 22)
            writer.writerow(
                {
                    "ride_id": f"s7838-{count}-{index + 1:04d}",
                    "started_at": (start + timedelta(days=offset)).isoformat() + "T08:30:00",
                    "duration_minutes": f"{duration:.2f}",
                    "bike_type": "classic",
                }
            )


def run_part1() -> dict[str, Any]:
    """Exercise JWT roles with a fresh SQLite database, never the real MySQL DB."""
    with tempfile.TemporaryDirectory(prefix="hw7-auth-") as directory:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(directory) / 'auth.sqlite'}"
        from fastapi.testclient import TestClient
        from hw4_backend import crud
        from hw4_backend.database import Base, SessionLocal, engine
        from hw4_backend.main import app
        from hw4_backend.security import create_access_token

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            crud.create_user(db, "reader_7838", "reader-pass-7838", "reader")
            crud.create_user(db, "writer_7838", "writer-pass-7838", "writer")
            crud.create_user(db, "moderator_7838", "moderator-pass-7838", "moderator")
        client = TestClient(app)

        def login(username: str, password: str) -> str:
            response = client.post("/auth/login", json={"username": username, "password": password})
            assert response.status_code == 200, response.text
            return response.json()["access_token"]

        reader, writer, moderator = (
            login("reader_7838", "reader-pass-7838"),
            login("writer_7838", "writer-pass-7838"),
            login("moderator_7838", "moderator-pass-7838"),
        )

        def header(token: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {token}"}

        owner = client.post(
            "/owners",
            json={"first_name": "Case", "last_name": "Owner", "email": "case.owner@example.com"},
            headers=header(writer),
        )
        assert owner.status_code == 201, owner.text
        payload = {
            "listing_code": "HW7-7838",
            "property_title": "JWT verification listing",
            "property_location": "San Jose",
            "submitter_email": "submitter@example.com",
            "property_description": "A deterministic listing used only for the HW7 isolated API verification.",
            "property_category": "Apartment",
            "terms_accepted": True,
            "available_units": 1,
            "owner_id": owner.json()["id"],
        }
        created = client.post("/listings", json=payload, headers=header(writer))
        assert created.status_code == 201, created.text
        moderator_payload = {**payload, "listing_code": "HW7-7838-MOD"}
        moderator_created = client.post(
            "/listings", json=moderator_payload, headers=header(moderator)
        )
        assert moderator_created.status_code == 201, moderator_created.text
        extra_owner = client.post(
            "/owners",
            json={
                "first_name": "Unused",
                "last_name": "Owner",
                "email": "unused.owner@example.com",
            },
            headers=header(writer),
        )
        expired = create_access_token(1, "reader_7838", "reader", ttl_seconds=-1)
        # Change a significant header byte.  Altering only the final Base64URL
        # character can preserve decoded padding bits and accidentally verify.
        invalid = "x" + reader[1:]
        me_response = client.get("/auth/me", headers=header(reader))
        outcomes = {
            "login_success": 200,
            "login_token_preview": writer[:48] + "...",
            "login_invalid": client.post(
                "/auth/login", json={"username": "reader_7838", "password": "wrong-password"}
            ).status_code,
            "me_missing_token": client.get("/auth/me").status_code,
            "me_invalid_token": client.get("/auth/me", headers=header(invalid)).status_code,
            "me_expired_token": client.get("/auth/me", headers=header(expired)).status_code,
            "me_success": me_response.status_code,
            "me_identity": me_response.json(),
            "create_reader_forbidden": client.post(
                "/listings", json=payload, headers=header(reader)
            ).status_code,
            "create_writer": created.status_code,
            "create_moderator": moderator_created.status_code,
            "list_reader": client.get("/listings", headers=header(reader)).status_code,
            "delete_writer_forbidden": client.delete(
                f"/listings/{created.json()['id']}", headers=header(writer)
            ).status_code,
            "delete_moderator": client.delete(
                f"/listings/{created.json()['id']}", headers=header(moderator)
            ).status_code,
            "delete_unused_owner_moderator": client.delete(
                f"/owners/{extra_owner.json()['id']}", headers=header(moderator)
            ).status_code,
        }
    expected = {
        "login_success": 200,
        "login_token_preview": writer[:48] + "...",
        "login_invalid": 401,
        "me_missing_token": 401,
        "me_invalid_token": 401,
        "me_expired_token": 401,
        "me_success": 200,
        "me_identity": {"id": 1, "username": "reader_7838", "role": "reader"},
        "create_reader_forbidden": 403,
        "create_writer": 201,
        "create_moderator": 201,
        "list_reader": 200,
        "delete_writer_forbidden": 403,
        "delete_moderator": 200,
        "delete_unused_owner_moderator": 204,
    }
    return {"outcomes": outcomes, "expected": expected, "passed": outcomes == expected}


def run_part2() -> dict[str, Any]:
    attempts, summary = run_fixed_benchmark()
    impossible = run_agent(
        "Give details for listing 999.",
        ScriptedModel([action("detail", {"listing_id": 999}), final("Listing 999 was not found.")]),
        required_tool_calls=1,
    )
    return {"attempts": attempts, "summary": summary, "impossible_id": impossible}


def run_part4_and_5(snapshot: Path) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    membership_csv = RAW / "bike_membership_wins_trips.csv"
    pay_per_ride_csv = RAW / "bike_pay_per_ride_wins_trips.csv"
    _write_trips(membership_csv, 620, date(2025, 10, 23), 365, long_rides=True)
    _write_trips(pay_per_ride_csv, 520, date(2013, 1, 1), 4745, long_rides=False)
    scenarios: dict[str, Any] = {}
    for name, csv_path in (
        ("membership_wins", membership_csv),
        ("pay_per_ride_wins", pay_per_ride_csv),
    ):
        agent = ReActBikeAgent(BikeTools(csv_path, snapshot))
        result = agent.run()
        scenarios[name] = result
        _write_json(RAW / f"bike_{name}_summary.json", result)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    hostile = FIXTURES / "hostile_pricing_fixture.txt"
    hostile.write_text(hostile_pricing_fixture(), encoding="utf-8")
    attacks = attack_results(ReActBikeAgent(BikeTools(pay_per_ride_csv, snapshot)))
    _write_json(
        RAW / "part5_attack_before_after.json", {"fixture": str(hostile), "attacks": attacks}
    )
    return {"scenarios": scenarios, "attacks": attacks, "hostile_fixture": str(hostile)}


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    snapshot = write_pricing_snapshot()
    part1 = run_part1()
    part2 = run_part2()
    part3 = run_reflexion_comparison()
    part45 = run_part4_and_5(snapshot)
    with tempfile.TemporaryDirectory(prefix="hw7-sandbox-") as directory:
        part6 = run_safety_demo(Path(directory))
    _write_json(RAW / "part1_jwt_results.json", part1)
    _write_json(RAW / "part2_attempts.json", part2["attempts"])
    _write_json(RAW / "part2_summary.json", part2["summary"])
    _write_json(RAW / "part2_impossible_id.json", part2["impossible_id"])
    _write_json(RAW / "part3_reflexion.json", part3)
    _write_json(RAW / "part6_safety_results.json", part6)
    summary = {
        "config": CONFIG.as_dict(),
        "part1": part1,
        "part2": part2["summary"],
        "part3": {
            "tasks": len(part3["rows"]),
            "stored_reflections": len(part3["stored_reflections"]),
        },
        "part4_decisions": {key: value["decision"] for key, value in part45["scenarios"].items()},
        "part5_attacks": len(part45["attacks"]),
        "part6": {
            "allowed": sum(row["passed"] for row in part6["allowed_tests"]),
            "blocked": sum(row["passed"] for row in part6["blocked_tests"]),
        },
    }
    _write_json(RAW / "run_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if part1["passed"] and part2["summary"]["successful_after_repair"] == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
