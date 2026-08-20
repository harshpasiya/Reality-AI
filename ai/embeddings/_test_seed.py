"""Seed script — inserts 15-20 fake listings into the local dev database.

Designed to be safely re-runnable: deletes all existing rows before inserting.
Run this after `docker-compose up -d` to populate the DB for local AI testing.

Usage (from repo root, with .venv active):
    python -m ai.embeddings._test_seed
"""

from __future__ import annotations

import os
import random
import sys
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print(
        "\n[ERROR] DATABASE_URL is not set.\n"
        "  1. Make sure docker-compose is running: docker-compose up -d\n"
        "  2. Copy .env.example to .env and set:\n"
        "       DATABASE_URL=postgresql://reality_ai:reality_ai_secret@localhost:5432/reality_ai\n"
    )
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("[ERROR] sqlalchemy not installed. Run: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

try:
    from faker import Faker
except ImportError:
    print("[ERROR] faker not installed. Run: pip install faker")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Neighbourhood anchor points — lat/lng clusters simulating real areas.
# Coordinates centred around Ahmedabad, Gujarat (the project's target city).
# ---------------------------------------------------------------------------
NEIGHBOURHOODS = [
    {"name": "Bopal",       "lat": 23.0323, "lng": 72.4700},
    {"name": "Satellite",   "lat": 23.0225, "lng": 72.5074},
    {"name": "Thaltej",     "lat": 23.0563, "lng": 72.5100},
    {"name": "Navrangpura", "lat": 23.0333, "lng": 72.5619},
    {"name": "Prahlad Nagar","lat": 23.0126, "lng": 72.5064},
]

FLAT_TITLES = [
    "Spacious {bhk}BHK near IT Park",
    "Modern {bhk}BHK flat with parking",
    "Well-ventilated {bhk}BHK in gated society",
    "Ready-to-move {bhk}BHK near metro station",
    "Semi-furnished {bhk}BHK with gym access",
    "Corner {bhk}BHK flat with city view",
]

LAND_TITLES = [
    "Residential plot in {area}",
    "Corner plot near {area} highway",
    "Commercial-residential mixed plot in {area}",
    "Villa plot with compound wall in {area}",
]

FLAT_DESCS = [
    (
        "A well-maintained {bhk}BHK apartment on the {floor} floor of a {age}-year-old society. "
        "The flat features {features}. "
        "Walking distance to schools, supermarkets, and the BRTS corridor."
    ),
    (
        "Bright and airy {bhk}BHK with {features}. "
        "The society has 24×7 security, a rooftop garden, and covered parking. "
        "Ideal for families looking for a quiet neighbourhood with good connectivity."
    ),
    (
        "A compact but efficiently laid-out {bhk}BHK in a {age}-year-old mid-rise building. "
        "Comes with {features} and a dedicated parking spot. "
        "Close to corporate hubs and expressway access."
    ),
]

LAND_DESCS = [
    (
        "A {sqft} sq ft residential plot in one of {area}'s fastest-growing micro-markets. "
        "North-facing, on a 30-ft wide road. "
        "Suitable for a G+3 structure; all approvals in place."
    ),
    (
        "Corner plot of {sqft} sq ft with excellent road access on two sides. "
        "Electricity, water, and drainage connections available. "
        "Ideal for a standalone bungalow or investor holding."
    ),
]

FEATURES = [
    "modular kitchen and vitrified tiles",
    "Italian marble flooring and a split AC in every room",
    "premium fittings and a large balcony",
    "wooden flooring in the master bedroom and a gourmet kitchen",
    "false ceiling with LED lighting and a walk-in wardrobe",
]


def _jitter(coord: float, radius: float = 0.015) -> float:
    """Add a small random offset to a coordinate so listings spread across a neighbourhood."""
    return round(coord + random.uniform(-radius, radius), 6)


def _make_flat(faker: Faker, neighbourhood: dict) -> dict:
    bhk = random.choice([1, 2, 3])
    floor = random.choice(["2nd", "3rd", "5th", "7th", "top"])
    age = random.randint(2, 12)
    price = round(random.uniform(35, 180) * 1e5, 2)  # ₹35L – ₹1.8Cr

    title = random.choice(FLAT_TITLES).format(bhk=bhk)
    title += f", {neighbourhood['name']}"
    desc = random.choice(FLAT_DESCS).format(
        bhk=bhk,
        floor=floor,
        age=age,
        features=random.choice(FEATURES),
    )
    return {
        "title": title,
        "description": desc,
        "price": Decimal(str(price)),
        "property_type": "flat",
        "lat": _jitter(neighbourhood["lat"]),
        "lng": _jitter(neighbourhood["lng"]),
    }


def _make_land(faker: Faker, neighbourhood: dict) -> dict:
    sqft = random.choice([800, 1000, 1200, 1500, 2000, 2700])
    price = round(sqft * random.uniform(4500, 12000), 2)  # ₹4500–₹12000/sq ft

    title = random.choice(LAND_TITLES).format(area=neighbourhood["name"])
    desc = random.choice(LAND_DESCS).format(sqft=sqft, area=neighbourhood["name"])
    return {
        "title": title,
        "description": desc,
        "price": Decimal(str(price)),
        "property_type": "house_land",
        "lat": _jitter(neighbourhood["lat"]),
        "lng": _jitter(neighbourhood["lng"]),
    }


def generate_listings(n: int = 18) -> list[dict]:
    """Generate n fake listings with a roughly 70/30 flat/land split."""
    faker = Faker("en_IN")
    listings = []
    for i in range(n):
        neighbourhood = NEIGHBOURHOODS[i % len(NEIGHBOURHOODS)]
        if i % 10 < 7:  # 70% flats
            listings.append(_make_flat(faker, neighbourhood))
        else:
            listings.append(_make_land(faker, neighbourhood))
    random.shuffle(listings)
    return listings


def main() -> None:
    try:
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # quick connection check
    except Exception as exc:
        print(
            f"\n[ERROR] Could not connect to the database.\n"
            f"  Make sure the Docker container is running:\n"
            f"    docker-compose up -d\n"
            f"  And that DATABASE_URL in .env is correct:\n"
            f"    DATABASE_URL=postgresql://reality_ai:reality_ai_secret@localhost:5432/reality_ai\n"
            f"\n  Original error: {exc}\n"
        )
        sys.exit(1)

    listings = generate_listings(18)

    with engine.begin() as conn:
        # Safe to re-run: clear existing rows first
        deleted = conn.execute(text("DELETE FROM listings")).rowcount
        if deleted:
            print(f"  Cleared {deleted} existing row(s) from listings table.")

        conn.execute(
            text(
                """
                INSERT INTO listings (title, description, price, property_type, lat, lng)
                VALUES (:title, :description, :price, :property_type, :lat, :lng)
                """
            ),
            listings,
        )

    # ── Summary ────────────────────────────────────────────────────────────
    prices = [float(l["price"]) for l in listings]
    flat_count = sum(1 for l in listings if l["property_type"] == "flat")
    land_count = len(listings) - flat_count

    print(f"\n[OK] Seeded {len(listings)} listings into '{DATABASE_URL.split('/')[-1]}':")
    print(f"   Property types : {flat_count} flat | {land_count} house_land")
    print(f"   Price range    : Rs.{min(prices):,.0f}  --  Rs.{max(prices):,.0f}")
    print(f"   Avg price      : Rs.{sum(prices)/len(prices):,.0f}")
    print(f"   Neighbourhoods : {', '.join(n['name'] for n in NEIGHBOURHOODS)}")
    print("\n   Sample titles:")
    for l in listings[:4]:
        print(f"     - {l['title']}  (Rs.{float(l['price']):,.0f})")
    print()


if __name__ == "__main__":
    main()
