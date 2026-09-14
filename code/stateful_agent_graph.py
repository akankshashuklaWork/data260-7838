#!/usr/bin/env python3
"""Part 3: Stateful Planner/Reviewer graph for rental listings.

The graph follows the assignment flow:

    Supervisor -> Planner -> Supervisor -> Reviewer -> Supervisor -> END
                              ^                         |
                              +------ issues -----------+

All model calls are made through the HW1 ``ModelClient`` adapter. The graph
does not import Ollama or LangChain model classes directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

class AgentState(TypedDict, total=False):
    """Shared memory passed between every graph node."""

    title: str
    content: str
    email: str
    strict: bool
    task: str
    llm: Any
    planner_proposal: Dict[str, Any]
    reviewer_feedback: Dict[str, Any]
    validation_error: str
    turn_count: int
    max_turns: int
    trace: List[Dict[str, Any]]


class PlannerOutput(BaseModel):
    """Strict Part 4 schema for Planner output."""

    model_config = ConfigDict(extra="forbid")
    tags: List[str] = Field(min_length=3, max_length=3)
    summary: str

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        if any(not isinstance(tag, str) or not 3 <= len(tag.strip()) <= 30 for tag in tags):
            raise ValueError("Each tag must be a string between 3 and 30 characters")
        return [tag.strip() for tag in tags]

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, summary: str) -> str:
        if len(summary.split()) > 25:
            raise ValueError("Summary must contain at most 25 words")
        return summary.strip()


def _json_from_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a model response and retain a useful error when it is invalid."""

    content = response.get("content", "")
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {"error": "Expected a JSON object"}
    except (TypeError, json.JSONDecodeError):
        return {"error": "Model returned invalid JSON", "raw": str(content)}


def _validation_message(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in error.errors()
    )


def _record_trace(state: AgentState, node: str, response: Dict[str, Any], output: Dict[str, Any]) -> List[Dict[str, Any]]:
    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": node,
            "output": output,
            "input_tokens": response.get("input_tokens"),
            "output_tokens": response.get("output_tokens"),
            "total_tokens": response.get("total_tokens"),
        }
    )
    return trace


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """Update graph bookkeeping; routing is handled separately."""

    next_turn = state.get("turn_count", 0) + 1
    trace = list(state.get("trace", []))
    trace.append({"node": "supervisor", "turn_count": next_turn})
    return {"turn_count": next_turn, "trace": trace}


def router_logic(state: AgentState) -> Literal["planner", "reviewer", "END"]:
    """Route according to the proposal/review state and the turn ceiling."""

    if state.get("turn_count", 0) >= state.get("max_turns", 10):
        return "END"
    if not state.get("planner_proposal"):
        return "planner"
    feedback = state.get("reviewer_feedback", {})
    if feedback.get("has_issues", False):
        return "planner"
    if not feedback:
        return "reviewer"
    return "END"


def planner_node(state: AgentState) -> Dict[str, Any]:
    """Ask the adapter to create or revise a rental-listing proposal."""

    llm = state["llm"]
    feedback = state.get("reviewer_feedback", {})
    feedback_text = json.dumps(feedback) if feedback else "No reviewer feedback yet."
    messages = [
        {
            "role": "system",
            "content": (
                "You are the Planner for a rental housing listing. Analyze the title and content "
                "and return only JSON with exactly these keys: tags and summary. The tags array "
                "must contain exactly three specific strings, each 3–30 characters. The summary "
                "must contain at most 25 words."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Title: {state.get('title', '')}\n"
                f"Content: {state.get('content', '')}\n"
                f"Task: {state.get('task', 'Create a useful rental-listing proposal.')}\n"
                f"Reviewer feedback or validation error from the previous attempt: {feedback_text}"
            ),
        },
    ]
    response = llm.complete(messages)
    raw_proposal = _json_from_response(response)
    try:
        proposal = PlannerOutput.model_validate(raw_proposal).model_dump()
        validation_error = ""
    except ValidationError as error:
        proposal = {}
        validation_error = _validation_message(error)
        feedback = {
            "has_issues": True,
            "feedback": f"Fix the Planner output validation errors: {validation_error}",
        }
    return {
        "planner_proposal": proposal,
        "reviewer_feedback": feedback if validation_error else {},
        "validation_error": validation_error,
        "trace": _record_trace(state, "planner", response, proposal),
    }


def reviewer_node(state: AgentState) -> Dict[str, Any]:
    """Review the Planner proposal and report whether correction is needed."""

    llm = state["llm"]
    messages = [
        {
            "role": "system",
            "content": (
                "You are the Reviewer for a rental housing listing. Check the Planner proposal "
                "against the title, content, and task. Return only JSON with keys "
                "has_issues (boolean), feedback (string), and approved (boolean)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Title: {state.get('title', '')}\n"
                f"Content: {state.get('content', '')}\n"
                f"Task: {state.get('task', '')}\n"
                f"Planner proposal: {json.dumps(state.get('planner_proposal', {}))}"
            ),
        },
    ]
    response = llm.complete(messages)
    feedback = _json_from_response(response)
    return {
        "reviewer_feedback": feedback,
        "trace": _record_trace(state, "reviewer", response, feedback),
    }


def build_graph():
    """Build the Supervisor -> Planner/Reviewer state graph."""

    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)
    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        router_logic,
        {"planner": "planner", "reviewer": "reviewer", "END": END},
    )
    graph.add_edge("planner", "supervisor")
    graph.add_edge("reviewer", "supervisor")
    return graph.compile()


def initial_state(
    title: str,
    content: str,
    email: str = "",
    task: str = "Create a useful rental-listing proposal.",
    max_turns: int = 10,
    llm: Any | None = None,
) -> AgentState:
    """Create a fresh graph state for one rental-listing input."""

    return {
        "title": title,
        "content": content,
        "email": email,
        "strict": True,
        "task": task,
        "llm": llm or _default_model_client(),
        "turn_count": 0,
        "max_turns": max_turns,
        "trace": [],
    }


def _default_model_client() -> Any:
    """Load the HW1 adapter only when a real model run is requested."""

    from src.model_client import ModelClient

    return ModelClient(model="qwen2:7b")


def run_graph(state: AgentState, show_stream: bool = True) -> AgentState:
    """Run the graph and optionally print each streamed node update."""

    final_state: AgentState = state
    for update in build_graph().stream(state):
        node, values = next(iter(update.items()))
        final_state = {**final_state, **values}
        if show_stream:
            print(f"[{node}] {json.dumps(values, default=str)}")
    return final_state


def _load_input(path: str | None) -> Dict[str, str]:
    if not path:
        return {
            "title": "Willow Glen two-bedroom rental",
            "content": "Bright two-bedroom home near transit with parking, a shared garden, and flexible lease terms.",
        }
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the HW2 stateful agent graph")
    parser.add_argument("--input", help="JSON file containing title and content")
    parser.add_argument("--max-turns", type=int, default=10)
    args = parser.parse_args()
    data = _load_input(args.input)
    state = initial_state(data["title"], data["content"], max_turns=args.max_turns)
    final_state = run_graph(state)
    print("FINAL STATE:")
    print(json.dumps({k: v for k, v in final_state.items() if k != "llm"}, indent=2, default=str))


if __name__ == "__main__":
    main()
