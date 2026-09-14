"""Offline routing test for the HW2 Part 3 graph."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stateful_agent_graph import initial_state, run_graph


class FakeModelClient:
    """Return one Planner proposal, then force one correction loop."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self.calls == 1:
            content = {"tags": ["bad"], "summary": "Invalid first attempt."}
        elif self.calls == 2 or self.calls == 4:
            content = {"tags": ["San Jose", "Two-bedroom", "Near transit"], "summary": "Two-bedroom rental near transit in San Jose."}
        else:
            content = {"has_issues": self.calls == 3, "feedback": "Add a concrete location detail." if self.calls == 3 else "Looks complete.", "approved": self.calls != 3}
        return {"content": json.dumps(content), "input_tokens": 1, "output_tokens": 1, "total_tokens": 2}


state = initial_state(
    "Willow Glen rental",
    "Two-bedroom rental near transit in San Jose.",
    llm=FakeModelClient(),
)
result = run_graph(state, show_stream=False)
nodes = [entry["node"] for entry in result["trace"]]
assert nodes == ["supervisor", "planner", "supervisor", "planner", "supervisor", "reviewer", "supervisor", "planner", "supervisor", "reviewer", "supervisor"]
assert result["reviewer_feedback"]["approved"] is True
assert result["turn_count"] == 6
assert result["validation_error"] == ""
print("PASS: Pydantic validation retry and Reviewer correction loop -> END")
