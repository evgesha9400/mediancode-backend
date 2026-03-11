# tests/test_api_craft/conftest.py
"""Fixtures for api_craft code generation tests."""

import importlib.util
import sys
import types
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api_craft.main import APIGenerator
from api_craft.models.input import InputAPI

SPECS_PATH = Path(__file__).parent.parent / "specs"


def load_input(filename: str) -> InputAPI:
    """Load and validate an API input from YAML file."""
    yaml_path = SPECS_PATH / filename
    with open(yaml_path, "r") as f:
        api_data = yaml.safe_load(f)
    return InputAPI.model_validate(api_data)


def _create_test_db_module(orm_module, prefix: str):
    """Create a fake database module backed by in-memory SQLite.

    Uses SQLAlchemy's async engine with aiosqlite to support
    the async session pattern used by generated views.
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    import datetime
    import sqlite3

    from pydantic import HttpUrl

    # Register SQLite adapters for types not natively supported
    sqlite3.register_adapter(HttpUrl, str)
    sqlite3.register_adapter(datetime.time, lambda t: t.isoformat())

    async_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    test_async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    db_module = types.ModuleType(f"{prefix}_database")

    async def get_session():
        async with test_async_session() as session:
            yield session

    db_module.get_session = get_session
    db_module.engine = async_engine
    db_module.async_session = test_async_session

    return db_module, async_engine, orm_module


def load_app(src_path: Path):
    """Dynamically import the FastAPI app from a generated project.

    Uses unique module names to avoid conflicts between different
    generated projects in the same test session.

    For database-enabled projects, replaces the async PostgreSQL session
    with an in-memory SQLite session so tests run without a real database.
    """
    import asyncio

    # Generate unique prefix for this import
    prefix = f"_gen_{uuid.uuid4().hex[:8]}"

    # Add src_path to sys.path so relative imports work
    sys.path.insert(0, str(src_path))

    has_database = (src_path / "database.py").exists()
    has_orm_models = (src_path / "orm_models.py").exists()

    modules_to_cleanup = []
    try:
        # If database-enabled, set up in-memory SQLite before loading modules
        if has_database and has_orm_models:
            # Load orm_models first to get the Base class
            orm_spec = importlib.util.spec_from_file_location(
                f"{prefix}_orm_models", src_path / "orm_models.py"
            )
            orm_module = importlib.util.module_from_spec(orm_spec)
            sys.modules[f"{prefix}_orm_models"] = orm_module
            sys.modules["orm_models"] = orm_module
            modules_to_cleanup.extend([f"{prefix}_orm_models", "orm_models"])
            orm_spec.loader.exec_module(orm_module)

            # Create fake database module with in-memory SQLite
            db_module, async_engine, orm_mod = _create_test_db_module(
                orm_module, prefix
            )
            sys.modules[f"{prefix}_database"] = db_module
            sys.modules["database"] = db_module
            modules_to_cleanup.extend([f"{prefix}_database", "database"])

            # Create tables using async engine
            async def _create_tables():
                async with async_engine.begin() as conn:
                    await conn.run_sync(orm_mod.Base.metadata.create_all)

            asyncio.get_event_loop().run_until_complete(_create_tables())

        # Load modules in dependency order with unique names
        module_files = [
            "orm_models",
            "database",
            "seed",
            "models",
            "path",
            "query",
            "views",
            "main",
        ]

        for module_name in module_files:
            # Skip orm_models and database if already loaded for DB projects
            if (
                has_database
                and has_orm_models
                and module_name in ("orm_models", "database")
            ):
                continue

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


@pytest.fixture(scope="session")
def items_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Items API once per test session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("items_api")

    api_input = load_input("items_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))

    src_path = tmp_path / "items-api" / "src"
    app = load_app(src_path)

    return TestClient(app)


@pytest.fixture(scope="session")
def shop_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Shop API once per test session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("shop_api")

    api_input = load_input("shop_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))

    src_path = tmp_path / "shop-api" / "src"
    app = load_app(src_path)

    return TestClient(app)
