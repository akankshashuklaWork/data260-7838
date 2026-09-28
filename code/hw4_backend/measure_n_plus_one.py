"""Run 30 timed requests for each page size/version and write raw JSON."""
import json, os, statistics, time
from pathlib import Path
import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8638")
OUT = Path(__file__).resolve().parents[2] / "reports/hw04/raw/n_plus_one.json"

def percentile(values, p):
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))
    return ordered[index]

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        login = client.post("/auth/login", json={"email": os.getenv("TEST_EMAIL", "test@example.com"), "password": os.getenv("TEST_PASSWORD", "testpass123")})
        login.raise_for_status()
        measurements = []
        for page_size in (10, 50, 200):
            for version in ("naive", "fixed"):
                latencies = []
                for request_number in range(30):
                    start = time.perf_counter()
                    response = client.get(
                        f"/measure/listings/{version}",
                        params={"page_size": page_size},
                    )
                    response.raise_for_status()
                    latency_ms = (time.perf_counter() - start) * 1000
                    latencies.append(latency_ms)
                    measurements.append(
                        {
                            "page_size": page_size,
                            "version": version,
                            "request": request_number + 1,
                            "status": response.status_code,
                            "sql_statements": int(
                                response.headers.get("X-SQL-Count", "-1")
                            ),
                            "latency_ms": latency_ms,
                        }
                    )
                sql_counts = [x["sql_statements"] for x in measurements[-30:]]
                print(
                    page_size,
                    version,
                    f"sql={statistics.mode(sql_counts)}",
                    f"p50={statistics.median(latencies):.3f}",
                    f"p95={percentile(latencies, 95):.3f}",
                    f"p99={percentile(latencies, 99):.3f}",
                )
    OUT.write_text(json.dumps(measurements, indent=2) + "\n")

if __name__ == "__main__": main()
