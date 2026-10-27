"""Listing embedding pipeline — keeps every listing's embedding column up to date.

This module provides two public functions frozen per AGENTS.md Section 5:

* ``run()`` — batch-embeds all un-embedded listings (initial seeded data pass).
* ``embed_single(listing_id)`` — embeds or re-embeds one listing on demand.

**Re-embedding flow (Phase 4):**  When ``amenities_service.fetch_and_cache()``
writes cached amenity data to a listing, it calls ``embed_single()`` a second
time.  Because ``build_listing_text()`` folds amenity info into the text
representation, the new embedding captures things like "near a good school" —
making semantic search aware of amenities, not just title/description.

Usage (from repo root, with .venv active and Docker DB running):
    python -m ai.embeddings.embed_listings
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ai.embeddings.embedding_model import EmbeddingModel

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ListingNotFoundError(Exception):
    """Raised when a listing ID does not exist in the database."""


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and configure it, "
        "then make sure the Docker database is running (docker-compose up -d)."
    )

_engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 5},
)

_embedding_model = EmbeddingModel()


# ---------------------------------------------------------------------------
# Text construction helpers
# ---------------------------------------------------------------------------


def _build_amenities_summary(amenities: dict[str, Any]) -> str:
    """Convert a cached amenities dict into a natural-language paragraph.

    Each category key (``schools``, ``hospitals``, ``restaurants``, ``transit``,
    ``parks``) maps to a list of dicts, each with at least ``name`` and
    ``distance_m``, and optionally ``rating`` and ``user_ratings_total``.

    Categories with empty lists are silently skipped.  Individual entries
    without a ``rating`` omit the rating clause.

    Args:
        amenities: The cached amenities dict from the ``amenities`` column.

    Returns:
        A human-readable summary string, or ``""`` if no categories have data.
    """
    if not amenities or not isinstance(amenities, dict):
        return ""

    # Friendly display names for each category
    category_labels = {
        "schools": "school",
        "hospitals": "hospital",
        "restaurants": "restaurant",
        "transit": "transit station",
        "parks": "park",
    }

    parts: list[str] = []

    for category, label in category_labels.items():
        entries = amenities.get(category)
        if not entries or not isinstance(entries, list):
            continue

        count = len(entries)
        plural = f"{label}s" if count > 1 else label

        # Find the highest-rated entry (if any have ratings)
        rated = [
            e for e in entries
            if e.get("rating") is not None and e["rating"] > 0
        ]

        if rated:
            best = max(rated, key=lambda e: e["rating"])
            best_name = best.get("name", "unnamed")
            best_rating = best["rating"]
            review_count = best.get("user_ratings_total")

            rating_clause = f"{best_name}, {best_rating} stars"
            if review_count and review_count > 0:
                rating_clause += f", {review_count} reviews"

            parts.append(f"{count} {plural} (highest rated: {rating_clause})")
        else:
            parts.append(f"{count} {plural}")

    if not parts:
        return ""

    # Join with commas and "and" before the last item
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"

    return f"Nearby amenities include {joined}."


def build_listing_text(listing: dict[str, Any]) -> str:
    """Construct a natural-language text representation of a listing for embedding.

    Combines title, description, property type, and price into a coherent
    paragraph.  Missing or ``None`` fields are gracefully skipped.

    If the listing has cached amenities data (a non-empty dict), a second
    paragraph summarising the nearby amenities is appended — this is what
    makes re-embedded listings "amenity-aware" for semantic search.

    Args:
        listing: A dict with keys matching the ``listing`` table columns:
            ``title``, ``description``, ``price``, ``property_type``, and
            optionally ``amenities``.

    Returns:
        A multi-sentence string suitable for passing to ``EmbeddingModel.embed()``.
    """
    segments: list[str] = []

    title = listing.get("title")
    if title:
        segments.append(str(title).strip())

    # Property type and price in a natural phrase
    ptype = listing.get("property_type")
    price = listing.get("price")
    if ptype and price is not None:
        try:
            price_val = float(price)
            if price_val >= 10_000_000:
                price_str = f"Rs.{price_val / 10_000_000:.2f} crore"
            else:
                price_str = f"Rs.{price_val / 100_000:.1f} lakh"
            segments.append(f"This is a {ptype} property priced at {price_str}.")
        except (ValueError, TypeError):
            segments.append(f"This is a {ptype} property.")
    elif ptype:
        segments.append(f"This is a {ptype} property.")

    description = listing.get("description")
    if description:
        segments.append(str(description).strip())

    # Amenities paragraph (only present after Phase 4 caching)
    amenities = listing.get("amenities")
    if amenities:
        # Handle both dict and JSON-string forms
        if isinstance(amenities, str):
            try:
                amenities = json.loads(amenities)
            except (json.JSONDecodeError, TypeError):
                amenities = None

        if amenities and isinstance(amenities, dict):
            amenities_text = _build_amenities_summary(amenities)
            if amenities_text:
                segments.append(amenities_text)

    return " ".join(segments)


# ---------------------------------------------------------------------------
# Public API — frozen signatures per AGENTS.md Section 5
# ---------------------------------------------------------------------------


def embed_single(listing_id: int) -> None:
    """Embed (or re-embed) a single listing by ID.

    Fetches the listing from the database, builds its text representation via
    ``build_listing_text()``, computes the embedding via ``EmbeddingModel``,
    and writes it back to the ``embedding`` column in a single committed
    transaction.

    This function is called:
    1. Right after a listing is created (amenities still ``None`` — baseline
       embedding so the listing is immediately searchable).
    2. Again after ``amenities_service.fetch_and_cache()`` writes cached
       amenity data (re-embed so semantic search picks up amenities).

    Args:
        listing_id: The primary key of the listing to embed.

    Raises:
        ListingNotFoundError: If no listing with that ID exists.
        SQLAlchemyError: If the database write fails (not caught here —
            callers should handle as appropriate).
    """
    with _engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, title, description, price, property_type, amenities "
                "FROM listing WHERE id = :listing_id"
            ),
            {"listing_id": listing_id},
        ).fetchone()

    if row is None:
        raise ListingNotFoundError(
            f"Listing with id={listing_id} does not exist."
        )

    listing_dict: dict[str, Any] = {
        "title": row.title,
        "description": row.description,
        "price": row.price,
        "property_type": row.property_type,
        "amenities": row.amenities,
    }

    text_repr = build_listing_text(listing_dict)
    vector = _embedding_model.embed(text_repr)

    with _engine.begin() as conn:
        conn.execute(
            text("UPDATE listing SET embedding = :vec WHERE id = :listing_id"),
            {"vec": str(vector), "listing_id": listing_id},
        )

    logger.info(
        "Embedded listing id=%d (%s), text_len=%d chars.",
        listing_id,
        (row.title or "untitled")[:40],
        len(text_repr),
    )


def run(batch_size: int = 50) -> int:
    """Batch-embed all listings whose ``embedding`` column is NULL.

    Processes rows in batches of *batch_size*, calling ``embed_single()`` for
    each.  Failures on individual rows are logged and skipped — the batch
    continues rather than aborting, and each listing is attempted at most
    once per call.

    This is for the initial pass over freshly-seeded data.  Day-to-day,
    individual listings are embedded via ``embed_single()`` directly.

    Args:
        batch_size: Number of IDs to fetch per batch.  Defaults to 50.

    Returns:
        The total number of listings successfully embedded.
    """
    total_updated = 0
    batch_num = 0
    # Keyset pagination: always move past the last ID seen. Re-selecting
    # "embedding IS NULL" from the start would pick up a listing that keeps
    # failing (e.g. empty text) on every pass and never terminate.
    last_id = 0

    while True:
        # Fetch next batch of un-embedded listing IDs
        with _engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id FROM listing "
                    "WHERE embedding IS NULL AND id > :last_id "
                    "ORDER BY id "
                    "LIMIT :batch_size"
                ),
                {"batch_size": batch_size, "last_id": last_id},
            ).fetchall()

        if not rows:
            break

        batch_num += 1
        ids = [row.id for row in rows]
        last_id = ids[-1]
        logger.info(
            "Batch %d: embedding %d listings (ids %d..%d)...",
            batch_num, len(ids), ids[0], ids[-1],
        )

        batch_ok = 0
        for listing_id in ids:
            try:
                embed_single(listing_id)
                batch_ok += 1
            except ListingNotFoundError:
                # Shouldn't happen (we just queried the id), but be safe
                logger.warning("Listing id=%d vanished mid-batch. Skipping.", listing_id)
            except (SQLAlchemyError, Exception) as exc:
                logger.error(
                    "Failed to embed listing id=%d: %s. Skipping.",
                    listing_id, exc,
                )

        total_updated += batch_ok
        logger.info(
            "Batch %d complete: %d/%d succeeded (total so far: %d).",
            batch_num, batch_ok, len(ids), total_updated,
        )

    logger.info("run() finished: %d listings embedded in %d batches.", total_updated, batch_num)
    return total_updated


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    count = run()
    print(f"\n[OK] Embedded {count} listings.")
