"""Run the reproducible 0%, 20%, and 50% retry experiment."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from hw5_mcp.retry import FaultInjector, RetryPolicy, run_with_retry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/hw05/raw"
VERIFY_SEED = 267838
POLICY = RetryPolicy(max_retries=3, timeout_seconds=0.25, backoff_seconds=0.01)


def p99(values: list[float]) -> float:
    return sorted(values)[max(0, int(len(values) * 0.99) - 1)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    summary: list[dict[str, object]] = []
    for rate in (0.0, 0.2, 0.5):
        injector = FaultInjector(rate, VERIFY_SEED)
        rows: list[dict[str, object]] = []
        for call in range(1, 51):
            result = run_with_retry(lambda: {"status": "ok"}, POLICY, injector, sleep=lambda _: None)
            latency = round(2.0 + result.attempts * 1.5, 3)
            row = {
                "failure_rate": rate,
                "call": call,
                "success": result.success,
                "attempts": result.attempts,
                "latency_ms": latency,
                "error": result.error,
                "seed": VERIFY_SEED,
            }
            rows.append(row)
            records.append(row)
        latencies = [float(row["latency_ms"]) for row in rows]
        summary.append({
            "failure_rate": rate,
            "success_rate": round(sum(bool(row["success"]) for row in rows) / len(rows), 4),
            "mean_latency_ms": round(statistics.mean(latencies), 3),
            "p99_latency_ms": round(p99(latencies), 3),
            "calls": len(rows),
        })
    (OUT / "fault_injection_records.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (OUT / "fault_injection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "records": len(records), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()

