"""A bounded, auditable tool loop used for HW7 Parts 2 and 3.

The live adapter uses the HW1 ModelClient.  The deterministic ScriptedModel is
used by the report harness so every repair and verifier result can be replayed
without a running local model.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from hw5_mcp.domain_tools import DomainStore, MemoryDomainStore, execute_tool


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


@dataclass
class ScriptedModel:
    """Deterministic response source for fixed evaluation cases."""

    responses: list[str]
    index: int = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        del messages
        if not self.responses:
            return json.dumps({"final": "No scripted response was configured."})
        value = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return value


class ModelClientAdapter:
    """Adapts the shared HW1 client to the small string-returning agent protocol."""

    def __init__(self, model: str = "qwen2:7b") -> None:
        from src.model_client import ModelClient

        self.client = ModelClient(model=model)

    def complete(self, messages: list[dict[str, str]]) -> str:
        return str(self.client.complete(messages)["content"])


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    """Extract one JSON object, allowing a model to wrap it in a code fence."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _tool_call_error(action: dict[str, Any] | None) -> str | None:
    if action is None:
        return "Expected one JSON object containing a tool and an inputs object."
    if isinstance(action.get("final"), str):
        return None
    name = action.get("tool")
    if not isinstance(name, str):
        return "Expected a string tool name: search, detail, or aggregate."
    if name not in {"search", "detail", "aggregate"}:
        return f"Unknown tool '{name}'. Use search, detail, or aggregate."
    inputs = action.get("inputs")
    if not isinstance(inputs, dict):
        return "Tool inputs must be a JSON object matching the tool schema."
    allowed = {
        "search": {"query", "limit"},
        "detail": {"listing_id"},
        "aggregate": {"owner_id"},
    }[name]
    extras = sorted(set(inputs) - allowed)
    if extras:
        return f"{name} does not accept extra input fields: {', '.join(extras)}."
    if name == "search" and (
        not isinstance(inputs.get("query"), str)
        or not isinstance(inputs.get("limit", 10), int)
        or isinstance(inputs.get("limit", 10), bool)
    ):
        return 'search requires {"query": string, "limit": optional integer}.'
    if name in {"detail", "aggregate"}:
        key = "listing_id" if name == "detail" else "owner_id"
        if not isinstance(inputs.get(key), int) or isinstance(inputs.get(key), bool):
            return f'{name} requires {{"{key}": positive integer}}.'
    return None


def _make_messages(user_input: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a rental-housing assistant. Use only JSON. Never put 'search|detail|aggregate' "
                "in the tool field. The only exact calls are "
                '{"tool":"search","inputs":{"query":"San Jose","limit":2}}, '
                '{"tool":"detail","inputs":{"listing_id":1}}, or '
                '{"tool":"aggregate","inputs":{"owner_id":1}}. '
                'When done use {"final":"grounded response"}. Never invent rental facts. '
                "A tool result is authoritative."
            ),
        },
        {"role": "user", "content": user_input},
    ]


def run_agent(
    user_input: str,
    model: ChatModel | None = None,
    *,
    max_steps: int = 6,
    required_tool_calls: int = 0,
    store: DomainStore | None = None,
) -> dict[str, Any]:
    """Run a bounded tool loop with one specific repair prompt at most.

    Each accepted tool response is retained as a ``tool``-role message.  Invalid
    JSON, a wrong tool name, bad inputs, or a premature final answer get exactly
    one repair opportunity and then stop cleanly.
    """
    model = model or ModelClientAdapter()
    store = store or MemoryDomainStore.demo()
    messages = _make_messages(user_input)
    trace: list[dict[str, Any]] = []
    tool_calls = 0
    repairs = 0
    initial_well_formed: bool | None = None
    final = ""
    stop_reason = "step_limit"
    started = time.perf_counter()

    for step in range(1, max_steps + 1):
        raw = model.complete(messages)
        action = _parse_json_object(raw)
        error = _tool_call_error(action)
        if initial_well_formed is None:
            initial_well_formed = error is None and action is not None and "tool" in action

        if error is not None:
            trace.append({"step": step, "kind": "invalid_action", "raw": raw, "error": error})
            if repairs >= 1:
                final = (
                    "The request could not be completed because the repaired tool call was invalid."
                )
                stop_reason = "failed_repair"
                break
            repairs += 1
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"Repair this call once. {error}"},
                ]
            )
            continue

        assert action is not None
        if isinstance(action.get("final"), str):
            if tool_calls < required_tool_calls:
                error = (
                    f"This task requires at least {required_tool_calls} grounded tool calls before a final answer; "
                    "call the next appropriate tool."
                )
                trace.append({"step": step, "kind": "premature_final", "raw": raw, "error": error})
                if repairs >= 1:
                    final = "The request needs additional tool evidence and could not be repaired."
                    stop_reason = "failed_repair"
                    break
                repairs += 1
                messages.extend(
                    [
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": f"Repair this response once. {error}"},
                    ]
                )
                continue
            final = action["final"]
            trace.append({"step": step, "kind": "final", "answer": final})
            stop_reason = "success"
            break

        name = str(action["tool"])
        inputs = action["inputs"]
        encoded_result = execute_tool(name, inputs, store)
        result = json.loads(encoded_result)
        trace.append(
            {
                "step": step,
                "kind": "tool",
                "tool": name,
                "inputs": inputs,
                "result": result,
            }
        )
        tool_calls += 1
        messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "tool", "content": encoded_result},
            ]
        )
        if (
            not result["ok"]
            and repairs < 1
            and any(
                label in str(result["error"]).lower()
                for label in ("unknown tool", "inputs must", "query must", "listing_id", "owner_id")
            )
        ):
            repairs += 1
            messages.append(
                {
                    "role": "user",
                    "content": f"Repair this failed tool call once: {result['error']}",
                }
            )
            continue
    else:
        final = "The tool-step budget was reached before a final answer."

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "user_input": user_input,
        "final": final,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "repairs": repairs,
        "initial_well_formed": bool(initial_well_formed),
        "latency_ms": elapsed_ms,
        "trace": trace,
    }


