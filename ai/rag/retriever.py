"""Filtered semantic retriever for the Reality AI chat pipeline.

This module is imported directly by Person 2's backend — the signature
``search(query, candidate_ids=None, top_k=5)`` is frozen per AGENTS.md
(Section 5).

How a search works
~~~~~~~~~~~~~~~~~~
1. ``ai.nlu.query_parser.parse_query`` turns the message into structured
   filters (price range, property type, BHK, locality). Off-topic messages
   return ``[]`` immediately — ``generate_response`` writes the polite decline.
2. Those filters become SQL ``WHERE`` clauses (bound parameters only). A
   locality is a gazetteer centroid + radius, matched with PostGIS
   ``ST_DWithin`` on geography (metres).
3. The *original* query is embedded with MiniLM and the filtered rows are
   ranked by pgvector distance.
4. If nothing matches, a relaxation ladder widens the search — radius x2,
   then drop BHK, then drop locality — and every result says which step it
   came from in ``match_note``. Price and property type are never relaxed:
   showing a customer something over budget would be worse than saying
   nothing matched.

Database connection
~~~~~~~~~~~~~~~~~~~
A single module-level SQLAlchemy ``Engine`` (DATABASE_URL from ``.env``); its
connection pool is reused across calls.

Indexing
~~~~~~~~
Exact scan, no vector index (see ``db/init.sql``): at a few hundred rows it
is sub-millisecond, and approximate indexes apply WHERE filters after the
index scan, which would silently drop filtered results.

Schema
~~~~~~
Queries Person 2's ``listing`` table (see ``ai/rag/listing_sql.py``). Only
available and under-offer listings are searchable.
"""

from __future__ import annotations

import logging
import numbers
import os
from dataclasses import dataclass, replace
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ai.embeddings.embedding_model import EmbeddingModel
from ai.nlu.gazetteer import get_place
from ai.nlu.query_parser import MAX_QUERY_CHARS, parse_query
from ai.nlu.schema import ParsedQuery
from ai.rag.listing_sql import BEDROOMS_SQL, LAT_SQL, LNG_SQL, VISIBLE_STATUS_SQL

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class RetrievalError(Exception):
    """Raised when the search query fails at the database layer.

    Wraps the underlying SQLAlchemy / psycopg2 exception so callers get a
    clean, predictable exception type rather than a raw driver error.
    The original exception is always chained via ``raise ... from e``.
    """


# ---------------------------------------------------------------------------
# Module-level singletons (expensive to create — instantiated once on import)
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

# Maximum top_k a caller is allowed to request — anything larger is clamped.
_MAX_TOP_K = 50

# match_note values, in ladder order.
MATCH_EXACT = "exact"
MATCH_RELAXED_RADIUS = "relaxed_radius"
MATCH_RELAXED_BHK = "relaxed_bhk"
MATCH_RELAXED_LOCALITY = "relaxed_locality"


# ---------------------------------------------------------------------------
# Filters -> SQL
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Filters:
    """The SQL-level filters for one attempt of the relaxation ladder."""

    price_min: float | None = None
    price_max: float | None = None
    property_type: str | None = None
    bhk: int | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = None
    candidate_ids: tuple[int, ...] | None = None

    def describe(self) -> str:
        """Short human-readable summary of the active filters, for logs."""
        parts = []
        if self.price_min is not None:
            parts.append(f"price>={self.price_min:.0f}")
        if self.price_max is not None:
            parts.append(f"price<={self.price_max:.0f}")
        if self.property_type:
            parts.append(f"type={self.property_type}")
        if self.bhk is not None:
            parts.append(f"bhk={self.bhk}")
        if self.radius_m is not None:
            parts.append(f"within {self.radius_m:.0f}m of ({self.lat}, {self.lng})")
        if self.candidate_ids is not None:
            parts.append(f"{len(self.candidate_ids)} candidate ids")
        return ", ".join(parts) or "none"


