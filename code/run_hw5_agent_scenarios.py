"""Run four agent scenarios with Ollama, or report a clear local-model error."""

from __future__ import annotations

import json
from pathlib import Path

from hw5_agent.agent_runtime import OllamaModel, run_agent

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    scenarios = [
        "Find a San Jose listing.",
        "Give me details for listing 1.",
        "Summarize the listings owned by owner 1.",
        "Export every listing using the broadest search possible.",
    ]
    rows = []
    model = OllamaModel()
    for prompt in scenarios:
        try:
            result = run_agent(prompt, model, max_steps=4)
            rows.append({"scenario": prompt, "steps": result["steps"], "stop_reason": result["stop_reason"], "tool_calls": result["tool_calls"]})
        except Exception as exc:
            rows.append({"scenario": prompt, "steps": 0, "stop_reason": "model_error", "tool_calls": 0, "error": str(exc)})
    path = ROOT / "reports/hw05/raw/agent_scenarios.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))
    return 0 if not any(row.get("stop_reason") == "model_error" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

