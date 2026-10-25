"""Tests for ai.rag.retriever's filter building and relaxation ladder — no database.

The SQLAlchemy engine and the embedding model are replaced with fakes that
record every SQL statement and return canned rows, so these run anywhere.
(Importing the module still loads MiniLM once, which is cached locally.)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.nlu import query_parser
from ai.rag import retriever

L = 1_00_000


def _row(i: int, **kw) -> SimpleNamespace:
    base = dict(id=i, title=f"Listing {i}", description="d", price=50 * L, property_type="flat",
                bhk=2, lat=21.15, lng=72.77, amenities=None, distance_score=0.5 + i / 100)
    base.update(kw)
    return SimpleNamespace(**base)


class FakeEngine:
    """Returns responses[n] for the n-th query; records (sql, params)."""

    def __init__(self, responses: list[list]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def connect(self):
        engine = self

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                engine.calls.append((str(sql), params))
                rows = engine.responses[len(engine.calls) - 1] if len(engine.calls) <= len(engine.responses) else []
                return SimpleNamespace(fetchall=lambda: rows)

        return Conn()


@pytest.fixture(autouse=True)
def _rules_backend(monkeypatch):
    monkeypatch.setenv("NLU_BACKEND", "rules")
    monkeypatch.setattr(retriever._embedding_model, "embed", lambda text: [0.1, 0.2, 0.3])
    query_parser.cache_clear()
    yield
    query_parser.cache_clear()


def _install(monkeypatch, responses) -> FakeEngine:
    engine = FakeEngine(responses)
    monkeypatch.setattr(retriever, "_engine", engine)
    return engine


def test_validation_unchanged(monkeypatch) -> None:
    _install(monkeypatch, [])
    with pytest.raises(ValueError):
        retriever.search("   ")
    with pytest.raises(ValueError):
        retriever.search("2bhk", top_k=0)
    assert retriever.search("2bhk in vesu", candidate_ids=[]) == []


def test_offtopic_returns_empty_without_db(monkeypatch) -> None:
    engine = _install(monkeypatch, [])
    assert retriever.search("what's the weather like today?") == []
    assert engine.calls == []


def test_all_filters_become_bound_parameters(monkeypatch) -> None:
    engine = _install(monkeypatch, [[_row(1)]])
    results = retriever.search("3bhk flat in vesu between 60 lakh and 1 crore", candidate_ids=[1, 2, 3])
    sql, params = engine.calls[0]
    for clause in ("price >= :price_min", "price <= :price_max", "property_type = :property_type",
                   "bhk = :bhk", "ST_DWithin(", "id = ANY(:candidate_ids)"):
        assert clause in sql
    assert params["price_min"] == 60 * L and params["price_max"] == 100 * L
    assert params["property_type"] == "flat" and params["bhk"] == 3
    assert (params["loc_lat"], params["loc_lng"], params["radius_m"]) == (21.1545, 72.7757, 2000.0)
    assert params["candidate_ids"] == [1, 2, 3]
    assert "vesu" not in sql.lower() and "60" not in sql  # nothing interpolated
    assert results[0]["match_note"] == "exact" and results[0]["bhk"] == 2


def test_no_filters_is_plain_semantic_search(monkeypatch) -> None:
    engine = _install(monkeypatch, [[_row(1), _row(2)]])
    results = retriever.search("show me some properties")
    sql, params = engine.calls[0]
    assert "WHERE embedding IS NOT NULL ORDER BY" in sql
    assert [r["id"] for r in results] == [1, 2]


def test_ladder_widens_radius_first(monkeypatch) -> None:
    engine = _install(monkeypatch, [[], [_row(7)]])
    results = retriever.search("2bhk in athwa")
    assert len(engine.calls) == 2
    assert engine.calls[0][1]["radius_m"] == 1500.0
    assert engine.calls[1][1]["radius_m"] == 3000.0 and engine.calls[1][1]["bhk"] == 2
    assert results[0]["match_note"] == "relaxed_radius"


def test_ladder_then_drops_bhk_then_locality(monkeypatch) -> None:
    engine = _install(monkeypatch, [[], [], [], [_row(9)]])
    results = retriever.search("5bhk flat in vesu under 80 lakh")
    notes = ["exact", "relaxed_radius", "relaxed_bhk", "relaxed_locality"]
    assert len(engine.calls) == 4
    assert "bhk" not in engine.calls[2][1] and engine.calls[2][1]["radius_m"] == 4000.0
    assert "radius_m" not in engine.calls[3][1]
    for _, params in engine.calls:  # price and type are never relaxed
        assert params["price_max"] == 80 * L and params["property_type"] == "flat"
    assert results[0]["match_note"] == notes[-1]


def test_impossible_budget_returns_empty(monkeypatch) -> None:
    engine = _install(monkeypatch, [])
    assert retriever.search("3bhk in vesu under 1 lakh") == []
    assert len(engine.calls) == 4  # every rung tried, price never dropped


def test_ladder_skips_steps_for_unset_filters(monkeypatch) -> None:
    engine = _install(monkeypatch, [])
    retriever.search("flat under 50 lakh")  # no locality, no bhk -> one attempt only
    assert len(engine.calls) == 1


def test_db_error_becomes_retrieval_error(monkeypatch) -> None:
    from sqlalchemy.exc import OperationalError

    class Broken:
        def connect(self):
            raise OperationalError("SELECT", {}, Exception("connection refused"))

    monkeypatch.setattr(retriever, "_engine", Broken())
    with pytest.raises(retriever.RetrievalError):
        retriever.search("2bhk in vesu")


def test_non_integer_candidate_ids_rejected(monkeypatch) -> None:
    engine = _install(monkeypatch, [])
    with pytest.raises(ValueError):
        retriever.search("2bhk in vesu", candidate_ids=["1; DROP TABLE listings"])
    with pytest.raises(ValueError):
        retriever.search("2bhk in vesu", candidate_ids=[True])
    assert engine.calls == []


def test_embedding_failure_becomes_retrieval_error(monkeypatch) -> None:
    _install(monkeypatch, [])

    def broken(text):
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(retriever._embedding_model, "embed", broken)
    with pytest.raises(retriever.RetrievalError):
        retriever.search("2bhk in vesu")


def test_query_is_capped_before_embedding(monkeypatch) -> None:
    _install(monkeypatch, [[_row(1)]])
    seen: list[str] = []
    monkeypatch.setattr(retriever._embedding_model, "embed", lambda text: seen.append(text) or [0.1])
    retriever.search("2bhk in vesu " + "x" * 10_000)
    assert len(seen[0]) <= retriever.MAX_QUERY_CHARS
