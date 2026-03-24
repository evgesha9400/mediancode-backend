# tests/support/api_client.py
"""Authenticated HTTP client helpers for API integration tests."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_current_user
from api.main import app
from api.models.database import (
    ApiModel,
    FieldModel,
    GenerationModel,
    Namespace,
    ObjectDefinition,
    UserModel,
)


def override_auth(clerk_id: str) -> None:
    """Set the Clerk auth dependency to return a fixed user ID.

    :param clerk_id: Clerk user ID to inject.
    """
    app.dependency_overrides[get_current_user] = lambda: clerk_id


def clear_auth() -> None:
    """Remove the Clerk auth dependency override."""
    app.dependency_overrides.pop(get_current_user, None)


def make_transport() -> ASGITransport:
    """Build an ASGI transport bound to the FastAPI app."""
    return ASGITransport(app=app)


async def cleanup_user_data(clerk_id: str) -> None:
    """Delete all DB entities owned by a test Clerk ID.

    Connects directly to PostgreSQL and deletes in reverse dependency
    order so FK constraints are satisfied.

    :param clerk_id: Clerk user ID whose data should be purged.
    """
    from api.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.clerk_id == clerk_id)
        )
        user = result.scalar_one_or_none()
        if user:
            uid = user.id
            await session.execute(
                delete(GenerationModel).where(GenerationModel.user_id == uid)
            )
            await session.execute(delete(ApiModel).where(ApiModel.user_id == uid))
            await session.execute(
                delete(ObjectDefinition).where(ObjectDefinition.user_id == uid)
            )
            await session.execute(delete(FieldModel).where(FieldModel.user_id == uid))
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()

    await engine.dispose()
