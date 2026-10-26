"""Nearby-amenities enrichment via the Google Places API.

Caches nearby schools, hospitals, restaurants, transit, and parks for a
listing, INCLUDING each place's Google rating and review count. This is
called once, at listing-creation time (or on-demand for backfilling) —
never live during a chat or search request. See AGENTS.md's "Hard Rules"
section: amenities are always cached, and any write to the amenities
column must trigger a re-embed so amenity/rating-aware queries actually
affect retrieval, not just chat replies.

After caching, calls ai.embeddings.embed_listings.embed_single() to
refresh the listing's embedding so amenity-aware queries work through
semantic search. If the re-embed fails, the amenities data is still
correctly cached — the failure is logged but not re-raised.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from ai.rag.listing_sql import LAT_SQL, LNG_SQL, VISIBLE_STATUS_SQL

load_dotenv()

logger = logging.getLogger(__name__)

# NOTE: creates its own engine rather than importing from retriever.py.
# If both modules grow more complex, consider a shared ai/db.py.
_DATABASE_URL = os.getenv("DATABASE_URL")
if not _DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and configure it, "
        "then make sure the Docker database is running (docker-compose up -d)."
    )
_engine = create_engine(_DATABASE_URL)

_PLACES_API_KEY_ENV = "GOOGLE_PLACES_API_KEY"
_PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# Category name (used as the JSON key / prompt_templates.py label) ->
# Google Places "type" value. Matches AGENTS.md's amenities cache shape:
# schools, hospitals, restaurants, transit, parks.
_CATEGORIES: dict[str, str] = {
    "schools": "school",
    "hospitals": "hospital",
    "restaurants": "restaurant",
    "transit": "transit_station",
    "parks": "park",
}

_SEARCH_RADIUS_M = 2000  # 2km \u2014 reasonable "nearby" radius for a residential search
_MAX_RESULTS_PER_CATEGORY = 5
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0


class ListingNotFoundError(Exception):
    """Raised when fetch_and_cache() is given a listing_id that doesn't exist."""


def _haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters.

    Google Places Nearby Search doesn't always return a ready-made
    distance field, so this is computed directly from each result's
    location rather than relying on that (or on `rankby=distance`, which
    would require dropping the `radius` parameter entirely).
    """
    R = 6_371_000  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def _get_listing_location(listing_id: int) -> tuple[float, float]:
    """Fetch a listing's (lat, lng). Raises ListingNotFoundError if missing."""
    with _engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {LAT_SQL}, {LNG_SQL} FROM listing WHERE id = :id"),
            {"id": listing_id},
        ).fetchone()
    if row is None:
        raise ListingNotFoundError(f"No listing found with id={listing_id}")
    return float(row[0]), float(row[1])


def _get_existing_amenities(listing_id: int) -> dict | None:
    with _engine.connect() as conn:
        row = conn.execute(
            text("SELECT amenities FROM listing WHERE id = :id"),
            {"id": listing_id},
        ).fetchone()
    if row is None or row[0] is None:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def _redact(message: object, api_key: str) -> str:
    """str(message) with the API key removed. requests puts the full URL,
    including ?key=..., into its exception messages, which end up in logs."""
    return str(message).replace(api_key, "<redacted>") if api_key else str(message)


