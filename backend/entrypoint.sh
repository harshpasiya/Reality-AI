#!/bin/sh
# entrypoint.sh — wait for DB, run migrations, then start the API server.
# Using /bin/sh (POSIX) for maximum compatibility across base images.

set -e

echo "⏳ Waiting for PostgreSQL to be ready..."
until python -c "
import sys, os
try:
    import psycopg
    psycopg.connect(os.environ['DATABASE_URL'])
    print('PostgreSQL is ready.')
except ImportError:
    import psycopg2
    psycopg2.connect(os.environ['DATABASE_URL'])
    print('PostgreSQL is ready.')
except Exception as e:
    print(f'Not ready yet: {e}')
    sys.exit(1)
"; do
  sleep 2
done

echo "🔄 Running Alembic migrations..."
alembic upgrade head

echo "🚀 Starting Reality AI backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
