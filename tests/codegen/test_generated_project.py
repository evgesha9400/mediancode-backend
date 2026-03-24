# tests/codegen/test_generated_project.py
"""Tests that generate projects to tmp_path and inspect the generated files
statically (no TestClient).

Merges legacy tests from:
- test_db_codegen, static generation tests from test_codegen,
  ZIP __pycache__ exclusion from test_generation_unit
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest

from api_craft.main import APIGenerator
from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputDatabaseConfig,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputResolvedFieldValidator,
)
from support.generated_app import load_input

pytestmark = pytest.mark.codegen


# ---------------------------------------------------------------------------
# Database codegen (from test_db_codegen)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the Items DB API project and return its root path."""
    tmp_path = tmp_path_factory.mktemp("items_db_api")
    api_input = load_input("items_api_db.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "items-db-api"


class TestDatabaseFilesGenerated:
    def test_orm_models_exists(self, db_project: Path):
        assert (db_project / "src" / "orm_models.py").exists()

    def test_database_py_exists(self, db_project: Path):
        assert (db_project / "src" / "database.py").exists()

    def test_docker_compose_exists(self, db_project: Path):
        assert (db_project / "docker-compose.yml").exists()

    def test_alembic_ini_exists(self, db_project: Path):
        assert (db_project / "alembic.ini").exists()

    def test_alembic_env_exists(self, db_project: Path):
        assert (db_project / "migrations" / "env.py").exists()

    def test_env_file_exists(self, db_project: Path):
        assert (db_project / ".env").exists()


class TestGeneratedCodeCompiles:
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
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "CreateItemRequestRecord" not in content

    def test_str_fields_use_correct_column_type(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "String(" in content or "Text" in content


class TestEnvFileContent:
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
        content = (db_project / "src" / "main.py").read_text()
        assert "create_all" not in content


class TestMakefileWithDatabase:
    def test_makefile_has_db_targets(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "db-up:" in content
        assert "db-migrate:" in content
        assert "db-upgrade:" in content
        assert "db-reset:" in content
        assert "db-downgrade:" in content
        assert "db-down:" in content
        assert "run-stack:" in content

    def test_makefile_has_core_targets(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "install:" in content
        assert "run-local:" in content

    def test_makefile_has_cleanup_target(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "cleanup:" in content

    def test_makefile_clean_aliases_cleanup(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "clean: cleanup" in content

    def test_makefile_cleanup_uses_compose_down(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "docker compose down -v" in content

    def test_makefile_includes_env(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "-include .env" in content

    def test_makefile_has_port_defaults(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "APP_PORT ?=" in content
        assert "DB_PORT ?=" in content


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

    def test_no_autogenerate_in_cmd(self, db_project: Path):
        content = (db_project / "Dockerfile").read_text()
        assert "autogenerate" not in content


@pytest.fixture(scope="module")
def uuid_db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the UUID PK API project and return its root path."""
    tmp_path = tmp_path_factory.mktemp("items_db_uuid_api")
    api_input = load_input("items_api_db_uuid.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "items-db-uuid-api"


class TestUuidPkCodegen:
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


class TestIntPkNoUuidImport:
    def test_no_uuid_import(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "import uuid" not in content

    def test_no_uuid_default(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "uuid.uuid4" not in content


class TestInitialMigration:
    def test_migration_file_exists(self, db_project: Path):
        assert (db_project / "migrations" / "versions" / "0001_initial.py").exists()

    def test_migration_compiles(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        compile(content, "0001_initial.py", "exec")

    def test_migration_has_revision(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert 'revision: str = "0001"' in content

    def test_migration_has_no_down_revision(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "down_revision: str | None = None" in content

    def test_migration_has_create_table(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "op.create_table(" in content

    def test_migration_has_correct_table(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert '"items"' in content

    def test_migration_has_primary_key(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "sa.PrimaryKeyConstraint(" in content

    def test_migration_has_downgrade(self, db_project: Path):
        content = (
            db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "op.drop_table(" in content


class TestUuidMigration:
    def test_migration_file_exists(self, uuid_db_project: Path):
        assert (
            uuid_db_project / "migrations" / "versions" / "0001_initial.py"
        ).exists()

    def test_migration_compiles(self, uuid_db_project: Path):
        content = (
            uuid_db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        compile(content, "0001_initial.py", "exec")

    def test_migration_has_uuid_column(self, uuid_db_project: Path):
        content = (
            uuid_db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "sa.Uuid()" in content

    def test_migration_has_no_autoincrement(self, uuid_db_project: Path):
        content = (
            uuid_db_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "autoincrement" not in content


class TestDbBackwardCompatibility:
    """Ensure database.enabled=false produces identical output."""

    def test_no_database_files_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        project = tmp_path / "items-api"

        assert not (project / "src" / "orm_models.py").exists()
        assert not (project / "src" / "database.py").exists()
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

    def test_makefile_has_core_targets_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "items-api" / "Makefile").read_text()

        assert "install:" in content
        assert "run-local:" in content
        assert "cleanup:" in content
        assert "clean: cleanup" in content

    def test_makefile_has_no_db_targets_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "items-api" / "Makefile").read_text()

        assert "db-up:" not in content
        assert "db-down:" not in content
        assert "run-stack:" not in content


class TestDatabaseDependencies:
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
    @pytest.fixture(scope="class")
    def mixed_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        api_input = InputAPI(
            name="MixedApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
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
        assert "StatusResponse(" in content

    def test_database_files_exist(self, mixed_project: Path):
        assert (mixed_project / "src" / "orm_models.py").exists()
        assert (mixed_project / "src" / "database.py").exists()
        assert (mixed_project / "docker-compose.yml").exists()
        assert (mixed_project / "alembic.ini").exists()

    def test_all_python_files_compile(self, mixed_project: Path):
        for py_file in mixed_project.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")


class TestServerDefaultCodegen:
    @pytest.fixture(scope="class")
    def server_defaults_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        api_input = InputAPI(
            name="DefaultsApi",
            objects=[
                InputModel(
                    name="Event",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(
                            name="created_at",
                            type="datetime",
                            exposure="read_only",
                            default={"kind": "generated", "strategy": "now"},
                        ),
                        InputField(
                            name="updated_at",
                            type="datetime",
                            exposure="read_only",
                            default={"kind": "generated", "strategy": "now_on_update"},
                        ),
                        InputField(
                            name="status",
                            type="str",
                            exposure="read_only",
                            default={"kind": "literal", "value": "active"},
                        ),
                        InputField(name="title", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetEvents",
                    path="/events",
                    method="GET",
                    response="Event",
                    response_shape="list",
                ),
            ],
            config=InputApiConfig(
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        tmp_path = tmp_path_factory.mktemp("defaults_api")
        APIGenerator().generate(api_input, path=str(tmp_path))
        return tmp_path / "defaults-api"

    def test_orm_file_compiles(self, server_defaults_project: Path):
        content = (server_defaults_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")

    def test_now_renders_func_now_in_orm(self, server_defaults_project: Path):
        content = (server_defaults_project / "src" / "orm_models.py").read_text()
        assert "server_default=func.now()" in content

    def test_func_imported_in_orm(self, server_defaults_project: Path):
        content = (server_defaults_project / "src" / "orm_models.py").read_text()
        assert "from sqlalchemy import" in content
        assert "func" in content

    def test_now_on_update_renders_onupdate(self, server_defaults_project: Path):
        content = (server_defaults_project / "src" / "orm_models.py").read_text()
        assert "onupdate=func.now()" in content

    def test_literal_renders_server_default_string(self, server_defaults_project: Path):
        content = (server_defaults_project / "src" / "orm_models.py").read_text()
        assert "server_default=\"'active'\"" in content

    def test_migration_file_compiles(self, server_defaults_project: Path):
        content = (
            server_defaults_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        compile(content, "0001_initial.py", "exec")

    def test_now_renders_in_migration(self, server_defaults_project: Path):
        content = (
            server_defaults_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "server_default=sa.func.now()" in content

    def test_literal_renders_in_migration(self, server_defaults_project: Path):
        content = (
            server_defaults_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "server_default=\"'active'\"" in content

    def test_now_on_update_migration_has_no_onupdate(
        self, server_defaults_project: Path
    ):
        content = (
            server_defaults_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "onupdate" not in content

    def test_all_python_files_compile(self, server_defaults_project: Path):
        for py_file in server_defaults_project.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")


# ---------------------------------------------------------------------------
# Static generation tests (from test_codegen)
# ---------------------------------------------------------------------------


def test_field_validator_body_indentation(tmp_path):
    api = InputAPI(
        name="IndentTest",
        endpoints=[
            InputEndpoint(
                name="GetItems", path="/items", method="GET", response="Item"
            )
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[
                    InputField(
                        name="value",
                        type="str",
                        field_validators=[
                            InputResolvedFieldValidator(
                                function_name="trim_value",
                                mode="before",
                                function_body="    v = v.strip()\n    return v",
                            )
                        ],
                    )
                ],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "indent-test" / "src" / "models.py").read_text()

    compile(models_py, "models.py", "exec")

    for line in models_py.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("v = v.strip()") or stripped.startswith("return v"):
            indent = len(line) - len(stripped)
            assert indent >= 8, f"Insufficient indent ({indent}): {line!r}"


def test_decimal_type_generates_import(tmp_path):
    api = InputAPI(
        name="DecimalTest",
        endpoints=[
            InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="price", type="decimal.Decimal")],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "decimal-test" / "src" / "models.py").read_text()

    assert "import decimal" in models_py or "from decimal import Decimal" in models_py
    compile(models_py, "models.py", "exec")


def test_clamp_to_range_renders_values(tmp_path):
    api = InputAPI(
        name="ClampTest",
        endpoints=[
            InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[
                    InputField(
                        name="weight",
                        type="float",
                        field_validators=[
                            InputResolvedFieldValidator(
                                function_name="clamp_to_range_weight",
                                mode="before",
                                function_body="    v = max(0, min(1000, v))\n    return v",
                            )
                        ],
                    )
                ],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "clamp-test" / "src" / "models.py").read_text()
    assert "max(0, min(1000, v))" in models_py
    assert "max(, min(, v))" not in models_py


def test_list_response_shape_generates_list_type(tmp_path):
    api = InputAPI(
        name="ListTest",
        endpoints=[
            InputEndpoint(
                name="GetItems",
                path="/items",
                method="GET",
                response="Item",
                response_shape="list",
            )
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="name", type="str")],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    views_py = (tmp_path / "list-test" / "src" / "views.py").read_text()

    assert "response_model=list[Item]" in views_py
    assert "return [Item(" in views_py or "return []" in views_py


def test_delete_endpoint_without_response_object(tmp_path):
    api = InputAPI(
        name="DeleteTest",
        endpoints=[
            InputEndpoint(
                name="GetItems", path="/items", method="GET", response="Item"
            ),
            InputEndpoint(
                name="DeleteItem",
                path="/items/{item_id}",
                method="DELETE",
                path_params=[InputPathParam(name="item_id", type="str")],
            ),
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="name", type="str")],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    views_py = (tmp_path / "delete-test" / "src" / "views.py").read_text()

    assert "async def delete_item" in views_py
    assert "status_code=204" in views_py
    assert "Response" in views_py
    compile(views_py, "views.py", "exec")


def test_delete_endpoint_without_response_resolves_orm_from_pk(tmp_path):
    api = InputAPI(
        name="DeletePkTest",
        endpoints=[
            InputEndpoint(
                name="DeleteProduct",
                path="/products/{tracking_id}",
                method="DELETE",
                path_params=[InputPathParam(name="tracking_id", type="uuid")],
            ),
        ],
        objects=[
            InputModel(
                name="Product",
                fields=[
                    InputField(
                        name="tracking_id", type="uuid", pk=True, exposure="read_only"
                    ),
                    InputField(name="name", type="str"),
                ],
            )
        ],
        config=InputApiConfig(
            response_placeholders=False,
            database=InputDatabaseConfig(enabled=True),
        ),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    views_py = (tmp_path / "delete-pk-test" / "src" / "views.py").read_text()

    assert "async def delete_product" in views_py
    assert "status_code=204" in views_py
    assert "session.delete(record)" in views_py
    assert "ProductRecord" in views_py
    assert "TODO" not in views_py
    compile(views_py, "views.py", "exec")


def test_path_param_uses_field_type(tmp_path):
    api = InputAPI(
        name="PathTypeTest",
        endpoints=[
            InputEndpoint(
                name="GetItem",
                path="/items/{item_id}",
                method="GET",
                response="Item",
                path_params=[
                    InputPathParam(name="item_id", type="uuid.UUID"),
                ],
            ),
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="name", type="str")],
            )
        ],
        config=InputApiConfig(response_placeholders=False),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    path_py = (tmp_path / "path-type-test" / "src" / "path.py").read_text()

    assert "uuid.UUID" in path_py
    assert "import uuid" in path_py


# ---------------------------------------------------------------------------
# ZIP __pycache__ exclusion (from test_generation_unit)
# ---------------------------------------------------------------------------


def test_zip_excludes_pycache():
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(tmp, "test-api")
        src = os.path.join(project, "src")
        pycache = os.path.join(src, "__pycache__")
        os.makedirs(pycache)

        with open(os.path.join(src, "main.py"), "w") as f:
            f.write("# main")
        with open(os.path.join(pycache, "main.cpython-313.pyc"), "wb") as f:
            f.write(b"\x00")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, project)
                    zf.write(file_path, arc_name)

        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)
            assert any("main.py" in n for n in names)
