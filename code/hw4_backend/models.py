from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

class SessionToken(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

class RentalHousingListing(Base):
    __tablename__ = "rental_housing_listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_title: Mapped[str] = mapped_column(String(255), nullable=False)
    property_location: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    submitter_email: Mapped[str] = mapped_column(String(255), nullable=False)
    property_description: Mapped[str] = mapped_column(Text, nullable=False)
    property_category: Mapped[str] = mapped_column(String(32), nullable=False)
    terms_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    related_rows = relationship("ListingAmenity", back_populates="listing", cascade="all, delete-orphan")

Index("ix_listing_location_category", RentalHousingListing.property_location, RentalHousingListing.property_category)

class ListingAmenity(Base):
    __tablename__ = "listing_amenities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("rental_housing_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    amenity: Mapped[str] = mapped_column(String(100), nullable=False)
    listing = relationship("RentalHousingListing", back_populates="related_rows")
