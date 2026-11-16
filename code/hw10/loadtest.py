"""Part 4.3: stage-latency experiment on 50 confirmed cache misses.

Closed loop and one request at a time: send a question, wait for the answer, then wait for the
evaluator to finish that trace before sending the next. Nothing overlaps, so every stage is
measured without contention from another request. Each response must report ``is_cached=False``
(the cache is emptied first, the 50 questions were checked to be dissimilar, and the run aborts
if any response is a hit). Afterwards 15 earlier questions are repeated so the cache-hit path has
its own measurements; those hits are kept out of the 50.

    PYTHONPATH=code python -m hw10.loadtest           # about an hour with the local models
"""

from __future__ import annotations

import json
import time

import httpx
from hw8.common import log, utc_iso

from .config import EVAL_RESULTS, INGRESS_URL, JUDGE_MODEL, LATENCY_REQUESTS, RAW_DIR
from .questions import LATENCY_QUESTIONS

HIT_REPEATS = 15
WARMUP_QUESTION = "Warm-up: what is a tenancy at will?"


def evaluated_ids() -> set[str]:
    if not EVAL_RESULTS.exists():
        return set()
    ids = set()
    for line in EVAL_RESULTS.read_text(encoding="utf-8").splitlines():
        try:
            ids.add(json.loads(line)["trace_id"])
        except (ValueError, KeyError):
            continue
    return ids


def wait_for_evaluation(trace_id: str, timeout: float = 400) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if trace_id in evaluated_ids():
            return True
        time.sleep(0.5)
    return False


def post(client: httpx.Client, question: str) -> tuple[dict, float]:
    started = time.perf_counter()
    reply = client.post(f"{INGRESS_URL}/ask", json={"question": question}, timeout=320)
    elapsed = (time.perf_counter() - started) * 1000
    return {"http_status": reply.status_code, **reply.json()}, elapsed


def main() -> int:
    questions = LATENCY_QUESTIONS[:LATENCY_REQUESTS]
    assert len(questions) == LATENCY_REQUESTS == len(set(questions))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    run: dict = {
        "started": utc_iso(),
        "judge_model": JUDGE_MODEL,
        "misses": [],
        "hits": [],
        "warmup_trace_id": None,
    }
    with httpx.Client() as client:
        # Warm the embedding model, the generator, and the judge so request 1 is not a cold start.
        warm, _ = post(client, WARMUP_QUESTION)
        run["warmup_trace_id"] = warm["trace_id"]
        wait_for_evaluation(warm["trace_id"])
        client.post(f"{INGRESS_URL}/reset", timeout=30)  # empty the cache: every question is new
        log(
            "LOAD",
            f"warm-up done trace_id={warm['trace_id']}; cache emptied; starting {len(questions)} misses",
        )

        for index, question in enumerate(questions, 1):
            body, client_ms = post(client, question)
            if body.get("is_cached") or body["http_status"] != 200:
                raise SystemExit(f"request {index} was not a clean cache miss: {body}")
            evaluated = wait_for_evaluation(body["trace_id"])
            run["misses"].append(
                {
                    "index": index,
                    "question": question,
                    "trace_id": body["trace_id"],
                    "is_cached": body["is_cached"],
                    "similarity": body["similarity"],
                    "client_ms": round(client_ms, 1),
                    "latency_ms": body["latency_ms"],
                    "evaluated": evaluated,
                }
            )
            log("LOAD", f"{index:02d}/{len(questions)} miss trace_id={body['trace_id']} "
                f"latency_ms={body['latency_ms']:.0f} evaluated={evaluated}")  # fmt: skip

        for index, question in enumerate(questions[:HIT_REPEATS], 1):
            body, client_ms = post(client, question)
            run["hits"].append(
                {
                    "index": index,
                    "question": question,
                    "trace_id": body["trace_id"],
                    "is_cached": body.get("is_cached"),
                    "similarity": body.get("similarity"),
                    "client_ms": round(client_ms, 1),
                    "latency_ms": body.get("latency_ms"),
                }
            )
            log("LOAD", f"hit-check {index:02d} is_cached={body.get('is_cached')} "
                f"latency_ms={body.get('latency_ms')}")  # fmt: skip
    run["finished"] = utc_iso()
    (RAW_DIR / "latency_run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    cached = sum(1 for m in run["misses"] if m["is_cached"])
    print(
        f"done: {len(run['misses'])} misses ({cached} served from cache), {len(run['hits'])} hit checks"
    )
    return 0 if cached == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
