"""Tests for ai.nlu.gazetteer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ai.nlu.gazetteer import LANDMARKS, LOCALITIES, get_place, resolve_place

_SEED_FILE = Path(__file__).resolve().parents[2] / "embeddings" / "_test_seed.py"


def _seed_neighbourhoods() -> list[dict]:
    """Read NEIGHBOURHOODS from _test_seed.py without importing it.

    Importing the seed script would exit the process when DATABASE_URL is
    unset, so the literal is pulled out of its source instead.
    """
    tree = ast.parse(_SEED_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "NEIGHBOURHOODS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("NEIGHBOURHOODS not found in _test_seed.py")


def test_every_seed_neighbourhood_is_a_locality() -> None:
    for hood in _seed_neighbourhoods():
        assert hood["name"] in LOCALITIES, f"{hood['name']} missing from LOCALITIES"


def test_locality_coordinates_match_seed() -> None:
    for hood in _seed_neighbourhoods():
        loc = LOCALITIES[hood["name"]]
        assert (loc["lat"], loc["lng"]) == (hood["lat"], hood["lng"]), hood["name"]


def test_every_entry_has_radius_and_lowercase_aliases() -> None:
    for table in (LOCALITIES, LANDMARKS):
        for name, data in table.items():
            assert data["radius_m"] in (1500, 2000, 2500), name
            assert all(a == a.lower() for a in data["aliases"]), name


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3bhk in Vesu", "Vesu"),
        ("VESU", "Vesu"),
        ("flat in city light", "Citylight"),
        ("ghoddod road", "Ghod Dod Road"),
        ("ghod dod", "Ghod Dod Road"),
        ("punakumbharia", "Puna Kumbharia"),
        ("near VR Mall", "VR Mall"),
        ("plot near dumas road", "Dumas Road"),  # longest match beats "Dumas"
        ("Ghod Dod Raod", "Ghod Dod Road"),  # misspelling -> fuzzy
        ("piploud", "Piplod"),  # misspelling -> fuzzy
        ("Vesu or Citylight", "Vesu"),  # first mentioned wins
        ("Citylight or Vesu", "Citylight"),
    ],
)
def test_resolve_place(text: str, expected: str) -> None:
    result = resolve_place(text)
    assert result is not None, text
    assert result[0] == expected


@pytest.mark.parametrize("text", ["xyz", "", "   ", "apple", "budget", "under", "parking"])
def test_resolve_place_no_match(text: str) -> None:
    assert resolve_place(text) is None


def test_short_strings_are_never_fuzzy_matched() -> None:
    assert resolve_place("pak") is None  # 1 edit from "pal", but too short to fuzz
    assert resolve_place("pal") is not None  # exact alias still works


def test_info_shape_and_get_place() -> None:
    name, info = resolve_place("adajan")
    assert name == "Adajan"
    assert set(info) == {"lat", "lng", "radius_m", "kind"}
    assert info["kind"] == "locality"
    assert get_place("VR Mall")["kind"] == "landmark"
    assert get_place("Nowhere") is None
