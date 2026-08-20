# Extends postgis/postgis:16-3.4 with the pgvector extension.
# The base image already includes PostGIS; we add pgvector via apt.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
