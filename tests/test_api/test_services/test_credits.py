# tests/test_api/test_services/test_credits.py
"""Integration tests for credit operations in UserService."""

import pytest

pytestmark = pytest.mark.integration

from unittest.mock import patch

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, UserModel
from api.services.user import UserService
from api.settings import Settings, get_settings

CREDIT_USER_A = "test_credit_user_a"


@pytest_asyncio.fixture
async def cleanup_credit_users(db_session: AsyncSession):
    """Clean up credit test data after tests."""
    yield

    await db_session.execute(
        delete(Namespace).where(Namespace.user_id == CREDIT_USER_A)
    )
    await db_session.execute(
        delete(UserModel).where(UserModel.clerk_id == CREDIT_USER_A)
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def credit_user(db_session: AsyncSession, cleanup_credit_users) -> UserModel:
    """Provision a user for credit tests and return the UserModel."""
    service = UserService(db_session)
    user = await service.ensure_provisioned(CREDIT_USER_A)
    await db_session.commit()
    return user


def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with overrides for testing."""
    defaults = {
        "beta_mode": False,
        "default_credits": 0,
    }
    defaults.update(overrides)
    return get_settings().model_copy(update=defaults)


@pytest.mark.asyncio
async def test_has_credits_in_beta_mode(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """With beta_mode=True, has_credits returns True even with 0 credits."""
    assert credit_user.credits_remaining == 0

    settings = _make_settings(beta_mode=True)
    service = UserService(db_session)
    result = await service.has_credits(credit_user, settings)

    assert result is True


@pytest.mark.asyncio
async def test_has_credits_with_credits(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """With beta_mode=False and credits_remaining > 0, returns True."""
    # Give the user some credits
    credit_user.credits_remaining = 5
    db_session.add(credit_user)
    await db_session.flush()

    settings = _make_settings(beta_mode=False)
    service = UserService(db_session)
    result = await service.has_credits(credit_user, settings)

    assert result is True


@pytest.mark.asyncio
async def test_has_credits_no_credits(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """With beta_mode=False and credits_remaining=0, returns False."""
    assert credit_user.credits_remaining == 0

    settings = _make_settings(beta_mode=False)
    service = UserService(db_session)
    result = await service.has_credits(credit_user, settings)

    assert result is False


@pytest.mark.asyncio
async def test_deduct_credit_beta_mode(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """In beta mode, deduct_credit returns True without changing credits."""
    initial_remaining = credit_user.credits_remaining
    initial_used = credit_user.credits_used

    with patch("api.services.user.get_settings") as mock_settings:
        mock_settings.return_value = _make_settings(beta_mode=True)
        service = UserService(db_session)
        result = await service.deduct_credit(credit_user)

    assert result is True

    # Refresh to verify no database change
    await db_session.refresh(credit_user)
    assert credit_user.credits_remaining == initial_remaining
    assert credit_user.credits_used == initial_used


@pytest.mark.asyncio
async def test_deduct_credit_success(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """With credits_remaining > 0, deducts 1 and increments credits_used."""
    # Give the user some credits
    credit_user.credits_remaining = 3
    credit_user.credits_used = 0
    db_session.add(credit_user)
    await db_session.flush()

    with patch("api.services.user.get_settings") as mock_settings:
        mock_settings.return_value = _make_settings(beta_mode=False)
        service = UserService(db_session)
        result = await service.deduct_credit(credit_user)

    assert result is True

    # Refresh to verify database change
    await db_session.refresh(credit_user)
    assert credit_user.credits_remaining == 2
    assert credit_user.credits_used == 1


@pytest.mark.asyncio
async def test_deduct_credit_insufficient(
    db_session: AsyncSession,
    credit_user: UserModel,
):
    """With credits_remaining=0, returns False."""
    assert credit_user.credits_remaining == 0

    with patch("api.services.user.get_settings") as mock_settings:
        mock_settings.return_value = _make_settings(beta_mode=False)
        service = UserService(db_session)
        result = await service.deduct_credit(credit_user)

    assert result is False

    # Refresh to verify no database change
    await db_session.refresh(credit_user)
    assert credit_user.credits_remaining == 0
    assert credit_user.credits_used == 0
