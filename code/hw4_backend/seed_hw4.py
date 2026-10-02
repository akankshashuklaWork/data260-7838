"""Seed 5,000 listings and 200 related rows deterministically with SEED=7838."""
import random
from sqlalchemy import delete
from .database import Base, SessionLocal, engine
from .models import ListingAmenity, PropertyOwner, RentalHousingListing

SEED = 7838

def main():
    Base.metadata.create_all(bind=engine)
    rng = random.Random(SEED)
    db = SessionLocal()
    try:
        db.execute(delete(ListingAmenity))
        db.execute(delete(RentalHousingListing))
        db.execute(delete(PropertyOwner))
        db.commit()
        owners = [
            PropertyOwner(
                first_name=f"Owner{i + 1}",
                last_name="Housing",
                email=f"owner{i + 1}@example.com",
            )
            for i in range(20)
        ]
        db.add_all(owners)
        db.flush()
        rows = []
        for i in range(5000):
            rows.append(
                RentalHousingListing(
                    listing_code=f"HW4-{i + 1:05d}",
                    property_title=f"Seed listing {i + 1}",
                    property_location=f"San Jose neighborhood {i % 20}",
                    submitter_email=f"seed{i}@example.com",
                    property_description=(
                        "Deterministic HW4 rental listing used for database "
                        "and N+1 measurements."
                    ),
                    property_category=rng.choice(
                        ["Apartment", "House", "Condo", "Townhouse"]
                    ),
                    terms_accepted=True,
                    available_units=(i % 4) + 1,
                    owner_id=owners[i % len(owners)].id,
                )
            )
        db.add_all(rows)
        db.flush()
        amenities = ["parking", "laundry", "balcony", "gym"]
        for i in range(200):
            db.add(
                ListingAmenity(
                    listing_id=rows[i % len(rows)].id,
                    amenity=rng.choice(amenities),
                )
            )
        db.commit()
        print(f"seeded owners={len(owners)} listings={len(rows)} related_rows=200 seed={SEED}")
    finally: db.close()

if __name__ == "__main__": main()
