# tests/test_api/test_services/test_base_service.py
"""Integration tests for BaseService system namespace protection."""

import pytest

pytestmark = pytest.mark.integration

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, TypeModel, UserModel
from api.services.type import TypeService
from api.settings import get_settings


@pytest.mark.asyncio
async def test_assert_mutable_rejects_system_type(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """_assert_mutable raises 403 for entities in the system namespace."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    system_type = result.scalars().first()
    assert system_type is not None

    service = TypeService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service._assert_mutable(system_type)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_assert_mutable_allows_user_type(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
    test_user: UserModel,
):
    """_assert_mutable does not raise for user-owned entities."""
    user_type = TypeModel(
        namespace_id=provisioned_namespace.id,
        user_id=test_user.id,
        name="UserType",
        python_type="UserType",
    )
    db_session.add(user_type)
    await db_session.flush()

    service = TypeService(db_session)
    # Should not raise
    service._assert_mutable(user_type)

    # Cleanup
    await db_session.execute(delete(TypeModel).where(TypeModel.id == user_type.id))
    await db_session.flush()


@pytest.mark.asyncio
async def test_delete_rejects_system_entity(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """BaseService.delete() raises 403 for system namespace entities."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    system_type = result.scalars().first()
    assert system_type is not None

    service = TypeService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.delete(system_type)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_rejects_system_entity(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """BaseService.update() raises 403 for system namespace entities."""
    settings = get_settings()
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == settings.system_namespace_id,
        )
    )
    system_type = result.scalars().first()
    assert system_type is not None

    service = TypeService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.update(system_type, {"name": "hacked"})
    assert exc_info.value.status_code == 403
