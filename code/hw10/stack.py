"""Start, check, and stop every long-running HW10 process.

    PYTHONPATH=code python -m hw10.stack up        # planner, writer, reviewer, evaluator, ingress
    PYTHONPATH=code python -m hw10.stack status
    PYTHONPATH=code python -m hw10.stack down

Kafka (s7838_kafka) and Redis (s7838_redis) are started separately with `make up-hw09`.
Each process writes its console output to data/hw10/logs/<name>.log. The agents use fresh consumer
groups that start from new messages, so old topic history is never replayed through the models.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import uuid

from .config import CONFIG, DATA_DIR, INGRESS_PORT, ROOT

LOGS = DATA_DIR / "logs"
PID_FILE = DATA_DIR / "stack.json"
HW8_DIR = ROOT / "code/hw8"
READY = "Consumer is ready"


def _launch(name: str, command: list[str], cwd, env: dict[str, str]) -> subprocess.Popen:
    LOGS.mkdir(parents=True, exist_ok=True)
    log_file = open(LOGS / f"{name}.log", "w", encoding="utf-8")  # noqa: SIM115 - lives with the process
    return subprocess.Popen(
        command,
        cwd=cwd,
        env={**os.environ, **env, "PYTHONUNBUFFERED": "1"},
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # survives this script; `down` signals the whole group
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _saved() -> dict[str, int]:
    return json.loads(PID_FILE.read_text()) if PID_FILE.exists() else {}


def up(evaluator: bool = True, ingress: bool = True) -> None:
    running = {name: pid for name, pid in _saved().items() if _alive(pid)}
    if running:
        print(f"already running: {running} (run `down` first)")
        return
    run_id = uuid.uuid4().hex[:6]
    pids: dict[str, int] = {}
    for agent in ("planner", "writer", "reviewer"):
        env = {
            "AGENT_LLM": "ollama",
            "AUTO_OFFSET_RESET": "latest",
            "GROUP_ID": f"{CONFIG.prefix}_{agent}_hw10_{run_id}",
            "PROCESSED_DB": str(DATA_DIR / f"idempotency_{agent}.db"),
        }
        pids[agent] = _launch(agent, [sys.executable, "-u", f"{agent}.py"], HW8_DIR, env).pid
    py_env = {"PYTHONPATH": str(ROOT / "code"), "INGRESS_PORT": str(INGRESS_PORT)}
    if evaluator:
        pids["evaluator"] = _launch(
            "evaluator", [sys.executable, "-u", "-m", "hw10.evaluator"], ROOT, py_env
        ).pid
    if ingress:
        command = [
            sys.executable, "-u", "-m", "uvicorn", "hw9.ingress:app",
            "--host", "127.0.0.1", "--port", str(INGRESS_PORT),
        ]  # fmt: skip
        pids["ingress"] = _launch("ingress", command, ROOT, py_env).pid
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps(pids))

    deadline = time.time() + 180
    waiting = set(pids)
    while waiting and time.time() < deadline:
        for name in list(waiting):
            log_path = LOGS / f"{name}.log"
            text = log_path.read_text() if log_path.exists() else ""
            if name == "ingress":
                if "Semantic cache ingress started" in text:
                    waiting.discard(name)
            elif READY in text:
                waiting.discard(name)
            if not _alive(pids[name]):
                raise SystemExit(f"{name} exited early; see {log_path}")
        time.sleep(0.5)
    if waiting:
        raise SystemExit(f"not ready after 180s: {sorted(waiting)}; see {LOGS}")
    print(f"ready: {pids}")


def down() -> None:
    for name, pid in _saved().items():
        if _alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGINT)
            print(f"stopped {name} ({pid})")
    time.sleep(1.5)
    for pid in _saved().values():
        if _alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    PID_FILE.unlink(missing_ok=True)


def status() -> dict[str, bool]:
    result = {name: _alive(pid) for name, pid in _saved().items()}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{INGRESS_PORT}/stats", timeout=3) as reply:
            result["ingress_http"] = reply.status == 200
    except OSError:
        result["ingress_http"] = False
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "up":
        up(evaluator="--no-evaluator" not in sys.argv, ingress="--no-ingress" not in sys.argv)
    elif command == "down":
        down()
    else:
        status()
