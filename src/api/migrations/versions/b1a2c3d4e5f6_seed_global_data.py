"""Seed global namespace, types, and validators

Revision ID: b1a2c3d4e5f6
Revises: 4141ad7f2255
Create Date: 2026-02-09 12:00:00.000000
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: str | None = "4141ad7f2255"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed UUIDs for seed data
GLOBAL_NAMESPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
TYPE_STR_ID = UUID("00000000-0000-0000-0001-000000000001")
TYPE_INT_ID = UUID("00000000-0000-0000-0001-000000000002")
TYPE_FLOAT_ID = UUID("00000000-0000-0000-0001-000000000003")
TYPE_BOOL_ID = UUID("00000000-0000-0000-0001-000000000004")
TYPE_DATETIME_ID = UUID("00000000-0000-0000-0001-000000000005")
TYPE_UUID_ID = UUID("00000000-0000-0000-0001-000000000006")

# Seed data for types
TYPES_DATA = [
    {
        "id": TYPE_STR_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "str",
        "python_type": "str",
        "description": "String type for text data",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_INT_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "int",
        "python_type": "int",
        "description": "Integer type for whole numbers",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_FLOAT_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "float",
        "python_type": "float",
        "description": "Floating point type for decimal numbers",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_BOOL_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "bool",
        "python_type": "bool",
        "description": "Boolean type for true/false values",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_DATETIME_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "datetime",
        "python_type": "datetime.datetime",
        "description": "Date and time type",
        "import_path": "from datetime import datetime",
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_UUID_ID,
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "uuid",
        "python_type": "uuid.UUID",
        "description": "Universally unique identifier",
        "import_path": "from uuid import UUID",
        "user_id": None,
        "parent_type_id": None,
    },
]

# Seed data for validators (only standard Pydantic Field constraints)
VALIDATORS_DATA = [
    # String validators
    {
        "id": UUID("00000000-0000-0000-0002-000000000001"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "max_length",
        "type": "string",
        "description": "Validates that string length does not exceed maximum",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(max_length=255)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000002"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "min_length",
        "type": "string",
        "description": "Validates that string length is at least minimum",
        "category": "inline",
        "parameter_type": "int",
        "example_usage": "Field(min_length=1)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000003"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "pattern",
        "type": "string",
        "description": "Validates string matches a regular expression pattern",
        "category": "inline",
        "parameter_type": "str",
        "example_usage": "Field(pattern=r'^[a-z]+$')",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000004"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "email_format",
        "type": "string",
        "description": "Validates email format using EmailStr type",
        "category": "inline",
        "parameter_type": "None",
        "example_usage": "EmailStr",
        "docs_url": "https://docs.pydantic.dev/latest/api/networks/#pydantic.networks.EmailStr",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000005"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "url_format",
        "type": "string",
        "description": "Validates URL format using HttpUrl type",
        "category": "inline",
        "parameter_type": "None",
        "example_usage": "HttpUrl",
        "docs_url": "https://docs.pydantic.dev/latest/api/networks/#pydantic.networks.HttpUrl",
    },
    # Numeric validators
    {
        "id": UUID("00000000-0000-0000-0002-000000000006"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "gt",
        "type": "numeric",
        "description": "Validates that number is greater than specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(gt=0)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000007"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "ge",
        "type": "numeric",
        "description": "Validates that number is greater than or equal to specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(ge=0)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000008"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "lt",
        "type": "numeric",
        "description": "Validates that number is less than specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(lt=100)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000009"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "le",
        "type": "numeric",
        "description": "Validates that number is less than or equal to specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(le=100)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000010"),
        "namespace_id": GLOBAL_NAMESPACE_ID,
        "name": "multiple_of",
        "type": "numeric",
        "description": "Validates that number is a multiple of specified value",
        "category": "inline",
        "parameter_type": "number",
        "example_usage": "Field(multiple_of=5)",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
    },
]


def upgrade() -> None:
    # Seed global namespace (required for FK constraints on types/validators)
    op.execute(
        f"""
        INSERT INTO namespaces (id, user_id, name, description, locked, is_default)
        VALUES ('{GLOBAL_NAMESPACE_ID}'::uuid, NULL, 'Global', 'Built-in types and validators', true, false)
        """
    )

    # Seed types data
    types_table = sa.table(
        "types",
        sa.column("id", postgresql.UUID),
        sa.column("namespace_id", postgresql.UUID),
        sa.column("user_id", sa.Text),
        sa.column("name", sa.Text),
        sa.column("python_type", sa.Text),
        sa.column("description", sa.Text),
        sa.column("import_path", sa.Text),
        sa.column("parent_type_id", postgresql.UUID),
    )
    op.bulk_insert(types_table, TYPES_DATA)

    # Seed validators data
    validators_table = sa.table(
        "validators",
        sa.column("id", postgresql.UUID),
        sa.column("namespace_id", postgresql.UUID),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("parameter_type", sa.String),
        sa.column("example_usage", sa.String),
        sa.column("docs_url", sa.String),
    )
    op.bulk_insert(validators_table, VALIDATORS_DATA)


def downgrade() -> None:
    # Delete seed data in reverse order (validators, types, namespace)
    op.execute(
        f"DELETE FROM validators WHERE namespace_id = '{GLOBAL_NAMESPACE_ID}'::uuid"
    )
    op.execute(f"DELETE FROM types WHERE namespace_id = '{GLOBAL_NAMESPACE_ID}'::uuid")
    op.execute(f"DELETE FROM namespaces WHERE id = '{GLOBAL_NAMESPACE_ID}'::uuid")
