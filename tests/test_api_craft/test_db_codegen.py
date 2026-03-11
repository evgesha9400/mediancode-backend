"""Tests for database-enabled code generation.

Validates that when database.enabled is true:
- ORM models, database.py are generated
- Docker Compose, Alembic config are generated
- Generated Python files compile without errors
- views.py uses DB session injection
- main.py has lifespan with DB init
- Makefile has db-* targets
"""

from pathlib import Path

import pytest

from api_craft.main import APIGenerator
from .conftest import load_input

pytestmark = pytest.mark.codegen


@pytest.fixture(scope="module")
def db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the Items DB API project and return its root path."""
    tmp_path = tmp_path_factory.mktemp("items_db_api")
    api_input = load_input("items_api_db.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "items-db-api"


class TestDatabaseFilesGenerated:
    """Verify all expected database files are created."""

    def test_orm_models_exists(self, db_project: Path):
        assert (db_project / "src" / "orm_models.py").exists()

    def test_database_py_exists(self, db_project: Path):
        assert (db_project / "src" / "database.py").exists()

    def test_no_seed_py(self, db_project: Path):
        """seed.py should NOT be generated."""
        assert not (db_project / "src" / "seed.py").exists()

    def test_docker_compose_exists(self, db_project: Path):
        assert (db_project / "docker-compose.yml").exists()

    def test_alembic_ini_exists(self, db_project: Path):
        assert (db_project / "alembic.ini").exists()

    def test_alembic_env_exists(self, db_project: Path):
        assert (db_project / "migrations" / "env.py").exists()

    def test_env_file_exists(self, db_project: Path):
        assert (db_project / ".env").exists()


class TestGeneratedCodeCompiles:
    """Verify generated Python files have valid syntax."""

    @pytest.mark.parametrize(
        "filename",
        [
            "src/orm_models.py",
            "src/database.py",
            "src/models.py",
            "src/views.py",
            "src/main.py",
        ],
    )
    def test_file_compiles(self, db_project: Path, filename: str):
        content = (db_project / filename).read_text()
        compile(content, filename, "exec")


class TestOrmModelsContent:
    """Verify ORM models are correctly generated."""

    def test_contains_base_class(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "class Base(DeclarativeBase):" in content

    def test_contains_item_record(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "class ItemRecord(Base):" in content

    def test_table_name_is_items(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert '__tablename__ = "items"' in content

    def test_pk_field_generated(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "primary_key=True" in content

    def test_no_create_request_in_orm(self, db_project: Path):
        """CreateItemRequest (no pk) should NOT be an ORM model."""
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "CreateItemRequestRecord" not in content

    def test_str_fields_use_correct_column_type(self, db_project: Path):
        """String fields with max_length use String(N), without use Text."""
        content = (db_project / "src" / "orm_models.py").read_text()
        # Item has str fields with max_length validators, so String(N) should be present
        assert "String(" in content or "Text" in content


class TestEnvFileContent:
    """Verify .env file is correctly generated."""

    def test_env_has_db_port(self, db_project: Path):
        content = (db_project / ".env").read_text()
        assert "DB_PORT=5433" in content

    def test_env_has_app_port(self, db_project: Path):
        content = (db_project / ".env").read_text()
        assert "APP_PORT=8001" in content


class TestDatabasePyContent:
    def test_contains_database_url(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "DATABASE_URL" in content

    def test_contains_async_engine(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "create_async_engine" in content

    def test_contains_get_session(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "async def get_session" in content

    def test_default_url_uses_api_name(self, db_project: Path):
        content = (db_project / "src" / "database.py").read_text()
        assert "items_db_api" in content


class TestViewsWithDatabase:
    def test_views_import_depends(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "Depends" in content

    def test_views_import_get_session(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "get_session" in content

    def test_views_import_orm_model(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "ItemRecord" in content

    def test_views_use_session_param(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "AsyncSession" in content
        assert "Depends(get_session)" in content

    def test_views_have_db_queries(self, db_project: Path):
        content = (db_project / "src" / "views.py").read_text()
        assert "select(" in content
        assert "session.execute" in content


class TestMainWithDatabase:
    def test_main_has_lifespan(self, db_project: Path):
        content = (db_project / "src" / "main.py").read_text()
        assert "lifespan" in content

    def test_main_imports_database(self, db_project: Path):
        content = (db_project / "src" / "main.py").read_text()
        assert "from database import" in content

    def test_main_no_create_all(self, db_project: Path):
        """Alembic is sole schema manager -- no create_all in app startup."""
        content = (db_project / "src" / "main.py").read_text()
        assert "create_all" not in content


class TestMakefileWithDatabase:
    def test_makefile_has_db_targets(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "db-up:" in content
        assert "db-init:" in content
        assert "db-upgrade:" in content
        assert "db-reset:" in content
        assert "db-downgrade:" in content

    def test_makefile_includes_env(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "-include .env" in content

    def test_makefile_has_port_defaults(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "APP_PORT ?=" in content
        assert "DB_PORT ?=" in content


class TestEnvFileContent:
    def test_env_has_db_port(self, db_project: Path):
        content = (db_project / ".env").read_text()
        assert "DB_PORT=5433" in content

    def test_env_has_app_port(self, db_project: Path):
        content = (db_project / ".env").read_text()
        assert "APP_PORT=8001" in content


class TestDockerComposeContent:
    def test_has_postgres_service(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "postgres:18" in content

    def test_has_api_service(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "api:" in content

    def test_has_database_url(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "DATABASE_URL" in content

    def test_db_name_matches_api(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "items_db_api" in content

    def test_db_port_uses_env_var(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "${DB_PORT:-5433}" in content

    def test_app_port_uses_env_var(self, db_project: Path):
        content = (db_project / "docker-compose.yml").read_text()
        assert "${APP_PORT:-8001}" in content


class TestDockerfileWithDatabase:
    def test_copies_migrations(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "migrations" in content

    def test_copies_alembic_ini(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "alembic.ini" in content

    def test_runs_alembic_upgrade(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "alembic upgrade head" in content


@pytest.fixture(scope="module")
def uuid_db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the UUID PK API project and return its root path."""
    tmp_path = tmp_path_factory.mktemp("items_db_uuid_api")
    api_input = load_input("items_api_db_uuid.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "items-db-uuid-api"


class TestUuidPkCodegen:
    """Verify UUID PK generates import uuid and default=uuid.uuid4."""

    def test_orm_models_import_uuid(self, uuid_db_project: Path):
        content = (uuid_db_project / "src" / "orm_models.py").read_text()
        assert "import uuid" in content

    def test_uuid_pk_has_default(self, uuid_db_project: Path):
        content = (uuid_db_project / "src" / "orm_models.py").read_text()
        assert "default=uuid.uuid4" in content

    def test_uuid_pk_has_primary_key(self, uuid_db_project: Path):
        content = (uuid_db_project / "src" / "orm_models.py").read_text()
        assert "primary_key=True" in content

    def test_uuid_pk_no_autoincrement(self, uuid_db_project: Path):
        content = (uuid_db_project / "src" / "orm_models.py").read_text()
        assert "autoincrement" not in content

    def test_orm_file_compiles(self, uuid_db_project: Path):
        content = (uuid_db_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")

    def test_no_seed_file(self, uuid_db_project: Path):
        """seed.py should NOT be generated."""
        assert not (uuid_db_project / "src" / "seed.py").exists()


class TestIntPkNoUuidImport:
    """Verify int PK does NOT generate import uuid."""

    def test_no_uuid_import(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "import uuid" not in content

    def test_no_uuid_default(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "uuid.uuid4" not in content


class TestBackwardCompatibility:
    """Ensure database.enabled=false produces identical output."""

    def test_no_database_files_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        project = tmp_path / "items-api"

        assert not (project / "src" / "orm_models.py").exists()
        assert not (project / "src" / "database.py").exists()
        assert not (project / "src" / "seed.py").exists()
        assert not (project / "docker-compose.yml").exists()
        assert not (project / "alembic.ini").exists()
        assert not (project / "migrations").exists()
        assert not (project / ".env").exists()

    def test_views_unchanged_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        views = (tmp_path / "items-api" / "src" / "views.py").read_text()

        assert "Depends" not in views
        assert "get_session" not in views
        assert "select(" not in views


class TestDatabaseDependencies:
    """Verify database dependencies are included in pyproject.toml."""

    def test_sqlalchemy_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "sqlalchemy" in content

    def test_asyncpg_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "asyncpg" in content

    def test_alembic_in_dependencies(self, db_project: Path):
        content = (db_project / "pyproject.toml").read_text()
        assert "alembic" in content

    def test_no_db_deps_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "items-api" / "pyproject.toml").read_text()
        assert "sqlalchemy" not in content
        assert "asyncpg" not in content
        assert "alembic" not in content


class TestMixedMode:
    """Verify mixed mode: DB-backed endpoints coexist with placeholder endpoints."""

    @pytest.fixture(scope="class")
    def mixed_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Generate an API with both PK and non-PK objects, placeholders enabled."""
        from api_craft.models.input import (
            InputAPI,
            InputApiConfig,
            InputDatabaseConfig,
            InputEndpoint,
            InputField,
            InputModel,
        )

        api_input = InputAPI(
            name="MixedApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
                InputModel(
                    name="StatusResponse",
                    fields=[
                        InputField(name="status", type="str"),
                        InputField(name="version", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="Item",
                    response_shape="list",
                ),
                InputEndpoint(
                    name="GetStatus",
                    path="/status",
                    method="GET",
                    response="StatusResponse",
                ),
            ],
            config=InputApiConfig(
                response_placeholders=True,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        tmp_path = tmp_path_factory.mktemp("mixed_api")
        APIGenerator().generate(api_input, path=str(tmp_path))
        return tmp_path / "mixed-api"

    def test_orm_model_exists_for_pk_object(self, mixed_project: Path):
        content = (mixed_project / "src" / "orm_models.py").read_text()
        assert "class ItemRecord(Base):" in content

    def test_no_orm_model_for_non_pk_object(self, mixed_project: Path):
        content = (mixed_project / "src" / "orm_models.py").read_text()
        assert "StatusResponseRecord" not in content

    def test_db_backed_endpoint_uses_session(self, mixed_project: Path):
        content = (mixed_project / "src" / "views.py").read_text()
        assert "select(" in content
        assert "session.execute" in content

    def test_non_pk_endpoint_uses_placeholders(self, mixed_project: Path):
        content = (mixed_project / "src" / "views.py").read_text()
        # StatusResponse endpoint should have placeholder values
        assert "StatusResponse(" in content

    def test_no_seed_file(self, mixed_project: Path):
        assert not (mixed_project / "src" / "seed.py").exists()

    def test_database_files_exist(self, mixed_project: Path):
        assert (mixed_project / "src" / "orm_models.py").exists()
        assert (mixed_project / "src" / "database.py").exists()
        assert (mixed_project / "docker-compose.yml").exists()
        assert (mixed_project / "alembic.ini").exists()

    def test_all_python_files_compile(self, mixed_project: Path):
        for py_file in mixed_project.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")
