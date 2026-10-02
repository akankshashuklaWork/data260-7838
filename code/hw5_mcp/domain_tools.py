"""The three safe domain tools shared by the MCP server and agent harness.

The default store is deterministic and offline-friendly.  A SQLAlchemy-backed
adapter is also provided for running the same tools against the ``s7838_rel``
application database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


Envelope = dict[str, Any]


class DomainStore(Protocol):
    def search(self, query: str, limit: int) -> list[dict[str, Any]]: ...
    def detail(self, listing_id: int) -> dict[str, Any] | None: ...
    def aggregate(self, owner_id: int) -> dict[str, Any] | None: ...


@dataclass
class MemoryDomainStore:
    """Small deterministic fixture used by offline tests and local MCP smoke tests."""

    owners: list[dict[str, Any]] = field(default_factory=list)
    listings: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def demo(cls) -> "MemoryDomainStore":
        owners = [
            {"id": 1, "first_name": "Maya", "last_name": "Chen", "email": "maya@example.com"},
            {"id": 2, "first_name": "Jordan", "last_name": "Lee", "email": "jordan@example.com"},
        ]
        listings = [
            {"id": 1, "listing_code": "SJ-100", "property_title": "Willow Glen Cottage", "property_location": "San Jose", "property_category": "House", "available_units": 1, "owner_id": 1},
            {"id": 2, "listing_code": "SJ-101", "property_title": "Downtown Apartment", "property_location": "San Jose", "property_category": "Apartment", "available_units": 2, "owner_id": 1},
            {"id": 3, "listing_code": "MT-200", "property_title": "Mountain View Condo", "property_location": "Mountain View", "property_category": "Condo", "available_units": 1, "owner_id": 2},
        ]
        return cls(owners=owners, listings=listings)

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        needle = query.casefold()
        matches = [
            {k: row[k] for k in ("id", "listing_code", "property_title", "property_location", "property_category", "available_units", "owner_id")}
            for row in self.listings
            if needle in " ".join(str(row[k]) for k in ("listing_code", "property_title", "property_location", "property_category")).casefold()
        ]
        return matches[:limit]

    def detail(self, listing_id: int) -> dict[str, Any] | None:
        row = next((item for item in self.listings if item["id"] == listing_id), None)
        if row is None:
            return None
        owner = next((item for item in self.owners if item["id"] == row["owner_id"]), None)
        return {**row, "owner": owner}

    def aggregate(self, owner_id: int) -> dict[str, Any] | None:
        owner = next((item for item in self.owners if item["id"] == owner_id), None)
        if owner is None:
            return None
        rows = [item for item in self.listings if item["owner_id"] == owner_id]
        return {
            "owner": owner,
            "listing_count": len(rows),
            "total_available_units": sum(item["available_units"] for item in rows),
            "listing_ids": [item["id"] for item in rows],
        }


class SqlAlchemyDomainStore:
    """Adapter over the existing ``s7838_rel`` SQLAlchemy session factory."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        from sqlalchemy import or_, select
        from hw4_backend.models import RentalHousingListing

        with self.session_factory() as db:
            needle = f"%{query}%"
            rows = db.scalars(
                select(RentalHousingListing)
                .where(or_(RentalHousingListing.listing_code.like(needle), RentalHousingListing.property_title.like(needle), RentalHousingListing.property_location.like(needle), RentalHousingListing.property_category.like(needle)))
                .order_by(RentalHousingListing.id)
                .limit(limit)
            ).all()
            return [_listing_dict(row) for row in rows]

    def detail(self, listing_id: int) -> dict[str, Any] | None:
        from hw4_backend.models import RentalHousingListing

        with self.session_factory() as db:
            row = db.get(RentalHousingListing, listing_id)
            if row is None:
                return None
            return _listing_dict(row, detail=True)

    def aggregate(self, owner_id: int) -> dict[str, Any] | None:
        from sqlalchemy import func, select
        from hw4_backend.models import PropertyOwner, RentalHousingListing

        with self.session_factory() as db:
            owner = db.get(PropertyOwner, owner_id)
            if owner is None:
                return None
            rows = db.scalars(select(RentalHousingListing).where(RentalHousingListing.owner_id == owner_id).order_by(RentalHousingListing.id)).all()
            return {"owner": {"id": owner.id, "first_name": owner.first_name, "last_name": owner.last_name, "email": owner.email}, "listing_count": len(rows), "total_available_units": sum(row.available_units for row in rows), "listing_ids": [row.id for row in rows]}


def _listing_dict(row: Any, detail: bool = False) -> dict[str, Any]:
    value = {"id": row.id, "listing_code": row.listing_code, "property_title": row.property_title, "property_location": row.property_location, "property_category": row.property_category, "available_units": row.available_units, "owner_id": row.owner_id}
    if detail:
        owner = getattr(row, "owner", None)
        value["owner"] = {"id": owner.id, "first_name": owner.first_name, "last_name": owner.last_name, "email": owner.email} if owner else None
    return value


def ok(data: Any) -> Envelope:
    return {"ok": True, "data": data, "error": None}


def error(message: str) -> Envelope:
    return {"ok": False, "data": None, "error": message}


def _validate_inputs(name: str, inputs: dict[str, Any]) -> str | None:
    if not isinstance(inputs, dict):
        return "inputs must be a JSON object"
    if name == "search":
        query = inputs.get("query")
        limit = inputs.get("limit", 10)
        if not isinstance(query, str) or len(query.strip()) < 2:
            return "query must be a non-empty string of at least 2 characters"
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 25:
            return "limit must be an integer from 1 through 25"
    elif name == "detail":
        if not isinstance(inputs.get("listing_id"), int) or inputs["listing_id"] <= 0:
            return "listing_id must be a positive integer"
    elif name == "aggregate":
        if not isinstance(inputs.get("owner_id"), int) or inputs["owner_id"] <= 0:
            return "owner_id must be a positive integer"
    else:
        return f"unknown tool: {name}"
    return None


def execute_tool(name: str, inputs: dict[str, Any], store: DomainStore | None = None) -> str:
    """Execute one domain tool and always return a JSON envelope string."""

    import json

    store = store or MemoryDomainStore.demo()
    invalid = _validate_inputs(name, inputs)
    if invalid:
        return json.dumps(error(invalid), sort_keys=True)

    # Domain safety rule: do not allow a broad export of the listing inventory.
    if name == "search" and inputs["query"].strip().casefold() in {"*", "all"} and inputs.get("limit", 10) > 10:
        return json.dumps(error("Safety rule blocked broad listing export; use a specific query or limit 10."), sort_keys=True)

    try:
        if name == "search":
            result = store.search(inputs["query"].strip(), inputs.get("limit", 10))
            return json.dumps(ok(result), sort_keys=True)
        if name == "detail":
            result = store.detail(inputs["listing_id"])
            return json.dumps(ok(result) if result is not None else error("Listing not found"), sort_keys=True)
        result = store.aggregate(inputs["owner_id"])
        return json.dumps(ok(result) if result is not None else error("Owner not found"), sort_keys=True)
    except Exception as exc:  # the single entry point must not crash its caller
        return json.dumps(error(f"domain operation failed: {exc}"), sort_keys=True)
