"""Shared test fixtures and configuration for the Reality AI test suite.

Test isolation strategy: each test runs inside a database transaction that
is rolled back at the end.  This avoids creating a separate test database
while ensuring tests never pollute each other's state.  The approach works
because we override FastAPI's ``get_db`` dependency with a session bound to
the same connection/transaction.

Prerequisite: the Docker Postgres container must be running and Alembic
migrations must have been applied (``alembic upgrade head``).
"""

import os
import sys
import types
import uuid

import pytest

# Tests never run the real AI: the 4B model needs the GPU and ~30 s to load,
# and its background tasks open their own DB connections, which cannot see
# rows inside the rolled-back test transaction.  PLACEHOLDER_MODE skips the
# start-up warm-up (environment variables beat the .env files), and
# ``_no_real_ai`` below makes ``import ai`` fail unless a test installs
# ``fake_ai``.
os.environ["PLACEHOLDER_MODE"] = "true"
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings, sqlalchemy_url
from app.core.database import get_db
from app.main import app


engine = create_engine(sqlalchemy_url(settings.DATABASE_URL), pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ai_package: the test may import lightweight ai/ modules (no model)"
    )


@pytest.fixture(autouse=True)
def _no_real_ai(request, monkeypatch):
    """Make the monorepo's ai/ package unimportable, as in a backend-only checkout."""
    if request.node.get_closest_marker("ai_package"):
        return
    for name in [n for n in sys.modules if n == "ai" or n.startswith("ai.")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "ai", None)


@pytest.fixture()
def db_session():
    """Yield a DB session wrapped in a transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Prevent the session from committing — nested calls to commit() become
    # SAVEPOINTs instead, so service-layer commits work normally but the
    # outer transaction is still rolled back at cleanup.
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session):
    """FastAPI TestClient with the DB dependency overridden."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_ai(monkeypatch):
    """Install stand-ins for the AI modules with the real return shapes.

    ``calls["results"]`` / ``calls["candidates"]`` set what ``search()`` and
    ``get_candidates()`` return; ``calls["search_error"]`` makes ``search()``
    raise.  Every call is recorded in ``calls``.  This is what catches
    dict-versus-ORM mistakes that PLACEHOLDER_MODE tests cannot.
    """
    calls: dict = {"embed_single": [], "fetch_and_cache": []}

    class RetrievalError(Exception):
        pass

    class BoundaryFilterError(Exception):
        pass

    def search(query, candidate_ids=None, top_k=5):
        calls["search"] = (query, candidate_ids)
        if "search_error" in calls:
            raise calls["search_error"]
        return calls.get("results", [])  # list of dicts, as the real search() returns

    def get_candidates(polygon):
        if len(polygon) < 3:
            raise ValueError("polygon must have at least 3 points")
        calls["get_candidates"] = polygon
        return calls.get("candidates", [])

    def generate_response(query, listings, history):
        assert all(isinstance(l, dict) for l in listings)
        calls["history"] = history
        return f"{len(listings)} properties"

    def embed_single(listing_id):
        calls["embed_single"].append(listing_id)

    def fetch_and_cache(listing_id, force=False):
        calls["fetch_and_cache"].append((listing_id, force))

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__path__ = []  # mark as a package so submodule imports resolve
        for key, value in attrs.items():
            setattr(mod, key, value)
        return mod

    retriever = module("ai.rag.retriever", search=search, RetrievalError=RetrievalError)
    boundary = module(
        "ai.rag.boundary_filter",
        get_candidates=get_candidates,
        BoundaryFilterError=BoundaryFilterError,
    )
    rag = module("ai.rag", retriever=retriever, boundary_filter=boundary)
    inference = module("ai.inference", generate_response=generate_response)
    embed_listings = module("ai.embeddings.embed_listings", embed_single=embed_single)
    embeddings = module("ai.embeddings", embed_listings=embed_listings)
    amenities_service = module(
        "ai.amenities.amenities_service", fetch_and_cache=fetch_and_cache
    )
    amenities = module("ai.amenities", amenities_service=amenities_service)
    ai = module("ai", rag=rag, inference=inference, embeddings=embeddings, amenities=amenities)

    for mod in (ai, rag, retriever, boundary, inference, embeddings,
                embed_listings, amenities, amenities_service):
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
    monkeypatch.setattr(settings, "PLACEHOLDER_MODE", False)
    calls["RetrievalError"] = RetrievalError
    calls["BoundaryFilterError"] = BoundaryFilterError
    return calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADAJAN = {"lat": 21.1702, "lng": 72.8311}


def unique_email(prefix: str) -> str:
    """An email no other test (or leftover row) uses."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def register_broker(client: TestClient, email: str = "broker@test.com", **extra) -> dict:
    """Register a broker and return the response JSON (includes access_token)."""
    resp = client.post("/auth/register", json={
        "email": email,
        "password": "testpass123",
        "name": "Test Broker",
        "role": "broker",
        **extra,
    })
    return resp.json()


def register_customer(client: TestClient, email: str = "cust@test.com") -> dict:
    """Register a customer and return the response JSON (includes access_token)."""
    resp = client.post("/auth/register", json={
        "email": email,
        "password": "testpass123",
        "name": "Test Customer",
        "role": "customer",
    })
    return resp.json()


def auth_header(token: str) -> dict[str, str]:
    """Build an Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


def listing_payload(**overrides) -> dict:
    """Build a minimal valid ListingCreate payload (a 2 BHK flat in Adajan)."""
    base = {
        "title": "Test Flat in Adajan",
        "description": "A cozy 2BHK flat",
        "price": 4500000,
        "property_type": "flat",
        "lat": ADAJAN["lat"],
        "lng": ADAJAN["lng"],
        "carpet_area": 900,
        "built_up_area": 1100,
        "rooms": {"bedrooms": 2, "bathrooms": 1},
    }
    base.update(overrides)
    return base


def create_listing(client: TestClient, token: str, **overrides) -> dict:
    """POST /listings as the given broker and return the listing JSON."""
    resp = client.post("/listings", json=listing_payload(**overrides), headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def broken_ai(monkeypatch):
    """Simulate an ai/ package that is installed but raises while importing.

    The real modules raise RuntimeError at import when DATABASE_URL is unset —
    not ImportError — so the backend must treat that as "AI unavailable".
    """
    import importlib.abc

    class _BrokenFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "ai" or fullname.startswith("ai."):
                raise RuntimeError("DATABASE_URL is not set.")
            return None

    for name in [m for m in sys.modules if m == "ai" or m.startswith("ai.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_BrokenFinder(), *sys.meta_path])
    monkeypatch.setattr(settings, "PLACEHOLDER_MODE", False)