def filters_from_parsed(parsed: ParsedQuery, candidate_ids: list[int] | None) -> _Filters:
    """Translate a ParsedQuery into SQL filters (locality -> centroid + radius)."""
    place = get_place(parsed.locality) if parsed.locality else None
    if parsed.locality and place is None:
        logger.warning("Locality %r is not in the gazetteer; ignoring it.", parsed.locality)
    return _Filters(
        price_min=parsed.price_min,
        price_max=parsed.price_max,
        property_type=parsed.property_type,
        bhk=parsed.bhk,
        lat=place["lat"] if place else None,
        lng=place["lng"] if place else None,
        radius_m=float(place["radius_m"]) if place else None,
        candidate_ids=tuple(int(i) for i in candidate_ids) if candidate_ids is not None else None,
    )


def relaxation_ladder(f: _Filters) -> list[tuple[str, _Filters]]:
    """The attempts to run, in order, each tagged with its match_note.

    Steps are cumulative (dropping BHK keeps the widened radius) and skipped
    when the filter they relax isn't set. Price and property type are never
    relaxed.
    """
    steps = [(MATCH_EXACT, f)]
    current = f
    if current.radius_m is not None:
        current = replace(current, radius_m=current.radius_m * 2)
        steps.append((MATCH_RELAXED_RADIUS, current))
    if current.bhk is not None:
        current = replace(current, bhk=None)
        steps.append((MATCH_RELAXED_BHK, current))
    if current.radius_m is not None:
        current = replace(current, lat=None, lng=None, radius_m=None)
        steps.append((MATCH_RELAXED_LOCALITY, current))
    return steps


# ORDER BY for each supported sort.  "relevance" ranks by embedding distance.
ORDERS = {
    "relevance": "distance_score ASC",
    "newest": "created_at DESC, id DESC",
    "price_asc": "price ASC, id ASC",
    "price_desc": "price DESC, id DESC",
}


def _where(f: _Filters) -> tuple[list[str], dict[str, Any]]:
    """WHERE clauses + bound parameters for *f*. Never interpolates values into SQL."""
    where = ["embedding IS NOT NULL", VISIBLE_STATUS_SQL]
    params: dict[str, Any] = {}
    if f.price_min is not None:
        where.append("price >= :price_min")
        params["price_min"] = f.price_min
    if f.price_max is not None:
        where.append("price <= :price_max")
        params["price_max"] = f.price_max
    if f.property_type is not None:
        where.append("property_type = :property_type")
        params["property_type"] = f.property_type
    if f.bhk is not None:
        where.append(f"{BEDROOMS_SQL} = :bhk")
        params["bhk"] = f.bhk
    if f.radius_m is not None:
        where.append(
            "ST_DWithin("
            "location::geography, "
            "ST_SetSRID(ST_MakePoint(:loc_lng, :loc_lat), 4326)::geography, "
            ":radius_m)"
        )
        params.update(loc_lng=f.lng, loc_lat=f.lat, radius_m=f.radius_m)
    if f.candidate_ids is not None:
        where.append("id = ANY(:candidate_ids)")
        params["candidate_ids"] = list(f.candidate_ids)
    return where, params


def _build_sql(
    f: _Filters,
    query_vector: list[float],
    top_k: int,
    *,
    exclude_ids: list[int] | None = None,
    order: str = "relevance",
) -> tuple[str, dict[str, Any]]:
    """SQL + bound parameters for one attempt. Never interpolates values into SQL.

    *exclude_ids* skips listings already shown (for "show more"); *order* is a
    key of ``ORDERS``.
    """
    where, params = _where(f)
    params.update(query_vector=str(query_vector), top_k=top_k)
    if exclude_ids:
        where.append("NOT (id = ANY(:exclude_ids))")
        params["exclude_ids"] = list(exclude_ids)

    sql = (
        f"SELECT id, title, description, price, property_type, {BEDROOMS_SQL} AS bhk, "
        f"{LAT_SQL} AS lat, {LNG_SQL} AS lng, amenities, "
        "embedding <-> :query_vector AS distance_score "
        "FROM listing WHERE " + " AND ".join(where) +
        f" ORDER BY {ORDERS[order]} LIMIT :top_k"
    )
    return sql, params


