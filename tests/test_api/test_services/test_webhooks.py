# tests/test_api/test_services/test_webhooks.py
"""Integration tests for webhook-related operations in UserService."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, UserModel
from api.services.user import UserService

WEBHOOK_USER_A = "test_webhook_user_a"


@pytest_asyncio.fixture
async def cleanup_webhook_users(db_session: AsyncSession):
    """Clean up webhook test data after tests."""
    yield

    await db_session.execute(
        delete(Namespace).where(Namespace.user_id == WEBHOOK_USER_A)
    )
    await db_session.execute(
        delete(UserModel).where(UserModel.clerk_id == WEBHOOK_USER_A)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_upsert_from_clerk_creates_user(
    db_session: AsyncSession,
    cleanup_webhook_users,
):
    """New clerk_id creates user with profile fields."""
    clerk_data = {
        "id": WEBHOOK_USER_A,
        "email": "webhook@example.com",
        "first_name": "Webhook",
        "last_name": "User",
        "username": "webhookuser",
        "image_url": "https://example.com/avatar.png",
    }

    service = UserService(db_session)
    user = await service.upsert_from_clerk(clerk_data)
    await db_session.commit()

    assert isinstance(user, UserModel)
    assert user.clerk_id == WEBHOOK_USER_A
    assert user.email == "webhook@example.com"
    assert user.first_name == "Webhook"
    assert user.last_name == "User"
    assert user.username == "webhookuser"
    assert user.image_url == "https://example.com/avatar.png"

    # Verify the user row exists in the database
    result = await db_session.execute(
        select(UserModel).where(UserModel.clerk_id == WEBHOOK_USER_A)
    )
    db_user = result.scalar_one()
    assert db_user.id == user.id


@pytest.mark.asyncio
async def test_upsert_from_clerk_updates_user(
    db_session: AsyncSession,
    cleanup_webhook_users,
):
    """Existing clerk_id updates profile fields."""
    # Create the user first
    initial_data = {
        "id": WEBHOOK_USER_A,
        "email": "old@example.com",
        "first_name": "Old",
        "last_name": "Name",
        "username": "olduser",
        "image_url": "https://example.com/old.png",
    }

    service = UserService(db_session)
    user = await service.upsert_from_clerk(initial_data)
    await db_session.commit()
    original_id = user.id

    # Update with new data
    updated_data = {
        "id": WEBHOOK_USER_A,
        "email": "new@example.com",
        "first_name": "New",
        "last_name": "Name",
        "username": "newuser",
        "image_url": "https://example.com/new.png",
    }

    user = await service.upsert_from_clerk(updated_data)
    await db_session.commit()

    assert user.id == original_id
    assert user.email == "new@example.com"
    assert user.first_name == "New"
    assert user.last_name == "Name"
    assert user.username == "newuser"
    assert user.image_url == "https://example.com/new.png"


@pytest.mark.asyncio
async def test_upsert_from_clerk_idempotent(
    db_session: AsyncSession,
    cleanup_webhook_users,
):
    """Calling twice with same data doesn't duplicate."""
    clerk_data = {
        "id": WEBHOOK_USER_A,
        "email": "idempotent@example.com",
        "first_name": "Same",
        "last_name": "Data",
        "username": "sameuser",
        "image_url": "https://example.com/same.png",
    }

    service = UserService(db_session)
    user_first = await service.upsert_from_clerk(clerk_data)
    await db_session.commit()

    user_second = await service.upsert_from_clerk(clerk_data)
    await db_session.commit()

    assert user_first.id == user_second.id
    assert user_second.email == "idempotent@example.com"

    # Verify only one user row exists
    result = await db_session.execute(
        select(UserModel).where(UserModel.clerk_id == WEBHOOK_USER_A)
    )
    users = result.scalars().all()
    assert len(users) == 1
