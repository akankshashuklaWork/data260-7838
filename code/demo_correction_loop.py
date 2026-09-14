"""Step 6 demo: force reviewer_node to always flag an issue and check the
Supervisor keeps sending work back to the Planner instead of ending early."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stateful_agent_graph as sag

_real_reviewer_node = sag.reviewer_node


def always_flag_reviewer(state):
    result = _real_reviewer_node(state)
    result["reviewer_feedback"] = {
        "has_issues": True,
        "feedback": "Forced for Step 6 self-correction demo: always request a revision.",
        "approved": False,
    }
    return result


sag.reviewer_node = always_flag_reviewer
graph = sag.build_graph()

state = sag.initial_state(
    "Willow Glen two-bedroom rental",
    "Bright two-bedroom home in San Jose near public transit, with parking, a shared garden, and flexible lease terms.",
    max_turns=6,
)

for update in graph.stream(state):
    node, values = next(iter(update.items()))
    printable = {k: v for k, v in values.items() if k != "trace"}
    print(f"[{node}] {json.dumps(printable, default=str)}")

print(
    "\nreviewer_node forced has_issues=True on every call -> Supervisor kept "
    "routing back to Planner until max_turns was reached."
)
