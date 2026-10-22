from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OwnerBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None


class OwnerOut(OwnerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """A reader account registration payload; privileged users are seeded locally."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class ListingBase(BaseModel):
    listing_code: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    property_title: str = Field(min_length=1)
    property_location: str = Field(min_length=1)
    submitter_email: EmailStr
    property_description: str = Field(min_length=26)
    property_category: str = Field(pattern="^(Apartment|House|Condo|Townhouse)$")
    terms_accepted: bool = True
    available_units: int = Field(default=1, ge=0)
    owner_id: int = Field(gt=0)


class ListingCreate(ListingBase):
    """Fields accepted when a listing is created."""


class ListingUpdate(ListingBase):
    """Fields accepted when a listing is updated."""


class AmenityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amenity: str


class ListingOut(ListingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    related_rows: list[AmenityOut] = []
