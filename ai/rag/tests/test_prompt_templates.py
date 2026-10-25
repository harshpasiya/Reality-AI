"""Tests for the amenity-question heuristic in ai.rag.prompt_templates."""

from __future__ import annotations

import pytest

from ai.rag.prompt_templates import is_amenity_related


@pytest.mark.parametrize("query", [
    "2bhk flat with parking in vesu",        # "park" inside "parking"
    "flat in adajan under 60 lakh",
    "3bhk with gym and lift",
    "",
])
def test_not_amenity_questions(query) -> None:
    assert not is_amenity_related(query)


@pytest.mark.parametrize("query", [
    "flat near a park in vesu",
    "is there a school nearby?",
    "2bhk close to the metro station",
    "Which HOSPITALS are near this flat",
])
def test_amenity_questions(query) -> None:
    assert is_amenity_related(query)
