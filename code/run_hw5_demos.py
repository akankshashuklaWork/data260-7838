"""Print the Part 3 retry demos and the Part 5 safety-rule demo (real output)."""

from __future__ import annotations

import json

from hw5_mcp.domain_tools import MemoryDomainStore, execute_tool
from hw5_mcp.retry import RetryPolicy, run_with_retry

POLICY = RetryPolicy(max_retries=3, timeout_seconds=0.25, backoff_seconds=0.01)
delays: list[float] = []


def flaky(fail_times: int):
    state = {"n": 0}

    def op():
        state["n"] += 1
        if state["n"] <= fail_times:
            raise OSError(f"storage unavailable (attempt {state['n']})")
        return {"status": "ok"}

    return op


def show(label: str, fail_times: int) -> None:
    delays.clear()
    r = run_with_retry(flaky(fail_times), POLICY, sleep=delays.append)
    print(f"{label}: success={r.success} attempts={r.attempts} error={r.error} backoff_delays_s={delays}")


show("Demo 1 first-attempt success", 0)
show("Demo 2 fail once, succeed on retry", 1)
show("Demo 3 fail on all 4 attempts (1 + 3 retries)", 99)

store = MemoryDomainStore.demo()
print("\nSafety rule")
for inputs in ({"query": "all", "limit": 10}, {"query": "all", "limit": 11}):
    out = json.loads(execute_tool("search", inputs, store))
    print("inputs", inputs, "-> ok", out["ok"], "| error:", out["error"])
