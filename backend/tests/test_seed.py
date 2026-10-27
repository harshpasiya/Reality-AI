"""Seed data checks — seeded listings must be findable by the AI's locality search."""

import math
import random

import pytest

from app.db import surat_reference_data as ref
from app.db.seed_synthetic_data import _flat, _house, _jitter, _plot


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine distance between two (lat, lng) points."""
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def test_jitter_stays_inside_gazetteer_radius():
    """Every seeded point is within its locality's AI search circle (exact match)."""
    random.seed(0)
    for name, loc in ref.LOCALITIES.items():
        for _ in range(500):
            point = _jitter(loc["lat"], loc["lng"], loc["radius_m"])
            assert _distance_m((loc["lat"], loc["lng"]), point) <= loc["radius_m"], name


def test_reference_data_matches_ai_gazetteer():
    """Once the ai/ package is importable, the copied centroids must still match."""
    gazetteer = pytest.importorskip("ai.nlu.gazetteer")
    assert set(gazetteer.LOCALITIES) == set(ref.LOCALITIES)
    for name, loc in ref.LOCALITIES.items():
        ai_loc = gazetteer.LOCALITIES[name]
        assert (ai_loc["lat"], ai_loc["lng"], ai_loc["radius_m"]) == (
            loc["lat"], loc["lng"], loc["radius_m"]
        ), name


def test_every_locality_has_landmarks_and_a_price_tier():
    for name, loc in ref.LOCALITIES.items():
        assert ref.SURAT_LANDMARKS[name], name
        assert loc["tier"] in ref.PRICE_BANDS, name


def test_flat_price_follows_tier_band_and_has_bedrooms():
    random.seed(1)
    for area, loc in ref.LOCALITIES.items():
        flat = _flat(area)
        bhk = flat["rooms"]["bedrooms"]
        low, high = ref.PRICE_BANDS[loc["tier"]][f"flat_{bhk}bhk"]
        assert low - 1000 <= flat["price"] <= high + 1000
        assert f"{bhk}BHK" in flat["title"]


def test_templates_render_without_placeholders():
    random.seed(2)
    for area in ref.LOCALITIES:
        for make in (_flat, _plot, _house):
            spec = make(area)
            for text in (spec["title"], spec["description"]):
                assert "{" not in text and "-ft-ft" not in text, text


def test_open_plots_have_no_rooms_and_houses_do():
    plot, house = _plot("Pal"), _house("Piplod")
    assert plot["rooms"] is None and plot["property_type"] == "house_land"
    assert house["rooms"]["bedrooms"] >= 2 and house["property_type"] == "house_land"
