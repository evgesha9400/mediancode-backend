"""Fixtures for API E2E tests."""

import pytest_asyncio
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

TEST_CLERK_ID = "test_user_e2e_shop"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client():
    """Module-scoped HTTP client with auth override and DB cleanup.

    Sets up:
    - Override get_current_user to return a static Clerk ID
    - httpx.AsyncClient with ASGITransport against the FastAPI app

    Tears down:
    - Clears dependency overrides
    - Deletes all DB entities owned by the test user (reverse dependency order)
    - Deletes the test user itself
    """
    app.dependency_overrides[get_current_user] = lambda: TEST_CLERK_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/v1",
    ) as c:
        yield c

    app.dependency_overrides.clear()

    # --- DB cleanup (handles both success and partial-failure cases) ---
    from api.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.clerk_id == TEST_CLERK_ID)
        )
        user = result.scalar_one_or_none()
        if user:
            uid = user.id
            # Reverse dependency order; DB-level CASCADE handles children:
            #   apis → api_endpoints (CASCADE)
            #   objects → fields_on_objects, applied_model_validators (CASCADE)
            #   fields → applied_constraints, applied_field_validators (CASCADE)
            await session.execute(delete(ApiModel).where(ApiModel.user_id == uid))
            await session.execute(
                delete(ObjectDefinition).where(ObjectDefinition.user_id == uid)
            )
            await session.execute(delete(FieldModel).where(FieldModel.user_id == uid))
            await session.execute(
                delete(GenerationModel).where(GenerationModel.user_id == uid)
            )
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()

    await engine.dispose()
