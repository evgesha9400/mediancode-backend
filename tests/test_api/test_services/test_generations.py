# tests/test_api/test_services/test_generations.py
"""Integration tests for generation tracking in UserService."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import ApiModel, GenerationModel, Namespace, UserModel
from api.services.user import UserService
from api.settings import get_settings, Settings

GEN_USER_A = "test_gen_user_a"


def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with overrides for testing."""
    defaults = {
        "beta_mode": False,
        "free_generation_limit": 3,
    }
    defaults.update(overrides)
    return get_settings().model_copy(update=defaults)


@pytest_asyncio.fixture
async def cleanup_gen_users(db_session: AsyncSession):
    """Clean up generation test data after tests."""
    yield

    user_result = await db_session.execute(
        select(UserModel).where(UserModel.clerk_id == GEN_USER_A)
    )
    user = user_result.scalar_one_or_none()
    if user:
        await db_session.execute(
            delete(GenerationModel).where(GenerationModel.user_id == user.id)
        )
        await db_session.execute(delete(ApiModel).where(ApiModel.user_id == user.id))
        await db_session.execute(delete(Namespace).where(Namespace.user_id == user.id))
        await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def gen_user(db_session: AsyncSession, cleanup_gen_users) -> UserModel:
    """Provision a user for generation tests."""
    service = UserService(db_session)
    user = await service.ensure_provisioned(GEN_USER_A)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def gen_api(db_session: AsyncSession, gen_user: UserModel) -> ApiModel:
    """Create a minimal API for generation tests."""
    ns_result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == gen_user.id, Namespace.is_default.is_(True)
        )
    )
    namespace = ns_result.scalar_one()

    api = ApiModel(
        namespace_id=namespace.id,
        user_id=gen_user.id,
        title="Test API",
        version="1.0.0",
        description="Test",
        base_url="/test",
        server_url="http://localhost",
    )
    db_session.add(api)
    await db_session.commit()
    await db_session.refresh(api)
    return api


@pytest.mark.asyncio
async def test_can_generate_in_beta_mode(
    db_session: AsyncSession,
    gen_user: UserModel,
):
    """With beta_mode=True, can_generate always returns True."""
    settings = _make_settings(beta_mode=True, free_generation_limit=0)
    service = UserService(db_session)
    result = await service.can_generate(gen_user, settings)

    assert result is True


@pytest.mark.asyncio
async def test_can_generate_under_limit(
    db_session: AsyncSession,
    gen_user: UserModel,
):
    """With 0 generations and limit=3, returns True."""
    settings = _make_settings(beta_mode=False, free_generation_limit=3)
    service = UserService(db_session)
    result = await service.can_generate(gen_user, settings)

    assert result is True


@pytest.mark.asyncio
async def test_can_generate_at_limit(
    db_session: AsyncSession,
    gen_user: UserModel,
    gen_api: ApiModel,
):
    """When generation count equals limit, returns False."""
    settings = _make_settings(beta_mode=False, free_generation_limit=2)
    service = UserService(db_session)

    # Record exactly 2 generations to hit the limit
    await service.record_generation(gen_user, gen_api.id)
    await service.record_generation(gen_user, gen_api.id)
    await db_session.commit()

    result = await service.can_generate(gen_user, settings)
    assert result is False


@pytest.mark.asyncio
async def test_record_generation_creates_row(
    db_session: AsyncSession,
    gen_user: UserModel,
    gen_api: ApiModel,
):
    """record_generation inserts a row in the generations table."""
    service = UserService(db_session)
    await service.record_generation(gen_user, gen_api.id)
    await db_session.commit()

    result = await db_session.execute(
        select(GenerationModel).where(GenerationModel.user_id == gen_user.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].api_id == gen_api.id


@pytest.mark.asyncio
async def test_record_generation_in_beta_still_records(
    db_session: AsyncSession,
    gen_user: UserModel,
    gen_api: ApiModel,
):
    """record_generation always records, even conceptually in beta mode."""
    service = UserService(db_session)
    await service.record_generation(gen_user, gen_api.id)
    await db_session.commit()

    result = await db_session.execute(
        select(GenerationModel).where(GenerationModel.user_id == gen_user.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
