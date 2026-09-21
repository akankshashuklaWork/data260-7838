"""FastAPI backend for the cumulative DATA 260 rental housing application."""

import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router

APP_DIR = Path(__file__).resolve().parent


class ListingInput(BaseModel):
    propertyTitle: str = Field(min_length=1)
    propertyLocation: str = Field(min_length=1)
    submitterEmail: str = Field(min_length=3)
    propertyDescription: str = Field(min_length=26)
    propertyCategory: str = Field(min_length=1)


class Listing(ListingInput):
    id: int


app = FastAPI(title="Rental Housing Listings API")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY") or secrets.token_urlsafe(32),
    session_cookie="s7838_session",
    max_age=60 * 60,
    same_site="lax",
    https_only=True,
)
app.include_router(auth_router)

listings: list[Listing] = [
    Listing(id=1, propertyTitle="Willow Glen two-bedroom", propertyLocation="San Jose, CA", submitterEmail="housing@example.com", propertyDescription="Bright two-bedroom home with parking and a shared garden near transit.", propertyCategory="Apartment"),
    Listing(id=2, propertyTitle="Northside family home", propertyLocation="Santa Clara, CA", submitterEmail="listings@example.com", propertyDescription="Quiet three-bedroom house with a private yard and updated kitchen.", propertyCategory="House"),
]


@app.get("/listings", include_in_schema=False)
def listings_page() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/styles.css", include_in_schema=False)
def styles() -> FileResponse:
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/script.js", include_in_schema=False)
def script() -> FileResponse:
    return FileResponse(APP_DIR / "script.js", media_type="application/javascript")


@app.get("/auth.css", include_in_schema=False)
def auth_styles() -> FileResponse:
    return FileResponse(APP_DIR / "auth.css", media_type="text/css")


@app.get("/api/listings", response_model=list[Listing])
def get_listings(search: Annotated[str | None, Query(max_length=100)] = None) -> list[Listing]:
    if not search or not search.strip():
        return listings
    term = search.strip().casefold()
    return [listing for listing in listings if term in listing.propertyTitle.casefold() or term in listing.propertyLocation.casefold()]


@app.post("/api/listings", status_code=303)
def create_listing(payload: ListingInput) -> RedirectResponse:
    next_id = max((listing.id for listing in listings), default=0) + 1
    listing = Listing(id=next_id, **payload.model_dump())
    listings.append(listing)
    return RedirectResponse(url="/listings", status_code=303)


@app.put("/api/listings/1", status_code=303)
def update_first_listing(payload: ListingInput) -> RedirectResponse:
    for index, listing in enumerate(listings):
        if listing.id == 1:
            updated = Listing(id=1, **payload.model_dump())
            listings[index] = updated
            return RedirectResponse(url="/listings", status_code=303)
    raise HTTPException(status_code=404, detail="Listing ID 1 does not exist")


@app.delete("/api/listings/highest", status_code=303)
def delete_highest_listing() -> RedirectResponse:
    if not listings:
        raise HTTPException(status_code=404, detail="No listings are available")
    highest = max(listings, key=lambda listing: listing.id)
    listings.remove(highest)
    return RedirectResponse(url="/listings", status_code=303)
