"""run() must terminate even when a listing can never be embedded — no database."""

from __future__ import annotations

from types import SimpleNamespace

from ai.embeddings import embed_listings


class PagingEngine:
    """Serves 'SELECT id ... WHERE embedding IS NULL AND id > :last_id LIMIT :batch_size'."""

    def __init__(self, ids):
        self.ids, self.queries = ids, 0

    def connect(self):
        engine = self

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                engine.queries += 1
                assert engine.queries < 50, "run() is looping"
                rows = [SimpleNamespace(id=i) for i in engine.ids if i > params.get("last_id", 0)]
                rows = rows[:params["batch_size"]]
                return SimpleNamespace(fetchall=lambda: rows)

        return Conn()


def test_run_skips_permanent_failures_and_terminates(monkeypatch) -> None:
    monkeypatch.setattr(embed_listings, "_engine", PagingEngine([1, 2, 3, 4, 5]))
    attempts: list[int] = []

    def embed(listing_id):
        attempts.append(listing_id)
        if listing_id in (2, 4):
            raise ValueError("embed() requires a non-empty string")

    monkeypatch.setattr(embed_listings, "embed_single", embed)
    assert embed_listings.run(batch_size=2) == 3
    assert attempts == [1, 2, 3, 4, 5]  # each listing tried exactly once
