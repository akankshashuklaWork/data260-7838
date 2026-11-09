"""Run the whole HW9 sequence once and save timestamped, unedited console output.

Starts the three HW8 agents and the ingress API as separate processes, runs every part in order, and
saves each step's output under reports/hw09/raw/console/ (used for the report screenshots).

    PYTHONPATH=code python -m hw9.run_log
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import httpx
from hw8.harness import AgentProcess, wait_until

from .config import CONFIG, DATA_DIR, REPORT_DIR, ROOT

TARGET = REPORT_DIR / "RUN_LOG.txt"
CONSOLE = REPORT_DIR / "raw/console"
PY = sys.executable
HW9_FILES = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "code/hw9").rglob("*.py"))
COMPOSE9 = ["docker", "compose", "-f", "code/hw9/docker-compose.yml"]

STEPS: list[tuple[str, list[str]]] = [
    ("01_redis_up", [*COMPOSE9, "up", "-d"]),
    ("02_docker_ps", ["docker", "ps", "--filter", "name=s7838_"]),
    ("03_part1_counter", [PY, "-m", "hw9.part1_counter_demo"]),
    ("04_part2_semantic_cache", [PY, "-m", "hw9.part2_cache_demo"]),
    ("05_part3_threshold_sweep", [PY, "-m", "hw9.part3_sweep", "--refresh"]),
    ("06_part3_stale_demo", [PY, "-m", "hw9.part3_stale_demo"]),
    ("07_part4_develop", [PY, "-m", "hw9.part4.run_part4", "develop"]),
    ("08_part4_demos", [PY, "-m", "hw9.part4.run_part4", "demos"]),
    ("09_part4_variants", [PY, "-m", "hw9.part4.run_part4", "variants"]),
    ("10_verify", [PY, "-m", "hw9.verify_hw9"]),
    ("11_ruff_check", [PY, "-m", "ruff", "check", *HW9_FILES]),
    ("12_ruff_format_check", [PY, "-m", "ruff", "format", "--check", *HW9_FILES]),
]


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def main() -> int:
    CONSOLE.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "code"), "PYTHONUNBUFFERED": "1"}
    lines = [
        f"[{stamp()}] HW9 reproducible run log (SID4 {CONFIG.sid4}, prefix {CONFIG.prefix})",
        "",
    ]
    agents = [
        AgentProcess(f"{name}.py", {}, DATA_DIR / f"{name}.log")
        for name in ("planner", "writer", "reviewer")
    ]
    ingress_log = open(DATA_DIR / "ingress.log", "w", encoding="utf-8")  # noqa: SIM115 - closed at the end
    ingress = subprocess.Popen(
        [
            PY,
            "-u",
            "-m",
            "uvicorn",
            "hw9.ingress:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(CONFIG.port),
        ],
        cwd=ROOT,
        env=env,
        stdout=ingress_log,
        stderr=subprocess.STDOUT,
    )
    all_ok = True
    try:
        for agent in agents:
            wait_until(
                lambda a=agent: any("Consumer is ready" in x for x in a.lines()),
                90,
                f"{agent.script} ready",
            )
        wait_until(
            lambda: "Semantic cache ingress started" in (DATA_DIR / "ingress.log").read_text(),
            120,
            "ingress ready",
        )
        lines.append(f"[{stamp()}] agents and ingress API are running (port {CONFIG.port})")
        # Warm-up: the first call loads the embedding model and the language model; it is not part of any result.
        with httpx.Client(timeout=300) as client:
            client.post(
                f"http://127.0.0.1:{CONFIG.port}/ask", json={"question": "What is a lease?"}
            )
            client.post(f"http://127.0.0.1:{CONFIG.port}/reset")
        lines += [f"[{stamp()}] warm-up request done (not recorded)", ""]

        for name, command in STEPS:
            lines.append(f"[{stamp()}] $ {' '.join(command)}")
            result = subprocess.run(
                command, cwd=ROOT, env=env, text=True, capture_output=True, check=False
            )
            output = "\n".join(
                line
                for line in (result.stdout + result.stderr).splitlines()
                if "Loading weights" not in line and "HF_TOKEN" not in line
            ).rstrip()
            (CONSOLE / f"{name}.txt").write_text(output + "\n", encoding="utf-8")
            lines += [output, f"[{stamp()}] exit={result.returncode}", ""]
            all_ok = all_ok and result.returncode == 0
            if (
                name == "04_part2_semantic_cache"
            ):  # the ingress server log holds the hit/miss lines with similarity
                time.sleep(1)
                (CONSOLE / "04b_ingress_log.txt").write_text(
                    "\n".join(
                        x
                        for x in (DATA_DIR / "ingress.log").read_text().splitlines()
                        if "[CACHE]" in x
                    )
                    + "\n"
                )
    finally:
        for agent in agents:
            agent.stop()
        ingress.terminate()
        ingress.wait(timeout=15)
        ingress_log.close()
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {TARGET} (all steps passed: {all_ok})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
