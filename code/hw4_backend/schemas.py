from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ListingBase(BaseModel):
    property_title: str = Field(min_length=1)
    property_location: str = Field(min_length=1)
    submitter_email: EmailStr
    property_description: str = Field(min_length=26)
    property_category: str = Field(pattern="^(Apartment|House|Condo|Townhouse)$")
    terms_accepted: bool = True

class ListingCreate(ListingBase): pass
class ListingUpdate(ListingBase): pass

class AmenityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amenity: str

class ListingOut(ListingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    related_rows: list[AmenityOut] = []
