"""Semantic retriever for the Reality AI RAG pipeline.

This module is imported directly by Person 2's backend — the function signature
``search(query, candidate_ids=None, top_k=5)`` is frozen per AGENTS.md (Section 5).

Performance note
~~~~~~~~~~~~~~~~
At larger scale, an HNSW or IVFFlat index on the ``embedding`` column will be
critical for sub-100ms latency.  An IVFFlat index already exists (created in
``db/init.sql`` with ``lists = 10``), but for serious production traffic the
index type and parameters should be revisited in Phase 5 (see the project
roadmap).  The current implementation works correctly with or without the index —
the planner will just do a sequential scan when the index is absent or not
suitable.

Database connection
~~~~~~~~~~~~~~~~~~~
A single module-level SQLAlchemy ``Engine`` is created on first import (using the
``DATABASE_URL`` environment variable loaded from ``.env``).  The engine's built-in
connection pool is reused across calls — **no** new connections are created per
``search()`` invocation.
"""

from __future__ import annotations

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
# Custom exception
# ---------------------------------------------------------------------------


class RetrievalError(Exception):
    """Raised when the semantic search query fails at the database layer.

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


# ---------------------------------------------------------------------------
# Public API — frozen signature per AGENTS.md Section 5
# ---------------------------------------------------------------------------


def search(
    query: str,
    candidate_ids: list[int] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return the *top_k* listings most semantically similar to *query*.

    This function embeds the user's natural-language query via
    ``EmbeddingModel.embed()``, then runs a pgvector cosine-distance query
    against the ``listings`` table.  If *candidate_ids* is provided (e.g.
    from a boundary-filter step), only those listing IDs are considered.

    Args:
        query: The user's search query in natural language.  Must be a
            non-empty string after whitespace stripping.
        candidate_ids: Optional list of listing IDs to restrict the search
            to (typically produced by ``ai.rag.boundary_filter.get_candidates``).
            Pass ``None`` (the default) to search all listings.  An **empty
            list** ``[]`` means "no candidates matched the drawn boundary" and
            will return an empty result immediately — it does **not** mean
            "no filter."
        top_k: Maximum number of results to return.  Clamped to a ceiling of
            50 to prevent accidentally huge queries.

    Returns:
        A list of dicts (may be empty), each containing:
        ``id``, ``title``, ``description``, ``price`` (float),
        ``property_type``, ``lat`` (float), ``lng`` (float),
        ``amenities`` (dict | None), and ``distance_score`` (float — the raw
        pgvector ``<->`` cosine distance; lower is more similar).

    Raises:
        ValueError: If *query* is empty after stripping, or *top_k* is not
            a positive integer.
        RetrievalError: If the database query fails for any reason.
    """

    # ── 1. Validate query ──────────────────────────────────────────────────
    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "query must be a non-empty string after stripping whitespace."
        )
    query = query.strip()

    # ── 2. Validate top_k ──────────────────────────────────────────────────
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}.")
    if top_k > _MAX_TOP_K:
        logger.warning(
            "top_k=%d exceeds maximum (%d); clamping to %d.",
            top_k, _MAX_TOP_K, _MAX_TOP_K,
        )
        top_k = _MAX_TOP_K

    # ── 3. Empty candidate list → immediate empty return ───────────────────
    if candidate_ids is not None and len(candidate_ids) == 0:
        logger.debug(
            "candidate_ids is an empty list — returning [] without querying DB."
        )
        return []

    # ── 4. Embed the query ─────────────────────────────────────────────────
    query_vector = _embedding_model.embed(query)

    # ── 5. Build & execute the SQL ─────────────────────────────────────────
    #    Always use bound parameters — never interpolate values into the SQL.
    base_sql = """
        SELECT
            id,
            title,
            description,
            price,
            property_type,
            lat,
            lng,
            amenities,
            embedding <-> :query_vector AS distance_score
        FROM listings
        WHERE embedding IS NOT NULL
    """

    params: dict[str, Any] = {
        "query_vector": str(query_vector),  # pgvector accepts text '[0.1,0.2,...]'
        "top_k": top_k,
    }

    if candidate_ids is not None:
        base_sql += "  AND id = ANY(:candidate_ids)\n"
        params["candidate_ids"] = candidate_ids

    base_sql += "ORDER BY distance_score ASC\nLIMIT :top_k"

    try:
        with _engine.connect() as conn:
            rows = conn.execute(text(base_sql), params).fetchall()
    except SQLAlchemyError as exc:
        logger.error(
            "Retrieval query failed. query=%r, candidate_ids=%s, error=%s",
            query[:80],
            "provided" if candidate_ids is not None else "None",
            exc,
        )
        raise RetrievalError(
            f"Database query failed during semantic search: {exc}"
        ) from exc

    # ── 6. Build result dicts ──────────────────────────────────────────────
    results: list[dict[str, Any]] = []
    for row in rows:
        results.append({
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "price": float(row.price) if row.price is not None else None,
            "property_type": row.property_type,
            "lat": row.lat,
            "lng": row.lng,
            "amenities": row.amenities,
            "distance_score": float(row.distance_score),
        })

    logger.info(
        "search() returned %d result(s) for query=%r (top_k=%d, candidates=%s).",
        len(results),
        query[:60],
        top_k,
        len(candidate_ids) if candidate_ids is not None else "all",
    )
    return results
