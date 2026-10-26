# Reality AI Backend — Architecture Write-up

**Version:** 1.0 · **Author:** Person 2 (Backend Track)  
**Audience:** Final-year academic report reviewers and the cross-team merge team.

---

## 1. Schema Design

### Entity Overview

| Table | Purpose |
|---|---|
| `broker` | Platform agents who list properties |
| `customer` | End-users who query listings via chat |
| `listing` | Core property record with spatial and AI columns |
| `conversation` | Rolling chat history per customer (JSON array) |
| `lead` | Lightweight inquiry record linking customer → listing |

### Geometry Column

`listing.location` uses GeoAlchemy2's `Geometry("POINT", srid=4326)`.  SRID 4326 (WGS-84) was chosen because it is the universal standard for GPS coordinates and is required by the PostGIS geography cast (`::`geography`) used in radius queries.

A GiST index (`idx_listing_location`, alongside functional geography index `idx_listing_location_geog`) is applied via `postgresql_using='gist'` — the spatial index type PostGIS supports for geometry columns.  Without it, both `ST_DWithin` and `ST_Contains` fall back to a full sequential scan.

### Vector Column

`listing.embedding` is a `Vector(384)` (pgvector) column, nullable, populated entirely by Person 1's `ai.embeddings.embed_listings` pipeline.  The dimension (384) matches the *all-MiniLM-L6-v2* embedding model; this is noted as a cross-team dependency in the model comment and must be confirmed before the initial Alembic migration is finalized.

### `property_type` Branching

A `CheckConstraint` enforces `property_type IN ('flat', 'house_land')` at the DB level, mirroring the `Literal["flat", "house_land"]` type on `ListingCreate`.  This provides two layers of rejection: Pydantic 422 before the DB is touched, and a DB constraint as a final safeguard.  Adding a new type requires both a DB migration and a schema update — this is intentional, not an oversight.

### `amenities` Column

`listing.amenities` is a nullable `JSON` column, populated by Person 1's `ai.amenities.amenities_service.fetch_and_cache()` as a background task after listing creation (see §5).  It is always included in `ListingResponse` per AGENTS.md §3, but may be `null` until the pipeline runs.

---

## 2. Endpoint List

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | None | Health check → `{"status": "ok"}` |
| `POST` | `/auth/register` | None | Register broker or customer; returns JWT |
| `POST` | `/auth/login` | None | Login; returns JWT |
| `POST` | `/listings` | Broker JWT | Create listing + trigger AI background tasks |
| `GET` | `/listings/{id}` | None | Fetch single listing by PK |
| `GET` | `/listings/search` | None | Radius search (`lat`, `lng`, `radius_km`) |
| `POST` | `/listings/search-boundary` | None | Polygon boundary search |
| `POST` | `/chat` | Customer JWT | RAG-orchestrated chat; persists conversation |
| `GET` | `/brokers/{id}/analytics` | Broker JWT (self) | Per-broker listing + lead analytics |

All paths match AGENTS.md §2 exactly.  `ListingResponse` always includes `amenities` per AGENTS.md §3.

---

## 3. Authentication

JWT-based auth is implemented with **python-jose** (HS256) and **passlib/bcrypt**.

- `security.hash_password` / `verify_password` — bcrypt hashing via `CryptContext`.
- `create_access_token` — produces a JWT embedding `sub` (email) and `exp`; expiry defaults to `JWT_EXPIRE_MINUTES` (60 min).
- `decode_access_token` — decodes and verifies; raises `InvalidTokenError` on any failure, abstracting away jose's raw exception hierarchy.
- `get_current_user` (FastAPI dependency) — decodes the token and returns the ORM user object; returns `HTTP 401` with a `WWW-Authenticate: Bearer` header on failure.

**User-enumeration protection:** `authenticate_user` returns `None` for both "no such user" and "wrong password" cases.  The route sends the same `"incorrect email or password"` response for both, with no distinguishing detail.

---

## 4. Boundary-Search Design & Polygon Validation

`POST /listings/search-boundary` accepts a free-drawn polygon from the frontend map UI.

