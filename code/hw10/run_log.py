"""Record real console output into reports/hw10/RUN_LOG.txt (and one raw file per step).

Every result in the report comes from a command that was run through this recorder, so
RUN_LOG.txt holds the unedited output with timestamps. Two forms:

    PYTHONPATH=code python -m hw10.run_log record 05_analyze -- python -m hw10.analyze_latency
    PYTHONPATH=code python -m hw10.run_log attach 04_loadtest data/hw10/logs/loadtest.log \
        --command "python -m hw10.loadtest"

`attach` is for a long run that was started in the background and wrote its own timestamped log.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .config import CONFIG, REPORT_DIR, ROOT

TARGET = REPORT_DIR / "RUN_LOG.txt"
CONSOLE = REPORT_DIR / "raw/console"


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clean(text: str) -> str:
    skip = (
        "Loading weights",
        "HF_TOKEN",
        "unauthenticated requests",
        "missing ScriptRunContext",
        "No runtime found",
    )
    return "\n".join(
        line for line in text.splitlines() if not any(s in line for s in skip)
    ).rstrip()


def append(name: str, command: str, output: str, exit_code: int, started: str) -> None:
    CONSOLE.mkdir(parents=True, exist_ok=True)
    (CONSOLE / f"{name}.txt").write_text(output + "\n", encoding="utf-8")
    new_file = not TARGET.exists()
    with open(TARGET, "a", encoding="utf-8") as handle:
        if new_file:
            handle.write(
                f"[{stamp()}] HW10 run log (SID4 {CONFIG.sid4}, prefix {CONFIG.prefix})\n\n"
            )
        handle.write(f"[{started}] $ {command}\n{output}\n[{stamp()}] exit={exit_code}\n\n")


def record(name: str, command: list[str]) -> int:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "code"), "PYTHONUNBUFFERED": "1"}
    started = stamp()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    output = clean(result.stdout + "\n" + result.stderr)
    append(name, " ".join(command), output, result.returncode, started)
    print(output)
    return result.returncode


def attach(name: str, file: str, command: str) -> int:
    path = Path(file)
    started = datetime.fromtimestamp(path.stat().st_ctime, UTC).isoformat(timespec="seconds")
    append(name, command, clean(path.read_text(encoding="utf-8")), 0, started)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 4 and args[0] == "record" and "--" in args:
        split = args.index("--")
        return record(args[1], args[split + 1 :])
    if len(args) >= 3 and args[0] == "attach":
        command = args[args.index("--command") + 1] if "--command" in args else "(see log)"
        return attach(args[1], args[2], command)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
