"""Boundary (hand-drawn polygon) filtering for property search.

Mirrors the PostGIS query logic Person 2's /listings/search-boundary
endpoint will also implement. This is intentionally a local, independent
implementation for now (see the TODO below) rather than an HTTP call to
Person 2's backend, since that endpoint isn't available during isolated
development.
"""

from __future__ import annotations

import logging
import math
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from ai.rag.listing_sql import VISIBLE_STATUS_SQL

load_dotenv()

logger = logging.getLogger(__name__)

# NOTE: this creates its own engine rather than importing one from
# retriever.py. If both modules grow more complex, consider refactoring
# to a shared ai/db.py so there's a single connection pool.
_DATABASE_URL = os.getenv("DATABASE_URL")
if not _DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and configure it, "
        "then make sure the Docker database is running (docker-compose up -d)."
    )
_engine = create_engine(_DATABASE_URL)

# A drawn boundary has tens of points; a cap stops an oversized request from
# tying up the database.
MAX_POLYGON_POINTS = 1000


class BoundaryFilterError(Exception):
    """Raised when a boundary query fails for reasons other than bad input."""


def get_candidates(polygon: list[list[float]]) -> list[int]:
    """Return listing IDs whose location falls inside a drawn polygon.

    TODO: this duplicates query logic Person 2's /listings/search-boundary
    endpoint will also implement. Once that endpoint exists, evaluate
    whether this should call it via HTTP instead of running its own query,
    to avoid the two implementations silently diverging. Keeping this
    local for now since Person 2's endpoint isn't built yet in isolated
    development (see AGENTS.md's connections section).

    Args:
        polygon: List of [lat, lng] pairs, at least 3 points. If the first
            and last points don't match, the ring is auto-closed by
            appending the first point (a common frontend omission) rather
            than raising.

    Returns:
        List of matching listing IDs. Empty list if nothing matches or the
        polygon is empty — never None.

    Raises:
        ValueError: If polygon has fewer than 3 distinct points (after
            attempting to auto-close the ring), more than MAX_POLYGON_POINTS
            points, or a point that is non-numeric, non-finite or outside
            lat -90..90 / lng -180..180. Self-intersecting polygons are
            repaired with ST_MakeValid rather than rejected.
        BoundaryFilterError: If the database query fails.
    """
    if not polygon:
        raise ValueError("polygon must contain at least 3 points, got an empty list")
    if len(polygon) > MAX_POLYGON_POINTS:
        raise ValueError(f"polygon has {len(polygon)} points; the maximum is {MAX_POLYGON_POINTS}")

    points = list(polygon)
    if points[0] != points[-1]:
        points.append(points[0])  # auto-close the ring

    if len(points) < 4:  # 3 distinct points + the closing repeat = 4
        raise ValueError(
            f"polygon must have at least 3 distinct points, got {len(points) - 1}"
        )

    # Build the WKT polygon string. Coordinates are validated floats from a
    # list already type-checked by the caller (or will raise TypeError/
    # ValueError naturally below on non-numeric input) — never
    # string-interpolated from untrusted raw text.
    try:
        coords = [(float(lat), float(lng)) for lat, lng in points]
    except (TypeError, ValueError) as e:
        raise ValueError(f"polygon contains non-numeric or malformed points: {e}") from e
    for lat, lng in coords:
        # NaN/inf would produce invalid WKT ("nan"), and an out-of-range point
        # is a frontend bug (often lat/lng swapped) that should surface as bad input.
        if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError(f"polygon point ({lat}, {lng}) is not a valid [lat, lng] pair")

    ring = ", ".join(f"{lng} {lat}" for lat, lng in coords)
    wkt_polygon = f"POLYGON(({ring}))"

    # ST_MakeValid: a hand-drawn boundary often crosses itself (a figure-8),
    # which makes ST_Contains raise a topology error instead of returning rows.
    sql = text(
        """
        SELECT id
        FROM listing
        WHERE ST_Contains(
            ST_MakeValid(ST_GeomFromText(:polygon_wkt, 4326)),
            location
        )
        AND """ + VISIBLE_STATUS_SQL
    )

    t0 = time.time()
    try:
        with _engine.connect() as conn:
            result = conn.execute(sql, {"polygon_wkt": wkt_polygon})
            ids = [row[0] for row in result]
    except Exception as e:
        logger.exception("Boundary query failed for polygon with %d points", len(points))
        raise BoundaryFilterError(f"Boundary query failed: {e}") from e

    elapsed_ms = (time.time() - t0) * 1000
    logger.debug(
        "get_candidates(): %d points -> %d matching listings (%.1fms)",
        len(points), len(ids), elapsed_ms,
    )
    return ids
