"""Part 3.5: a cached answer that depends on a database record goes stale, then is invalidated.

Strategy: every cache entry stores a data-version marker (the record's data_version at the time the
answer was produced). On a hit, the handler compares that marker with the record's current version; a
mismatch invalidates the entry and the question is answered again by the agent pipeline.
"""

from __future__ import annotations

import asyncio
import json
import re

from .config import RAW_DIR
from .ingress import QueryHandler
from .listing_db import ListingDatabase
from .pipeline_client import PipelineClient
from .semantic_cache import SemanticCache

LISTING_ID = 1
QUESTION = "What is the monthly rent for the Maple Court two-bedroom apartment?"


def mentions(answer: str, amount: int) -> bool:
    return str(amount) in re.sub(r"[,$]", "", answer)


async def main() -> int:
    db = ListingDatabase()
    db.restore_seed(LISTING_ID)
    cache = SemanticCache(threshold=0.85)
    cache.clear()
    pipeline = PipelineClient()
    await pipeline.start()
    handler = QueryHandler(cache, db, pipeline)
    steps = []
    try:
        row = db.get_listing(LISTING_ID)
        print(
            f"Database record: listing {LISTING_ID} {row['property_title']} monthly_rent=${row['monthly_rent']:,} data_version={row['data_version']}"
        )

        print("\n--- Step 1: ask once (cache miss, answer is stored with data_version 1) ---")
        handler.check_data_version = False
        first = await handler.handle(QUESTION)
        print(
            f"is_cached={first['is_cached']} data_version={first['data_version']}\nAnswer: {first['answer']}"
        )
        steps.append({"step": "first_ask", **first})

        print("\n--- Step 2: update the record so the cached answer becomes stale ---")
        row = db.update_listing(LISTING_ID, monthly_rent=2650, security_deposit=2650)
        print(
            f"Database record now: monthly_rent=${row['monthly_rent']:,} data_version={row['data_version']}"
        )

        print("\n--- Step 3: ask again with NO invalidation -> the stale answer is returned ---")
        stale = await handler.handle(QUESTION)
        old_in_answer = mentions(stale["answer"], 2450)
        print(
            f"is_cached={stale['is_cached']} similarity={stale['similarity']} (stored data_version={stale['data_version']}, "
            f"database data_version={row['data_version']})\nAnswer: {stale['answer']}"
        )
        print(
            f"STALE HIT: answer still states the old rent $2,450: {old_in_answer}; current rent is $2,650"
        )
        steps.append({"step": "stale_hit", "old_amount_in_answer": old_in_answer, **stale})

        print(
            "\n--- Step 4: invalidation strategy ON (compare the stored data_version with the record) ---"
        )
        handler.check_data_version = True
        fixed = await handler.handle(QUESTION)
        new_in_answer = mentions(fixed["answer"], 2650)
        print(
            f"is_cached={fixed['is_cached']} data_version={fixed['data_version']}\nAnswer: {fixed['answer']}"
        )
        print(f"Answer states the new rent $2,650: {new_in_answer}")
        steps.append({"step": "after_invalidation", "new_amount_in_answer": new_in_answer, **fixed})

        print("\n--- Step 5: ask again -> a fresh, correct cache hit ---")
        again = await handler.handle(QUESTION)
        print(
            f"is_cached={again['is_cached']} similarity={again['similarity']} data_version={again['data_version']}"
        )
        steps.append({"step": "fresh_hit", **again})
    finally:
        await pipeline.stop()
        cache.clear()
        db.restore_seed(LISTING_ID)

    print(
        "\nTrade-off: the version check costs one database read on every cache hit and only protects entries "
        "that record which row they depend on; it never serves a stale answer, but a hit is slightly slower."
    )
    (RAW_DIR / "part3_stale_demo.json").write_text(json.dumps(steps, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
