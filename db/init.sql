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
    -- Local-test only: bedroom count for the retriever's BHK filter (NULL for
    -- plots). Person 2's real schema exposes bedrooms through the `rooms` JSON
    -- field instead; the mapping happens at merge time.
    bhk          INTEGER,
    lat          DOUBLE PRECISION NOT NULL,
    lng          DOUBLE PRECISION NOT NULL,
    embedding    vector(384),
    amenities    JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- No vector index on purpose. At a few hundred rows an exact scan takes well
-- under a millisecond. The IVFFlat index that used to be here was (a) built on
-- an empty table, so its clusters were meaningless, (b) built for cosine
-- distance while the retriever orders by <-> (L2), and (c) approximate indexes
-- apply WHERE filters AFTER the index scan, so price/BHK/locality filters
-- could silently return fewer than top_k rows. Revisit (HNSW + pgvector
-- iterative scans) only at real production scale — see Prompt 5.1.
