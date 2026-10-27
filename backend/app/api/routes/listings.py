"""Listing routes — create, fetch, search, edit, status, withdraw and photos."""

import logging
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.broker import Broker
from app.models.listing import Listing
from app.schemas.listing import (
    ListingCreate,
    ListingResponse,
    ListingStatusUpdate,
    ListingUpdate,
)
from app.services import listing_service, geo_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Listings"])


# ---------------------------------------------------------------------------
# AI pipeline helpers (graceful when ai/ package is not yet available)
# ---------------------------------------------------------------------------


def _queue_embed_single(background_tasks: BackgroundTasks, listing_id: int) -> None:
    """Queue ``embed_single(listing_id)`` if Person 1's package is importable."""
    try:
        from ai.embeddings.embed_listings import embed_single  # type: ignore[import-untyped]

        background_tasks.add_task(embed_single, listing_id)
        logger.info("Queued embed_single for listing %s", listing_id)
    except ImportError:
        logger.warning(
            "ai.embeddings.embed_listings not available — skipping embed_single "
            "for listing %s (expected during isolated backend development)",
            listing_id,
        )
    except Exception:  # installed but failed while importing — never fail the request
        logger.exception(
            "ai.embeddings.embed_listings failed to import; listing %s not embedded", listing_id
        )


def _queue_fetch_and_cache(
    background_tasks: BackgroundTasks, listing_id: int, force: bool = False
) -> None:
    """Queue ``fetch_and_cache`` (which re-embeds the listing itself)."""
    try:
        from ai.amenities.amenities_service import fetch_and_cache  # type: ignore[import-untyped]

        if force:
            background_tasks.add_task(fetch_and_cache, listing_id, force=True)
        else:
            background_tasks.add_task(fetch_and_cache, listing_id)
        logger.info("Queued fetch_and_cache(force=%s) for listing %s", force, listing_id)
    except ImportError:
        logger.warning(
            "ai.amenities.amenities_service not available — skipping fetch_and_cache "
            "for listing %s (expected during isolated backend development)",
            listing_id,
        )
    except Exception:  # installed but failed while importing — never fail the request
        logger.exception(
            "ai.amenities.amenities_service failed to import; listing %s not enriched", listing_id
        )


def _owned_listing(db: Session, listing_id: int, current_user) -> Listing:
    """Return the listing if *current_user* is the broker who owns it."""
    if not isinstance(current_user, Broker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can manage listings",
        )
    listing = listing_service.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing with id {listing_id} not found",
        )
    if listing.broker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own listings",
        )
    return listing


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new listing (broker only)",
)
def create_listing(
    body: ListingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ListingResponse:
    """Create a listing, then queue AI embedding + amenities caching.

    Only authenticated brokers may call this endpoint.  The AI background
    tasks (``embed_single`` and ``fetch_and_cache``) are scheduled but not
    awaited — if the ``ai/`` package is missing, a warning is logged and
    the listing is still created successfully.
    """
    if not isinstance(current_user, Broker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can create listings",
        )

    listing = listing_service.create_listing(db, broker_id=current_user.id, data=body)

    # Queue Person 1's pipelines — uses embed_single (per-listing),
    # NOT run() which is only for the initial batch pass over seeded data.
    _queue_embed_single(background_tasks, listing.id)
    _queue_fetch_and_cache(background_tasks, listing.id)

    return listing  # type: ignore[return-value]


@router.get(
    "/listings/search",
    response_model=list[ListingResponse],
    summary="Search listings by radius around a point with optional price and property type filters",
)
def search_listings(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: float = Query(..., gt=0, le=100, description="Search radius in km"),
    price_min: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    price_max: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    property_type: Optional[Literal["flat", "house_land"]] = Query(
        None, description="Filter by property type ('flat' or 'house_land')"
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
) -> list[ListingResponse]:
    """Return available / under-offer listings within *radius_km* of the point."""
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="price_min must not be greater than price_max",
        )
    filters = {}
    if price_min is not None:
        filters["price_min"] = price_min
    if price_max is not None:
        filters["price_max"] = price_max
    if property_type is not None:
        filters["property_type"] = property_type

    results = geo_service.search_by_radius(
        db, lat=lat, lng=lng, radius_km=radius_km, limit=limit, filters=filters
    )
    return results  # type: ignore[return-value]


@router.get(
    "/listings/{listing_id}",
    response_model=ListingResponse,
    summary="Fetch a single listing by ID",
)
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
) -> ListingResponse:
    """Return the listing including cached amenities and status, or 404.

    Sold and withdrawn listings are still returned (with their ``status``)
    so saved links keep working; search endpoints hide them.  Each fetch
    counts as one view in broker analytics.
    """
    listing = listing_service.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing with id {listing_id} not found",
        )
    listing_service.record_views(db, [listing.id])
    db.commit()
    return listing  # type: ignore[return-value]


@router.patch(
    "/listings/{listing_id}",
    response_model=ListingResponse,
    summary="Edit a listing (owning broker only)",
)
def update_listing(
    listing_id: int,
    body: ListingUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ListingResponse:
    """Apply a partial update, then refresh what the AI layer derived from it.

    A location change queues ``fetch_and_cache(id, force=True)`` (which
    re-embeds afterwards); a title, description, price or type change queues
    ``embed_single(id)``.  Neither delays the response, and a failed
    re-embed never fails the update.
    """
    listing = _owned_listing(db, listing_id, current_user)
    try:
        outcome = listing_service.update_listing(db, listing, body)
    except listing_service.ListingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    if outcome.location_changed:
        _queue_fetch_and_cache(background_tasks, listing.id, force=True)
    elif outcome.text_changed:
        _queue_embed_single(background_tasks, listing.id)

    return outcome.listing  # type: ignore[return-value]


@router.patch(
    "/listings/{listing_id}/status",
    response_model=ListingResponse,
    summary="Mark a listing available, under offer, sold or withdrawn (owning broker only)",
)
def update_listing_status(
    listing_id: int,
    body: ListingStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ListingResponse:
    """Change the lifecycle status; sold / withdrawn listings leave customer search."""
    listing = _owned_listing(db, listing_id, current_user)
    return listing_service.set_status(db, listing, body.status)  # type: ignore[return-value]


@router.delete(
    "/listings/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw a listing (owning broker only)",
)
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Response:
    """Soft delete: sets ``status = 'withdrawn'``.

    The row is kept so the broker's leads and analytics history survive
    (a hard delete would also fail while leads reference the listing).
    """
    listing = _owned_listing(db, listing_id, current_user)
    listing_service.set_status(db, listing, "withdrawn")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/listings/{listing_id}/images",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a listing photo — JPEG or PNG up to 5 MB (owning broker only)",
)
async def upload_listing_image(
    listing_id: int,
    file: UploadFile = File(..., description="JPEG or PNG, at most 5 MB"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ListingResponse:
    """Store the photo under ``/uploads/<listing_id>/`` and append it to ``images``."""
    listing = _owned_listing(db, listing_id, current_user)

    content = await file.read(listing_service.MAX_IMAGE_BYTES + 1)
    if len(content) > listing_service.MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be at most 5 MB",
        )
    ext = listing_service.image_extension(content)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG and PNG images are accepted",
        )

    return listing_service.add_image(db, listing, content, ext)  # type: ignore[return-value]
