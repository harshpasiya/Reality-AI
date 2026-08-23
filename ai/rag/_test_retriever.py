"""Manual review test for ai.rag.retriever.search().

Runs 12 diverse queries against the live database and prints the top-3
results for each in a readable format.  This is NOT an automated test —
no assertions, no pass/fail.  The purpose is to let a human eyeball whether
the semantic search is returning sensible results across different intents.

Usage (from repo root, with .venv active and Docker DB running):
    python -m ai.rag._test_retriever
"""

from __future__ import annotations

import sys

from ai.rag.retriever import search

# ---------------------------------------------------------------------------
# Test queries — 12 total across 4 categories
# ---------------------------------------------------------------------------
QUERIES: list[tuple[str, str]] = [
    # ── Price-based (3) ────────────────────────────────────────────────────
    ("PRICE", "cheap 2BHK flat under 50 lakhs"),
    ("PRICE", "luxury 4BHK apartment above 2 crore in premium area"),
    ("PRICE", "affordable 1BHK for first-time buyer on a tight budget"),

    # ── Location-based (3) ─────────────────────────────────────────────────
    ("LOCATION", "flat near VR Mall in Adajan"),
    ("LOCATION", "residential plot close to Dumas Beach"),
    ("LOCATION", "apartment near Surat Railway Station with good connectivity"),

    # ── Vague / broad (2) ──────────────────────────────────────────────────
    ("BROAD", "show me some apartments in Surat"),
    ("BROAD", "looking for property options for my family"),

    # ── Very specific (4) ──────────────────────────────────────────────────
    ("SPECIFIC", "3BHK with covered parking and modular kitchen in gated society"),
    ("SPECIFIC", "corner plot with two-road frontage near Ring Road"),
    ("SPECIFIC", "flat with swimming pool and gym in Vesu or Citylight"),
    ("SPECIFIC", "ground floor flat suitable for elderly parents near a park"),
]


def _fmt_price(price: float | None) -> str:
    if price is None:
        return "N/A"
    if price >= 10_000_000:
        return f"Rs.{price / 10_000_000:.2f} Cr"
    return f"Rs.{price / 100_000:.1f} L"


def main() -> None:
    print("=" * 72)
    print("  RETRIEVER MANUAL REVIEW -- 12 queries, top-3 results each")
    print("=" * 72)

    for i, (category, query) in enumerate(QUERIES, 1):
        results = search(query, top_k=3)

        print(f"\n{'-' * 72}")
        print(f"  [{category}] Query {i}: \"{query}\"")
        print(f"{'-' * 72}")

        if not results:
            print("  (no results)")
            continue

        for rank, r in enumerate(results, 1):
            print(
                f"  {rank}. {r['title']}\n"
                f"     Price: {_fmt_price(r['price'])}  |  "
                f"Type: {r['property_type']}  |  "
                f"Dist: {r['distance_score']:.4f}"
            )

    print(f"\n{'=' * 72}")
    print(f"  Done — {len(QUERIES)} queries executed.")
    print(f"{'=' * 72}\n")


if __name__ == "__main__":
    main()