def _build_count_sql(f: _Filters) -> tuple[str, dict[str, Any]]:
    """How many listings match *f* in total (ignores paging)."""
    where, params = _where(f)
    return "SELECT count(*) FROM listing WHERE " + " AND ".join(where), params


def _row_to_dict(row: Any, match_note: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "price": float(row.price) if row.price is not None else None,
        "property_type": row.property_type,
        "bhk": row.bhk,
        "lat": row.lat,
        "lng": row.lng,
        "amenities": row.amenities,
        "distance_score": float(row.distance_score),
        "match_note": match_note,
    }


@dataclass(frozen=True)
class SearchPage:
    """One page of results for already-parsed filters (used by conversations)."""

    listings: list[dict[str, Any]]
    total: int          # matching listings at the ladder step that answered
    match_note: str | None


def search_parsed(
    parsed: ParsedQuery,
    embed_text: str,
    *,
    candidate_ids: list[int] | None = None,
    page_size: int = 10,
    exclude_ids: list[int] | None = None,
    order: str = "relevance",
) -> SearchPage:
    """Run the filtered search for an already-resolved ParsedQuery.

    Like ``search()``, but the caller supplies the filters (e.g. merged with
    earlier messages in a conversation) and the text to rank by, can skip
    listings already shown, choose the sort order, and gets the total count.

    Raises:
        ValueError: On an unknown *order*.
        RetrievalError: If embedding or the database query fails.
    """
    if order not in ORDERS:
        raise ValueError(f"order must be one of {sorted(ORDERS)}, got {order!r}.")
    page_size = max(1, min(int(page_size), _MAX_TOP_K))
    if candidate_ids is not None and len(candidate_ids) == 0:
        return SearchPage([], 0, None)

    try:
        query_vector = _embedding_model.embed((embed_text or "property")[:MAX_QUERY_CHARS])
    except Exception as exc:
        logger.error("Query embedding failed. text=%r, error=%s", embed_text[:80], exc)
        raise RetrievalError(f"Embedding the query failed: {exc}") from exc

    filters = filters_from_parsed(parsed, candidate_ids)
    try:
        with _engine.connect() as conn:
            for match_note, attempt in relaxation_ladder(filters):
                count_sql, count_params = _build_count_sql(attempt)
                total = int(conn.execute(text(count_sql), count_params).scalar() or 0)
                if total == 0:
                    continue
                sql, params = _build_sql(attempt, query_vector, page_size,
                                         exclude_ids=exclude_ids, order=order)
                rows = conn.execute(text(sql), params).fetchall()
                logger.info("search_parsed(): [%s] filters: %s -> %d total, %d on this page, "
                            "match_note=%s, order=%s", parsed.describe(), attempt.describe(),
                            total, len(rows), match_note, order)
                return SearchPage([_row_to_dict(row, match_note) for row in rows], total, match_note)
    except SQLAlchemyError as exc:
        logger.error("Retrieval query failed. filters=%s, error=%s", filters.describe(), exc)
        raise RetrievalError(f"Database query failed during search: {exc}") from exc

    return SearchPage([], 0, None)


def listing_prices(listing_ids: list[int]) -> list[float]:
    """Prices of the given listings (any status), for relative follow-ups like "cheaper"."""
    ids = [int(i) for i in listing_ids if isinstance(i, numbers.Integral) and not isinstance(i, bool)]
    if not ids:
        return []
    try:
        with _engine.connect() as conn:
            rows = conn.execute(text("SELECT price FROM listing WHERE id = ANY(:ids)"),
                                {"ids": ids}).fetchall()
    except SQLAlchemyError as exc:
        raise RetrievalError(f"Database query failed: {exc}") from exc
    return [float(r[0]) for r in rows if r[0] is not None]


