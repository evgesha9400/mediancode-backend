# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api_craft.main import APIGenerator
from api_craft.models.input import InputAPI

SPECS_PATH = Path(__file__).parent / "specs"


def load_input(filename: str) -> InputAPI:
    """Load and validate an API input from YAML file."""
    yaml_path = SPECS_PATH / filename
    with open(yaml_path, "r") as f:
        api_data = yaml.safe_load(f)
    return InputAPI.model_validate(api_data)


def load_app(src_path: Path):
    """Dynamically import the FastAPI app from a generated project.

    Uses unique module names to avoid conflicts between different
    generated projects in the same test session.
    """
    # Generate unique prefix for this import
    prefix = f"_gen_{uuid.uuid4().hex[:8]}"

    # Add src_path to sys.path so relative imports work
    sys.path.insert(0, str(src_path))

    modules_to_cleanup = []
    try:
        # Load modules in dependency order with unique names
        module_files = ["models", "path", "query", "views", "main"]

        for module_name in module_files:
            module_path = src_path / f"{module_name}.py"
            if not module_path.exists():
                continue

            unique_name = f"{prefix}_{module_name}"
            spec = importlib.util.spec_from_file_location(unique_name, module_path)
            module = importlib.util.module_from_spec(spec)

            # Register with both unique and simple names for import resolution
            sys.modules[unique_name] = module
            sys.modules[module_name] = module
            modules_to_cleanup.append(unique_name)
            modules_to_cleanup.append(module_name)

            spec.loader.exec_module(module)

        return sys.modules["main"].app
    finally:
        # Clean up sys.path
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))

        # Clean up sys.modules to prevent cross-test pollution
        for mod_name in modules_to_cleanup:
            sys.modules.pop(mod_name, None)


# --- E2E fixtures ---


@pytest.fixture(scope="session")
def items_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Items API once per test session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("items_api")

    api_input = load_input("items_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))

    src_path = tmp_path / "items-api" / "src"
    app = load_app(src_path)

    return TestClient(app)


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
    """Provision a test user and return their default namespace."""
    from api.models.database import FieldConstraintModel, Namespace, TypeModel
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

    # Cleanup: delete children first, then namespace
    await db_session.execute(
        delete(TypeModel).where(TypeModel.namespace_id == namespace.id)
    )
    await db_session.execute(
        delete(FieldConstraintModel).where(
            FieldConstraintModel.namespace_id == namespace.id
        )
    )
    await db_session.execute(delete(Namespace).where(Namespace.id == namespace.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def test_namespace(db_session: AsyncSession):
    """Create a test namespace, cleaned up after the test."""
    from api.models.database import Namespace

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
