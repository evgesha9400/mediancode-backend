# tests/test_api_types.py
"""Integration tests for types endpoint."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, TypeModel
from conftest import TEST_USER_ID


@pytest_asyncio.fixture
async def test_type(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test type in the user namespace."""
    type_model = TypeModel(
        namespace_id=test_namespace.id,
        user_id=TEST_USER_ID,
        name="CustomType",
        python_type="CustomType",
        description="Custom test type",
    )
    db_session.add(type_model)
    await db_session.commit()
    await db_session.refresh(type_model)

    yield type_model

    # Cleanup
    await db_session.execute(delete(TypeModel).where(TypeModel.id == type_model.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_provisioning_creates_types(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that provisioning creates copies of all global types for the user."""
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == provisioned_namespace.id,
        )
    )
    types = result.scalars().all()

    # Should have all 8 standard types
    assert len(types) == 8

    type_names = {t.name for t in types}
    expected = {
        "str",
        "int",
        "float",
        "bool",
        "datetime",
        "uuid",
        "EmailStr",
        "HttpUrl",
    }
    assert type_names == expected


@pytest.mark.asyncio
async def test_provisioned_types_have_correct_user_id(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that provisioned types are owned by the user."""
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == provisioned_namespace.id,
        )
    )
    types = result.scalars().all()

    assert all(t.user_id == TEST_USER_ID for t in types)


@pytest.mark.asyncio
async def test_provisioned_types_preserve_parent_relationships(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that parent_type_id relationships are correctly remapped."""
    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == provisioned_namespace.id,
        )
    )
    types = result.scalars().all()
    by_name = {t.name: t for t in types}

    # EmailStr and HttpUrl should have parent_type_id pointing to the user's str type
    assert by_name["EmailStr"].parent_type_id == by_name["str"].id
    assert by_name["HttpUrl"].parent_type_id == by_name["str"].id

    # Primitive types should have no parent
    for name in ["str", "int", "float", "bool", "datetime", "uuid"]:
        assert by_name[name].parent_type_id is None


@pytest.mark.asyncio
async def test_list_types_includes_custom_and_provisioned(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_type: TypeModel,
    provisioned_namespace: Namespace,
):
    """Test that user sees both provisioned types and custom types."""
    result = await db_session.execute(
        select(TypeModel).join(Namespace).where(Namespace.user_id == TEST_USER_ID)
    )
    types = result.scalars().all()

    # Should have at least 8 provisioned types + 1 custom type
    assert len(types) >= 9

    type_names = {t.name for t in types}
    assert "CustomType" in type_names
    assert "str" in type_names


@pytest.mark.asyncio
async def test_provisioned_types_include_primitives(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Test that primitive types are always available after provisioning."""
    expected_primitives = ["str", "int", "float", "bool", "datetime", "uuid"]

    result = await db_session.execute(
        select(TypeModel).where(
            TypeModel.namespace_id == provisioned_namespace.id,
        )
    )
    types = result.scalars().all()

    type_names = {t.name for t in types}
    for expected_name in expected_primitives:
        assert (
            expected_name in type_names
        ), f"Primitive type '{expected_name}' should be available after provisioning"
