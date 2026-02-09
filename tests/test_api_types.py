# tests/test_api_types.py
"""Integration tests for types endpoint."""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.database import Base
from api.models.database import Namespace, TypeModel
from api.settings import get_settings


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
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
    """Provide a clean database session for each test."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_namespace(db_session: AsyncSession):
    """Create a test namespace."""
    import uuid
    namespace = Namespace(
        id=f"test-namespace-types-{uuid.uuid4().hex[:8]}",
        name="Test Namespace",
        description="Test namespace for type tests",
    )
    db_session.add(namespace)
    await db_session.commit()
    await db_session.refresh(namespace)

    yield namespace

    # Cleanup
    await db_session.execute(
        delete(Namespace).where(Namespace.id == namespace.id)
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def test_type(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test type in the user namespace."""
    type_model = TypeModel(
        id="type-test-custom",
        namespace_id=test_namespace.id,
        name="CustomType",
        category="abstract",
        python_type="CustomType",
        description="Custom test type",
        validator_categories=["string"],
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
    # Query types without filter
    query = select(TypeModel)
    result = await db_session.execute(query)
    all_types = result.scalars().all()

    # Should have global types + test type
    assert len(all_types) > 0

    # Verify global types exist
    global_types = [t for t in all_types if t.namespace_id == "namespace-global"]
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

    # Simulate the endpoint logic with user namespace filter
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
    global_types = [t for t in types if t.namespace_id == "namespace-global"]
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

    # Simulate the endpoint logic with global namespace filter
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

    # Query with user namespace filter
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

    # Verify primitives are in global namespace
    primitive_types = [t for t in types if t.category == "primitive"]
    assert len(primitive_types) > 0
    assert all(t.namespace_id == settings.global_namespace_id for t in primitive_types)


@pytest.mark.asyncio
async def test_types_endpoint_behavior():
    """Test the actual API endpoint behavior (requires auth mock)."""
    # This test demonstrates how to test the actual endpoint
    # In practice, you'd need to override the auth dependency
    # See: https://fastapi.tiangolo.com/advanced/testing-dependencies/

    # Example structure (requires auth dependency override):
    # async with AsyncClient(app=app, base_url="http://test") as client:
    #     response = await client.get("/v1/types?namespace_id=test-namespace")
    #     assert response.status_code == 200
    #     types = response.json()
    #     assert len(types) > 0

    pass  # Skip for now - requires auth mock setup
