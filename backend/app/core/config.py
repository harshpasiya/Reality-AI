"""Application settings and configuration loading via Pydantic BaseSettings."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Monorepo layout: <repo>/backend/app/core/config.py.  The shared .env lives
# at the repo root (the ai/ package reads it too); backend/.env, if present,
# overrides it for backend-only settings.
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILES = (REPO_ROOT / ".env", BACKEND_DIR / ".env")

# The backend imports Person 1's ai/ package, which sits at the repo root.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string (e.g. postgresql://user:pass@localhost:5432/dbname)",
    )
    SECRET_KEY: str = Field(
        ...,
        description="Secret key used for signing JWT tokens (at least 32 characters)",
    )

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    PLACEHOLDER_MODE: bool = Field(
        default=True,
        description=(
            "When True, POST /chat returns mock replies instead of invoking AI model. "
            "Set to false once Person 1's ai/ package is merged."
        ),
    )
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed frontend origins (the Next.js dev URL locally)",
    )
    UPLOAD_DIR: str = Field(
        default=str(BACKEND_DIR / "uploads"),
        description="Directory where listing photos are stored and served from /uploads",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_strength(cls, value: str) -> str:
        """Reject short keys — a guessable key lets anyone sign valid JWTs."""
        if len(value) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """``CORS_ORIGINS`` split into a list, ignoring blanks."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


def sqlalchemy_url(url: str) -> str:
    """Return *url* with the psycopg 3 driver selected when it is installed.

    A bare ``postgresql://`` URL makes SQLAlchemy pick psycopg2.  Both drivers
    are in requirements.txt (the AI modules use psycopg2), so this only
    matters when one of them is missing.  Shared by the app engine, Alembic
    and the test suite so they always agree on the driver.
    """
    if url.startswith("postgresql://"):
        try:
            import psycopg  # noqa: F401

            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        except ImportError:
            pass
    return url


try:
    settings = Settings()
except Exception as e:
    sys.stderr.write(
        f"\n[CRITICAL ERROR] Failed to load backend configuration:\n{e}\n"
        f"Please verify DATABASE_URL and SECRET_KEY are correctly set in your environment or .env file.\n\n"
    )
    sys.exit(1)

# Person 1's ai/ modules read DATABASE_URL, GOOGLE_PLACES_API_KEY, NLU_BACKEND
# and HF_TOKEN from os.environ, and raise RuntimeError at import when
# DATABASE_URL is missing.  pydantic-settings reads .env without exporting
# it, so export it here (never overriding real environment variables).
for _env_file in reversed(ENV_FILES):  # backend/.env wins, as in Settings
    load_dotenv(_env_file, override=False)
os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
