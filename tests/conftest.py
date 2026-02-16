# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.models.database import Namespace


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
async def provisioned_namespace(db_session: AsyncSession):
    """Provision a test user and return their default namespace.

    The namespace starts empty. Seed data (types, constraints) lives in the
    system namespace and is shared read-only via OR clauses in service queries.
    """
    from api.services.user_provisioning import UserProvisioningService

    service = UserProvisioningService(db_session)
    await service.ensure_provisioned(TEST_USER_ID)
    await db_session.commit()

    result = await db_session.execute(
        select(Namespace).where(
            Namespace.user_id == TEST_USER_ID,
            Namespace.is_default.is_(True),
        )
    )
    namespace = result.scalar_one()

    yield namespace

    # Cleanup: namespace is empty (no copied data), just delete it
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def test_namespace(db_session: AsyncSession):
    """Create a test namespace, cleaned up after the test."""
    namespace = Namespace(
        name="Test Namespace",
        description="Test namespace for integration tests",
        user_id=TEST_USER_ID,
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    # Cleanup
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()
