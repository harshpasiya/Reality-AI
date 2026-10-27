"""
Local development setup script.
Usage:  .venv\Scripts\python.exe setup_local.py

Creates the PostGIS extension (and pgvector when the server has it), then
applies every Alembic migration — the same path Docker and CI use, so a
local database never drifts from the migrations.  Without pgvector the
initial migration stores ``listing.embedding`` as JSONB.
"""
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.core.database import engine

# ── 1. Enable extensions ──────────────────────────────────────────────────────
print("Enabling extensions...")
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    conn.commit()
    print("  postgis ... OK")
    available = conn.execute(
        text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar()
    if available:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
        print("  pgvector ... OK")
    else:
        print("  pgvector ... SKIPPED (not installed in PostgreSQL - OK for dev)")

# ── 2. Apply migrations ───────────────────────────────────────────────────────
print("Running alembic upgrade head...")
result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])
if result.returncode != 0:
    sys.exit("  Alembic upgrade failed - see the output above.")

print("\n Setup complete!")
print("  Start the server:  .venv\\Scripts\\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000")
