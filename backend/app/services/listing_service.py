"""Listing persistence service — create, update, fetch, and filtered search."""

import os
import uuid
from dataclasses import dataclass

from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead import Lead
from app.models.listing import Listing
from app.schemas.listing import ListingCreate, ListingUpdate

# Fields whose change alters the listing's embedding text (schema rec. R3).
EMBEDDED_FIELDS = ("title", "description", "price", "property_type")

MAX_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}


class ListingValidationError(ValueError):
    """Raised when an update would leave the listing in an invalid state."""


@dataclass
class UpdateOutcome:
    """What a listing update changed, so the route can queue the right AI job."""

    listing: Listing
    text_changed: bool
    location_changed: bool


def _point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def create_listing(
    db: Session,
    broker_id: int,
    data: ListingCreate,
) -> Listing:
    """Persist a new listing and return the ORM instance.

    Converts ``data.lat`` / ``data.lng`` into a PostGIS Point
    (SRID 4326) — the API never exposes the internal Geometry type.

    This function intentionally does **not** call Person 1's
    embedding or amenities pipelines.  The calling route is
    responsible for scheduling those as FastAPI ``BackgroundTasks``
    so that persistence stays fast and the service stays focused
    on database writes only.
    """
    listing = Listing(
        broker_id=broker_id,
        title=data.title,
        description=data.description,
        price=data.price,
        property_type=data.property_type,
        location=_point(data.lat, data.lng),
        carpet_area=data.carpet_area,
        built_up_area=data.built_up_area,
        plot_area=data.plot_area,
        floor_number=data.floor_number,
        rooms=data.rooms.model_dump(exclude_none=True) if data.rooms else None,
    )

    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def get_listing(db: Session, listing_id: int) -> Listing | None:
    """Fetch a single listing by its primary key, or ``None`` if missing.

    The route is responsible for turning ``None`` into a 404 response.
    """
    return db.query(Listing).filter(Listing.id == listing_id).first()


def update_listing(db: Session, listing: Listing, data: ListingUpdate) -> UpdateOutcome:
    """Apply a partial update and report what changed.

    Raises ``ListingValidationError`` if the result would be a flat without
    ``rooms.bedrooms``.  Never calls the AI pipelines itself (see
    ``create_listing``).
    """
    sent = data.model_fields_set
    new_type = data.property_type if "property_type" in sent else listing.property_type
    if "rooms" in sent:
        new_rooms = data.rooms.model_dump(exclude_none=True) if data.rooms else None
    else:
        new_rooms = listing.rooms
    if new_type == "flat" and not (new_rooms or {}).get("bedrooms"):
        raise ListingValidationError("rooms.bedrooms is required for flats")

    text_changed = False
    for name in EMBEDDED_FIELDS:
        if name in sent:
            new_value = getattr(data, name)
            old_value = getattr(listing, name)
            if name == "price":
                changed = old_value is None or float(old_value) != float(new_value)
            else:
                changed = old_value != new_value
            if changed:
                setattr(listing, name, new_value)
                text_changed = True

    for name in ("carpet_area", "built_up_area", "plot_area", "floor_number"):
        if name in sent:
            setattr(listing, name, getattr(data, name))
    if "rooms" in sent:
        listing.rooms = new_rooms

    location_changed = False
    if "lat" in sent:
        current = to_shape(listing.location)
        if (current.y, current.x) != (data.lat, data.lng):
            listing.location = _point(data.lat, data.lng)
            location_changed = True

    db.commit()
    db.refresh(listing)
    return UpdateOutcome(listing, text_changed, location_changed)


def set_status(db: Session, listing: Listing, status: str) -> Listing:
    """Change a listing's lifecycle status (no AI call needed)."""
    listing.status = status
    db.commit()
    db.refresh(listing)
    return listing


def record_views(db: Session, listing_ids: list[int]) -> None:
    """Atomically add one view to each listing (caller commits)."""
    if listing_ids:
        db.query(Listing).filter(Listing.id.in_(listing_ids)).update(
            {Listing.view_count: Listing.view_count + 1},
            synchronize_session=False,
        )


def image_extension(content: bytes) -> str | None:
    """Return ``"jpg"`` / ``"png"`` from the file's magic bytes, else ``None``."""
    for signature, ext in _IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            return ext
    return None


def add_image(db: Session, listing: Listing, content: bytes, ext: str) -> Listing:
    """Save an already-validated image under ``UPLOAD_DIR/<listing_id>/``."""
    folder = os.path.join(settings.UPLOAD_DIR, str(listing.id))
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(folder, filename), "wb") as fh:
        fh.write(content)

    images = list(listing.images or [])
    images.append({"url": f"/uploads/{listing.id}/{filename}", "order": len(images)})
    listing.images = images
    db.commit()
    db.refresh(listing)
    return listing


def broker_listings(
    db: Session,
    broker_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[tuple[Listing, int]]:
    """A broker's listings (every status), newest first, with lead counts."""
    lead_counts = (
        db.query(Lead.listing_id, func.count(Lead.id).label("cnt"))
        .group_by(Lead.listing_id)
        .subquery()
    )
    query = (
        db.query(Listing, func.coalesce(lead_counts.c.cnt, 0))
        .outerjoin(lead_counts, lead_counts.c.listing_id == Listing.id)
        .filter(Listing.broker_id == broker_id)
    )
    if status is not None:
        query = query.filter(Listing.status == status)
    return query.order_by(Listing.created_at.desc(), Listing.id.desc()).offset(offset).limit(limit).all()


def search_listings(
    db: Session,
    filters: dict,
    limit: int = 20,
) -> list[Listing]:
    """Return listings matching the given filters.

    Currently supports:
    - ``price_min`` / ``price_max`` (float)
    - ``property_type`` (``'flat'`` | ``'house_land'``)

    Structured so additional filters can be added later without
    a rewrite.
    """
    query = db.query(Listing)

    if "price_min" in filters and filters["price_min"] is not None:
        query = query.filter(Listing.price >= filters["price_min"])
    if "price_max" in filters and filters["price_max"] is not None:
        query = query.filter(Listing.price <= filters["price_max"])
    if "property_type" in filters and filters["property_type"] is not None:
        query = query.filter(Listing.property_type == filters["property_type"])

    return query.order_by(Listing.created_at.desc()).limit(limit).all()
