"""Initial schema with all 12 tables.

Revision ID: 001
Revises:
Create Date: 2025-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Users (synced from Clerk)
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), nullable=False, comment="Clerk user ID"),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("profile_image_url", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_tier", sa.Text(), nullable=False, server_default="free"),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # 2. Namespaces
    op.create_table(
        "namespaces",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True, comment="Null for global namespace"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_namespaces_user_id", "namespaces", ["user_id"])

    # 3. Types
    op.create_table(
        "types",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
            comment="inline (built-in) or custom",
        ),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            comment="primitive, abstract, or collection",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.CheckConstraint("category IN ('inline', 'custom')", name="ck_types_category"),
        sa.CheckConstraint(
            "type IN ('primitive', 'abstract', 'collection')", name="ck_types_type"
        ),
    )
    op.create_index("ix_types_namespace_id", "types", ["namespace_id"])
    op.create_unique_constraint("uq_types_namespace_name", "types", ["namespace_id", "name"])

    # 4. Validators
    op.create_table(
        "validators",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            comment="Applies to: string, numeric, or collection",
        ),
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
            comment="inline (built-in) or custom",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parameter_type",
            sa.Text(),
            nullable=True,
            comment="Expected parameter type (int, string, regex, etc.)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "type IN ('string', 'numeric', 'collection')", name="ck_validators_type"
        ),
        sa.CheckConstraint(
            "category IN ('inline', 'custom')", name="ck_validators_category"
        ),
    )
    op.create_index("ix_validators_namespace_id", "validators", ["namespace_id"])
    op.create_unique_constraint(
        "uq_validators_namespace_name", "validators", ["namespace_id", "name"]
    )

    # 5. Fields
    op.create_table(
        "fields",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type_id", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["type_id"], ["types.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_fields_namespace_id", "fields", ["namespace_id"])
    op.create_index("ix_fields_user_id", "fields", ["user_id"])
    op.create_index("ix_fields_type_id", "fields", ["type_id"])
    op.create_unique_constraint(
        "uq_fields_namespace_name", "fields", ["namespace_id", "name"]
    )

    # 6. Field Validators (junction table)
    op.create_table(
        "field_validators",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("field_id", sa.Text(), nullable=False),
        sa.Column("validator_id", sa.Text(), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Validator parameters",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["validator_id"], ["validators.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_field_validators_field_id", "field_validators", ["field_id"])
    op.create_index(
        "ix_field_validators_validator_id", "field_validators", ["validator_id"]
    )
    op.create_unique_constraint(
        "uq_field_validators_field_validator",
        "field_validators",
        ["field_id", "validator_id"],
    )

    # 7. Objects
    op.create_table(
        "objects",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_objects_namespace_id", "objects", ["namespace_id"])
    op.create_index("ix_objects_user_id", "objects", ["user_id"])
    op.create_unique_constraint(
        "uq_objects_namespace_name", "objects", ["namespace_id", "name"]
    )

    # 8. Object Fields (junction table)
    op.create_table(
        "object_fields",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("object_id", sa.Text(), nullable=False),
        sa.Column("field_id", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_object_fields_object_id", "object_fields", ["object_id"])
    op.create_index("ix_object_fields_field_id", "object_fields", ["field_id"])
    op.create_unique_constraint(
        "uq_object_fields_object_field", "object_fields", ["object_id", "field_id"]
    )

    # 9. APIs
    op.create_table(
        "apis",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("server_url", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_apis_namespace_id", "apis", ["namespace_id"])
    op.create_index("ix_apis_user_id", "apis", ["user_id"])

    # 10. Tags
    op.create_table(
        "tags",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("api_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tags_namespace_id", "tags", ["namespace_id"])
    op.create_index("ix_tags_api_id", "tags", ["api_id"])
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    op.create_unique_constraint("uq_tags_api_name", "tags", ["api_id", "name"])

    # 11. Endpoints
    op.create_table(
        "endpoints",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("namespace_id", sa.Text(), nullable=False),
        sa.Column("api_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tag_id", sa.Text(), nullable=True),
        sa.Column("query_params_object_id", sa.Text(), nullable=True),
        sa.Column("request_body_object_id", sa.Text(), nullable=True),
        sa.Column("response_body_object_id", sa.Text(), nullable=True),
        sa.Column("response_shape", sa.Text(), nullable=False, server_default="object"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["query_params_object_id"], ["objects.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["request_body_object_id"], ["objects.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["response_body_object_id"], ["objects.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name="ck_endpoints_method",
        ),
        sa.CheckConstraint(
            "response_shape IN ('object', 'list')", name="ck_endpoints_response_shape"
        ),
    )
    op.create_index("ix_endpoints_namespace_id", "endpoints", ["namespace_id"])
    op.create_index("ix_endpoints_api_id", "endpoints", ["api_id"])
    op.create_index("ix_endpoints_user_id", "endpoints", ["user_id"])
    op.create_index("ix_endpoints_tag_id", "endpoints", ["tag_id"])
    op.create_unique_constraint(
        "uq_endpoints_api_method_path", "endpoints", ["api_id", "method", "path"]
    )

    # 12. Endpoint Path Params
    op.create_table(
        "endpoint_path_params",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("endpoint_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type_id", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["type_id"], ["types.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_endpoint_path_params_endpoint_id", "endpoint_path_params", ["endpoint_id"]
    )
    op.create_unique_constraint(
        "uq_endpoint_path_params_endpoint_name",
        "endpoint_path_params",
        ["endpoint_id", "name"],
    )


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table("endpoint_path_params")
    op.drop_table("endpoints")
    op.drop_table("tags")
    op.drop_table("apis")
    op.drop_table("object_fields")
    op.drop_table("objects")
    op.drop_table("field_validators")
    op.drop_table("fields")
    op.drop_table("validators")
    op.drop_table("types")
    op.drop_table("namespaces")
    op.drop_table("users")