def _fetch_category(lat: float, lng: float, place_type: str, api_key: str) -> list[dict] | None:
    """Query Google Places Nearby Search for one category. Never raises.

    Returns the raw results ([] for a genuine ZERO_RESULTS), or None when the
    request failed, so the caller can avoid caching a failure as "no amenities".
    """
    params = {
        "location": f"{lat},{lng}",
        "radius": _SEARCH_RADIUS_M,
        "type": place_type,
        "key": api_key,
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(_PLACES_NEARBY_URL, params=params, timeout=10)
        except requests.RequestException as e:
            logger.warning(
                "Places API request failed (attempt %d/%d) for type=%s: %s",
                attempt, _MAX_RETRIES, place_type, _redact(e, api_key),
            )
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue

        if resp.status_code != 200:
            logger.warning(
                "Places API returned HTTP %d for type=%s (attempt %d/%d)",
                resp.status_code, place_type, attempt, _MAX_RETRIES,
            )
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue

        try:
            body = resp.json()
        except ValueError:
            logger.warning("Places API returned a non-JSON body for type=%s (attempt %d/%d)",
                           place_type, attempt, _MAX_RETRIES)
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue
        status = body.get("status")

        if status == "OK":
            return body.get("results", [])
        if status == "ZERO_RESULTS":
            return []  # valid outcome, not an error
        if status in ("OVER_QUERY_LIMIT", "UNKNOWN_ERROR"):
            logger.warning(
                "Places API status=%s for type=%s (attempt %d/%d) \u2014 retrying",
                status, place_type, attempt, _MAX_RETRIES,
            )
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue

        # REQUEST_DENIED, INVALID_REQUEST, etc. \u2014 retrying won't help.
        logger.warning(
            "Places API status=%s for type=%s \u2014 not retrying (%s)",
            status, place_type,
            _redact(body.get("error_message", "no error_message"), api_key),
        )
        return None

    logger.warning(
        "Places API gave up after %d attempts for type=%s.",
        _MAX_RETRIES, place_type,
    )
    return None


def _format_places(raw_results: list[dict], origin_lat: float, origin_lng: float) -> list[dict]:
    """Turn raw Places API results into the cached shape: name, distance_m,
    rating, user_ratings_total. Sorted by rating descending (unrated last),
    capped to _MAX_RESULTS_PER_CATEGORY.
    """
    formatted = []
    for place in raw_results:
        loc = place.get("geometry", {}).get("location", {})
        if "lat" not in loc or "lng" not in loc:
            continue
        distance_m = _haversine_distance_m(origin_lat, origin_lng, loc["lat"], loc["lng"])
        formatted.append(
            {
                "name": place.get("name", "Unknown"),
                "distance_m": round(distance_m),
                "rating": place.get("rating"),  # may be None \u2014 not every place has one
                "user_ratings_total": place.get("user_ratings_total", 0),
            }
        )

    formatted.sort(key=lambda p: (p["rating"] is None, -(p["rating"] or 0)))
    return formatted[:_MAX_RESULTS_PER_CATEGORY]


def fetch_and_cache(listing_id: int, force: bool = False) -> None:
    """Fetch nearby amenities for a listing and cache them, then re-embed.

    Args:
        listing_id: The listing to enrich.
        force: If False (default) and amenities are already cached, this
            is a no-op \u2014 avoids re-spending API quota on a listing that
            hasn't moved. Pass True to refresh anyway (e.g. after a
            listing's location is edited \u2014 see the note on the Listing
            model about this).

    Nothing is written when the API key is missing or any category's request
    fails, so the listing is retried on the next run rather than cached as
    having no amenities.

    Raises:
        ListingNotFoundError: If listing_id doesn't exist.
    """
    lat, lng = _get_listing_location(listing_id)  # raises ListingNotFoundError

    if not force:
        existing = _get_existing_amenities(listing_id)
        if existing is not None:
            logger.debug("Listing %d already has cached amenities \u2014 skipping (force=False).", listing_id)
            return

    api_key = os.environ.get(_PLACES_API_KEY_ENV)
    if not api_key:
        # Don't cache anything: an empty cache would look "done" and this
        # listing would never be fetched again once the key is configured.
        logger.error("%s is not set — amenities for listing %d not fetched.",
                     _PLACES_API_KEY_ENV, listing_id)
        return

    try:
        amenities: dict[str, list[dict]] = {}
        failed: list[str] = []
        for category, place_type in _CATEGORIES.items():
            raw_results = _fetch_category(lat, lng, place_type, api_key)
            if raw_results is None:
                failed.append(category)
                continue
            amenities[category] = _format_places(raw_results, lat, lng)

        if failed:
            # Leave the column as it was (usually NULL) so a later run retries,
            # instead of caching a failure as "no amenities nearby".
            logger.warning("Amenities for listing %d not cached: Places API failed for %s.",
                           listing_id, ", ".join(failed))
            return

        with _engine.begin() as conn:
            conn.execute(
                text("UPDATE listing SET amenities = :amenities WHERE id = :id"),
                {"amenities": json.dumps(amenities), "id": listing_id},
            )

        total_found = sum(len(v) for v in amenities.values())
        logger.info(
            "Cached amenities for listing %d: %d places across %d categories.",
            listing_id, total_found, len(_CATEGORIES),
        )

    except Exception:
        logger.exception("fetch_and_cache() failed for listing_id=%d", listing_id)
        return  # amenities caching failure shouldn't crash the caller (e.g. a
                # background task queued from Person 2's POST /listings)

    # Re-embed now that amenities (with ratings) are available, so
    # amenity/rating-aware queries actually affect retrieval \u2014 not just
    # chat replies. A failure here is logged but doesn't undo the
    # successful amenities cache above.
    try:
        from ai.embeddings.embed_listings import embed_single
        embed_single(listing_id)
        logger.info("Re-embedded listing %d after amenities caching.", listing_id)
    except Exception:
        logger.warning(
            "Re-embed after amenities caching failed for listing %d \u2014 "
            "amenities are cached correctly, but this listing's embedding "
            "does not yet reflect them.",
            listing_id, exc_info=True,
        )


def fetch_and_cache_all_missing(delay_seconds: float = 0.2) -> int:
    """Batch-fill amenities for every visible listing that doesn't have them yet.

    Sold and withdrawn listings are skipped to save Places API quota; the
    backend calls ``fetch_and_cache`` itself when a listing is created or moved.

    Mirrors what would run during demo-data prep after seeding synthetic
    listings. A short delay between calls keeps well under Places API rate
    limits during a bulk run.

    Args:
        delay_seconds: Pause between listings, to avoid bursting the API.

    Returns:
        The number of listings processed.
    """
    with _engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT id FROM listing WHERE amenities IS NULL AND {VISIBLE_STATUS_SQL}")
        ).fetchall()

    ids = [row[0] for row in rows]
    logger.info("fetch_and_cache_all_missing(): %d listing(s) need amenities.", len(ids))

    for i, listing_id in enumerate(ids, 1):
        fetch_and_cache(listing_id)
        if i < len(ids):
            time.sleep(delay_seconds)
        if i % 25 == 0:
            logger.info("Amenities backfill progress: %d/%d", i, len(ids))

    logger.info("Amenities backfill complete: %d listing(s) processed.", len(ids))
    return len(ids)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) > 1:
        target_id = int(sys.argv[1])
        force_flag = "--force" in sys.argv
        print(f"Fetching amenities for listing {target_id} (force={force_flag})...")
        fetch_and_cache(target_id, force=force_flag)
        cached = _get_existing_amenities(target_id)
        print(json.dumps(cached, indent=2))
    else:
        print("No listing_id given \u2014 running fetch_and_cache_all_missing()...")
        count = fetch_and_cache_all_missing()
        print(f"Processed {count} listing(s).")
