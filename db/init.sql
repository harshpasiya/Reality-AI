-- Reality AI — Local dev database initialisation
-- Runs automatically on first container start via docker-entrypoint-initdb.d.
-- Installs required extensions and creates a minimal listing table for
-- AI-track testing independently of Person 2's real backend.

-- ──────────────────────────────────────────────────────────────────────
-- Extensions
-- ──────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────────────────────────────
-- listing table
--
-- NOTE: This mirrors a SUBSET of Person 2's real schema (app/models/listing.py
-- in the backend repo) for local AI-track testing only. The authoritative
-- schema and all migrations live in the backend repo. Do not treat this as
-- the source of truth — if the real schema changes, update this file to match.
--
-- Same names, types and constraints as the backend for every column the AI
-- reads or writes. Omitted: carpet_area, built_up_area, plot_area,
-- floor_number, images, view_count, updated_at; broker_id has no foreign key
-- because there is no broker table here.
-- embedding dimension: 384 (all-MiniLM-L6-v2, see ai/embeddings/embedding_model.py)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listing (
    id            SERIAL PRIMARY KEY,
    broker_id     INTEGER,
    title         VARCHAR(200) NOT NULL,
    description   TEXT,
    price         NUMERIC(12, 2) NOT NULL,
    property_type VARCHAR NOT NULL,
    location      geometry(POINT, 4326) NOT NULL,
    -- {"bedrooms": int, "bathrooms": int, ...}; NULL for open plots
    rooms         JSON,
    embedding     vector(384),
    amenities     JSON,
    status        VARCHAR(20) NOT NULL DEFAULT 'available',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_listing_property_type CHECK (property_type IN ('flat', 'house_land')),
    CONSTRAINT ck_listing_status CHECK (status IN ('available', 'under_offer', 'sold', 'withdrawn')),
    CONSTRAINT ck_listing_rooms_bedrooms CHECK (
        rooms IS NULL OR rooms::jsonb->'bedrooms' IS NULL
        OR (rooms::jsonb->>'bedrooms') ~ '^[0-9]+$'
    )
);

CREATE INDEX IF NOT EXISTS ix_listing_status ON listing (status);
CREATE INDEX IF NOT EXISTS idx_listing_location ON listing USING gist (location);
CREATE INDEX IF NOT EXISTS idx_listing_location_geog ON listing USING gist ((location::geography));
CREATE INDEX IF NOT EXISTS ix_listing_bedrooms ON listing (((rooms->>'bedrooms')::int));

-- No vector index on purpose. At a few hundred rows an exact scan takes well
-- under a millisecond. The IVFFlat index that used to be here was (a) built on
-- an empty table, so its clusters were meaningless, (b) built for cosine
-- distance while the retriever orders by <-> (L2), and (c) approximate indexes
-- apply WHERE filters AFTER the index scan, so price/BHK/locality filters
-- could silently return fewer than top_k rows. Revisit (HNSW + pgvector
-- iterative scans) only at real production scale — see Prompt 5.1.
