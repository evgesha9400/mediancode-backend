# src/api/settings.py
"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

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
    :ivar global_namespace_id: ID of the global namespace containing built-in types/validators.
    :ivar frontend_url: Frontend URL for CORS configuration.
    """

    model_config = SettingsConfigDict(
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/median_code"
    )
    clerk_frontend_api_url: str = "https://clerk.example.com"
    clerk_jwt_audience: str | None = None
    global_namespace_id: str = "namespace-global"
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"  # "development" or "production"

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
