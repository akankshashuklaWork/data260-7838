"""Relational listing store plus a Redis-backed view counter (Part 1).

The `rental_housing_listings` table lives in a SQLite file named after my prefix
(`s7838_rel.db`). Redis holds the fast counter; the database row is only updated
every 10th view.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

import redis

from .config import DATA_DIR, DB_PATH, PREFIX, REDIS_HOST, REDIS_PORT

log = logging.getLogger("hw9.listing_db")

SEED_LISTINGS = [
    # (id, short_name, title, location, category, monthly_rent, security_deposit, pet_policy)
    (
        1,
        "Maple Court",
        "Maple Court 2BR",
        "San Jose, CA",
        "Apartment",
        2450,
        2450,
        "cats only, $300 pet deposit",
    ),
    (2, "Cedar Heights", "Cedar Heights 1BR", "Sunnyvale, CA", "Condo", 2900, 2900, "no pets"),
    (
        3,
        "Willow Lane",
        "Willow Lane Townhouse",
        "Santa Clara, CA",
        "Townhouse",
        3600,
        3600,
        "dogs and cats, $500 pet deposit",
    ),
    (
        4,
        "Birch Street",
        "Birch Street House",
        "Mountain View, CA",
        "House",
        4200,
        4200,
        "pets negotiable",
    ),
    (
        5,
        "Harbor View",
        "Harbor View Studio",
        "Oakland, CA",
        "Apartment",
        1850,
        1850,
        "cats only, $250 pet deposit",
    ),
    (
        6,
        "Pine Ridge",
        "Pine Ridge 3BR",
        "Fremont, CA",
        "House",
        3300,
        3300,
        "dogs and cats, $400 pet deposit",
    ),
]


class ListingDatabase:
    def __init__(self, db_path: str | None = None, redis_client: redis.Redis | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path or DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.redis_client = redis_client or redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )
        self.redis_client.ping()  # fail early when Redis is not running
        self.last_synced = False  # True when the most recent increment wrote to the database
        self._setup()

    def _setup(self) -> None:
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS rental_housing_listings (
                   id INTEGER PRIMARY KEY,
                   short_name TEXT UNIQUE NOT NULL,
                   property_title TEXT NOT NULL,
                   property_location TEXT NOT NULL,
                   property_category TEXT NOT NULL,
                   monthly_rent INTEGER NOT NULL,
                   security_deposit INTEGER NOT NULL,
                   pet_policy TEXT NOT NULL,
                   data_version INTEGER NOT NULL DEFAULT 1,
                   view_count INTEGER NOT NULL DEFAULT 0)"""
        )
        if self.conn.execute("SELECT COUNT(*) FROM rental_housing_listings").fetchone()[0] == 0:
            self.conn.executemany(
                """INSERT INTO rental_housing_listings
                   (id, short_name, property_title, property_location, property_category,
                    monthly_rent, security_deposit, pet_policy) VALUES (?,?,?,?,?,?,?,?)""",
                SEED_LISTINGS,
            )
            self.conn.commit()

    # ---- plain database helpers ---------------------------------------------------------
    def get_listing(self, listing_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM rental_housing_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_listing_in_text(self, text: str) -> dict[str, Any] | None:
        """Return the listing whose short name (for example "Maple Court") appears in the text."""
        lowered = text.lower()
        for row in self.conn.execute("SELECT * FROM rental_housing_listings"):
            if row["short_name"].lower() in lowered:
                return dict(row)
        return None

    def update_listing(self, listing_id: int, **fields: Any) -> dict[str, Any]:
        """Change a record and bump its data_version so cached answers can be recognised as stale."""
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.conn.execute(
            f"UPDATE rental_housing_listings SET {assignments}, data_version = data_version + 1 "
            "WHERE id = ?",
            (*fields.values(), listing_id),
        )
        self.conn.commit()
        return self.get_listing(listing_id)  # type: ignore[return-value]

    def restore_seed(self, listing_id: int) -> None:
        """Put one listing back to its seed values (used to repeat the stale-answer demo)."""
        seed = next(row for row in SEED_LISTINGS if row[0] == listing_id)
        self.conn.execute(
            "UPDATE rental_housing_listings SET monthly_rent = ?, security_deposit = ?, data_version = 1 "
            "WHERE id = ?",
            (seed[5], seed[6], listing_id),
        )
        self.conn.commit()

    def reset_views(self, listing_id: int) -> None:
        """Start a demo from zero: clear the Redis counter and the stored database count."""
        self.redis_client.delete(f"{PREFIX}:views:listing:{listing_id}")
        self.conn.execute(
            "UPDATE rental_housing_listings SET view_count = 0 WHERE id = ?", (listing_id,)
        )
        self.conn.commit()

    def stored_view_count(self, listing_id: int) -> int:
        row = self.conn.execute(
            "SELECT view_count FROM rental_housing_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return row["view_count"]

    # ---- Part 1: the one new method -----------------------------------------------------
    def increment_listing_views(self, listing_id: int) -> int:
        """Count one view in Redis; every 10th view is also written to the database row."""
        key = f"{PREFIX}:views:listing:{listing_id}"
        count = self.redis_client.incr(key)  # atomic, so concurrent views are never lost
        self.last_synced = False
        if count % 10 == 0:
            self.conn.execute(
                "UPDATE rental_housing_listings SET view_count = ? WHERE id = ?",
                (count, listing_id),
            )
            self.conn.commit()
            log.info("Synced views to database: listing %s has %s views", listing_id, count)
            self.last_synced = True
        return count

    def close(self) -> None:
        self.conn.close()
        self.redis_client.close()
