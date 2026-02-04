# src/api/settings.py
"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    :ivar database_url: PostgreSQL connection string for async SQLAlchemy.
    :ivar clerk_issuer_url: Clerk issuer URL for JWT validation.
    :ivar clerk_audience: Expected audience claim in Clerk JWTs.
    :ivar global_namespace_id: ID of the global namespace containing built-in types/validators.
    :ivar frontend_url: Frontend URL for CORS configuration.
    """

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/median_code"
    )
    clerk_issuer_url: str = "https://clerk.your-domain.com"
    clerk_audience: str | None = None
    global_namespace_id: str = "namespace-global"
    frontend_url: str = "http://localhost:5173"

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance.

    :returns: Singleton Settings instance loaded from environment.
    """
    return Settings()
