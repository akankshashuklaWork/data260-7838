"""Create offline MCP-style outputs for the three domain tools."""

from __future__ import annotations

import json
from pathlib import Path

from hw5_mcp.domain_tools import MemoryDomainStore, execute_tool


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "reports/hw05/raw/mcp_inspector_outputs.json"
    store = MemoryDomainStore.demo()
    calls = []
    for tool, inputs in [
        ("search", {"query": "San Jose", "limit": 2}),
        ("detail", {"listing_id": 1}),
        ("aggregate", {"owner_id": 1}),
        ("search", {"query": "", "limit": 2}),
        ("detail", {"listing_id": 0}),
        ("aggregate", {"owner_id": 0}),
    ]:
        calls.append({"tool": tool, "inputs": inputs, "output": json.loads(execute_tool(tool, inputs, store))})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"domain_server": {"tool_count": 3, "calls": calls}, "meals_server": {"tools": ["search_meals_by_name", "meals_by_ingredient", "random_meal", "meal_details"], "network_calls": "run with mcp dev and Inspector"}}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

