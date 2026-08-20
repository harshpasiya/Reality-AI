-- Reality AI — Local dev database initialisation
-- Runs automatically on first container start via docker-entrypoint-initdb.d.
-- Installs required extensions and creates a minimal listings table for
-- AI-track testing independently of Person 2's real backend.

-- ──────────────────────────────────────────────────────────────────────
-- Extensions
-- ──────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────────────────────────────
-- listings table
--
-- NOTE: This mirrors a SUBSET of Person 2's real schema (backend/app/models/listing.py)
-- for local AI-track testing only. The authoritative schema and all
-- migrations live in the backend repo. Do not treat this as the source
-- of truth — if the real schema changes, update this file to match.
--
-- Omitted columns (added by Person 2's backend): broker_id, carpet_area,
-- built_up_area, plot_area, floor_number, rooms (JSON), location (PostGIS
-- geometry). We store lat/lng as raw doubles here for simplicity.
-- embedding dimension: 384 (all-MiniLM-L6-v2, see ai/embeddings/embedding_model.py)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listings (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    price        NUMERIC(12, 2),
    property_type TEXT CHECK (property_type IN ('flat', 'house_land')),
    lat          DOUBLE PRECISION NOT NULL,
    lng          DOUBLE PRECISION NOT NULL,
    embedding    vector(384),
    amenities    JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cosine-distance similarity search (used by rag/retriever.py)
-- Created as CONCURRENTLY would fail inside a transaction; plain CREATE INDEX
-- is safe here since the table is empty on first init.
CREATE INDEX IF NOT EXISTS listings_embedding_idx
    ON listings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
