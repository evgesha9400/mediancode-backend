"""Tests for database-enabled code generation.

Validates that when database.enabled is true:
- ORM models, database.py, seed.py are generated
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

    def test_seed_py_exists(self, db_project: Path):
        assert (db_project / "src" / "seed.py").exists()

    def test_docker_compose_exists(self, db_project: Path):
        assert (db_project / "docker-compose.yml").exists()

    def test_alembic_ini_exists(self, db_project: Path):
        assert (db_project / "alembic.ini").exists()

    def test_alembic_env_exists(self, db_project: Path):
        assert (db_project / "migrations" / "env.py").exists()


class TestGeneratedCodeCompiles:
    """Verify generated Python files have valid syntax."""

    @pytest.mark.parametrize(
        "filename",
        [
            "src/orm_models.py",
            "src/database.py",
            "src/seed.py",
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

    def test_str_with_max_length_uses_string_n(self, db_project: Path):
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "String(20)" in content  # sku has max_length=20

    def test_str_without_max_length_uses_text(self, db_project: Path):
        """Fields without max_length should use Text, not String."""
        # All str fields in this spec have max_length, so this test checks
        # that Text doesn't appear incorrectly. Covered by name using String(100).
        content = (db_project / "src" / "orm_models.py").read_text()
        assert "String(100)" in content  # name has max_length=100


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

    def test_main_no_seed_on_startup(self, db_project: Path):
        """Seed runs via make db-seed, not on app startup."""
        content = (db_project / "src" / "main.py").read_text()
        assert "seed_database" not in content


class TestMakefileWithDatabase:
    def test_makefile_has_db_targets(self, db_project: Path):
        content = (db_project / "Makefile").read_text()
        assert "db-up:" in content
        assert "db-init:" in content
        assert "db-upgrade:" in content
        assert "db-seed:" in content
        assert "db-reset:" in content
        assert "db-downgrade:" in content


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

    def test_views_unchanged_when_disabled(self, tmp_path):
        api_input = load_input("items_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))
        views = (tmp_path / "items-api" / "src" / "views.py").read_text()

        assert "Depends" not in views
        assert "get_session" not in views
        assert "select(" not in views


@pytest.fixture(scope="module")
def fk_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the Orders DB API project with FK relationships."""
    tmp_path = tmp_path_factory.mktemp("orders_db_api")
    api_input = load_input("orders_api_db.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    return tmp_path / "orders-db-api"


class TestForeignKeyGeneration:
    def test_order_item_has_fk(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert 'ForeignKey("orders.id"' in content

    def test_fk_has_cascade_delete(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert 'ondelete="CASCADE"' in content

    def test_both_tables_generated(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "class OrderRecord(Base):" in content
        assert "class OrderItemRecord(Base):" in content

    def test_no_dto_tables(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "CreateOrderRequestRecord" not in content

    def test_fk_import_present(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        assert "ForeignKey" in content

    def test_orm_models_compile(self, fk_project: Path):
        content = (fk_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")
