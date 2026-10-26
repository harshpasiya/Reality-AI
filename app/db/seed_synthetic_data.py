"""Synthetic data seeder — generates realistic test data for Surat, Gujarat.

Usage:
    python -m app.db.seed_synthetic_data              # default counts
    python -m app.db.seed_synthetic_data --force      # overwrite existing rows
    python -m app.db.seed_synthetic_data -n 200       # custom listing count
    python -m app.db.seed_synthetic_data --reset      # DELETE all rows first, then seed

The listing data comes from the AI track (``app/db/surat_reference_data.py``,
copied from ``ai/nlu/gazetteer.py`` and ``ai/embeddings/_test_seed.py``):
gazetteer locality centroids and radii, tier-based price bands, and the AI
seed's title / description templates.  Titles and descriptions name the BHK,
property type and locality because the AI ranks listings by the meaning of
exactly that text, and the chat reply prints the title.

After seeding, run the AI pipelines so chat search can find the listings:
    python -m ai.embeddings.embed_listings         # embeddings (search needs them)
    python -m ai.amenities.amenities_service       # amenities (needs GOOGLE_PLACES_API_KEY)
"""

import argparse
import random
import sys

from faker import Faker
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.surat_reference_data import (
    FACINGS,
    FLAT_DESC_TEMPLATES,
    FLAT_FEATURES,
    FLAT_TITLE_TEMPLATES,
    LAND_DESC_TEMPLATES,
    LAND_TITLE_TEMPLATES,
    LOCALITIES,
    PRICE_BANDS,
    ROADS,
    SOCIETIES,
    SURAT_LANDMARKS,
)
from app.models.broker import Broker
from app.models.customer import Customer
from app.models.listing import Listing
from app.models.lead import Lead
from app.models.conversation import Conversation

fake = Faker("en_IN")

# Kept for scripts that only need points (e.g. the load test).
REAL_CITY_COORDS: list[tuple[float, float]] = [
    (loc["lat"], loc["lng"]) for loc in LOCALITIES.values()
]

# Share of each listing kind.  The AI seed only has flats (75%) and plots
# (25%); houses are added because the AI eval set asks for bungalows, row
# houses, villas and tenements (property_type house_land, bhk null).
KIND_WEIGHTS = {"flat": 72, "plot": 18, "house": 10}

# Carpet area (sq ft) by BHK — the AI seed has no areas; these are typical
# Surat ranges so price per sq ft stays plausible.
FLAT_CARPET_SQFT = {1: (380, 560), 2: (600, 900), 3: (900, 1400), 4: (1400, 2300)}
PLOT_SQFT = [600, 800, 1000, 1200, 1500, 2000, 2500, 3000]  # as in the AI seed

HOUSE_KINDS = ["bungalow", "row house", "villa", "tenement"]
HOUSE_FEATURES = ["private garden", "car parking", "terrace", "modular kitchen",
                  "corner plot", "gated society", "balcony"]
HOUSE_TITLE_TEMPLATES = [
    "{bhk}BHK {kind} in {area}",
    "{bhk}BHK {kind} with {feature}, {area}",
    "Independent {bhk}BHK {kind} near {landmark}",
]
HOUSE_DESC_TEMPLATES = [
    "A {bhk}BHK {kind} in {area} on a {plot} sq ft plot with {built_up} sq ft built-up area. "
    "Comes with {feature}. Close to {landmark}.",
    "{facing}-facing {bhk}BHK {kind} in {area}, {floors} floors, {built_up} sq ft built-up. "
    "Highlights: {feature}. Near {landmark}.",
]
CONSTRUCTION_RATE_PER_SQFT = (1800, 3200)

# Status mix for a believable inventory (most listings are on the market).
STATUS_WEIGHTS = {"available": 85, "under_offer": 6, "sold": 6, "withdrawn": 3}
LEAD_STATUS_WEIGHTS = {"new": 40, "contacted": 30, "visit_scheduled": 15, "closed": 7, "lost": 8}
LEAD_MESSAGES = [
    "Is the price negotiable?",
    "Is parking included?",
    "Can I visit this weekend?",
    "What is the maintenance per month?",
    "Is a home loan available for this property?",
    None,
]


def _ordinal_suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _jitter(lat: float, lng: float, radius_m: float) -> tuple[float, float]:
    """A random point within half the locality's search radius.

    The AI seed jitters up to ~1.3 km, which puts some listings outside a
    1500 m locality circle; half the radius keeps every seeded listing inside
    the AI's exact-match search for its locality.
    """
    # ~0.009 degrees per km at Surat's latitude; the square's corner stays inside the circle
    delta = (radius_m / 2000) * 0.009 / 1.4142
    return (
        round(lat + random.uniform(-delta, delta), 6),
        round(lng + random.uniform(-delta, delta), 6),
    )


def _broker_phone() -> str:
    """A random Indian mobile number in E.164 form."""
    return "+91" + str(random.randint(6, 9)) + "".join(random.choices("0123456789", k=9))


