# tests/support/generated_app.py
"""Helpers for loading generated FastAPI projects in-process.

Migrated from the old ``tests/test_api_craft/conftest.py``.  Provides
:func:`load_input` for YAML specs and :func:`load_app` for dynamically
importing a generated project with an in-memory SQLite backend.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from api_craft.main import APIGenerator
from api_craft.models.input import InputAPI

SPECS_PATH = Path(__file__).resolve().parent.parent / "specs"


def load_input(filename: str) -> InputAPI:
    """Load and validate an API input from a YAML spec file.

    :param filename: Name of YAML file relative to ``tests/specs/``.
    :returns: Validated :class:`InputAPI` instance.
    """
    yaml_path = SPECS_PATH / filename
    with open(yaml_path, "r") as f:
        api_data = yaml.safe_load(f)
    return InputAPI.model_validate(api_data)


def _create_test_db_module(orm_module, prefix: str):
    """Create a fake ``database`` module backed by in-memory SQLite."""
    import datetime
    import sqlite3

    from pydantic import HttpUrl
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

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

    For database-enabled projects the async PostgreSQL session is
    replaced with an in-memory SQLite session so tests run without
    a real database.

    :param src_path: Path to the ``src/`` directory of a generated project.
    :returns: The FastAPI ``app`` instance.
    """
    import asyncio

    prefix = f"_gen_{uuid.uuid4().hex[:8]}"
    sys.path.insert(0, str(src_path))

    has_database = (src_path / "database.py").exists()
    has_orm_models = (src_path / "orm_models.py").exists()

    modules_to_cleanup: list[str] = []
    try:
        if has_database and has_orm_models:
            orm_spec = importlib.util.spec_from_file_location(
                f"{prefix}_orm_models", src_path / "orm_models.py"
            )
            orm_module = importlib.util.module_from_spec(orm_spec)
            sys.modules[f"{prefix}_orm_models"] = orm_module
            sys.modules["orm_models"] = orm_module
            modules_to_cleanup.extend([f"{prefix}_orm_models", "orm_models"])
            orm_spec.loader.exec_module(orm_module)

            db_module, async_engine, orm_mod = _create_test_db_module(
                orm_module, prefix
            )
            sys.modules[f"{prefix}_database"] = db_module
            sys.modules["database"] = db_module
            modules_to_cleanup.extend([f"{prefix}_database", "database"])

            async def _create_tables():
                async with async_engine.begin() as conn:
                    await conn.run_sync(orm_mod.Base.metadata.create_all)

            asyncio.get_event_loop().run_until_complete(_create_tables())

        module_files = [
            "orm_models",
            "database",
            "models",
            "path",
            "query",
            "views",
            "main",
        ]

        for module_name in module_files:
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

            sys.modules[unique_name] = module
            sys.modules[module_name] = module
            modules_to_cleanup.append(unique_name)
            modules_to_cleanup.append(module_name)

            spec.loader.exec_module(module)

        return sys.modules["main"].app
    finally:
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))
        for mod_name in modules_to_cleanup:
            sys.modules.pop(mod_name, None)


def generate_and_client(
    spec_filename: str, tmp_path: Path
) -> TestClient:
    """Generate a project from a YAML spec and return a live TestClient.

    :param spec_filename: YAML file name under ``tests/specs/``.
    :param tmp_path: Temporary directory for generated output.
    :returns: A :class:`TestClient` wired to the generated FastAPI app.
    """
    api_input = load_input(spec_filename)
    APIGenerator().generate(api_input, path=str(tmp_path))

    kebab_name = api_input.name.replace(" ", "-").lower()
    for segment in ("_", " "):
        kebab_name = kebab_name.replace(segment, "-")
    project_name = api_input.name
    from api_craft.models.types import Name

    n = Name(project_name)
    project_dir = tmp_path / n.kebab_name
    src_path = project_dir / "src"
    app = load_app(src_path)
    return TestClient(app)
