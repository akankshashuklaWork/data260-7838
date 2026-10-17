"""CRUD routes for the MongoDB rental-listing document view."""

from fastapi import APIRouter, HTTPException, status
from pymongo.errors import PyMongoError

from ..db import listings_collection
from ..schemas import RentalListingCreate, RentalListingUpdate
from ..utils import is_object_id, object_id, serialize_document, utc_now


router = APIRouter(prefix="/api/rental-listings", tags=["rental-listings"])


def _find_listing(listing_id: str) -> dict:
    if not is_object_id(listing_id):
        raise HTTPException(status_code=400, detail="listing_id must be a valid MongoDB ObjectId")
    listing = listings_collection().find_one({"_id": object_id(listing_id)})
    if listing is None:
        raise HTTPException(status_code=404, detail="rental listing not found")
    return listing


@router.post("", status_code=status.HTTP_201_CREATED)
def create_listing(payload: RentalListingCreate) -> dict:
    document = payload.model_dump(mode="python")
    document["listing_status"] = document["listing_status"].value
    document["property_category"] = document["property_category"].value
    timestamp = utc_now()
    document["created_at"] = timestamp
    document["updated_at"] = timestamp
    try:
        result = listings_collection().insert_one(document)
        return serialize_document(listings_collection().find_one({"_id": result.inserted_id}))
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while creating rental listing") from error


@router.get("")
def list_listings() -> list[dict]:
    try:
        return [serialize_document(item) for item in listings_collection().find().sort("created_at", -1)]
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while retrieving rental listings") from error


@router.get("/{listing_id}")
def get_listing(listing_id: str) -> dict:
    try:
        return serialize_document(_find_listing(listing_id))
    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while retrieving rental listing") from error


@router.put("/{listing_id}")
def update_listing(listing_id: str, payload: RentalListingUpdate) -> dict:
    try:
        _find_listing(listing_id)
        updates = payload.model_dump(exclude_unset=True, mode="python")
        if not updates:
            raise HTTPException(status_code=400, detail="at least one field is required for an update")
        for field in ("listing_status", "property_category"):
            if field in updates and updates[field] is not None:
                updates[field] = updates[field].value
        updates["updated_at"] = utc_now()
        listings_collection().update_one({"_id": object_id(listing_id)}, {"$set": updates})
        return serialize_document(_find_listing(listing_id))
    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while updating rental listing") from error


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(listing_id: str) -> None:
    try:
        _find_listing(listing_id)
        listings_collection().delete_one({"_id": object_id(listing_id)})
    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while deleting rental listing") from error
