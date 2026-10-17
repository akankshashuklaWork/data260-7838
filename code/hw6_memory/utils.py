"""Small serialization and token-accounting helpers shared by the route modules."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_object_id(value: str) -> bool:
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def object_id(value: str) -> ObjectId:
    return ObjectId(value)


def serialize_document(value: Any) -> Any:
    """Convert MongoDB values into JSON-safe values without changing their names."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_document(item) for item in value]
    if isinstance(value, dict):
        return {"id" if key == "_id" else key: serialize_document(item) for key, item in value.items()}
    return value


def estimate_tokens(text: str) -> int:
    """Use the same documented four-characters-per-token estimate as the HW1 adapter."""
    return max(1, len(text) // 4)


def message_text(role: str, content: str) -> str:
    return f"{role}: {content}"
