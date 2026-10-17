"""PyMongo connection, collection accessors, and MongoDB validators for HW6."""

from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True)


def get_db() -> Database:
    settings = get_settings()
    return get_client()[settings.mongodb_db]


def listings_collection():
    return get_db()["rental_listings"]


def messages_collection():
    return get_db()["messages"]


def summaries_collection():
    return get_db()["summaries"]


def episodes_collection():
    return get_db()["episodes"]


LISTING_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["property_title", "listing_status", "property_category", "available_on", "created_at", "updated_at"],
        "properties": {
            "property_title": {"bsonType": "string", "minLength": 1, "maxLength": 100},
            "property_description": {"bsonType": ["string", "null"], "maxLength": 2000},
            "listing_status": {"enum": ["available", "pending", "rented"]},
            "property_category": {"enum": ["Apartment", "House", "Condo", "Townhouse"]},
            "available_on": {"bsonType": "date"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}


def ensure_database_schema() -> None:
    """Create the four collections, document validation, and query-supporting indexes."""
    db = get_db()
    existing = set(db.list_collection_names())
    if "rental_listings" not in existing:
        db.create_collection("rental_listings", validator=LISTING_VALIDATOR, validationLevel="strict")
    else:
        db.command({"collMod": "rental_listings", "validator": LISTING_VALIDATOR, "validationLevel": "strict"})

    for name in ("messages", "summaries", "episodes"):
        if name not in existing:
            db.create_collection(name)

    listings_collection().create_index([("created_at", DESCENDING)])
    messages_collection().create_index([("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)])
    summaries_collection().create_index([("user_id", ASCENDING), ("scope", ASCENDING), ("created_at", DESCENDING)])
    episodes_collection().create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
