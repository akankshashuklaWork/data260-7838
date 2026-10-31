"""Part 2 run: start Planner, Writer, and Reviewer as separate processes and ask one question.

This does what four terminals do (`python planner.py`, `python writer.py`,
`python reviewer.py`, `python send_question.py`), but captures every process's output so
one message journey can be shown as time-ordered log lines.

    PYTHONPATH=code python -m hw8.run_pipeline            # live qwen2:7b model
    PYTHONPATH=code python -m hw8.run_pipeline --stub     # offline stand-in model
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .config import CONFIG
from .harness import HW8_DIR, ROOT, AgentProcess, wait_until

RAW = ROOT / "reports/hw08/raw"
AGENTS = ["planner", "writer", "reviewer"]


def run_pipeline(stub: bool, workdir: Path, unique_groups: bool, question: str | None = None):
    """Run one question through all three agents; return the journey and final message."""
    env_base = {"AGENT_LLM": "stub" if stub else "ollama"}
    run_id = uuid.uuid4().hex[:6]
    if unique_groups:  # start from "now" so earlier runs' messages are ignored
        env_base["AUTO_OFFSET_RESET"] = "latest"
    processes: list[AgentProcess] = []
    try:
        for agent in AGENTS:
            env = {**env_base, "PROCESSED_DB": str(workdir / f"{agent}_idempotency.db")}
            if unique_groups:
                env["GROUP_ID"] = f"{CONFIG.prefix}_{agent}_{run_id}"
            processes.append(AgentProcess(f"{agent}.py", env, workdir / f"{agent}.log"))
        for process in processes:
            wait_until(
                lambda p=process: any("Consumer is ready" in line for line in p.lines()),
                60,
                f"{process.script} to be ready",
            )

        command = [sys.executable, "-u", "send_question.py"]
        if question:
            command.append(question)
        started = time.time()
        sent = subprocess.run(
            command, cwd=HW8_DIR, capture_output=True, text=True, check=False, timeout=300
        )
        seconds = round(time.time() - started, 1)
    finally:
        for process in processes:
            process.stop()

    out_lines = sent.stdout.splitlines()
    split = out_lines.index("{") if "{" in out_lines else len(out_lines)
    final = json.loads("\n".join(out_lines[split:])) if split < len(out_lines) else None
    correlation_id = final["correlation_id"] if final else None
    journey = out_lines[:split]
    for process in processes:
        journey += [line for line in process.lines() if correlation_id and correlation_id in line]
    return {
        "correlation_id": correlation_id,
        "final": final,
        "seconds": seconds,
        "model": "stub" if stub else CONFIG.model,
        "journey": sorted(journey),  # every line starts with a UTC timestamp
        "returncode": sent.returncode,
        "stderr": sent.stderr[-500:],
    }


def main() -> int:
    stub = "--stub" in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        result = run_pipeline(stub, Path(tmp), unique_groups=True)
    RAW.mkdir(parents=True, exist_ok=True)
    name = "part2_pipeline_stub.json" if stub else "part2_pipeline_live.json"
    (RAW / name).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("\n".join(result["journey"]))
    print(json.dumps(result["final"], indent=2))
    print(f"model={result['model']} seconds={result['seconds']}")
    return 0 if result["final"] and result["final"]["status"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
