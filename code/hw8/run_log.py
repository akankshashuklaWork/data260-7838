"""Run the full HW8 sequence once and save timestamped, unedited console output.

Starts from a clean Docker stack, so the container logs and every result in the report
come from this one run. Each step's output is also saved under reports/hw08/raw/console/
for the screenshot renderer.

    PYTHONPATH=code python -m hw8.run_log
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import httpx

from .config import CONFIG
from .harness import HW8_DIR, ROOT

TARGET = ROOT / "reports/hw08/RUN_LOG.txt"
CONSOLE = ROOT / "reports/hw08/raw/console"
COMPOSE = ["docker", "compose", "-f", "code/hw8/docker-compose.yml"]
KAFKA_TOPICS = "/opt/kafka/bin/kafka-topics.sh"
PREFIX_TOPICS = [
    CONFIG.request_topic,
    CONFIG.response_topic,
    CONFIG.inbox_topic,
    CONFIG.tasks_topic,
    CONFIG.drafts_topic,
    CONFIG.final_topic,
    CONFIG.dead_letter_topic,
]
PY = sys.executable
LINT_FILES = sorted(str(p.relative_to(ROOT)) for p in HW8_DIR.rglob("*.py"))

# (file name, command, working directory relative to the repo root)
STEPS: list[tuple[str, list[str], str]] = [
    ("01_compose_down", [*COMPOSE, "down", "-v"], "."),
    ("02_compose_up", [*COMPOSE, "up", "-d", "--build"], "."),
    (
        "03_docker_ps",
        [
            "docker",
            "ps",
            "--filter",
            "name=s7838_",
            "--format",
            "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}",
        ],
        ".",
    ),
    (
        "04_kafka_topics",
        [
            "docker",
            "exec",
            "s7838_kafka",
            KAFKA_TOPICS,
            "--describe",
            "--bootstrap-server",
            "localhost:9092",
        ],
        ".",
    ),
    ("05_homework_demo", [PY, "homework_demo.py"], "code/hw8"),
    ("06_worker_log", ["docker", "logs", "s7838_worker"], "."),
    ("07_api_log", ["docker", "logs", "s7838_api"], "."),
    ("08_part2_pipeline_live", [PY, "-m", "hw8.run_pipeline"], "."),
    ("09_part3_failure_tests", [PY, "-m", "hw8.failure_tests"], "."),
    ("10_verify", [PY, "-m", "hw8.verify_hw8"], "."),
    ("11_ruff_check", [PY, "-m", "ruff", "check", *LINT_FILES], "."),
    ("12_ruff_format_check", [PY, "-m", "ruff", "format", "--check", *LINT_FILES], "."),
]


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def wait_until_ready() -> str:
    """Wait for the API container to answer and the worker to log that it is listening."""
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            api_up = httpx.get(f"http://127.0.0.1:{CONFIG.port}/", timeout=2).status_code == 200
            logs = subprocess.run(
                ["docker", "logs", "s7838_worker"], capture_output=True, text=True
            )
            if api_up and "Consumer is ready and listening..." in logs.stdout + logs.stderr:
                return "API and worker are ready"
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return "TIMED OUT waiting for API and worker"


def main() -> int:
    CONSOLE.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "code"), "PYTHONUNBUFFERED": "1"}
    lines = [
        f"[{stamp()}] HW8 reproducible run log (SID4 {CONFIG.sid4}, prefix {CONFIG.prefix})",
        "",
    ]
    all_passed = True
    for name, command, cwd in STEPS:
        lines.append(f"[{stamp()}] $ {' '.join(command)}   (cwd={cwd})")
        result = subprocess.run(
            command, cwd=ROOT / cwd, env=env, text=True, capture_output=True, check=False
        )
        output = (result.stdout + result.stderr).rstrip()
        (CONSOLE / f"{name}.txt").write_text(output + "\n", encoding="utf-8")
        lines.append(output)
        lines.append(f"[{stamp()}] exit={result.returncode}")
        lines.append("")
        all_passed = all_passed and result.returncode == 0
        if name == "02_compose_up":
            lines.append(f"[{stamp()}] {wait_until_ready()}")
            lines.append("")
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {TARGET} (all steps passed: {all_passed})")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