def _road_values(road: str) -> dict:
    """``ROADS`` entries already end in "-ft"; some templates add "-ft" again."""
    return {"road": road, "road_ft": road.removesuffix("-ft")}


def _fill(template: str, **values) -> str:
    # "{road}-ft" in the AI templates would render "30-ft-ft"
    return template.replace("{road}-ft", "{road_ft}-ft").format(**values)


def _flat(area: str) -> dict:
    """A flat built from the AI seed's templates and tier price bands."""
    tier = LOCALITIES[area]["tier"]
    bhk = random.choices([1, 2, 3, 4], weights=[15, 40, 35, 10])[0]
    floor = random.randint(1, 15)
    floors = random.randint(floor, floor + random.randint(2, 8))
    feature = random.choice(FLAT_FEATURES)
    price = round(random.uniform(*PRICE_BANDS[tier][f"flat_{bhk}bhk"]), -3)
    carpet = round(random.uniform(*FLAT_CARPET_SQFT[bhk]))
    values = dict(
        bhk=bhk, floor=floor, suffix=_ordinal_suffix(floor), floors=floors,
        society=random.choice(SOCIETIES), area=area, tier=tier,
        landmark=random.choice(SURAT_LANDMARKS[area]), facing=random.choice(FACINGS),
        feature=feature, feature_cap=feature[0].upper() + feature[1:],
        age=random.randint(0, 10), rent=int(price * random.uniform(0.003, 0.005)),
        walkdist=f"{random.choice([5, 7, 8, 10, 12, 15])}-minute walk",
    )
    bathrooms = max(1, bhk - random.choice([0, 1]))
    return {
        "property_type": "flat",
        "title": _fill(random.choice(FLAT_TITLE_TEMPLATES), **values),
        "description": _fill(random.choice(FLAT_DESC_TEMPLATES), **values)
        + f" Carpet area {carpet} sq ft.",
        "price": price,
        "carpet_area": carpet,
        "built_up_area": round(carpet * random.uniform(1.15, 1.3)),
        "plot_area": None,
        "floor_number": floor,
        "rooms": {"bedrooms": bhk, "bathrooms": bathrooms,
                  "balconies": random.choice([0, 1, 2]), "hall": 1, "kitchen": 1},
    }


def _plot(area: str) -> dict:
    """An open plot from the AI seed's land templates (rooms is NULL)."""
    tier = LOCALITIES[area]["tier"]
    sqft = random.choice(PLOT_SQFT)
    values = dict(
        area=area, sqft=sqft, facing=random.choice(FACINGS),
        landmark=random.choice(SURAT_LANDMARKS[area]), **_road_values(random.choice(ROADS)),
    )
    return {
        "property_type": "house_land",
        "title": _fill(random.choice(LAND_TITLE_TEMPLATES), **values),
        "description": _fill(random.choice(LAND_DESC_TEMPLATES), **values),
        "price": round(sqft * random.uniform(*PRICE_BANDS[tier]["land_sqft"]), -3),
        "carpet_area": None,
        "built_up_area": None,
        "plot_area": sqft,
        "floor_number": None,
        "rooms": None,  # open plots have no rooms
    }


def _house(area: str) -> dict:
    """A bungalow / row house / villa / tenement: land price + construction."""
    tier = LOCALITIES[area]["tier"]
    bhk = random.choices([2, 3, 4, 5], weights=[20, 40, 30, 10])[0]
    plot = random.choice(PLOT_SQFT[2:])
    floors = random.choice([1, 2, 3])
    built_up = min(round(plot * random.uniform(0.6, 0.9)) * floors, 450 * bhk + 600)
    price = round(
        plot * random.uniform(*PRICE_BANDS[tier]["land_sqft"])
        + built_up * random.uniform(*CONSTRUCTION_RATE_PER_SQFT),
        -3,
    )
    feature = random.choice(HOUSE_FEATURES)
    values = dict(
        bhk=bhk, kind=random.choice(HOUSE_KINDS), area=area, feature=feature,
        landmark=random.choice(SURAT_LANDMARKS[area]), facing=random.choice(FACINGS),
        plot=plot, built_up=built_up, floors=floors,
    )
    return {
        "property_type": "house_land",
        "title": random.choice(HOUSE_TITLE_TEMPLATES).format(**values),
        "description": random.choice(HOUSE_DESC_TEMPLATES).format(**values),
        "price": price,
        "carpet_area": None,
        "built_up_area": built_up,
        "plot_area": plot,
        "floor_number": None,
        "rooms": {"bedrooms": bhk, "bathrooms": max(2, bhk - 1),
                  "balconies": random.choice([1, 2]), "hall": 1, "kitchen": 1,
                  "garden": int(feature == "private garden")},
    }


_MAKERS = {"flat": _flat, "plot": _plot, "house": _house}


