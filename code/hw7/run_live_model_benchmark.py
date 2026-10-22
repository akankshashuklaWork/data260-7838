"""Optional genuine local-model benchmark for HW7 Part 2.

This intentionally records the model's observed behavior rather than replacing
it with a scripted result.  It needs a locally running Ollama qwen2:7b server.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import TASKS, ModelClientAdapter, run_agent

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "reports/hw07/raw/part2_live_model_attempts.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.start <= 20 or not 1 <= args.count <= 20 or args.start + args.count > 21:
        raise SystemExit("--start and --count must select attempts within 1..20")
    model = ModelClientAdapter("qwen2:7b")
    existing = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else []
    by_attempt = {item["attempt"]: item for item in existing}
    for number in range(args.start, args.start + args.count):
        task = TASKS[(number - 1) % len(TASKS)]
        result = run_agent(
            task.prompt,
            model,
            required_tool_calls=len(task.calls),
            max_steps=6,
        )
        by_attempt[number] = {
            "attempt": number,
            "task": task.label,
            "model": "qwen2:7b",
            "result": result,
        }
        TARGET.write_text(
            json.dumps([by_attempt[key] for key in sorted(by_attempt)], indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "attempt": number,
                    "task": task.label,
                    "stop_reason": result["stop_reason"],
                    "tool_calls": result["tool_calls"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
