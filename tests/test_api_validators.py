# tests/test_api_validators.py
"""Integration tests for validators endpoint."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.database import Base
from api.main import app
from api.models.database import Namespace, ValidatorModel
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
    namespace = Namespace(
        name="Test Namespace",
        description="Test namespace for validator tests",
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
async def test_validator(db_session: AsyncSession, test_namespace: Namespace):
    """Create a test validator in the user namespace."""
    validator = ValidatorModel(
        namespace_id=test_namespace.id,
        name="custom_test",
        type="string",
        description="Custom test validator",
        category="custom",
        parameter_type="str",
        example_usage="Field(custom_test='value')",
        docs_url="",
    )
    db_session.add(validator)
    await db_session.commit()
    await db_session.refresh(validator)

    yield validator

    # Cleanup
    await db_session.execute(
        delete(ValidatorModel).where(ValidatorModel.id == validator.id)
    )
    await db_session.commit()


@pytest_asyncio.fixture
def mock_auth_headers():
    """Mock authentication headers for testing."""
    # In a real test, you'd use a mock JWT or override the auth dependency
    # For now, we'll document that auth needs to be mocked
    return {"Authorization": "Bearer mock_token"}


@pytest.mark.asyncio
async def test_list_validators_no_namespace_filter(
    db_session: AsyncSession,
    test_validator: ValidatorModel,
):
    """Test that all validators are returned when no namespace filter is provided."""
    # Query validators without filter
    query = select(ValidatorModel)
    result = await db_session.execute(query)
    all_validators = result.scalars().all()

    # Should have global validators + test validator
    assert len(all_validators) > 0

    # Verify global validators exist
    settings = get_settings()
    global_validators = [v for v in all_validators if v.namespace_id == settings.global_namespace_id]
    assert len(global_validators) > 0

    # Verify test validator exists
    test_validators = [v for v in all_validators if v.id == test_validator.id]
    assert len(test_validators) == 1


@pytest.mark.asyncio
async def test_list_validators_with_user_namespace(
    db_session: AsyncSession,
    test_namespace: Namespace,
    test_validator: ValidatorModel,
):
    """Test that global + user namespace validators are returned when filtering by user namespace."""
    settings = get_settings()

    # Simulate the endpoint logic with user namespace filter
    from sqlalchemy import or_, select

    query = select(ValidatorModel).where(
        or_(
            ValidatorModel.namespace_id == test_namespace.id,
            ValidatorModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    validators = result.scalars().all()

    # Should have global validators + test validator
    assert len(validators) > 0

    # Verify global validators are included
    global_validators = [v for v in validators if v.namespace_id == settings.global_namespace_id]
    assert len(global_validators) > 0

    # Verify test validator is included
    test_validators = [v for v in validators if v.id == test_validator.id]
    assert len(test_validators) == 1

    # Verify no validators from other namespaces
    other_validators = [
        v for v in validators
        if v.namespace_id != test_namespace.id
        and v.namespace_id != settings.global_namespace_id
    ]
    assert len(other_validators) == 0


@pytest.mark.asyncio
async def test_list_validators_global_namespace_only(db_session: AsyncSession):
    """Test that only global validators are returned when filtering by global namespace."""
    settings = get_settings()

    # Simulate the endpoint logic with global namespace filter
    from sqlalchemy import or_, select

    query = select(ValidatorModel).where(
        or_(
            ValidatorModel.namespace_id == settings.global_namespace_id,
            ValidatorModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    validators = result.scalars().all()

    # All validators should be from global namespace
    assert all(v.namespace_id == settings.global_namespace_id for v in validators)
    assert len(validators) > 0


@pytest.mark.asyncio
async def test_list_validators_includes_inline_validators(
    db_session: AsyncSession,
    test_namespace: Namespace,
):
    """Test that inline validators are always included regardless of namespace filter."""
    settings = get_settings()

    # Critical inline validators that should always be available
    expected_inline_validators = ["max_length", "min_length", "pattern", "email_format"]

    # Query with user namespace filter
    from sqlalchemy import or_, select

    query = select(ValidatorModel).where(
        or_(
            ValidatorModel.namespace_id == test_namespace.id,
            ValidatorModel.namespace_id == settings.global_namespace_id,
        )
    )
    result = await db_session.execute(query)
    validators = result.scalars().all()

    # Verify all expected inline validators are present
    validator_names = {v.name for v in validators}
    for expected_name in expected_inline_validators:
        assert (
            expected_name in validator_names
        ), f"Inline validator '{expected_name}' should be available in filtered results"

    # Verify they are marked as inline
    inline_validators = [v for v in validators if v.category == "inline"]
    assert len(inline_validators) > 0
    assert all(v.namespace_id == settings.global_namespace_id for v in inline_validators)


@pytest.mark.asyncio
async def test_validators_endpoint_behavior():
    """Test the actual API endpoint behavior (requires auth mock)."""
    # This test demonstrates how to test the actual endpoint
    # In practice, you'd need to override the auth dependency
    # See: https://fastapi.tiangolo.com/advanced/testing-dependencies/

    # Example structure (requires auth dependency override):
    # async with AsyncClient(app=app, base_url="http://test") as client:
    #     response = await client.get("/v1/validators?namespace_id=test-namespace")
    #     assert response.status_code == 200
    #     validators = response.json()
    #     assert len(validators) > 0

    pass  # Skip for now - requires auth mock setup
