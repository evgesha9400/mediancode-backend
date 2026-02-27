# src/api/database.py
"""Database engine, session factory, and dependency injection."""

from collections.abc import AsyncGenerator

import orjson
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.settings import get_settings


def _json_serializer(obj: object) -> str:
    """JSON serializer for JSONB columns. Handles UUID, datetime, Decimal, etc."""
    return orjson.dumps(obj).decode("utf-8")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
    connect_args={"prepared_statement_cache_size": 0},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for dependency injection.

    :yields: An async database session that auto-closes after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
