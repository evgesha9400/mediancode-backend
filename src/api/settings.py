# src/api/settings.py
"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_file() -> str:
    """Determine which env file to load.

    Priority: .env.local (local dev) > .env (fallback)
    """
    if Path(".env.local").exists():
        return ".env.local"
    return ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    :ivar database_url: PostgreSQL connection string for async SQLAlchemy.
    :ivar clerk_frontend_api_url: Clerk Frontend API URL for JWT validation (from Clerk dashboard).
    :ivar clerk_jwt_audience: Expected audience claim in Clerk JWTs (optional).
    :ivar system_namespace_id: ID of the system namespace containing built-in seed types/constraints.
    :ivar frontend_url: Frontend URL for CORS configuration.
    :ivar beta_mode: Skip credit checks when True.
    :ivar default_credits: Credits granted to new users (0 during beta).
    :ivar clerk_webhook_secret: Svix signing secret for Clerk webhooks.
    """

    model_config = SettingsConfigDict(
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/median_code"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_asyncpg_scheme(cls, v: str) -> str:
        """Ensure database URL uses the asyncpg driver scheme.

        Railway and other PaaS providers inject DATABASE_URL with
        ``postgres://`` or ``postgresql://`` scheme. SQLAlchemy's async
        engine requires ``postgresql+asyncpg://``.

        :param v: Raw database URL from environment.
        :returns: URL with ``postgresql+asyncpg://`` scheme.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    clerk_frontend_api_url: str = "https://clerk.example.com"
    clerk_jwt_audience: str | None = None
    system_namespace_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"  # "development" or "production"
    beta_mode: bool = True  # Skip credit checks when True
    default_credits: int = 0  # Credits granted to new users (0 during beta)
    clerk_webhook_secret: str = ""  # Svix signing secret for Clerk webhooks

    @field_validator("system_namespace_id", mode="before")
    @classmethod
    def parse_uuid(cls, v: str | UUID) -> UUID:
        """Parse UUID from string if needed.

        :param v: Raw UUID from environment (string or UUID object).
        :returns: UUID object.
        """
        if isinstance(v, str):
            return UUID(v)
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance.

    :returns: Singleton Settings instance loaded from environment.
    """
    return Settings()
