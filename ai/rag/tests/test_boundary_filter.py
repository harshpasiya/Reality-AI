"""Tests for ai.rag.boundary_filter input validation and SQL — no database."""

from __future__ import annotations

import pytest

from ai.rag import boundary_filter

SQUARE = [[21.10, 72.70], [21.10, 72.80], [21.20, 72.80], [21.20, 72.70]]


class FakeEngine:
    def __init__(self, ids):
        self.ids, self.calls = ids, []

    def connect(self):
        engine = self

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                engine.calls.append((str(sql), params))
                return iter([(i,) for i in engine.ids])

        return Conn()


def test_valid_polygon_is_closed_and_made_valid(monkeypatch) -> None:
    engine = FakeEngine([3, 7])
    monkeypatch.setattr(boundary_filter, "_engine", engine)
    assert boundary_filter.get_candidates(SQUARE) == [3, 7]
    sql, params = engine.calls[0]
    assert "ST_MakeValid(" in sql
    # lng lat order, ring closed with the first point
    assert params["polygon_wkt"] == ("POLYGON((72.7 21.1, 72.8 21.1, 72.8 21.2, "
                                     "72.7 21.2, 72.7 21.1))")


@pytest.mark.parametrize("polygon", [
    [],
    [[21.1, 72.7], [21.2, 72.8]],
    [[21.1, 72.7], [21.2, "x"], [21.3, 72.9]],
    [[21.1, 72.7], [21.2, float("nan")], [21.3, 72.9]],
    [[21.1, 72.7], [21.2, float("inf")], [21.3, 72.9]],
    [[72.7, 21.1], [95.0, 21.2], [21.3, 72.9]],   # lat out of range (swapped pair)
    [[21.1, 72.7]] * (boundary_filter.MAX_POLYGON_POINTS + 1),
])
def test_bad_polygons_raise_value_error_without_db(monkeypatch, polygon) -> None:
    engine = FakeEngine([])
    monkeypatch.setattr(boundary_filter, "_engine", engine)
    with pytest.raises(ValueError):
        boundary_filter.get_candidates(polygon)
    assert engine.calls == []
