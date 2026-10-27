-- Reality AI Initial Database Extension Setup
-- Enables geospatial (postgis) and vector similarity search (pgvector) extensions

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
