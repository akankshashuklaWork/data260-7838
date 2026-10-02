"""Offline HW5 Part 4–5 test runner with assert-based PASS/FAIL output."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hw5_agent.agent_runtime import MockModel, run_agent
from hw5_mcp.domain_tools import MemoryDomainStore, execute_tool


def run(name: str, fn) -> bool:
    try:
        fn()
        print(f"PASS {name}")
        return True
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        return False


def main() -> int:
    store = MemoryDomainStore.demo()
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "agent_runs.jsonl"
        tests = [
            ("search valid", lambda: assert_ok(execute_tool("search", {"query": "San Jose", "limit": 3}, store))),
            ("search invalid schema", lambda: assert_error(execute_tool("search", {"query": "", "limit": 3}, store), "query")),
            ("detail valid", lambda: assert_ok(execute_tool("detail", {"listing_id": 1}, store))),
            ("detail invalid schema", lambda: assert_error(execute_tool("detail", {"listing_id": -1}, store), "listing_id")),
            ("aggregate valid", lambda: assert_ok(execute_tool("aggregate", {"owner_id": 1}, store))),
            ("aggregate invalid schema", lambda: assert_error(execute_tool("aggregate", {"owner_id": 0}, store), "owner_id")),
            ("safety rule allowed", lambda: assert_ok(execute_tool("search", {"query": "all", "limit": 10}, store))),
            ("safety rule blocked", lambda: assert_error(execute_tool("search", {"query": "all", "limit": 11}, store), "Safety rule blocked")),
            ("agent max steps offline", lambda: assert_agent_max_steps(store, log_path)),
        ]
        passed = sum(run(name, fn) for name, fn in tests)
    print(f"SUMMARY {passed}/{len(tests)} tests passed")
    return 0 if passed == len(tests) else 1


def assert_ok(text: str) -> None:
    value = json.loads(text)
    assert value["ok"] is True, value


def assert_error(text: str, fragment: str) -> None:
    value = json.loads(text)
    assert value["ok"] is False, value
    assert fragment.lower() in value["error"].lower(), value


def assert_agent_max_steps(store, log_path: Path) -> None:
    model = MockModel([json.dumps({"tool": "search", "inputs": {"query": "San Jose", "limit": 1}})])
    result = run_agent("find a listing", model, max_steps=2, store=store, log_path=log_path)
    assert result["stop_reason"] == "max_steps", result
    assert result["tool_calls"] == 2, result


if __name__ == "__main__":
    raise SystemExit(main())

