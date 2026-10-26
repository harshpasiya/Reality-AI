"""EXPLAIN ANALYZE helper for spatial queries.

Run this script against the seeded database to verify that the GiST index
(created in the initial migration) is actually being used.  You should see
``Index Scan using idx_listing_location`` in the output — if you see
``Seq Scan`` instead, the index is missing or the planner has stats that
make it prefer the scan (usually because the table is nearly empty).

Usage::

    # Activate venv first, then:
    python -m app.db._explain_check

Environment:
    DATABASE_URL must be set (via .env or environment).
"""

from __future__ import annotations

import sys
from textwrap import indent

from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal


# ---------------------------------------------------------------------------
# Representative query parameters — adjust to match your seeded data's city.
# These are real Surat, Gujarat coordinates.
# ---------------------------------------------------------------------------
_RADIUS_LAT = 21.1702  # Surat city centre
_RADIUS_LNG = 72.8311
_RADIUS_M = 5000  # 5 km

_POLYGON_WKT = (
    "POLYGON(("
    "72.81 21.15, "
    "72.81 21.19, "
    "72.85 21.19, "
    "72.85 21.15, "
    "72.81 21.15"
    "))"
)


def _explain(session, label: str, sql: str, params: dict) -> None:
    """Run EXPLAIN ANALYZE and print the plan."""
    explain_sql = f"EXPLAIN ANALYZE {sql}"
    result = session.execute(text(explain_sql), params)
    plan_lines = [row[0] for row in result]
    plan_text = "\n".join(plan_lines)

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)
    print(indent(plan_text, "  "))

    # Heuristic pass/fail check
    if "Index Scan" in plan_text or "Bitmap Index Scan" in plan_text:
        print("\n  ✅  Index scan confirmed — GiST index is being used.")
    else:
        print(
            "\n  ⚠️   No index scan detected.  Possible causes:\n"
            "      • GiST index not yet applied (run alembic upgrade head).\n"
            "      • Table has too few rows for the planner to choose the index\n"
            "        (run the seed script with a larger dataset, or run\n"
            "        ANALYZE listing; manually).\n"
        )


def main() -> None:
    """Run EXPLAIN ANALYZE on radius-search and boundary-search queries."""
    session = SessionLocal()
    try:
        # ------------------------------------------------------------------ #
        # Query 1 — radius search (mirrors geo_service.search_by_radius)     #
        # ------------------------------------------------------------------ #
        _explain(
            session,
            label="Radius search — ST_DWithin (::geography cast, ~5 km)",
            sql="""
                SELECT id, title
                FROM listing
                WHERE ST_DWithin(
                    location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
                ORDER BY
                    ST_Distance(
                        location::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                    )
                LIMIT 20
            """,
            params={
                "lat": _RADIUS_LAT,
                "lng": _RADIUS_LNG,
                "radius_m": _RADIUS_M,
            },
        )

        # ------------------------------------------------------------------ #
        # Query 2 — boundary search (mirrors geo_service.boundary_candidate_ids) #
        # ------------------------------------------------------------------ #
        _explain(
            session,
            label="Boundary search — ST_Contains with polygon",
            sql="""
                SELECT id, title
                FROM listing
                WHERE ST_Contains(
                    ST_GeomFromText(:wkt, 4326),
                    location
                )
                LIMIT 50
            """,
            params={"wkt": _POLYGON_WKT},
        )

    finally:
        session.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        print(
            "   Make sure the database is running, DATABASE_URL is set, and\n"
            "   the seed data has been loaded.",
            file=sys.stderr,
        )
        sys.exit(1)
