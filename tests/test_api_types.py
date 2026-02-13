# tests/test_api_types.py
"""Integration tests for types endpoint."""

import pytest

pytestmark = pytest.mark.integration

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace, TypeModel
from api.settings import get_settings


@pytest_asyncio.fixture
async def test_type(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test type in the user namespace."""
    type_model = TypeModel(
        namespace_id=test_namespace.id,
        name="CustomType",
        python_type="CustomType",
        description="Custom test type",
    )
    db_session.add(type_model)
    await db_session.commit()
    await db_session.refresh(type_model)

    yield type_model

    # Cleanup
    await db_session.execute(
        delete(TypeModel).where(TypeModel.id == type_model.id)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_types_no_namespace_filter(
    db_session: AsyncSession,
    test_type: TypeModel,
):
    """Test that all types are returned when no namespace filter is provided."""
    query = select(TypeModel)
    result = await db_session.execute(query)
    all_types = result.scalars().all()

    # Should have global types + test type
    assert len(all_types) > 0

    # Verify global types exist
    global_types = [t for t in all_types if t.namespace_id == get_settings().global_namespace_id]
    assert len(global_types) > 0

    # Verify test type exists
    test_types = [t for t in all_types if t.id == test_type.id]
    assert len(test_types) == 1


@pytest.mark.asyncio
async def test_list_types_with_user_namespace(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_type: TypeModel,
):
    """Test that global + user namespace types are returned when filtering by user namespace."""
    settings = get_settings()

    from sqlalchemy import or_, select

    query = select(TypeModel).where(
        or_(
            TypeModel.namespace_id == test_namespace.id,
            TypeModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    types = result.scalars().all()

    # Should have global types + test type
    assert len(types) > 0

    # Verify global types are included
    global_types = [t for t in types if t.namespace_id == get_settings().global_namespace_id]
    assert len(global_types) > 0

    # Verify test type is included
    test_types = [t for t in types if t.id == test_type.id]
    assert len(test_types) == 1

    # Verify no types from other namespaces
    other_types = [
        t for t in types
        if t.namespace_id != test_namespace.id
        and t.namespace_id != settings.global_namespace_id
    ]
    assert len(other_types) == 0


@pytest.mark.asyncio
async def test_list_types_global_namespace_only(db_session: AsyncSession):
    """Test that only global types are returned when filtering by global namespace."""
    settings = get_settings()

    from sqlalchemy import or_, select

    query = select(TypeModel).where(
        or_(
            TypeModel.namespace_id == settings.global_namespace_id,
            TypeModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    types = result.scalars().all()

    # All types should be from global namespace
    assert all(t.namespace_id == settings.global_namespace_id for t in types)
    assert len(types) > 0


@pytest.mark.asyncio
async def test_list_types_includes_primitives(
    db_session: AsyncSession,
    test_namespace: Namespace,
):
    """Test that primitive types are always included regardless of namespace filter."""
    settings = get_settings()

    # Critical primitive types that should always be available
    expected_primitives = ["str", "int", "float", "bool", "datetime", "uuid"]

    from sqlalchemy import or_, select

    query = select(TypeModel).where(
        or_(
            TypeModel.namespace_id == test_namespace.id,
            TypeModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    types = result.scalars().all()

    # Verify all expected primitive types are present
    type_names = {t.name for t in types}
    for expected_name in expected_primitives:
        assert (
            expected_name in type_names
        ), f"Primitive type '{expected_name}' should be available in filtered results"

    # Verify global types are from global namespace
    global_types = [t for t in types if t.namespace_id == settings.global_namespace_id]
    assert len(global_types) > 0
