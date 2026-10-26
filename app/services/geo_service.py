"""Geospatial query service — radius and boundary search on listings."""

from sqlalchemy.orm import Session
from sqlalchemy import cast, func
from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement

from app.models.listing import Listing, VISIBLE_STATUSES


def search_by_radius(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int = 20,
    filters: dict | None = None,
) -> list[Listing]:
    """Return customer-visible listings within *radius_km* of the given point.

    Parameters
    ----------
    lat : float
        Latitude, must be in ``[-90, 90]``.
    lng : float
        Longitude, must be in ``[-180, 180]``.
    radius_km : float
        Search radius in kilometres, capped at 100 km to prevent
        accidentally huge queries that would scan the entire table.
    limit : int
        Maximum results to return.

    Notes
    -----
    Both sides of the distance comparison are cast to ``::geography``
    so that the radius (converted to metres) is interpreted as an
    actual surface distance, **not** in degrees.  This is a common
    correctness bug — without the cast, 1 degree ≈ 111 km at the
    equator but much less at higher latitudes.  Do not "simplify" this
    by removing the cast.

    Sold and withdrawn listings are excluded (``VISIBLE_STATUSES``).
    The geography GiST index ``idx_listing_location_geog`` serves this query.
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be in [-90, 90], got {lat}")
    if not (-180 <= lng <= 180):
        raise ValueError(f"lng must be in [-180, 180], got {lng}")
    if radius_km <= 0:
        raise ValueError(f"radius_km must be positive, got {radius_km}")
    # Cap at 100 km — prevents an accidentally huge query
    radius_km = min(radius_km, 100.0)

    point = WKTElement(f"POINT({lng} {lat})", srid=4326)
    radius_m = radius_km * 1000

    query = db.query(Listing).filter(
        Listing.status.in_(VISIBLE_STATUSES),
        func.ST_DWithin(
            cast(Listing.location, Geography),
            cast(point, Geography),
            radius_m,
        ),
    )

    if filters:
        if "price_min" in filters and filters["price_min"] is not None:
            query = query.filter(Listing.price >= filters["price_min"])
        if "price_max" in filters and filters["price_max"] is not None:
            query = query.filter(Listing.price <= filters["price_max"])
        if "property_type" in filters and filters["property_type"] is not None:
            query = query.filter(Listing.property_type == filters["property_type"])

    return (
        query.order_by(
            func.ST_Distance(
                cast(Listing.location, Geography),
                cast(point, Geography),
            )
        )
        .limit(limit)
        .all()
    )


def _polygon_geom(polygon: list[list[float]]):
    """Build a repaired PostGIS polygon from validated ``[lat, lng]`` points.

    WKT standard uses ``(longitude, latitude)`` coordinate ordering, so the
    input pairs are swapped.  ``ST_MakeValid`` repairs self-crossing shapes
    (a figure-8 becomes two lobes) instead of rejecting them — the same rule
    as ``ai.rag.boundary_filter.get_candidates()``.
    """
    wkt_pts = ", ".join(f"{lng} {lat}" for lat, lng in polygon)
    return func.ST_MakeValid(WKTElement(f"POLYGON(({wkt_pts}))", srid=4326))


def boundary_candidate_ids(db: Session, polygon: list[list[float]]) -> list[int]:
    """IDs of customer-visible listings inside the polygon.

    Backend-side equivalent of ``get_candidates()``, used when the ``ai/``
    package is not installed (isolated backend development).
    """
    rows = (
        db.query(Listing.id)
        .filter(
            Listing.status.in_(VISIBLE_STATUSES),
            func.ST_Contains(_polygon_geom(polygon), Listing.location),
        )
        .all()
    )
    return [r.id for r in rows]


def visible_listings_by_ids(
    db: Session, ids: list[int], limit: int | None = None
) -> list[Listing]:
    """Load customer-visible listings for *ids*, preserving the order of *ids*."""
    if not ids:
        return []
    rows = (
        db.query(Listing)
        .filter(Listing.id.in_(ids), Listing.status.in_(VISIBLE_STATUSES))
        .all()
    )
    by_id = {row.id: row for row in rows}
    ordered = [by_id[i] for i in ids if i in by_id]
    return ordered[:limit] if limit is not None else ordered
