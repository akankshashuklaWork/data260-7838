"""Part 1 demo: CREATE_LISTING then GET_LISTING through FastAPI -> Kafka -> worker -> Kafka.

Run `make up-hw08` first. The script plays the client: it creates ONE correlation_id,
sends each request, and merges its own log lines with the FastAPI and worker container
logs (matched on correlation_id) into one time-ordered sequence per request.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid

import httpx
from common import utc_iso
from config import CONFIG

URL = f"http://127.0.0.1:{CONFIG.port}/listings"
CONTAINERS = {"s7838_api": "FASTAPI", "s7838_worker": "WORKER"}

LISTING = {
    "propertyTitle": "Sunny 2BR near Caltrain",
    "propertyLocation": "San Jose, CA",
    "submitterEmail": "akanksha@example.com",
    "propertyDescription": "Bright two-bedroom apartment with parking, laundry, and a quiet courtyard.",
    "propertyCategory": "Apartment",
    "termsAccepted": "true",
}


def client_line(text: str) -> str:
    return f"{utc_iso()} [CLIENT] {text}"


def container_lines(correlation_id: str, since: str) -> list[str]:
    """Pull the log lines for this correlation_id from the API and worker containers."""
    lines: list[str] = []
    for container in CONTAINERS:
        result = subprocess.run(
            ["docker", "logs", "--since", since, container],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (result.stdout + result.stderr).splitlines():
            if correlation_id in line and "[" in line:
                lines.append(line)
    return lines


def send(operation: str, data: dict, correlation_id: str) -> tuple[dict, list[str]]:
    """Send one request through the API and return (response, time-ordered log lines)."""
    since = utc_iso()
    request = {"operation": operation, "data": data, "correlation_id": correlation_id}
    own = [client_line(f"sending {operation} correlation_id={correlation_id}")]
    own.append(client_line(f"request body={json.dumps(request, separators=(',', ':'))}"))
    response = httpx.post(URL, json=request, timeout=30).json()
    own.append(client_line(f"response received correlation_id={response.get('correlation_id')}"))
    own.append(client_line(f"response body={json.dumps(response, separators=(',', ':'))}"))
    time.sleep(0.5)  # let the container logs flush
    return response, sorted(own + container_lines(correlation_id, since))


def main() -> int:
    print(
        f"{utc_iso()} [CLIENT] Rental listing Kafka demo for Akanksha Shukla (SID4 {CONFIG.sid4})"
    )

    print("\nStep 1: create one correlation_id")
    correlation_id = str(uuid.uuid4())
    print(f"{utc_iso()} [CLIENT] correlation_id={correlation_id}")

    print(
        f"\nSteps 2-6: CREATE_LISTING -> {CONFIG.request_topic} -> worker -> {CONFIG.response_topic}"
    )
    created, lines = send("CREATE_LISTING", LISTING, correlation_id)
    print("\n".join(lines))

    print("\nStep 7: extract the generated listing_id from the CREATE_LISTING response")
    listing_id = created.get("listing_id")
    print(f"{utc_iso()} [CLIENT] success={created.get('success')} listing_id={listing_id}")
    if not listing_id:
        print(f"{utc_iso()} [CLIENT] CREATE_LISTING failed: {created}")
        return 1

    print(f"\nSteps 8-9: GET_LISTING for listing_id={listing_id} (full sequence)")
    get_correlation_id = correlation_id  # the same journey keeps the same correlation_id
    fetched, lines = send("GET_LISTING", {"listing_id": listing_id}, get_correlation_id)
    print("\n".join(lines))

    print("\nStep 10: retrieved listing and correlation_id check")
    print(json.dumps(fetched.get("listing"), indent=2))
    preserved = created.get("correlation_id") == fetched.get("correlation_id") == correlation_id
    print(f"{utc_iso()} [CLIENT] correlation_id preserved end to end: {preserved}")
    return 0 if fetched.get("success") and preserved else 1


if __name__ == "__main__":
    sys.exit(main())
