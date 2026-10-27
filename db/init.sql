-- Reality AI — database initialisation
-- Runs automatically on the first start of a fresh Docker volume
-- (docker-entrypoint-initdb.d).
--
-- Only the extensions are created here.  Every table, constraint and index
-- comes from the backend's Alembic migrations (backend/app/db/migrations),
-- applied by `python setup_local.py` in backend/.  Creating tables here too
-- would make the first migration fail with "relation already exists".

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- No vector index on purpose. At a few hundred rows an exact scan takes well
-- under a millisecond, and approximate indexes (IVFFlat/HNSW) apply WHERE
-- filters AFTER the index scan, so price/BHK/locality filters could silently
-- return fewer than top_k rows. Revisit only at real production scale.
