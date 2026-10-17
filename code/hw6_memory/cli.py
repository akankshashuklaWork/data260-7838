"""Small command-line client for sending reproducible chats and memory commands."""

import argparse
import json

import httpx

from .config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one message to the HW6 memory service.")
    parser.add_argument("message")
    parser.add_argument("--user", default="akanksha")
    parser.add_argument("--session", default="hw6-demo")
    args = parser.parse_args()
    settings = get_settings()
    response = httpx.post(
        f"http://127.0.0.1:{settings.port_base}/api/chat",
        json={"user_id": args.user, "session_id": args.session, "message": args.message},
        timeout=60,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
