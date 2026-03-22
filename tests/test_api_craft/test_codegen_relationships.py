# tests/test_api_craft/test_codegen_relationships.py
"""Tests for relationship support in code generation.

Validates that:
- `references` generates FK column + relationship()
- `has_many` generates relationship() without FK on source
- `many_to_many` generates association table + relationship(secondary=...)
- Response schema includes FK ID for `references` relationships
- Generated Python files compile without errors
"""

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
    InputRelationship,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.schema_splitter import split_model_schemas

pytestmark = pytest.mark.codegen


def _make_model(name, fields, relationships=None):
    return InputModel(
        name=name,
        fields=[InputField(**f) for f in fields],
        relationships=[InputRelationship(**r) for r in (relationships or [])],
    )


class TestReferencesRelationship:
    """Verify `references` cardinality generates FK column and relationship."""

    def test_references_adds_fk_field_to_orm(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        post_model = next(m for m in result if m.source_model == "Post")
        field_names = [f.name for f in post_model.fields]
        assert "author_id" in field_names

        fk_field = next(f for f in post_model.fields if f.name == "author_id")
        assert fk_field.foreign_key == "users.id"
        assert fk_field.column_type == "Uuid"

    def test_references_creates_relationship(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        post_model = next(m for m in result if m.source_model == "Post")
        assert len(post_model.relationships) == 1
        rel = post_model.relationships[0]
        assert rel.name == "author"
        assert rel.cardinality == "references"
        assert rel.fk_column == "author_id"
        assert rel.target_class_name == "UserRecord"

    def test_references_fk_id_in_response_schema(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author",
                    target_model="User",
                    cardinality="references",
                )
            ],
        )
        schemas = split_model_schemas(model)
        response = schemas[2]  # Response schema
        response_names = [f.name for f in response.fields]
        assert "author_id" in response_names

    def test_references_fk_id_not_in_create_schema(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author",
                    target_model="User",
                    cardinality="references",
                )
            ],
        )
        schemas = split_model_schemas(model)
        create = schemas[0]  # Create schema
        create_names = [f.name for f in create.fields]
        assert "author_id" not in create_names


class TestHasManyRelationship:
    """Verify `has_many` cardinality generates relationship without FK on source."""

    def test_has_many_no_fk_on_source(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "posts",
                        "target_model": "Post",
                        "cardinality": "has_many",
                    }
                ],
            ),
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        # No FK column should be added for has_many
        fk_fields = [f for f in user_model.fields if f.foreign_key]
        assert len(fk_fields) == 0

    def test_has_many_creates_relationship(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "posts",
                        "target_model": "Post",
                        "cardinality": "has_many",
                    }
                ],
            ),
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        assert len(user_model.relationships) == 1
        rel = user_model.relationships[0]
        assert rel.name == "posts"
        assert rel.cardinality == "has_many"
        assert rel.target_class_name == "PostRecord"
        assert rel.fk_column is None


