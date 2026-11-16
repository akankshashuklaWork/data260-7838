"""Part 3.1: freeze the 20 evaluation cases.

Each case is a *real* Writer draft produced by the running Planner -> Writer pipeline (local
qwen2:7b, temperature 0). For questions about a listing the Writer receives that record's facts,
exactly as the ingress hands them over. The result is written once to ``eval_cases.json``; the
human labels (``human_labels.csv``) are added by hand afterwards and both files are committed
before any judge score exists.

    PYTHONPATH=code python -m hw10.build_eval_cases        # needs: make up-hw09, stack up (agents)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from aiokafka import AIOKafkaProducer
from hw8.common import log, to_bytes, utc_iso
from hw8.tracing import new_trace_id
from hw9.ingress import facts_for
from hw9.listing_db import ListingDatabase

from .collector import Bundle, Collector, open_consumer
from .config import CONFIG, EVAL_CASES, KAFKA_BOOTSTRAP
from .questions import EVAL_QUESTIONS

PER_CASE_TIMEOUT_S = 240


async def build() -> list[dict]:
    db = ListingDatabase()
    collector = Collector()
    consumer = await open_consumer()
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()

    async def pump() -> None:
        async for msg in consumer:
            collector.add(msg.topic, msg.value)

    pump_task = asyncio.create_task(pump())
    cases: list[dict] = []
    try:
        await asyncio.sleep(2)  # let the consumer finish joining its group
        for number, question in enumerate(EVAL_QUESTIONS, 1):
            trace_id = new_trace_id()
            listing = db.find_listing_in_text(question)
            message = {"correlation_id": trace_id, "question": question}
            if listing:
                message["context"] = facts_for(listing)
            bundle = collector.bundles.setdefault(trace_id, Bundle(trace_id))
            await producer.send_and_wait(
                CONFIG.inbox_topic, to_bytes(message), key=trace_id.encode()
            )
            if not await collector.wait_for_all(bundle, timeout=PER_CASE_TIMEOUT_S):
                raise SystemExit(f"case {number}: missing {bundle.missing()} for {trace_id}")
            assert bundle.plan and bundle.draft and bundle.final
            cases.append(
                {
                    "case_id": f"C{number:02d}",
                    "trace_id": trace_id,
                    "question": question,
                    "context": message.get("context", ""),
                    "plan": bundle.plan["plan"],
                    "draft": bundle.draft["draft"],
                    "source": f"Writer draft from {CONFIG.drafts_topic} ({CONFIG.model}, temperature 0)",
                    "created_at": utc_iso(),
                }
            )
            log(
                "BUILD",
                f"C{number:02d} trace_id={trace_id} words={len(cases[-1]['draft'].split())}",
            )
    finally:
        pump_task.cancel()
        await consumer.stop()
        await producer.stop()
    return cases


def main() -> int:
    if EVAL_CASES.exists() and "--force" not in sys.argv:
        print(f"{EVAL_CASES} already exists; it is frozen. Use --force only before labelling.")
        return 1
    started = time.time()
    cases = asyncio.run(build())
    EVAL_CASES.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {EVAL_CASES} in {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
