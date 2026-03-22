# src/api/migrations/versions/4141ad7f2255_initial_schema.py
"""Initial schema (structure only, no data)

Revision ID: 4141ad7f2255
Revises:
Create Date: 2026-02-05 00:21:53.575168
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from api_craft.models.enums import (
    Cardinality,
    Container,
    HttpMethod,
    ResponseShape,
    ValidatorMode,
    check_constraint_sql,
)

# revision identifiers, used by Alembic.
revision: str = "4141ad7f2255"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("clerk_id", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_clerk_id"), "users", ["clerk_id"], unique=True)

    # Create namespaces table
    op.create_table(
        "namespaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_namespaces_user_name"),
    )
    op.create_index(
        op.f("ix_namespaces_user_id"), "namespaces", ["user_id"], unique=False
    )
    # Partial unique index: only one default namespace per user
    op.create_index(
        "ix_namespaces_one_default_per_user",
        "namespaces",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )

    # Create types table
    op.create_table(
        "types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("python_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("import_path", sa.Text(), nullable=True),
        sa.Column("parent_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["parent_type_id"], ["types.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_types_namespace_id"), "types", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_types_user_id"), "types", ["user_id"], unique=False)

    # Create field_constraints table
    op.create_table(
        "field_constraints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("parameter_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("docs_url", sa.Text(), nullable=True),
        sa.Column("compatible_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_field_constraints_namespace_id"),
        "field_constraints",
        ["namespace_id"],
        unique=False,
    )

    # Create field_validator_templates table (catalogue of reusable field validators)
    op.create_table(
        "field_validator_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("compatible_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column(
            "parameters", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            check_constraint_sql("mode", ValidatorMode),
            name="ck_field_validator_templates_mode",
        ),
    )

    # Create model_validator_templates table (catalogue of reusable model validators)
    op.create_table(
        "model_validator_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column(
            "parameters", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "field_mappings", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            check_constraint_sql("mode", ValidatorMode),
            name="ck_model_validator_templates_mode",
        ),
    )

    # Create apis table
    op.create_table(
        "apis",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("server_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_apis_namespace_id"), "apis", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_apis_user_id"), "apis", ["user_id"], unique=False)

    # Create generations table
    op.create_table(
        "generations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generations_user_id"), "generations", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_generations_api_id"), "generations", ["api_id"], unique=False
    )

    # Create fields table
    op.create_table(
        "fields",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("container", sa.Text(), nullable=True),
        sa.CheckConstraint(
            check_constraint_sql("container", Container), name="ck_fields_container"
        ),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["types.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fields_namespace_id"), "fields", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_fields_type_id"), "fields", ["type_id"], unique=False)
    op.create_index(op.f("ix_fields_user_id"), "fields", ["user_id"], unique=False)

    # Create objects table
    op.create_table(
        "objects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_objects_namespace_id"), "objects", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_objects_user_id"), "objects", ["user_id"], unique=False)

    # Create applied_field_validators table (links fields to field_validator_templates)
    op.create_table(
        "applied_field_validators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["field_validator_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applied_field_validators_field_id"),
        "applied_field_validators",
        ["field_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applied_field_validators_template_id"),
        "applied_field_validators",
        ["template_id"],
        unique=False,
    )

    # Create fields_on_objects table
    op.create_table(
        "fields_on_objects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "role IN ('pk', 'writable', 'write_only', 'read_only', "
            "'created_timestamp', 'updated_timestamp', 'generated_uuid')",
            name="ck_fields_on_objects_role",
        ),
    )
    op.create_index(
        op.f("ix_fields_on_objects_field_id"),
        "fields_on_objects",
        ["field_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fields_on_objects_object_id"),
        "fields_on_objects",
        ["object_id"],
        unique=False,
    )

    # Create object_relationships table
    op.create_table(
        "object_relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cardinality", sa.Text(), nullable=False),
        sa.Column(
            "is_inferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("inverse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["source_object_id"], ["objects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_object_id"], ["objects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inverse_id"], ["object_relationships.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            check_constraint_sql("cardinality", Cardinality),
            name="ck_object_relationships_cardinality",
        ),
    )
    op.create_index(
        op.f("ix_object_relationships_source_object_id"),
        "object_relationships",
        ["source_object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_object_relationships_target_object_id"),
        "object_relationships",
        ["target_object_id"],
        unique=False,
    )

    # Create applied_model_validators table (links objects to model_validator_templates)
    op.create_table(
        "applied_model_validators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column(
            "field_mappings", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["model_validator_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applied_model_validators_object_id"),
        "applied_model_validators",
        ["object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applied_model_validators_template_id"),
        "applied_model_validators",
        ["template_id"],
        unique=False,
    )

    # Create applied_constraints table
    op.create_table(
        "applied_constraints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("constraint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["constraint_id"], ["field_constraints.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applied_constraints_constraint_id"),
        "applied_constraints",
        ["constraint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applied_constraints_field_id"),
        "applied_constraints",
        ["field_id"],
        unique=False,
    )

    # Create api_endpoints table
    op.create_table(
        "api_endpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("api_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tag_name", sa.Text(), nullable=True),
        sa.Column(
            "path_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "query_params_object_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("use_envelope", sa.Boolean(), nullable=False),
        sa.Column("response_shape", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["query_params_object_id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            check_constraint_sql("method", HttpMethod),
            name="ck_api_endpoints_method",
        ),
        sa.CheckConstraint(
            check_constraint_sql("response_shape", ResponseShape),
            name="ck_api_endpoints_response_shape",
        ),
    )
    op.create_index(
        op.f("ix_api_endpoints_api_id"), "api_endpoints", ["api_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_api_endpoints_api_id"), table_name="api_endpoints")
    op.drop_table("api_endpoints")
    op.drop_index(
        op.f("ix_applied_constraints_field_id"),
        table_name="applied_constraints",
    )
    op.drop_index(
        op.f("ix_applied_constraints_constraint_id"),
        table_name="applied_constraints",
    )
    op.drop_table("applied_constraints")
    op.drop_index(
        op.f("ix_applied_model_validators_template_id"),
        table_name="applied_model_validators",
    )
    op.drop_index(
        op.f("ix_applied_model_validators_object_id"),
        table_name="applied_model_validators",
    )
    op.drop_table("applied_model_validators")
    op.drop_index(
        op.f("ix_object_relationships_target_object_id"),
        table_name="object_relationships",
    )
    op.drop_index(
        op.f("ix_object_relationships_source_object_id"),
        table_name="object_relationships",
    )
    op.drop_table("object_relationships")
    op.drop_index(
        op.f("ix_fields_on_objects_object_id"),
        table_name="fields_on_objects",
    )
    op.drop_index(
        op.f("ix_fields_on_objects_field_id"),
        table_name="fields_on_objects",
    )
    op.drop_table("fields_on_objects")
    op.drop_index(
        op.f("ix_applied_field_validators_template_id"),
        table_name="applied_field_validators",
    )
    op.drop_index(
        op.f("ix_applied_field_validators_field_id"),
        table_name="applied_field_validators",
    )
    op.drop_table("applied_field_validators")
    op.drop_index(op.f("ix_objects_user_id"), table_name="objects")
    op.drop_index(op.f("ix_objects_namespace_id"), table_name="objects")
    op.drop_table("objects")
    op.drop_index(op.f("ix_fields_type_id"), table_name="fields")
    op.drop_index(op.f("ix_fields_user_id"), table_name="fields")
    op.drop_index(op.f("ix_fields_namespace_id"), table_name="fields")
    op.drop_table("fields")
    op.drop_index(op.f("ix_generations_api_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_user_id"), table_name="generations")
    op.drop_table("generations")
    op.drop_index(op.f("ix_apis_user_id"), table_name="apis")
    op.drop_index(op.f("ix_apis_namespace_id"), table_name="apis")
    op.drop_table("apis")
    op.drop_table("model_validator_templates")
    op.drop_table("field_validator_templates")
    op.drop_index(
        op.f("ix_field_constraints_namespace_id"), table_name="field_constraints"
    )
    op.drop_table("field_constraints")
    op.drop_index(op.f("ix_types_user_id"), table_name="types")
    op.drop_index(op.f("ix_types_namespace_id"), table_name="types")
    op.drop_table("types")
    op.drop_index("ix_namespaces_one_default_per_user", table_name="namespaces")
    op.drop_index(op.f("ix_namespaces_user_id"), table_name="namespaces")
    op.drop_table("namespaces")
    op.drop_index(op.f("ix_users_clerk_id"), table_name="users")
    op.drop_table("users")

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
