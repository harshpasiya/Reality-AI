import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure backend root is on sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.core.config import settings, sqlalchemy_url
from app.core.database import Base
import app.models  # noqa: F401 load models for metadata auto-detection

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# Set database URL dynamically from app settings
# (same driver selection as app.core.database, so Alembic never needs a
# driver the app doesn't).  '%' is doubled because ConfigParser interpolates.
config.set_main_option(
    "sqlalchemy.url", sqlalchemy_url(settings.DATABASE_URL).replace("%", "%%")
)

target_metadata = Base.metadata

# ── Autogenerate filters ──────────────────────────────────────────────────
# PostGIS installs many tables (tiger geocoder, topology, spatial_ref_sys,
# geometry_columns, etc.) that we must NOT include in migrations.
# Whitelist approach: only track tables registered in our ORM metadata.
_APP_TABLES = set(target_metadata.tables.keys())


def _include_object(obj, name, type_, reflected, compare_to):
    """Only include ORM-registered tables in autogenerate diffs."""
    if type_ == "table":
        return name in _APP_TABLES
    # Include columns, indexes, etc. only if they belong to an app table
    if hasattr(obj, "table") and hasattr(obj.table, "name"):
        return obj.table.name in _APP_TABLES
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
