from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .models import ListingAmenity, RentalHousingListing, User
from .schemas import ListingCreate, ListingUpdate
from .security import hash_password

def create_user(db: Session, name: str, email: str, password: str) -> User:
    row = User(name=name, email=email, password_hash=hash_password(password))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def create_listing(db: Session, payload: ListingCreate) -> RentalHousingListing:
    row = RentalHousingListing(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def get_listing(db: Session, listing_id: int) -> RentalHousingListing | None:
    return db.get(RentalHousingListing, listing_id)

def update_listing(
    db: Session, listing_id: int, payload: ListingUpdate
) -> RentalHousingListing | None:
    row = get_listing(db, listing_id)
    if not row:
        return None

    for key, value in payload.model_dump().items():
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
