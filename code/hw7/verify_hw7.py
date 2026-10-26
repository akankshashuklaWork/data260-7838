"""Objective HW7 self-check; uses only temporary state and report artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from .bike_agent import TOOL_SCHEMAS
from .bike_ui import app as bike_ui
from .config import CONFIG
from .run_artifacts import main as generate_artifacts

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/hw07"
RAW = REPORT / "raw"


def check(name: str, passed: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "passed": passed, **({"detail": detail} if detail else {})}


def main() -> int:
    generated = generate_artifacts()
    part1 = json.loads((RAW / "part1_jwt_results.json").read_text(encoding="utf-8"))
    part2 = json.loads((RAW / "part2_summary.json").read_text(encoding="utf-8"))
    part3 = json.loads((RAW / "part3_reflexion.json").read_text(encoding="utf-8"))
    part4_a = json.loads((RAW / "bike_membership_wins_summary.json").read_text(encoding="utf-8"))
    part4_b = json.loads((RAW / "bike_pay_per_ride_wins_summary.json").read_text(encoding="utf-8"))
    part6 = json.loads((RAW / "part6_safety_results.json").read_text(encoding="utf-8"))
    trip_csv = (RAW / "bike_membership_wins_trips.csv").read_bytes()
    ui_response = TestClient(bike_ui).post(
        "/run",
        files={"trip_csv": ("trips.csv", trip_csv, "text/csv")},
        data={"pricing_url": "https://citibikenyc.com/plans-and-pricing"},
    )
    checks = [
        check("JWT authentication and reader/writer/moderator status codes", part1["passed"]),
        check(
            "20 fixed Part 2 attempts repair to success",
            part2["attempts"] == 20 and part2["successful_after_repair"] == 20,
        ),
        check(
            "Reflexion runs have stored evidence and bounded retries",
            len(part3["stored_reflections"]) >= 1 and part3["max_retries"] == 2,
        ),
        check(
            "Bike scenarios make opposite required decisions",
            part4_a["decision"] == "Buy Monthly Membership"
            and part4_b["decision"] == "Pay Per Ride/Minute",
        ),
        check(
            "Each bike CSV has at least 500 rows",
            part4_a["cost_breakdown"]["trip_count"] >= 500
            and part4_b["cost_breakdown"]["trip_count"] >= 500,
        ),
        check(
            "File-tool safety contract has five allows and five blocks",
            all(row["passed"] for row in part6["allowed_tests"] + part6["blocked_tests"]),
        ),
        check(
            "Pricing snapshot has URL/date/hash",
            (REPORT / "pricing/citibike_pricing_snapshot.json").exists(),
        ),
        check(
            "MRKL tool schemas define the required three tools",
            set(TOOL_SCHEMAS) == {"csv_sql", "policy_retriever", "calculator"},
        ),
        check(
            "Bike UI renders timeline, citation timestamp, and metrics",
            ui_response.status_code == 200
            and "Timeline" in ui_response.text
            and "captured:" in ui_response.text
            and "Steps:" in ui_response.text,
        ),
    ]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {
        "homework": 7,
        "SID4": CONFIG.sid4,
        "commit_hash": commit,
        "model": CONFIG.model,
        "hardware": CONFIG.hardware,
        "seed": CONFIG.seed,
        "verify_seed": CONFIG.verify_seed,
        "checks": checks,
        "passed": generated == 0 and all(item["passed"] for item in checks),
    }
    (REPORT / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
