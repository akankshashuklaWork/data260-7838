"""Part 1 demo: the Redis view counter for one listing, 25 accesses."""

from __future__ import annotations

import logging

from .config import DATA_DIR
from .listing_db import ListingDatabase

LISTING_ID = 1


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(  # the "Synced views to database" log message goes to this file
        filename=DATA_DIR / "hw9.log", level=logging.INFO, format="%(asctime)s %(message)s"
    )
    db = ListingDatabase()
    db.reset_views(LISTING_ID)
    print("=== Testing Counter ===\n")
    for access in range(1, 26):
        total = db.increment_listing_views(LISTING_ID)
        print(f"Access #{access}: Total = {total}")
        if db.last_synced:
            print("✓ Synced views to database")
    redis_count = db.redis_client.get(f"s7838:views:listing:{LISTING_ID}")
    print(f"\nRedis key s7838:views:listing:{LISTING_ID} = {redis_count}")
    print(
        f"Database view_count for listing {LISTING_ID} = {db.stored_view_count(LISTING_ID)}"
        " (written only on every 10th view)"
    )
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
