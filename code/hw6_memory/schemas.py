"""Pydantic validation models for rental listings and memory endpoints."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class ListingCategory(str, Enum):
    apartment = "Apartment"
    house = "House"
    condo = "Condo"
    townhouse = "Townhouse"


class ListingStatus(str, Enum):
    available = "available"
    pending = "pending"
    rented = "rented"


ShortText = Annotated[str, Field(min_length=1, max_length=100)]


class RentalListingCreate(BaseModel):
    property_title: ShortText
    property_description: str | None = Field(default=None, max_length=2000)
    listing_status: ListingStatus = ListingStatus.available
    property_category: ListingCategory
    available_on: datetime

    @field_validator("property_title")
    @classmethod
    def property_title_cannot_be_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("property_title must contain non-whitespace characters")
        return value


class RentalListingUpdate(BaseModel):
    property_title: ShortText | None = None
    property_description: str | None = Field(default=None, max_length=2000)
    listing_status: ListingStatus | None = None
    property_category: ListingCategory | None = None
    available_on: datetime | None = None

    @field_validator("property_title")
    @classmethod
    def updated_property_title_cannot_be_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("property_title must contain non-whitespace characters")
        return value


class ChatRequest(BaseModel):
    user_id: ShortText
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("user_id", "session_id", "message")
    @classmethod
    def text_cannot_be_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("value must contain non-whitespace characters")
        return value
