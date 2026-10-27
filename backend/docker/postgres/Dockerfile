FROM postgis/postgis:16-3.4

# Install pgvector for PostgreSQL 16.
# The PostgreSQL APT repository is already configured
# in the postgis/postgis image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