**Validation pipeline (three layers):**

1. **Pydantic** (`BoundarySearchRequest`): validates ≥3 points, each point a `[lat, lng]` pair within bounds, and auto-closes the ring if the first and last points differ — accommodating a common frontend omission without erroring.
2. **`ST_MakeValid`** (`geo_service.boundary_candidate_ids`, or the AI's `get_candidates()` when installed): self-crossing shapes are repaired rather than rejected, so the map's boundary search and `/chat` with a polygon follow the same rule.
3. **PostGIS** (`ST_Contains`): the validated WKT string is passed as a parameterized query — never string-interpolated — preventing SQL injection.

**Coordinate ordering:** WKT standard uses `(longitude, latitude)` while the API accepts `[lat, lng]`.  The service layer swaps coordinates when rendering the WKT string; this is documented with a comment to prevent regression.

---

## 5. Amenities-Caching Trigger Design

The `POST /listings` route queues two of Person 1's functions as **FastAPI `BackgroundTasks`** immediately after the DB commit:

```
ai.embeddings.embed_listings.embed_single(listing.id)
ai.amenities.amenities_service.fetch_and_cache(listing.id)
```

**Why background tasks rather than synchronous calls:**
- The external geocoding + amenity-enrichment call can take several seconds; blocking the HTTP response on it would make listing creation feel slow.
- The listing is immediately usable (search will return it) even before amenities are populated.
- `fetch_and_cache` itself triggers a second re-embed internally once amenities are ready, keeping the listing's vector search-text current without this route needing to know that detail.

Both imports are wrapped in `try/except ImportError` so the endpoint remains fully functional during isolated development before Person 1's `ai/` package exists alongside this repo.

---

## 6. AI-Layer Bridge Design

The backend calls Person 1's AI layer via **direct Python imports** (`from ai.rag.retriever import search`), not HTTP.

**Rationale:** At final merge the repos are combined under a single Python environment.  A direct import avoids the latency, serialization overhead, auth complexity, and operational burden of an internal HTTP hop.  It also makes the call stack trivially debuggable — one Python traceback, no distributed trace needed.

**Isolation during development:** every AI import is wrapped in `try/except ImportError`.  If `ai/` is absent, the endpoint falls back gracefully (DB query or placeholder response) and logs a `WARNING`.  `PLACEHOLDER_MODE=true` (env-var) makes the `/chat` endpoint return canned responses that reference retrieved listing titles — enough to fully test the conversation persistence, history logic, and error paths before the fine-tuned model is available.

---

## 7. Performance Results (Phase 5)

> **Note:** Performance metrics were gathered running `python -m app.db._load_test` against a seeded dataset of 100 listings in Surat, Gujarat using 5 concurrent workers.

| Metric | GET /listings/search (Radius) | POST /listings/search-boundary (Polygon) |
|---|---|---|
| min | 18.2 ms | 14.7 ms |
| median | 23.0 ms | 26.7 ms |
| p95 | 2056.4 ms | 36.8 ms |
| max | 2061.4 ms | 40.4 ms |

Run `python -m app.db._explain_check` to verify spatial query execution plans. Boundary polygon search uses `Index Scan using idx_listing_location` (GiST spatial index execution time ~0.92 ms).

---

## 8. Known Limitations

| # | Limitation | Notes |
|---|---|---|
| 1 | CORS wildcard in production | `allow_origins=["*"]` is acceptable for local dev; must be restricted before any real deployment. |
| 2 | Single-city dataset | All seed data and coordinate examples are Surat, Gujarat only. Expanding cities requires additional seed data and no code changes. |
| 3 | No RBAC | Authorization is ownership-based only (broker can only see their own analytics). Full RBAC would require a roles table. |
| 4 | `embedding` dimension is a cross-team dependency | If Person 1 changes their model, a DB migration is required. The dimension is documented as a `TODO` comment on the model. |
| 5 | Amenities may be `null` indefinitely | If Person 1's pipeline is unavailable, the field stays `null`. The API exposes it correctly but there is no retry/fallback mechanism in this repo. |