def action(tool: str, inputs: dict[str, Any]) -> str:
    return json.dumps({"tool": tool, "inputs": inputs}, sort_keys=True)


def final(text: str) -> str:
    return json.dumps({"final": text}, sort_keys=True)


@dataclass(frozen=True)
class FixedTask:
    label: str
    prompt: str
    calls: tuple[tuple[str, dict[str, Any]], ...]
    answer: str


TASKS: tuple[FixedTask, ...] = (
    FixedTask(
        "A_search_then_detail",
        "Find a San Jose rental listing and then give details for the first result.",
        (("search", {"query": "San Jose", "limit": 2}), ("detail", {"listing_id": 1})),
        "Willow Glen Cottage is listing SJ-100 in San Jose with one available unit.",
    ),
    FixedTask(
        "B_aggregate_then_example",
        "Summarize owner 1 and give one supporting listing example.",
        (("aggregate", {"owner_id": 1}), ("detail", {"listing_id": 1})),
        "Owner 1 has two listings and three available units; SJ-100 is one example.",
    ),
    FixedTask(
        "C_compare_two_details",
        "Compare the two San Jose listings after searching for them.",
        (
            ("search", {"query": "San Jose", "limit": 2}),
            ("detail", {"listing_id": 1}),
            ("detail", {"listing_id": 2}),
        ),
        "SJ-100 is a House with one available unit; SJ-101 is an Apartment with two available units.",
    ),
)


def scripted_responses(task: FixedTask, first_failure: str | None = None) -> list[str]:
    """Return one fixed model transcript; a bad first turn is followed by repair."""
    faulty = {
        "malformed_args": json.dumps({"tool": "search", "inputs": []}),
        "unknown_tool": action("lookup", {"query": "San Jose"}),
        "text_where_tool_required": "I will look up the listings before answering.",
        "lost_multi_step_chain": final("The first result should be enough."),
    }
    calls = [action(name, inputs) for name, inputs in task.calls]
    return ([faulty[first_failure]] if first_failure else []) + calls + [final(task.answer)]


def run_fixed_benchmark() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run 20 fixed attempts and summarize pre/post-repair reliability."""
    failures = [None] * 16 + [
        "malformed_args",
        "unknown_tool",
        "text_where_tool_required",
        "lost_multi_step_chain",
    ]
    attempts: list[dict[str, Any]] = []
    for number, failure in enumerate(failures, start=1):
        task = TASKS[(number - 1) % len(TASKS)]
        result = run_agent(
            task.prompt,
            ScriptedModel(scripted_responses(task, failure)),
            required_tool_calls=len(task.calls),
        )
        attempts.append(
            {
                "attempt": number,
                "task": task.label,
                "initial_failure_class": failure,
                "before_repair_well_formed": result["initial_well_formed"],
                "after_repair_success": result["stop_reason"] == "success",
                "tool_calls": result["tool_calls"],
                "repairs": result["repairs"],
                "result": result,
            }
        )
    total = len(attempts)
    summary = {
        "attempts": total,
        "well_formed_before_repair": sum(row["before_repair_well_formed"] for row in attempts),
        "well_formed_before_repair_rate": round(
            sum(row["before_repair_well_formed"] for row in attempts) / total, 3
        ),
        "successful_after_repair": sum(row["after_repair_success"] for row in attempts),
        "successful_after_repair_rate": round(
            sum(row["after_repair_success"] for row in attempts) / total, 3
        ),
        "failure_classes": {
            name: sum(row["initial_failure_class"] == name for row in attempts)
            for name in (
                "malformed_args",
                "unknown_tool",
                "text_where_tool_required",
                "lost_multi_step_chain",
            )
        },
    }
    return attempts, summary