# ---------------------------------------------------------------------------
# Public API — frozen signature per AGENTS.md Section 5
# ---------------------------------------------------------------------------


def search(
    query: str,
    candidate_ids: list[int] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return up to *top_k* listings matching *query*'s filters, best match first.

    Args:
        query: The user's message in natural language. Must be a non-empty
            string after whitespace stripping.
        candidate_ids: Optional listing IDs to restrict the search to
            (typically from ``ai.rag.boundary_filter.get_candidates``). ``None``
            (the default) searches all listings. An **empty list** means "no
            candidates matched the drawn boundary" and returns ``[]`` — it does
            **not** mean "no filter".
        top_k: Maximum number of results. Clamped to 50.

    Returns:
        A list of dicts (may be empty) with ``id``, ``title``, ``description``,
        ``price`` (float), ``property_type``, ``bhk`` (int | None), ``lat``,
        ``lng``, ``amenities`` (dict | None), ``distance_score`` (float — pgvector
        ``<->`` L2 distance between normalised embeddings; lower is more
        similar) and ``match_note`` ("exact", "relaxed_radius", "relaxed_bhk"
        or "relaxed_locality"). Off-topic queries return ``[]``.

    Raises:
        ValueError: If *query* is empty after stripping, *top_k* is not a
            positive integer, or *candidate_ids* holds a non-integer.
        RetrievalError: If embedding the query or the database query fails.
    """
    # ── 1. Validate input ──────────────────────────────────────────────────
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string after stripping whitespace.")
    query = query.strip()

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}.")
    if top_k > _MAX_TOP_K:
        logger.warning("top_k=%d exceeds maximum (%d); clamping.", top_k, _MAX_TOP_K)
        top_k = _MAX_TOP_K

    if candidate_ids is not None:
        if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) for i in candidate_ids):
            raise ValueError("candidate_ids must be a list of integer listing IDs.")
        if len(candidate_ids) == 0:
            logger.debug("candidate_ids is an empty list — returning [] without querying DB.")
            return []

    # ── 2. Understand the query ────────────────────────────────────────────
    parsed = parse_query(query)
    if not parsed.is_property_query:
        logger.info("search(): not a property query (%r) — returning [].", query[:60])
        return []

    # ── 3. Filtered ranking with the relaxation ladder ─────────────────────
    # Same cap as the parser: MiniLM reads only ~256 tokens anyway, and an
    # oversized message shouldn't cost a full tokenization.
    try:
        query_vector = _embedding_model.embed(query[:MAX_QUERY_CHARS])
    except Exception as exc:
        logger.error("Query embedding failed. query=%r, error=%s", query[:80], exc)
        raise RetrievalError(f"Embedding the query failed: {exc}") from exc
    filters = filters_from_parsed(parsed, candidate_ids)

    for match_note, attempt in relaxation_ladder(filters):
        sql, params = _build_sql(attempt, query_vector, top_k)
        try:
            with _engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
        except SQLAlchemyError as exc:
            logger.error("Retrieval query failed. query=%r, filters=%s, error=%s",
                         query[:80], attempt.describe(), exc)
            raise RetrievalError(f"Database query failed during search: {exc}") from exc
        if rows:
            logger.info(
                "search(): %r -> [%s] (%s) filters: %s -> %d row(s), match_note=%s",
                query[:60], parsed.describe(), parsed.source, attempt.describe(),
                len(rows), match_note,
            )
            return [_row_to_dict(row, match_note) for row in rows]

    logger.info("search(): %r -> [%s] (%s) — no matches even after relaxation (filters: %s).",
                query[:60], parsed.describe(), parsed.source, filters.describe())
    return []