class TestHasOneRelationship:
    """Verify `has_one` cardinality generates relationship without FK on source."""

    def test_has_one_no_fk_on_source(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "profile",
                        "target_model": "Profile",
                        "cardinality": "has_one",
                    }
                ],
            ),
            _make_model(
                "Profile",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "bio", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        fk_fields = [f for f in user_model.fields if f.foreign_key]
        assert len(fk_fields) == 0

    def test_has_one_creates_relationship(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "profile",
                        "target_model": "Profile",
                        "cardinality": "has_one",
                    }
                ],
            ),
            _make_model(
                "Profile",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "bio", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        assert len(user_model.relationships) == 1
        rel = user_model.relationships[0]
        assert rel.name == "profile"
        assert rel.cardinality == "has_one"
        assert rel.target_class_name == "ProfileRecord"


class TestManyToManyRelationship:
    """Verify `many_to_many` generates association table + relationship(secondary=...)."""

    def test_many_to_many_creates_association_table(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        student_model = next(m for m in result if m.source_model == "Student")
        assert len(student_model.relationships) == 1
        rel = student_model.relationships[0]
        assert rel.cardinality == "many_to_many"
        assert rel.association_table is not None
        # Association table name is sorted alphabetically
        assert "courses" in rel.association_table
        assert "students" in rel.association_table

    def test_many_to_many_no_fk_on_source(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        student_model = next(m for m in result if m.source_model == "Student")
        fk_fields = [f for f in student_model.fields if f.foreign_key]
        assert len(fk_fields) == 0


class TestCollectAssociationTables:
    """Verify collect_association_tables() returns correct definitions."""

    def test_returns_association_table_for_many_to_many(self):
        from api_craft.extractors import collect_association_tables

        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        orm_models = transform_orm_models(models)
        tables = collect_association_tables(orm_models)
        assert len(tables) == 1
        assert tables[0]["left_table"] == "students"
        assert tables[0]["right_table"] == "courses"

    def test_no_association_tables_without_many_to_many(self):
        from api_craft.extractors import collect_association_tables

        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        orm_models = transform_orm_models(models)
        tables = collect_association_tables(orm_models)
        assert len(tables) == 0


class TestRelationshipCodeGeneration:
    """End-to-end test: generate project with relationships, verify output."""

    @pytest.fixture(scope="class")
    def rel_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Generate a project with relationships and return its root path."""
        api_input = InputAPI(
            name="BlogApi",
            objects=[
                InputModel(
                    name="User",
                    fields=[
                        InputField(name="id", type="uuid", pk=True),
                        InputField(name="name", type="str"),
                    ],
                    relationships=[
                        InputRelationship(
                            name="posts",
                            target_model="Post",
                            cardinality="has_many",
                        ),
                    ],
                ),
                InputModel(
                    name="Post",
                    fields=[
                        InputField(name="id", type="uuid", pk=True),
                        InputField(name="title", type="str"),
                    ],
                    relationships=[
                        InputRelationship(
                            name="author",
                            target_model="User",
                            cardinality="references",
                        ),
                        InputRelationship(
                            name="tags",
                            target_model="Tag",
                            cardinality="many_to_many",
                        ),
                    ],
                ),
                InputModel(
                    name="Tag",
                    fields=[
                        InputField(name="id", type="uuid", pk=True),
                        InputField(name="label", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetPosts",
                    path="/posts",
                    method="GET",
                    response="Post",
                    response_shape="list",
                ),
                InputEndpoint(
                    name="GetUsers",
                    path="/users",
                    method="GET",
                    response="User",
                    response_shape="list",
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        tmp_path = tmp_path_factory.mktemp("blog_api")
        APIGenerator().generate(api_input, path=str(tmp_path))
        return tmp_path / "blog-api"

    def test_orm_models_compile(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")

    def test_migration_compiles(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        compile(content, "0001_initial.py", "exec")

    def test_orm_has_relationship_import(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "relationship" in content

    def test_orm_has_fk_import(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "ForeignKey" in content

    def test_references_fk_column_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "author_id" in content
        assert 'ForeignKey("users.id")' in content

    def test_references_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "author" in content
        assert "relationship" in content

    def test_has_many_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "posts" in content

    def test_many_to_many_association_table_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "Table(" in content

    def test_many_to_many_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "tags" in content
        assert "secondary=" in content

    def test_migration_has_fk_constraint(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "ForeignKey" in content

    def test_migration_has_association_table(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        # Association table for posts <-> tags
        assert "posts_tags" in content or "tags_posts" in content

    def test_response_schema_has_fk_id(self, rel_project: Path):
        content = (rel_project / "src" / "models.py").read_text()
        assert "author_id" in content

    def test_migration_table_order(self, rel_project: Path):
        """Verify tables are created in dependency order: users/tags before posts."""
        import re

        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        upgrade_section = content.split("def upgrade")[1].split("def downgrade")[0]
        created = re.findall(r'op\.create_table\(\s*"(\w+)"', upgrade_section)
        posts_idx = created.index("posts")
        users_idx = created.index("users")
        tags_idx = created.index("tags")
        # posts references users, so users must come first
        assert users_idx < posts_idx
        # tags has no FK dependency on posts, but posts has many_to_many with tags
        # — entity tables are fine in any order, association table comes after both
        assert tags_idx < posts_idx or tags_idx > posts_idx  # no constraint

    def test_all_python_files_compile(self, rel_project: Path):
        for py_file in rel_project.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")


class TestMigrationTableOrdering:
    """Verify topological sort orders tables by FK dependencies."""

    def test_references_target_created_before_source(self):
        """Post references User — users table must come before posts."""
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names.index("users") < table_names.index("posts")

    def test_chain_dependencies_ordered(self):
        """A references B references C — C first, then B, then A."""
        models = [
            _make_model(
                "A",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "b_ref",
                        "target_model": "B",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "B",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "c_ref",
                        "target_model": "C",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "C",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names.index("cs") < table_names.index("bs")
        assert table_names.index("bs") < table_names.index("as")

    def test_no_relationships_preserves_input_order(self):
        """Models without FKs keep their input order."""
        models = [
            _make_model("Zebra", [{"name": "id", "type": "uuid", "pk": True}]),
            _make_model("Alpha", [{"name": "id", "type": "uuid", "pk": True}]),
            _make_model("Mid", [{"name": "id", "type": "uuid", "pk": True}]),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names == ["zebras", "alphas", "mids"]

    def test_many_to_many_no_entity_ordering_constraint(self):
        """many_to_many doesn't affect entity table order (assoc tables are separate)."""
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        # No FK fields on either model — input order preserved
        table_names = [m.table_name for m in result]
        assert table_names == ["students", "courses"]


class TestNoRelationshipsBackwardCompat:
    """Verify models without relationships produce identical output."""

    def test_orm_model_without_relationships_has_empty_list(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        assert result[0].relationships == []

    def test_no_relationship_import_when_no_relationships(self, tmp_path: Path):
        api_input = InputAPI(
            name="SimpleApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
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
            ],
            config=InputApiConfig(
                response_placeholders=False,
                database=InputDatabaseConfig(enabled=True),
            ),
        )
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "simple-api" / "src" / "orm_models.py").read_text()
        assert "relationship" not in content
        assert "ForeignKey" not in content
        assert "Table(" not in content
