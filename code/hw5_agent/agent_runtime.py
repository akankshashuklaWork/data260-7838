"""Safe tool entry point and bounded Ollama agent loop for HW5 Parts 4–5."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from hw5_mcp.domain_tools import DomainStore, MemoryDomainStore, execute_tool

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "reports/hw05/raw/agent_runs.jsonl"


class Model(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class OllamaModel:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2:7b")

    def complete(self, messages: list[dict[str, str]]) -> str:
        from ollama import chat

        response = chat(model=self.model, messages=messages)
        return str(response["message"]["content"])


@dataclass
class MockModel:
    """Small deterministic model used by offline tests and demos."""

    responses: list[str]
    index: int = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return response


def _parse_model_response(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {"final": text}


def _write_log(event: dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), **event}, sort_keys=True) + "\n")


def run_agent(
    user_input: str,
    model: Model | None = None,
    *,
    max_steps: int = 4,
    store: DomainStore | None = None,
    log_path: Path = LOG_PATH,
) -> dict[str, Any]:
    """Run a bounded tool-using loop and return an auditable summary."""

    model = model or OllamaModel()
    store = store or MemoryDomainStore.demo()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a rental-listing assistant. Reply with JSON only. "
                "To call a tool use {\"tool\":\"search|detail|aggregate\",\"inputs\":{...}}. "
                "When done use {\"final\":\"answer\"}. Never invent listing facts."
            ),
        },
        {"role": "user", "content": user_input},
    ]
    tool_calls = 0
    trace: list[dict[str, Any]] = []
    stop_reason = "max_steps"
    final = ""

    for step in range(1, max_steps + 1):
        try:
            raw = model.complete(messages)
            action = _parse_model_response(raw)
        except Exception as exc:
            stop_reason = "model_error"
            final = f"Model error: {exc}"
            _write_log({"event": "stop", "step": step, "stop_reason": stop_reason, "final": final}, log_path)
            break

        if isinstance(action.get("final"), str):
            final = action["final"]
            stop_reason = "normal_completion"
            trace.append({"step": step, "action": "final", "result": final})
            _write_log({"event": "step", "step": step, "action": "final", "result": final}, log_path)
            break

        name = action.get("tool")
        inputs = action.get("inputs", {})
        if not isinstance(name, str):
            final = "The model returned an invalid tool call."
            stop_reason = "invalid_tool_call"
            _write_log({"event": "stop", "step": step, "stop_reason": stop_reason, "final": final}, log_path)
            break

        tool_calls += 1
        result_text = execute_tool(name, inputs, store)
        result = json.loads(result_text)
        trace.append({"step": step, "action": "tool", "tool": name, "inputs": inputs, "result": result})
        _write_log({"event": "tool_call", "step": step, "tool": name, "inputs": inputs, "result": result}, log_path)
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "tool", "content": result_text})
        if result.get("ok") is False and str(result.get("error", "")).startswith("Safety rule blocked"):
            stop_reason = "safety_rule_blocked"
            final = result["error"]
            _write_log({"event": "stop", "step": step, "stop_reason": stop_reason, "final": final}, log_path)
            break
    else:
        final = "Maximum tool steps reached."

    if not final:
        final = "Maximum tool steps reached."
    _write_log({"event": "run_summary", "user_input": user_input, "steps": len(trace), "tool_calls": tool_calls, "stop_reason": stop_reason, "final": final}, log_path)
    return {"final": final, "steps": len(trace), "tool_calls": tool_calls, "stop_reason": stop_reason, "trace": trace}

