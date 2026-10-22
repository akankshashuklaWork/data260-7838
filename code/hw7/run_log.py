"""Run the repeatable HW7 checks and save timestamped, unedited console output."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "reports/hw07/RUN_LOG.txt"
SOURCE_FILES = [
    "code/hw7/agent.py",
    "code/hw7/reflexion.py",
    "code/hw7/bike_agent.py",
    "code/hw7/bike_ui.py",
    "code/hw7/file_tools.py",
    "code/hw7/run_artifacts.py",
    "code/hw7/run_live_model_benchmark.py",
    "code/hw7/verify_hw7.py",
    "code/hw4_backend/main.py",
    "code/hw4_backend/security.py",
    "code/hw4_backend/models.py",
    "code/hw4_backend/schemas.py",
    "code/hw4_backend/crud.py",
    "code/hw4_backend/database.py",
    "code/hw4_backend/migrate_hw7.py",
]


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    commands = [
        [sys.executable, "-m", "compileall", "-q", "code/hw7", "code/hw4_backend"],
        [sys.executable, "-m", "hw7.verify_hw7"],
        [sys.executable, "-m", "ruff", "check", *SOURCE_FILES],
        [sys.executable, "-m", "pre_commit", "run", "--files", *SOURCE_FILES],
    ]
    environment = {**os.environ, "PYTHONPATH": "code"}
    target_lines = [f"[{stamp()}] HW7 reproducible run log", ""]
    all_passed = True
    for command in commands:
        target_lines.append(f"[{stamp()}] $ {' '.join(command)}")
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        target_lines.append(result.stdout.rstrip())
        if result.stderr:
            target_lines.append(result.stderr.rstrip())
        target_lines.append(f"[{stamp()}] exit={result.returncode}")
        target_lines.append("")
        all_passed = all_passed and result.returncode == 0
    TARGET.write_text("\n".join(target_lines) + "\n", encoding="utf-8")
    print(TARGET.read_text(encoding="utf-8"), end="")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
