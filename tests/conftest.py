# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.models.database import GenerationModel, Namespace, UserModel


# --- Integration test (database) fixtures ---


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
    from api.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Create a session factory for tests."""
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    """Provide a database session that rolls back after each test."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


TEST_USER_ID = "test_user_integration"


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserModel:
    """Provision a test user and return the UserModel."""
    from api.services.user import UserService

    service = UserService(db_session)
    user = await service.ensure_provisioned(TEST_USER_ID)
    await db_session.commit()

    yield user

    # Cleanup: delete generations, namespace, and user created during provisioning
    await db_session.execute(
        delete(GenerationModel).where(GenerationModel.user_id == user.id)
    )
    await db_session.execute(delete(Namespace).where(Namespace.user_id == user.id))
    await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def provisioned_namespace(
    db_session: AsyncSession, test_user: UserModel
) -> Namespace:
    """Return the test user's default namespace.

    The namespace starts empty. Seed data (types, constraints) lives in the
    system namespace and is shared read-only via OR clauses in service queries.
    """
    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == test_user.id,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    return namespace


@pytest_asyncio.fixture
async def test_namespace(db_session: AsyncSession, test_user: UserModel) -> Namespace:
    """Create a test namespace, cleaned up after the test."""
    namespace = Namespace(
        name="Test Namespace",
        description="Test namespace for integration tests",
        user_id=test_user.id,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    # Cleanup
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()
