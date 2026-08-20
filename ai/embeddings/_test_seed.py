"""Seed script — inserts 210 fake listings for Surat, Gujarat into the local dev database.

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
        "       DATABASE_URL=postgresql://reality_ai:reality_ai_secret@localhost:5433/reality_ai\n"
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
# Surat neighbourhood anchor points (real coordinates, Gujarat, India)
# ---------------------------------------------------------------------------
NEIGHBOURHOODS = [
    {"name": "Adajan",         "lat": 21.1848, "lng": 72.7803, "tier": "premium"},
    {"name": "Vesu",           "lat": 21.1545, "lng": 72.7757, "tier": "premium"},
    {"name": "Athwa",          "lat": 21.1880, "lng": 72.8263, "tier": "premium"},
    {"name": "Piplod",         "lat": 21.1600, "lng": 72.8000, "tier": "premium"},
    {"name": "Citylight",      "lat": 21.1724, "lng": 72.8101, "tier": "premium"},
    {"name": "Pal",            "lat": 21.1977, "lng": 72.7742, "tier": "mid"},
    {"name": "Althan",         "lat": 21.1674, "lng": 72.8180, "tier": "mid"},
    {"name": "Bhatar",         "lat": 21.1882, "lng": 72.8500, "tier": "mid"},
    {"name": "Ghod Dod Road",  "lat": 21.1790, "lng": 72.8198, "tier": "premium"},
    {"name": "Palanpur",       "lat": 21.2088, "lng": 72.8056, "tier": "mid"},
    {"name": "Jahangirpura",   "lat": 21.2218, "lng": 72.8289, "tier": "mid"},
    {"name": "Varachha",       "lat": 21.2197, "lng": 72.8684, "tier": "budget"},
    {"name": "Katargam",       "lat": 21.2377, "lng": 72.8428, "tier": "budget"},
    {"name": "Udhna",          "lat": 21.2120, "lng": 72.8400, "tier": "budget"},
    {"name": "Dumas",          "lat": 21.0977, "lng": 72.7166, "tier": "premium"},
    {"name": "Sarthana",       "lat": 21.2356, "lng": 72.8741, "tier": "budget"},
    {"name": "Rander",         "lat": 21.2360, "lng": 72.7669, "tier": "mid"},
    {"name": "Sachin",         "lat": 21.0862, "lng": 72.8641, "tier": "budget"},
    {"name": "Puna Kumbharia", "lat": 21.2551, "lng": 72.8211, "tier": "budget"},
    {"name": "Kapodra",        "lat": 21.2282, "lng": 72.8059, "tier": "budget"},
]

# ---------------------------------------------------------------------------
# Price bands by neighbourhood tier
# ---------------------------------------------------------------------------
PRICE_BANDS = {
    "premium": {
        "flat_1bhk": (3500000,  6500000),
        "flat_2bhk": (6000000, 12000000),
        "flat_3bhk": (9000000, 22000000),
        "flat_4bhk": (16000000, 45000000),
        "land_sqft": (8000, 22000),
    },
    "mid": {
        "flat_1bhk": (2000000,  4000000),
        "flat_2bhk": (3500000,  7500000),
        "flat_3bhk": (5500000, 12000000),
        "flat_4bhk": (9000000, 18000000),
        "land_sqft": (4500, 10000),
    },
    "budget": {
        "flat_1bhk": (1000000,  2500000),
        "flat_2bhk": (1800000,  4000000),
        "flat_3bhk": (3000000,  6500000),
        "flat_4bhk": (5000000, 10000000),
        "land_sqft": (2000,  5500),
    },
}

FLAT_TITLE_TEMPLATES = [
    "{bhk}BHK flat near {landmark}",
    "Spacious {bhk}BHK in {society}, {area}",
    "Modern {bhk}BHK with {feature} in {area}",
    "Ready-to-move {bhk}BHK apartment, {area}",
    "Well-ventilated {bhk}BHK near {landmark}",
    "Semi-furnished {bhk}BHK in gated society, {area}",
    "New {bhk}BHK flat - {floors}-storey building, {area}",
    "Corner {bhk}BHK with city view, {area}",
    "{bhk}BHK luxury flat with gym & pool, {area}",
    "{bhk}BHK flat - {floors} floors, {facing}-facing, {area}",
]

LAND_TITLE_TEMPLATES = [
    "Residential plot in {area}",
    "Corner plot near {landmark}",
    "{sqft} sq ft NA plot, {area}",
    "Prime plot on {road} road, {area}",
    "Bungalow plot in {area} society",
    "AUDA-approved plot, {area}",
    "Freehold residential plot, {area}",
    "Plot with {road}-ft road frontage, {area}",
]

SURAT_LANDMARKS = {
    "Adajan":         ["VR Mall", "Adajan Patiya", "L.P. Savani School"],
    "Vesu":           ["Dumas Road", "Vesu Main Road", "Iscon-Ambli Road"],
    "Athwa":          ["Athwa Gate", "Ghod Dod Road", "Surat Railway Station"],
    "Piplod":         ["Piplod Circle", "Udhna Darwaja", "City Light Road"],
    "Citylight":      ["Citylight Cinema", "Citylight Road", "Tapi River"],
    "Pal":            ["Pal Circle", "Pal Gam Road", "Surat Airport"],
    "Althan":         ["Althan Circle", "SNS College", "VIP Road"],
    "Bhatar":         ["Bhatar Road", "Ring Road", "Bhatar Char Rasta"],
    "Ghod Dod Road":  ["Ghod Dod Circle", "Parle Point", "Nirmala Convent"],
    "Palanpur":       ["Palanpur Patia", "Surat-Navsari Highway", "BRTS"],
    "Jahangirpura":   ["Jahangir Circle", "Surat Municipal Market", "NH-48"],
    "Varachha":       ["Varachha Road", "Umra Road", "Diamond Market"],
    "Katargam":       ["Katargam Gate", "Textile Market", "Ring Road"],
    "Udhna":          ["Udhna Darwaja", "GIDC", "Udhna Magdalla Road"],
    "Dumas":          ["Dumas Beach", "Dumas Road", "Arabian Sea"],
    "Sarthana":       ["Sarthana Nature Park", "Tapi River", "Sarthana Jakatnaka"],
    "Rander":         ["Rander Road", "Rander Village", "Tapi River"],
    "Sachin":         ["Sachin GIDC", "Sachin-Surat Highway", "Hazira Road"],
    "Puna Kumbharia": ["Kumbharia Circle", "Surat-Gandhinagar Highway", "BRTS"],
    "Kapodra":        ["Kapodra Circle", "Udhna Magdalla Road", "Surat Ring Road"],
}

SOCIETIES = [
    "Shree Residency", "Param Heights", "Shivalay Tower",
    "Om Shanti Complex", "Krishna Villa", "Sai Elegance",
    "Titanium City Centre", "Aakar Heights", "Siddhivinayak Tower",
    "Ganesh Residency", "Diamond Tower", "Silver Arch",
    "Royal Garden", "Nilamber Harmony", "Aura Homes",
    "Bhoomi Greens", "Rajhans Montessa", "Sun Infra Tower",
    "Unique Shanti", "Synergy Towers",
]

FLAT_FEATURES = [
    "parking and modular kitchen",
    "rooftop terrace and gym",
    "covered parking and split ACs",
    "Italian marble flooring",
    "false ceiling and LED lighting",
    "walk-in wardrobe and premium fittings",
    "garden-facing balcony",
    "24x7 security and CCTV",
    "solar power backup",
    "clubhouse and swimming pool",
]

ROADS = ["30-ft", "40-ft", "60-ft", "80-ft", "100-ft"]
FACINGS = ["North", "South", "East", "West", "North-East", "South-West"]

FLAT_DESC_TEMPLATES = [
    (
        "A well-maintained {bhk}BHK apartment on the {floor}{suffix} floor of {society} in {area}. "
        "The flat features {feature}. "
        "{walkdist} from {landmark}, making it ideal for working professionals."
    ),
    (
        "Bright and airy {bhk}BHK in {society}, {area}. "
        "The unit comes with {feature} and dedicated parking. "
        "The society has 24x7 security and a rooftop garden. "
        "Excellent connectivity to {landmark} and the main arterial roads."
    ),
    (
        "A {bhk}BHK flat in a {age}-year-old society in {area}. "
        "{feature_cap} included. "
        "{area} is a well-established {tier} locality with reliable water supply, "
        "wide roads, and proximity to top schools and hospitals."
    ),
    (
        "Compact yet thoughtfully designed {bhk}BHK in {area}. "
        "Floor: {floor}{suffix}. Features: {feature}. "
        "Close to {landmark} and within 10 minutes of Surat's textile market district."
    ),
    (
        "Investor alert — {bhk}BHK in {area} with a monthly rental potential of "
        "Rs.{rent:,}. "
        "Society: {society}. Features: {feature}. "
        "Ready to move in; all legal clearances in place."
    ),
]

LAND_DESC_TEMPLATES = [
    (
        "A {sqft} sq ft residential plot on a {road}-ft wide road in {area}. "
        "{facing}-facing. "
        "Suitable for G+3 construction. All utility connections available. "
        "Walking distance to {landmark}."
    ),
    (
        "Corner plot of {sqft} sq ft in {area} — two-road frontage, {road}-ft and 20-ft. "
        "NA (Non-Agriculture) clearance obtained. "
        "Near {landmark}; ideal for a bungalow or small apartment building."
    ),
    (
        "Prime {sqft} sq ft residential plot in {area} near {landmark}. "
        "Level ground, {facing}-facing. "
        "Electricity, water, and drainage connections on boundary. "
        "SUDA-approved layout."
    ),
]


def ordinal_suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _jitter(coord: float, radius: float = 0.012) -> float:
    return round(coord + random.uniform(-radius, radius), 6)


def _walk_distance() -> str:
    mins = random.choice([5, 7, 8, 10, 12, 15])
    return f"{mins}-minute walk"


def _make_flat(neighbourhood: dict) -> dict:
    area = neighbourhood["name"]
    tier = neighbourhood["tier"]
    bhk = random.choices([1, 2, 3, 4], weights=[15, 40, 35, 10])[0]
    floor = random.randint(1, 15)
    suffix = ordinal_suffix(floor)
    floors = random.randint(floor, floor + random.randint(2, 8))
    age = random.randint(0, 10)
    feature = random.choice(FLAT_FEATURES)
    feature_cap = feature[0].upper() + feature[1:]
    society = random.choice(SOCIETIES)
    landmark = random.choice(SURAT_LANDMARKS.get(area, ["Surat Railway Station"]))
    facing = random.choice(FACINGS)
    band = PRICE_BANDS[tier][f"flat_{bhk}bhk"]
    price = round(random.uniform(*band), -3)
    rent = int(price * random.uniform(0.003, 0.005))

    title_tmpl = random.choice(FLAT_TITLE_TEMPLATES)
    title = title_tmpl.format(
        bhk=bhk, landmark=landmark, society=society, area=area,
        feature=feature, floors=floors, facing=facing,
    )

    desc_tmpl = random.choice(FLAT_DESC_TEMPLATES)
    desc = desc_tmpl.format(
        bhk=bhk, floor=floor, suffix=suffix, society=society, area=area,
        feature=feature, feature_cap=feature_cap, landmark=landmark,
        age=age, tier=tier, rent=rent, walkdist=_walk_distance(),
    )

    return {
        "title": title,
        "description": desc,
        "price": Decimal(str(price)),
        "property_type": "flat",
        "lat": _jitter(neighbourhood["lat"]),
        "lng": _jitter(neighbourhood["lng"]),
    }


def _make_land(neighbourhood: dict) -> dict:
    area = neighbourhood["name"]
    tier = neighbourhood["tier"]
    sqft = random.choice([600, 800, 1000, 1200, 1500, 2000, 2500, 3000])
    road = random.choice(ROADS)
    facing = random.choice(FACINGS)
    landmark = random.choice(SURAT_LANDMARKS.get(area, ["Surat Railway Station"]))
    sqft_rate = random.uniform(*PRICE_BANDS[tier]["land_sqft"])
    price = round(sqft * sqft_rate, -3)

    title_tmpl = random.choice(LAND_TITLE_TEMPLATES)
    title = title_tmpl.format(
        area=area, landmark=landmark, sqft=sqft, road=road,
    )

    desc_tmpl = random.choice(LAND_DESC_TEMPLATES)
    desc = desc_tmpl.format(
        sqft=sqft, road=road, area=area, facing=facing, landmark=landmark,
    )

    return {
        "title": title,
        "description": desc,
        "price": Decimal(str(price)),
        "property_type": "house_land",
        "lat": _jitter(neighbourhood["lat"]),
        "lng": _jitter(neighbourhood["lng"]),
    }


def generate_listings(n: int = 210) -> list[dict]:
    """Generate n listings across Surat neighbourhoods — roughly 75% flat, 25% land."""
    random.seed(42)  # reproducible
    listings = []
    for i in range(n):
        neighbourhood = NEIGHBOURHOODS[i % len(NEIGHBOURHOODS)]
        if random.random() < 0.75:
            listings.append(_make_flat(neighbourhood))
        else:
            listings.append(_make_land(neighbourhood))
    random.shuffle(listings)
    return listings


def main() -> None:
    try:
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(
            f"\n[ERROR] Could not connect to the database.\n"
            f"  Make sure the Docker container is running:\n"
            f"    docker-compose up -d\n"
            f"  And that DATABASE_URL in .env is correct:\n"
            f"    DATABASE_URL=postgresql://reality_ai:reality_ai_secret@localhost:5433/reality_ai\n"
            f"\n  Original error: {exc}\n"
        )
        sys.exit(1)

    listings = generate_listings(210)

    with engine.begin() as conn:
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
    flat_count  = sum(1 for l in listings if l["property_type"] == "flat")
    land_count  = len(listings) - flat_count

    by_area: dict[str, int] = {}
    for l in listings:
        # Find which neighbourhood this listing belongs to (by nearest anchor)
        pass

    print(f"\n[OK] Seeded {len(listings)} Surat listings into '{DATABASE_URL.split('/')[-1]}':")
    print(f"   Property types : {flat_count} flat | {land_count} house_land")
    print(f"   Price range    : Rs.{min(prices):,.0f}  --  Rs.{max(prices):,.0f}")
    print(f"   Avg price      : Rs.{sum(prices)/len(prices):,.0f}")
    print(f"   Neighbourhoods : {len(NEIGHBOURHOODS)} areas across Surat city")
    print(f"   Coverage       : Adajan, Vesu, Athwa, Piplod, Citylight, Pal, Althan,")
    print(f"                    Bhatar, Ghod Dod Rd, Palanpur, Jahangirpura, Varachha,")
    print(f"                    Katargam, Udhna, Dumas, Sarthana, Rander, Sachin,")
    print(f"                    Puna Kumbharia, Kapodra")
    print(f"\n   Sample listings:")
    for l in random.sample(listings, 5):
        print(f"     [{l['property_type'][:4]}] {l['title']}  (Rs.{float(l['price']):,.0f})")
    print()


if __name__ == "__main__":
    main()
