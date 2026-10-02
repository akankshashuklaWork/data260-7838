from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .models import ListingAmenity, PropertyOwner, RentalHousingListing, User
from .schemas import ListingCreate, ListingUpdate, OwnerCreate, OwnerUpdate
from .security import hash_password

def create_user(db: Session, name: str, email: str, password: str) -> User:
    row = User(name=name, email=email, password_hash=hash_password(password))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def create_listing(db: Session, payload: ListingCreate) -> RentalHousingListing:
    if not db.get(PropertyOwner, payload.owner_id):
        raise ValueError("Owner not found for owner_id")
    row = RentalHousingListing(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_owner(db: Session, payload: OwnerCreate) -> PropertyOwner:
    row = PropertyOwner(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_owners(db: Session, offset: int, limit: int) -> list[PropertyOwner]:
    return db.scalars(select(PropertyOwner).order_by(PropertyOwner.id).offset(offset).limit(limit)).all()


def get_owner(db: Session, owner_id: int) -> PropertyOwner | None:
    return db.get(PropertyOwner, owner_id)


def update_owner(db: Session, owner_id: int, payload: OwnerUpdate) -> PropertyOwner | None:
    row = get_owner(db, owner_id)
    if not row:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_owner(db: Session, owner_id: int) -> PropertyOwner | None:
    row = get_owner(db, owner_id)
    if not row:
        return None
    if db.scalar(select(RentalHousingListing.id).where(RentalHousingListing.owner_id == owner_id).limit(1)):
        raise ValueError("Cannot delete owner with associated listings")
    db.delete(row)
    db.commit()
    return row

def get_listing(db: Session, listing_id: int) -> RentalHousingListing | None:
    return db.get(RentalHousingListing, listing_id)


def list_listings(db: Session, offset: int, limit: int) -> list[RentalHousingListing]:
    statement = (
        select(RentalHousingListing)
        .options(joinedload(RentalHousingListing.owner), joinedload(RentalHousingListing.related_rows))
        .order_by(RentalHousingListing.id)
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).unique().all()


def listings_by_owner(db: Session, owner_id: int) -> list[RentalHousingListing]:
    if not get_owner(db, owner_id):
        raise ValueError("Owner not found")
    return db.scalars(
        select(RentalHousingListing).where(RentalHousingListing.owner_id == owner_id).order_by(RentalHousingListing.id)
    ).all()

def update_listing(
    db: Session, listing_id: int, payload: ListingUpdate
) -> RentalHousingListing | None:
    row = get_listing(db, listing_id)
    if not row:
        return None

    data = payload.model_dump()
    if not db.get(PropertyOwner, data["owner_id"]):
        raise ValueError("Owner not found for owner_id")
    for key, value in data.items():
        setattr(row, key, value)

    db.commit()
    db.refresh(row)
    return row

def delete_listing(db: Session, listing_id: int) -> RentalHousingListing | None:
    row = get_listing(db, listing_id)
    if not row:
        return None

    db.delete(row)
    db.commit()
    return row

def list_naive(
    db: Session, offset: int, limit: int
) -> list[RentalHousingListing]:
    rows = db.scalars(select(RentalHousingListing).offset(offset).limit(limit)).all()
    for row in rows: row.related_rows
    return rows

def list_fixed(
    db: Session, offset: int, limit: int
) -> list[RentalHousingListing]:
    statement = (
        select(RentalHousingListing)
        .options(joinedload(RentalHousingListing.related_rows))
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).unique().all()

def add_amenity(db: Session, listing_id: int, amenity: str):
    row = ListingAmenity(listing_id=listing_id, amenity=amenity)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
