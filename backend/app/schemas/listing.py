"""Pydantic schemas for Listing data validation and serialization."""

import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

try:
    from geoalchemy2.shape import to_shape

    _GEO_AVAILABLE = True
except ImportError:
    _GEO_AVAILABLE = False

logger = logging.getLogger(__name__)

ListingStatus = Literal["available", "under_offer", "sold", "withdrawn"]


class Rooms(BaseModel):
    """Room breakdown stored in ``listing.rooms`` (AGENTS.md §4).

    ``bedrooms`` is the key the AI search filters on ("2 BHK" queries), so
    unknown keys are rejected — a typo such as ``"bedroom"`` would otherwise
    make the listing silently unsearchable.  "1 RK" is stored as ``1``.
    """

    model_config = ConfigDict(extra="forbid")

    bedrooms: int | None = Field(None, ge=1, le=10)
    bathrooms: int | None = Field(None, ge=0, le=20)
    balconies: int | None = Field(None, ge=0, le=20)
    hall: int | None = Field(None, ge=0, le=10)
    kitchen: int | None = Field(None, ge=0, le=10)
    garden: int | None = Field(None, ge=0, le=10)


class ListingBase(BaseModel):
    """Shared fields across listing create/response schemas."""

    title: str = Field(..., max_length=200, description="Listing headline")
    description: str | None = Field(None, description="Detailed description")
    price: float = Field(..., gt=0, description="Price in INR")
    property_type: Literal["flat", "house_land"] = Field(
        ..., description="Must be 'flat' or 'house_land' per AGENTS.md"
    )
    carpet_area: float | None = Field(None, ge=0)
    built_up_area: float | None = Field(None, ge=0)
    plot_area: float | None = Field(None, ge=0)
    floor_number: int | None = None


def _require_flat_bedrooms(property_type: str | None, rooms: Rooms | None) -> None:
    """Flats must state a bedroom count; houses may, open plots leave rooms null."""
    if property_type == "flat" and (rooms is None or rooms.bedrooms is None):
        raise ValueError("rooms.bedrooms is required for flats")


class ListingCreate(ListingBase):
    """Schema for creating a new listing.

    Accepts ``lat`` and ``lng`` as separate floats — the service layer
    converts them into a PostGIS Point on write.  The internal Geometry
    type is never exposed through the API.  ``amenities`` is deliberately
    absent: only the AI amenities service writes it.
    """

    model_config = ConfigDict(extra="forbid")

    rooms: Rooms | None = Field(
        None, description="Room breakdown, e.g. {'bedrooms': 2, 'bathrooms': 1}"
    )
    lat: float = Field(..., ge=-90, le=90, description="Latitude (WGS-84)")
    lng: float = Field(..., ge=-180, le=180, description="Longitude (WGS-84)")

    @model_validator(mode="after")
    def _check_rooms(self) -> "ListingCreate":
        _require_flat_bedrooms(self.property_type, self.rooms)
        return self


class ListingUpdate(BaseModel):
    """Partial update for ``PATCH /listings/{id}`` — send only changed fields.

    ``lat`` and ``lng`` must be sent together.  ``status`` has its own
    endpoint and ``amenities`` is never client-writable.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=200)
    description: str | None = None
    price: float | None = Field(None, gt=0)
    property_type: Literal["flat", "house_land"] | None = None
    carpet_area: float | None = Field(None, ge=0)
    built_up_area: float | None = Field(None, ge=0)
    plot_area: float | None = Field(None, ge=0)
    floor_number: int | None = None
    rooms: Rooms | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _check_fields(self) -> "ListingUpdate":
        sent = self.model_fields_set
        for name in ("title", "price", "property_type"):
            if name in sent and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if ("lat" in sent) != ("lng" in sent) or (
            "lat" in sent and (self.lat is None or self.lng is None)
        ):
            raise ValueError("lat and lng must be sent together")
        return self


class ListingStatusUpdate(BaseModel):
    """Body for ``PATCH /listings/{id}/status``."""

    status: ListingStatus


class ListingImage(BaseModel):
    """One photo of a listing, served from ``/uploads``."""

    url: str
    order: int


class ListingResponse(ListingBase):
    """Schema returned by listing endpoints.

    Includes ``amenities`` per AGENTS.md §3 — may be null until
    Person 1's pipeline populates it.
    ``lat`` / ``lng`` are extracted from the PostGIS ``location`` column.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    broker_id: int
    rooms: dict[str, Any] | None = Field(
        None, description="Room breakdown as JSON, e.g. {'bedrooms': 2, 'bathrooms': 1}"
    )
    lat: float | None = Field(None, ge=-90, le=90, description="Latitude (WGS-84)")
    lng: float | None = Field(None, ge=-180, le=180, description="Longitude (WGS-84)")
    amenities: dict[str, Any] | None = Field(
        None,
        description=(
            "Cached nearby-amenity data (schools, hospitals, restaurants, "
            "transit, parks) — populated by AI pipeline, may be null"
        ),
    )
    status: ListingStatus = "available"
    images: list[ListingImage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_orm_row(cls, data: Any) -> Any:
        """Copy ORM columns into a dict and derive lat/lng from ``location``.

        Works on a copy so the ORM object is never mutated, and skips the
        deferred ``embedding`` column so serialising never loads it.
        """
        if not isinstance(data, dict) and hasattr(data, "__table__"):
            data = {
                c.name: getattr(data, c.name)
                for c in data.__table__.columns
                if c.name != "embedding"
            }
        if isinstance(data, dict):
            loc = data.get("location")
            if loc is not None and _GEO_AVAILABLE and "lat" not in data:
                try:
                    point = to_shape(loc)
                    data = {**data, "lat": point.y, "lng": point.x}
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to extract lat/lng from location geometry: %s", exc)
            if data.get("images") is None:
                data = {**data, "images": []}
        return data


class BrokerListingItem(ListingResponse):
    """A listing in the broker's own dashboard, with its counters."""

    view_count: int = 0
    lead_count: int = 0
