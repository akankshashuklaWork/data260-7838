"""Seed 5,000 listings and 200 related rows deterministically with SEED=7838."""
import random
from sqlalchemy import delete
from .database import Base, db_session_basede26, engine
from .models import ListingAmenity, RentalHousingListing

SEED = 7838

def main():
    Base.metadata.create_all(bind=engine)
    rng = random.Random(SEED)
    db = db_session_basede26()
    try:
        db.execute(delete(ListingAmenity)); db.execute(delete(RentalHousingListing)); db.commit()
        rows = []
        for i in range(5000):
            rows.append(RentalHousingListing(property_title=f"Seed listing {i + 1}", property_location=f"San Jose neighborhood {i % 20}", submitter_email=f"seed{i}@example.com", property_description="Deterministic HW4 rental listing used for database and N+1 measurements.", property_category=rng.choice(["Apartment", "House", "Condo", "Townhouse"]), terms_accepted=True))
        db.add_all(rows); db.flush()
        for i in range(200): db.add(ListingAmenity(listing_id=rows[i % len(rows)].id, amenity=rng.choice(["parking", "laundry", "balcony", "gym"])))
        db.commit(); print(f"seeded listings={len(rows)} related_rows=200 seed={SEED}")
    finally: db.close()

if __name__ == "__main__": main()
