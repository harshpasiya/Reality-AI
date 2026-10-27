# Reality AI — Backend Service

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?style=flat&logo=postgresql)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791.svg?style=flat&logo=postgresql)](https://postgis.net/)
[![pgvector](https://img.shields.io/badge/pgvector-0.2%2B-blue.svg)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker)](https://www.docker.com/)

**Reality AI Backend** is a high-performance RESTful API service built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL (PostGIS + pgvector)**. It serves as the core data, spatial search, authentication, and RAG orchestration layer for **Reality AI** — an AI-powered real estate exploration and publishing platform tailored for **Surat, Gujarat**.

---

## 🚀 Key Features

- 📍 **Spatial Boundary & Radius Search**: Native PostGIS queries (`ST_DWithin`, `ST_Contains`) supporting radius filtering with price/type constraints (`price_min`, `price_max`, `property_type`) and hand-drawn polygon boundary search with max-vertex validation (≤ 100 points).
- ⚡ **Dual GiST Spatial Indexes**: Optimized PostGIS performance with `idx_listing_location` (Geometry GiST) and `idx_listing_location_geog` (Geography GiST) for instant spatial queries.
- 🔍 **Vector Similarity Search**: `pgvector` vector indexes supporting 384-dimensional embeddings for semantic search over listing descriptions and amenities.
- 🔐 **Authentication & Security**: Role-based access control (`broker` vs `customer`), unique email enforcement across roles, OAuth2 + JWT authentication, password hashing (`passlib`/`bcrypt`), and token validation (`python-jose`).
- 💬 **Conversational Chat & Lead Tracking**: Customer-only AI chat (`POST /chat`) returning AI-ranked listings (shown listings count as views), complete history recall (`GET /chat/{conversation_id}`), and explicit "Contact broker" leads (`POST /listings/{id}/leads`) returning top-level and per-message listings.
- 🤖 **AI RAG Orchestration**: Direct Python interface integration for Person 1's AI package (`ai.rag`, `ai.embeddings`, `ai.amenities`, `ai.inference`) with seamless fallback to `PLACEHOLDER_MODE`.
- 🏬 **Amenities Caching Pipeline**: Automatic background caching of Google Places amenities (schools, hospitals, restaurants, transit, parks) and automatic listing re-embedding.
- 📊 **Broker Analytics**: Per-listing view counts, lead counts and status; broker dashboard listings and a leads inbox with follow-up status.
- 🐳 **Containerized & Automated Workflows**: Multi-stage Docker setup with healthcheck dependency waiting, automatic Alembic migrations, and synthetic data seeding script generating 500+ Surat listings, leads, and sample chat sessions.

---

## 🛠️ Technology Stack

| Component | Technology | Description |
|---|---|---|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance Python web framework for REST APIs |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) | Lightning-fast ASGI server implementation |
| **Database** | [PostgreSQL 16](https://www.postgresql.org/) | Relational database engine |
| **Geo Extension** | [PostGIS 3.4](https://postgis.net/) | Spatial database extension for location-based queries |
| **Vector Extension** | [pgvector](https://github.com/pgvector/pgvector) | Vector similarity search extension |
| **ORM & Spatial** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [GeoAlchemy2](https://geoalchemy2.readthedocs.io/) | Object-Relational Mapper & spatial query builder |
| **Database Migrations**| [Alembic](https://alembic.sqlalchemy.org/) | Schema migration tool |
| **Authentication** | [python-jose](https://github.com/mpdaved/python-jose) + [passlib](https://passlib.readthedocs.io/) | JWT signing, verification, and bcrypt hashing |
| **Geometry** | [Shapely](https://shapely.readthedocs.io/) | Polygon manipulation and validation |
| **Testing** | [Pytest](https://docs.pytest.org/) + [HTTPX](https://www.python-httpx.org/) | Async test suite and HTTP client mock engine |

---

## 📂 Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── deps.py               # Dependency injection (DB session, JWT auth)
│   │   └── routes/
│   │       ├── analytics.py      # GET /brokers/{id}/analytics
│   │       ├── auth.py           # POST /auth/register, /auth/login, GET /auth/me
│   │       ├── boundary_search.py# POST /listings/search-boundary
│   │       ├── chat.py           # POST /chat, GET /chat/{conversation_id}
│   │       └── listings.py       # POST /listings, GET /listings/{id}, GET /listings/search
│   ├── core/
│   │   ├── config.py             # Pydantic Settings & environment variables
│   │   ├── database.py           # SQLAlchemy Engine & Session factory (psycopg v3/v2 auto-adapter)
│   │   └── security.py           # Password hashing & JWT token creation/decoding
│   ├── db/
│   │   ├── init.sql              # Docker initialization script (PostGIS & pgvector setup)
│   │   ├── seed_synthetic_data.py# Generator for 500+ synthetic Surat listings, leads & chats
│   │   ├── _explain_check.py     # EXPLAIN ANALYZE verification script for spatial indexes
│   │   └── migrations/           # Alembic database migrations
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── broker.py             # Broker model
│   │   ├── customer.py           # Customer model
│   │   ├── listing.py            # Listing model (PostGIS Point, vector embedding, JSON amenities)
│   │   ├── conversation.py       # Customer conversation & message history
│   │   └── lead.py               # Customer lead inquiry model
│   ├── schemas/                  # Pydantic data validation schemas
│   └── services/                 # Business logic layer
│       ├── analytics_service.py  # Broker analytics queries
│       ├── auth_service.py       # User registration (cross-role email uniqueness) & auth logic
│       ├── geo_service.py        # Spatial radius (filtered) & boundary search logic
│       └── listing_service.py    # Listing CRUD operations
├── tests/                        # Comprehensive Pytest test suite
│   ├── test_analytics.py
│   ├── test_auth.py
│   ├── test_boundary.py
│   ├── test_chat.py
│   └── test_listings.py
├── .env.example                  # Template for environment variables
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Multi-container orchestration (API + PostGIS DB + pgAdmin)
├── Dockerfile                    # Multi-stage Python 3.11 container build
├── entrypoint.sh                 # Docker startup script (resilient DB wait loop, migrate, launch)
├── requirements.txt              # Production Python dependencies
├── seed_demo_user.py             # Quick seed script for test accounts
├── setup_local.py                # Setup script for non-Docker local environments
└── Reality-AI-AGENTS.md          # Shared cross-team contract spec
```

---

## ⚙️ Environment Variables

Create a `.env` file in the project root (or copy `.env.example`):

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://postgres:postgres@localhost:5432/reality_ai` | PostgreSQL connection URI |
| `SECRET_KEY` | Yes | *(none — startup fails without it)* | Secret key for JWT signing, at least 32 characters |
| `POSTGRES_USER` | No | `postgres` | PostgreSQL container username |
| `POSTGRES_PASSWORD` | No | `postgres` | PostgreSQL container password |
| `POSTGRES_DB` | No | `reality_ai` | PostgreSQL container database name |
| `PLACEHOLDER_MODE` | No | `true` | When `true`, chat endpoint uses internal fallback AI responses |
| `GOOGLE_PLACES_API_KEY` | Optional | `""` | Google Places API key for amenities caching pipeline |

> **Note**: For Docker Compose setups, set `DATABASE_URL=postgresql://postgres:postgres@db:5432/reality_ai` (using container service name `db`).

---

## ⚡ Quickstart & Setup Guide

### Method 1: Docker Compose (Recommended)

The simplest way to run the entire backend stack (API server + PostGIS/pgvector DB + pgAdmin):

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Dev8735/Reality_AI_Backend.git
   cd Reality_AI_Backend
   ```

2. **Start the containers**:
   ```bash
   docker-compose up --build
   ```

3. **Access the services**:
   - **FastAPI API Server**: `http://localhost:8000`
   - **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
   - **pgAdmin 4 Web Interface**: `http://localhost:5050` (credentials from `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` in `.env`; bound to localhost)

---

### Method 2: Local Python Setup (Without Docker)

If you prefer to run the FastAPI app directly on your local system using Python virtual environment:

#### Prerequisites
- **Python 3.11+** installed
- **PostgreSQL 16** with **PostGIS** extension installed locally

#### Step-by-Step Instructions

1. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure database & run initial setup**:
   Make sure PostgreSQL is running on `localhost:5432` with database `reality_ai` created, then run the automated setup script:
   ```bash
   python setup_local.py
   ```
   *This script enables `postgis` & `vector` extensions, creates tables, stamps Alembic, and sets up spatial indexes.*

4. **Seed synthetic test data (500 listings, leads & conversations)**:
   ```bash
   python -m app.db.seed_synthetic_data -n 500
   python seed_demo_user.py
   ```

5. **Start the Uvicorn development server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 🗄️ Database Schema & Spatial Indexing

### Schema Overview

| Table | Description | Key Columns |
|---|---|---|
| `broker` | Real estate brokers | `id`, `name`, `email`, `phone_hash`, `password_hash`, `created_at` |
| `customer` | Platform customers | `id`, `name`, `email`, `password_hash`, `created_at` |
| `listing` | Property listings | `id`, `broker_id`, `title`, `description`, `price`, `property_type`, `location` (PostGIS `POINT`), `carpet_area`, `built_up_area`, `plot_area`, `floor_number`, `rooms`, `embedding` (vector), `amenities`, `created_at` |
| `conversation` | Customer chat sessions | `id`, `customer_id`, `messages` (JSONB ISO history with listing IDs) |
| `lead` | Explicit "Contact broker" enquiries | `id`, `listing_id`, `customer_id`, `message`, `status`, `conversation_id`, `created_at`, `updated_at` (one per customer and listing) |

### Spatial Indexing

To ensure lightning-fast PostGIS performance, two GiST spatial indexes are created on `listing.location`:
- `idx_listing_location`: Geometry GiST index for `ST_Contains` polygon queries.
- `idx_listing_location_geog`: Functional Geography GiST index `(CAST(location AS geography))` for `ST_DWithin` radius queries.

### Database Migrations (Alembic)

To apply latest database migrations:
```bash
alembic upgrade head
```

To generate a new migration after updating ORM models:
```bash
alembic revision --autogenerate -m "describe_your_change"
```

---

## 📡 API Endpoints Reference

Per the cross-team contract (`Reality-AI-AGENTS.md`), all endpoints adhere strictly to the following specification:

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/` | Public | Health check status (`{"status": "ok"}`) |
| `POST` | `/auth/register` | Public | Signup for broker or customer (enforces cross-role email uniqueness) |
| `POST` | `/auth/login` | Public | Authenticate user & return JWT token |
| `GET` | `/auth/me` | Bearer Auth | Fetch current authenticated user's profile |
| `POST` | `/listings` | Broker Only | Publish a new listing & queue background AI tasks |
| `GET` | `/listings/{id}` | Public | Get single listing details with cached amenities |
| `GET` | `/listings/search` | Public | Radius search (`lat`, `lng`, `radius_km`) with optional `price_min`, `price_max`, `property_type` |
| `POST` | `/listings/search-boundary` | Public | Polygon boundary search (`[[lat, lng], ...]`, 3-1000 vertices; self-crossing shapes repaired) |
| `POST` | `/chat` | Customer Auth | Process customer chat message via RAG & LLM (422 on bad input, 503 if AI search is down) |
| `GET` | `/chat/{conversation_id}` | Customer Auth | Fetch complete chat history (returns top-level & per-message `listings`) |
| `GET` | `/brokers/{id}/analytics` | Broker Auth | Total listings, views and leads, with a per-listing breakdown |

### Interactive OpenAPI Documentation

Once the server is running, explore and test endpoints interactively at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Testing

The repository features a complete test suite powered by `pytest` and `httpx`.

Run all tests:
```bash
pytest
```

Run tests with detailed output:
```bash
pytest -v -s
```

Run specific test module:
```bash
pytest tests/test_boundary.py
```

---

## 🤝 Cross-Team Integration Contract

This repository is built following the strict contract in [`Reality-AI-AGENTS.md`](./Reality-AI-AGENTS.md). 

At final integration, this repository drops into the `backend/` folder of the unified repository (`git subtree` merge).
- **Target City**: Surat, Gujarat (all synthetic coordinates are in Surat).
- **AI Track Interface**: Backend imports `ai.rag`, `ai.embeddings`, `ai.amenities`, and `ai.inference`.
- **Frontend Track Interface**: Frontend consumes standard FastAPI JSON endpoints.

---

## 📄 License

This project is part of the **Reality AI Platform**. All rights reserved.