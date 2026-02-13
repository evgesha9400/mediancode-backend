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

# revision identifiers, used by Alembic.
revision: str = "4141ad7f2255"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create namespaces table
    op.create_table(
        "namespaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.PrimaryKeyConstraint("id"),
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
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("python_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("import_path", sa.Text(), nullable=True),
        sa.Column("parent_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["parent_type_id"], ["types.id"]),
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
        sa.Column("parameter_type", sa.Text(), nullable=False),
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
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("server_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_apis_namespace_id"), "apis", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_apis_user_id"), "apis", ["user_id"], unique=False)

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
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["types.id"]),
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
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_objects_namespace_id"), "objects", ["namespace_id"], unique=False
    )
    op.create_index(op.f("ix_objects_user_id"), "objects", ["user_id"], unique=False)

    # Create field_validators table (custom validator function definitions)
    op.create_table(
        "field_validators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("function_name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("function_body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_field_validators_namespace_id"),
        "field_validators",
        ["namespace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_field_validators_user_id"),
        "field_validators",
        ["user_id"],
        unique=False,
    )

    # Create field_validator_associations table
    op.create_table(
        "field_validator_associations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("validator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["validator_id"], ["field_validators.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_field_validator_associations_validator_id"),
        "field_validator_associations",
        ["validator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_field_validator_associations_field_id"),
        "field_validator_associations",
        ["field_id"],
        unique=False,
    )

    # Create object_field_associations table
    op.create_table(
        "object_field_associations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_object_field_associations_field_id"),
        "object_field_associations",
        ["field_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_object_field_associations_object_id"),
        "object_field_associations",
        ["object_id"],
        unique=False,
    )

    # Create model_validators table (custom model-level validator function definitions)
    op.create_table(
        "model_validators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("namespace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("function_name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("function_body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_validators_namespace_id"),
        "model_validators",
        ["namespace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_validators_user_id"),
        "model_validators",
        ["user_id"],
        unique=False,
    )

    # Create object_model_validator_associations table
    op.create_table(
        "object_model_validator_associations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("validator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["validator_id"], ["model_validators.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_object_model_validator_associations_validator_id"),
        "object_model_validator_associations",
        ["validator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_object_model_validator_associations_object_id"),
        "object_model_validator_associations",
        ["object_id"],
        unique=False,
    )

    # Create field_constraint_values table
    op.create_table(
        "field_constraint_values",
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
        op.f("ix_field_constraint_values_constraint_id"),
        "field_constraint_values",
        ["constraint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_field_constraint_values_field_id"),
        "field_constraint_values",
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
        sa.Column(
            "method",
            sa.Enum("GET", "POST", "PUT", "PATCH", "DELETE", name="http_method"),
            nullable=False,
        ),
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
        sa.Column(
            "request_body_object_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "response_body_object_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("use_envelope", sa.Boolean(), nullable=False),
        sa.Column(
            "response_shape",
            sa.Enum("object", "list", name="response_shape"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["query_params_object_id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["request_body_object_id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["response_body_object_id"], ["objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_endpoints_api_id"), "api_endpoints", ["api_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_api_endpoints_api_id"), table_name="api_endpoints")
    op.drop_table("api_endpoints")
    op.drop_index(
        op.f("ix_field_constraint_values_field_id"),
        table_name="field_constraint_values",
    )
    op.drop_index(
        op.f("ix_field_constraint_values_constraint_id"),
        table_name="field_constraint_values",
    )
    op.drop_table("field_constraint_values")
    op.drop_index(
        op.f("ix_object_model_validator_associations_object_id"),
        table_name="object_model_validator_associations",
    )
    op.drop_index(
        op.f("ix_object_model_validator_associations_validator_id"),
        table_name="object_model_validator_associations",
    )
    op.drop_table("object_model_validator_associations")
    op.drop_index(op.f("ix_model_validators_user_id"), table_name="model_validators")
    op.drop_index(
        op.f("ix_model_validators_namespace_id"), table_name="model_validators"
    )
    op.drop_table("model_validators")
    op.drop_index(
        op.f("ix_object_field_associations_object_id"),
        table_name="object_field_associations",
    )
    op.drop_index(
        op.f("ix_object_field_associations_field_id"),
        table_name="object_field_associations",
    )
    op.drop_table("object_field_associations")
    op.drop_index(
        op.f("ix_field_validator_associations_field_id"),
        table_name="field_validator_associations",
    )
    op.drop_index(
        op.f("ix_field_validator_associations_validator_id"),
        table_name="field_validator_associations",
    )
    op.drop_table("field_validator_associations")
    op.drop_index(op.f("ix_field_validators_user_id"), table_name="field_validators")
    op.drop_index(
        op.f("ix_field_validators_namespace_id"), table_name="field_validators"
    )
    op.drop_table("field_validators")
    op.drop_index(op.f("ix_objects_user_id"), table_name="objects")
    op.drop_index(op.f("ix_objects_namespace_id"), table_name="objects")
    op.drop_table("objects")
    op.drop_index(op.f("ix_fields_type_id"), table_name="fields")
    op.drop_index(op.f("ix_fields_user_id"), table_name="fields")
    op.drop_index(op.f("ix_fields_namespace_id"), table_name="fields")
    op.drop_table("fields")
    op.drop_index(op.f("ix_apis_user_id"), table_name="apis")
    op.drop_index(op.f("ix_apis_namespace_id"), table_name="apis")
    op.drop_table("apis")
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

    # Drop enums
    op.execute("DROP TYPE IF EXISTS http_method")
    op.execute("DROP TYPE IF EXISTS response_shape")

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