def seed(
    n_listings: int = 500,
    n_brokers: int = 10,
    n_customers: int = 30,
) -> None:
    """Seed the database with synthetic data.

    Leaves ``embedding`` and ``amenities`` as NULL — those columns are
    populated by Person 1's AI pipelines, not this script.
    """
    db = SessionLocal()
    try:
        # ── Brokers ──────────────────────────────────────────────
        brokers: list[Broker] = []
        dummy_hash = hash_password("password123")
        for _ in range(n_brokers):
            phone = _broker_phone()
            broker = Broker(
                name=fake.name(),
                email=fake.unique.email(),
                phone=phone,
                phone_hash=hash_password(phone),
                password_hash=dummy_hash,
            )
            db.add(broker)
            brokers.append(broker)
        db.flush()
        print(f"  Created {len(brokers)} brokers")

        # ── Customers ───────────────────────────────────────────
        customers: list[Customer] = []
        for _ in range(n_customers):
            customer = Customer(
                name=fake.name(),
                email=fake.unique.email(),
                password_hash=dummy_hash,
            )
            db.add(customer)
            customers.append(customer)
        db.flush()
        print(f"  Created {len(customers)} customers")

        # ── Listings ────────────────────────────────────────────
        listings: list[Listing] = []
        area_of: dict[int, str] = {}
        statuses, status_weights = zip(*STATUS_WEIGHTS.items())
        kinds, kind_weights = zip(*KIND_WEIGHTS.items())
        areas = list(LOCALITIES)
        for i in range(n_listings):
            area = areas[i % len(areas)]  # even coverage, as in the AI seed
            loc = LOCALITIES[area]
            lat, lng = _jitter(loc["lat"], loc["lng"], loc["radius_m"])
            spec = _MAKERS[random.choices(kinds, weights=kind_weights)[0]](area)

            listing = Listing(
                broker_id=random.choice(brokers).id,
                location=WKTElement(f"POINT({lng} {lat})", srid=4326),
                status=random.choices(statuses, weights=status_weights)[0],
                view_count=random.randint(0, 60),
                **spec,
            )
            db.add(listing)
            # Flush one row at a time: SQLAlchemy's batched INSERT casts every
            # column, including embedding::VECTOR, which fails on dev databases
            # without pgvector (embedding is JSONB there).
            db.flush()
            listings.append(listing)
            area_of[listing.id] = area

        print(f"  Created {n_listings} listings")

        # ── Leads (explicit enquiries, one per customer and listing) ──
        leads_count = 0
        lead_statuses, lead_weights = zip(*LEAD_STATUS_WEIGHTS.items())
        visible = [l for l in listings if l.status in ("available", "under_offer")] or listings
        for customer in customers:
            for l in random.sample(visible, k=min(len(visible), random.randint(1, 3))):
                db.add(Lead(
                    listing_id=l.id,
                    customer_id=customer.id,
                    message=random.choice(LEAD_MESSAGES),
                    status=random.choices(lead_statuses, weights=lead_weights)[0],
                ))
                leads_count += 1
        db.flush()
        print(f"  Created {leads_count} leads")

        # ── Conversations ──────────────────────────────────────
        conv_count = 0
        for customer in customers[:10]:
            # Same question as the message below: 2 BHK flats in Adajan
            shown = [
                l for l in visible
                if area_of[l.id] == "Adajan" and (l.rooms or {}).get("bedrooms") == 2
            ][:3] or visible[:3]
            conv = Conversation(
                customer_id=customer.id,
                messages=[
                    {"role": "user", "content": "Looking for 2BHK flats in Adajan", "timestamp": "2026-10-01T10:00:00+00:00"},
                    {"role": "assistant", "content": "[PLACEHOLDER MODE] Here are top properties in Adajan", "timestamp": "2026-10-01T10:00:02+00:00", "listing_ids": [l.id for l in shown]},
                ]
            )
            db.add(conv)
            conv_count += 1
        print(f"  Created {conv_count} sample conversations")

        db.commit()
        print(f"\nSeed complete: {n_brokers} brokers, {n_customers} customers, {n_listings} listings, {leads_count} leads, {conv_count} conversations")

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Reality AI database with synthetic data")
    parser.add_argument("-n", "--n-listings", type=int, default=500, help="Number of listings")
    parser.add_argument("--n-brokers", type=int, default=10, help="Number of brokers")
    parser.add_argument("--n-customers", type=int, default=30, help="Number of customers")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if tables already contain data",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete ALL brokers, customers, listings, leads and conversations before seeding",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            db.execute(text(
                "TRUNCATE lead, conversation, listing, customer, broker RESTART IDENTITY"
            ))
            db.commit()
            print("Reset: emptied lead, conversation, listing, customer and broker tables.")
        existing = db.query(Listing).count()
        if existing > 0 and not args.force:
            print(
                f"Database already has {existing} listings. "
                "Use --force to seed anyway (will add more rows, not replace)."
            )
            sys.exit(1)
    finally:
        db.close()

    print("Seeding database...")
    seed(
        n_listings=args.n_listings,
        n_brokers=args.n_brokers,
        n_customers=args.n_customers,
    )


if __name__ == "__main__":
    main()
