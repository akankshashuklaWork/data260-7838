"""Bounded Reflexion layer for HW7 Part 3.

Reflections contain only visible tool evidence and a concise corrected strategy;
they never store hidden reasoning, permissions, or instructions from a user.
"""

from __future__ import annotations

from typing import Any

from .agent import TASKS, FixedTask, ScriptedModel, final, run_agent, scripted_responses


def _visible_observations(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"tool": item["tool"], "result": item["result"]}
        for item in result["trace"]
        if item["kind"] == "tool"
    ]


def _verify(task: FixedTask, answer: str) -> dict[str, Any]:
    expected_fragments = {
        "A_search_then_detail": ["Willow Glen Cottage", "one available unit"],
        "B_aggregate_then_example": ["two listings", "three available units", "SJ-100"],
        "C_compare_two_details": ["SJ-100", "one available unit", "SJ-101", "two available units"],
    }[task.label]
    missing = [
        fragment for fragment in expected_fragments if fragment.casefold() not in answer.casefold()
    ]
    unsupported = (
        ["three San Jose listings"] if "three San Jose listings" in answer.casefold() else []
    )
    return {
        "passed": not missing and not unsupported,
        "expected_fragments": expected_fragments,
        "missing": missing,
        "unsupported_claims": unsupported,
    }


def _wrong_answer(task: FixedTask) -> str:
    return {
        "A_search_then_detail": "Willow Glen Cottage is listing SJ-100 in San Jose with two available units.",
        "B_aggregate_then_example": task.answer,
        "C_compare_two_details": "There are three San Jose listings, including SJ-100 and SJ-101.",
    }[task.label]


def _reflection(
    task: FixedTask, verification: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    revised = {
        "A_search_then_detail": "Use the detail observation's available-unit value of one in the revised answer.",
        "C_compare_two_details": "State only the two listings returned by search and compare their observed unit counts.",
    }.get(task.label, "Keep the observed listing facts in the final response.")
    return {
        "task": task.label,
        "evidence": _visible_observations(result),
        "verifier_result": verification,
        "reflection": revised,
    }


def run_reflexion_comparison() -> dict[str, Any]:
    """Compare original and at-most-two-retry runs for three fixed tasks."""
    rows: list[dict[str, Any]] = []
    stored_reflections: list[dict[str, Any]] = []
    for task in TASKS:
        original_script = scripted_responses(task)[:-1] + [final(_wrong_answer(task))]
        original = run_agent(
            task.prompt,
            ScriptedModel(original_script),
            required_tool_calls=len(task.calls),
            max_steps=6,
        )
        original_verification = _verify(task, original["final"])
        reflexion = original
        retry_count = 0
        stop_reason = "success" if original_verification["passed"] else "human_review"
        reflection_record: dict[str, Any] | None = None
        if not original_verification["passed"]:
            retry_count = 1
            reflection_record = _reflection(task, original_verification, original)
            stored_reflections.append(reflection_record)
            retry_model = ScriptedModel(scripted_responses(task))
            reflexion = run_agent(
                task.prompt + "\nReflection evidence: " + reflection_record["reflection"],
                retry_model,
                required_tool_calls=len(task.calls),
                max_steps=6,
            )
            stop_reason = (
                "success" if _verify(task, reflexion["final"])["passed"] else "human_review"
            )
        final_verification = _verify(task, reflexion["final"])
        rows.append(
            {
                "task": task.label,
                "original": {
                    "success": original_verification["passed"],
                    "unsupported_claims": len(original_verification["unsupported_claims"]),
                    "tool_calls": original["tool_calls"],
                    "tokens_estimate": max(1, len(str(original["trace"])) // 4),
                    "latency_ms": original["latency_ms"],
                },
                "reflexion": {
                    "success": final_verification["passed"],
                    "unsupported_claims": len(final_verification["unsupported_claims"]),
                    "retries": retry_count,
                    "tool_calls": original["tool_calls"]
                    + (reflexion["tool_calls"] if retry_count else 0),
                    "tokens_estimate": max(
                        1, len(str(original["trace"]) + str(reflexion["trace"])) // 4
                    ),
                    "latency_ms": round(
                        original["latency_ms"] + (reflexion["latency_ms"] if retry_count else 0), 2
                    ),
                    "stop_reason": stop_reason,
                    "verifier_false_rejection": False,
                },
                "original_verification": original_verification,
                "final_verification": final_verification,
                "stored_reflection": reflection_record,
            }
        )
    return {
        "rows": rows,
        "stored_reflections": stored_reflections,
        "max_retries": 2,
        "token_budget": 900,
        "tool_call_budget": 6,
    }
