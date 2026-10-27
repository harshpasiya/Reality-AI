# 📋 Reality AI — Team Onboarding & Delivery Checklist

This checklist is designed for developers, QA engineers, and contributors working on the **Reality AI Backend Service** (`backend/` track). Items marked with `[✅]` have been fully built, verified, and tested in this codebase. Items marked with `[ ]` are optional, pending external dependencies (such as Person 1's `ai/` package), or local environment-specific setups.

---

## 🛠️ Phase 1: Local Environment & Dependency Setup

### 1.1 Prerequisites Verification
- [✅] **Python**: Installed Python `3.11+` (`python --version` or `python3 --version`).
- [✅] **PostgreSQL**: Installed PostgreSQL `16` with **PostGIS 3.4+** extension available.
- [ ] **pgvector**: `pgvector` extension installed in PostgreSQL *(Optional for dev — fallback to JSONB if omitted)*.
- [✅] **Docker & Compose**: Docker Desktop / Engine configuration available (`Dockerfile`, `docker-compose.yml`).
- [✅] **Git**: Git installed and repository cloned.

### 1.2 Virtual Environment & Package Installation
- [✅] Created Python virtual environment:
  ```bash
  python -m venv .venv
  ```
- [✅] Activated virtual environment:
  - Windows (PowerShell): `.\.venv\Scripts\Activate.ps1`
  - Linux/macOS: `source .venv/bin/activate`
- [✅] Upgraded `pip` and installed production dependencies:
  ```bash
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  ```

### 1.3 Environment Variables Configuration
- [✅] Copied `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```
- [✅] Configured environment variables in `.env`:
  - `DATABASE_URL`: `postgresql://postgres:postgres@localhost:5432/reality_ai` (or container equivalent).
  - `SECRET_KEY`: Custom secret key for JWT signing.
  - `PLACEHOLDER_MODE`: Set to `true` for local isolated testing without live AI LLM APIs.
- [ ] `GOOGLE_PLACES_API_KEY`: Configured if testing live Google Places amenities lookup *(Optional)*.
- [✅] Verified `.env` is listed in `.gitignore` and **NEVER** committed to Git.

---

## 🗄️ Phase 2: Database Initialization & Migrations

### 2.1 Database Setup & Extensions
- [✅] Created PostgreSQL database named `reality_ai`.
- [✅] Enabled required spatial extension:
  ```sql
  CREATE EXTENSION IF NOT EXISTS postgis;
  ```
- [ ] Enabled vector extension *(Optional for dev)*:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- [✅] Executed automated setup script (`python setup_local.py`).

### 2.2 Schema Migrations (Alembic)
- [✅] Applied latest Alembic database migrations:
  ```bash
  python -m alembic upgrade head
  ```
- [✅] Verified database tables created: `broker`, `customer`, `listing`, `conversation`, `lead`, `alembic_version`.
- [✅] Verified PostGIS Spatial Indexes created on `listing.location`:
  - `idx_listing_location` (Geometry GiST for `ST_Contains` polygon search).
  - `idx_listing_location_geog` (Geography GiST for `ST_DWithin` radius search).

### 2.3 Test Data Seeding
- [✅] Seeded synthetic Surat listings, leads, and chat sessions:
  ```bash
  python -m app.db.seed_synthetic_data -n 500
  ```
- [✅] Seeded demo test accounts (`broker` & `customer`):
  ```bash
  python seed_demo_user.py
  ```

---

## 📡 Phase 3: API & AGENTS.md Contract Verification

All endpoints strictly comply with the frozen cross-team contract (`Reality-AI-AGENTS.md`):

### 3.1 Authentication & Authorization Endpoints
- [✅] `POST /auth/register`:
  - Enforces cross-role email uniqueness (email cannot exist as both broker and customer).
  - Hashes passwords using bcrypt via `passlib`.
- [✅] `POST /auth/login`:
  - Authenticates user credentials and returns JWT bearer token.
- [✅] `GET /auth/me`:
  - Returns authenticated user details (id, name, email, role).

### 3.2 Listing & Search Endpoints
- [✅] `POST /listings`:
  - Requires `broker` role authentication.
  - Creates PostGIS `POINT(lng lat)` geometry in SRID 4326.
  - Queues automatic background amenities caching and re-embedding (`embed_single`).
- [✅] `GET /listings/{id}`:
  - Returns listing details with embedded amenities JSON.
  - Returns lat (`location.y`) and lng (`location.x`) coordinates.
- [✅] `GET /listings/search` (Radius Search):
  - Accepts `lat`, `lng`, `radius_km`.
  - Supports filters: `price_min`, `price_max`, `property_type` (`flat` | `house_land`).
  - Utilizes `ST_DWithin` with geography spatial index.
- [✅] `POST /listings/search-boundary` (Polygon Boundary Search):
  - Accepts hand-drawn polygon array: `[[lat, lng], ...]`.
  - Validates polygon vertices (3-1000, finite, valid lat/lng ranges) — same rule as the AI's `get_candidates()`.
  - Repairs self-crossing polygons with `ST_MakeValid` instead of rejecting them.
  - Note: coordinates are *not* restricted to Surat's bounding region.
  - Utilizes `ST_Contains` with geometry spatial index.

### 3.3 Chat & AI Integration Endpoints
- [✅] `POST /chat`:
  - Requires `customer` role authentication.
  - Process customer message via RAG pipeline or `PLACEHOLDER_MODE` fallback.
  - Handles `search()` results as dicts, returns 422 / 503 on AI errors, and records views — never leads — for listings shown.
  - Saves message history into `conversation.messages` JSONB.
- [✅] `GET /chat/{conversation_id}`:
  - Requires `customer` role authentication.
  - Returns complete conversation history with recommended listing IDs and full listing metadata.

### 3.4 Broker Analytics Endpoint
- [✅] `GET /brokers/{id}/analytics`:
  - Requires `broker` role authentication matching `{id}`.
  - Returns total listings, total views and total leads, with per-listing view count, lead count and status.

---

## 🤖 Phase 4: AI Track & Cross-Team Integration

- [ ] **AI Physical Package Integration**: Direct import of Person 1's `ai/` package modules *(External package maintained by Person 1)*.
- [✅] **Fallback Handling**: Verified `PLACEHOLDER_MODE=true` works seamlessly when AI modules are uninstalled/mocked.
- [✅] **Geographic Constraint**: Verified synthetic coordinates and location inputs adhere to **Surat, Gujarat** bounds (`lat: 21.0 - 21.3`, `lng: 72.7 - 73.0`).

---

## 🧪 Phase 5: Testing & Quality Assurance

- [✅] Executed full Pytest suite (24/24 passing):
  ```bash
  python -m pytest
  ```
- [✅] Passed individual test modules without errors:
  - [✅] `python -m pytest tests/test_auth.py`
  - [✅] `python -m pytest tests/test_listings.py`
  - [✅] `python -m pytest tests/test_boundary.py`
  - [✅] `python -m pytest tests/test_chat.py`
  - [✅] `python -m pytest tests/test_analytics.py`
- [✅] Verified spatial query performance with EXPLAIN ANALYZE (`python -m app.db._explain_check`).
- [✅] Swagger API Docs tested interactively at `http://localhost:8000/docs`.

---

## 🐳 Phase 6: Docker Containerization Check

- [✅] Built Docker Compose configuration (`Dockerfile`, `docker-compose.yml`, `entrypoint.sh`).
- [ ] Docker live container daemon test execution (`docker-compose up --build`).

---

## 🚀 Phase 7: Pre-PR & Commit Checklist

Before opening a Pull Request or pushing changes:
- [✅] **No Hardcoded Secrets**: Scanned code for plain-text credentials, API keys, or private tokens.
- [✅] **Clean Git Status**: Checked `git status` for unintended scratch files or untracked test logs.
- [✅] **Formatting & Linting**: Checked code formatting against PEP 8 standard.
- [✅] **Schema Migrations**: Created and committed Alembic migration scripts.
- [✅] **Subtree Merge Structure**: Ensured repository root matches the `backend/` folder target for final unified repository merge.

---

*Reality AI Backend Team Checklist — Last Updated: October 2026*
