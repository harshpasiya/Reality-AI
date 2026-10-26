"""Listing ORM model — cross-team contract defined in AGENTS.md §4.

Do NOT rename columns, change types, or add/remove fields without
coordinating with the AI and Frontend tracks first.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import deferred, relationship
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector

from app.core.database import Base

# Listing lifecycle (AGENTS.md §4).  Only VISIBLE_STATUSES appear in customer
# search (radius, boundary, chat); every status stays visible to the broker.
LISTING_STATUSES = ("available", "under_offer", "sold", "withdrawn")
VISIBLE_STATUSES = ("available", "under_offer")


class Listing(Base):
    """A real-estate listing published by a broker.

    Location is stored as a PostGIS Point (SRID 4326) for geospatial queries.
    The ``embedding`` column is populated by Person 1's AI pipeline
    (``ai.embeddings.embed_listings``), not by this repo.
    The ``amenities`` column is populated by Person 1's amenities service
    (``ai.amenities.amenities_service.fetch_and_cache``), not by this repo.

    ``PATCH /listings/{id}`` re-embeds the listing when its text, price or
    type changes, and calls ``fetch_and_cache(listing.id, force=True)`` when
    its location changes, so neither the embedding nor amenities go stale.
    """

    __tablename__ = "listing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    broker_id = Column(
        Integer, ForeignKey("broker.id"), nullable=False, index=True
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    property_type = Column(String, nullable=False)
    location = Column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    carpet_area = Column(Numeric, nullable=True)
    built_up_area = Column(Numeric, nullable=True)
    plot_area = Column(Numeric, nullable=True)
    floor_number = Column(Integer, nullable=True)
    # Shape: {"bedrooms": int 1-10, "bathrooms": int, "balconies": int, ...}.
    # The AI search filters on (rooms->>'bedrooms')::int; NULL for open plots.
    # none_as_null: Python None is stored as SQL NULL, not the JSON value 'null'.
    rooms = Column(JSON(none_as_null=True), nullable=True)
    # CONFIRMED: Embedding dimension = 384 (sentence-transformers all-MiniLM-L6-v2,
    # as confirmed with Person 1 / AI track). Changing this requires a DB migration
    # since existing data can't be resized in-place.  Deferred so ordinary
    # listing queries don't load 384 floats per row; written only by the AI track.
    embedding = deferred(Column(Vector(384), nullable=True))
    # Written by ai.amenities.amenities_service only — the backend reads it but
    # never writes it, and it is excluded from every request schema.
    amenities = Column(JSON(none_as_null=True), nullable=True)
    status = Column(String(20), nullable=False, server_default="available")
    # Photo list: [{"url": "/uploads/<id>/<file>", "order": 0}, ...]
    images = Column(JSON(none_as_null=True), nullable=True)
    # Times the listing was opened or shown in a chat reply (broker analytics).
    view_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "property_type IN ('flat', 'house_land')",
            name="ck_listing_property_type",
        ),
        CheckConstraint(
            "status IN ('available', 'under_offer', 'sold', 'withdrawn')",
            name="ck_listing_status",
        ),
        CheckConstraint(
            "rooms IS NULL OR rooms::jsonb->'bedrooms' IS NULL "
            "OR (rooms::jsonb->>'bedrooms') ~ '^[0-9]+$'",
            name="ck_listing_rooms_bedrooms",
        ),
        Index("ix_listing_status", "status"),
        # GiST indexes: geometry for ST_Contains, geography for ST_DWithin
        Index("idx_listing_location", "location", postgresql_using="gist"),
        Index(
            "idx_listing_location_geog",
            text("(location::geography)"),
            postgresql_using="gist",
        ),
        Index("ix_listing_bedrooms", text("((rooms->>'bedrooms')::int)")),
    )

    # Relationships
    broker = relationship("Broker", back_populates="listings")
    leads = relationship("Lead", back_populates="listing")

    def __repr__(self) -> str:
        return f"<Listing id={self.id} title={self.title!r} type={self.property_type}>"
