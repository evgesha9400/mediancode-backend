"""Seed system namespace, types, and field constraints

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
SYSTEM_NAMESPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
TYPE_STR_ID = UUID("00000000-0000-0000-0001-000000000001")
TYPE_INT_ID = UUID("00000000-0000-0000-0001-000000000002")
TYPE_FLOAT_ID = UUID("00000000-0000-0000-0001-000000000003")
TYPE_BOOL_ID = UUID("00000000-0000-0000-0001-000000000004")
TYPE_DATETIME_ID = UUID("00000000-0000-0000-0001-000000000005")
TYPE_UUID_ID = UUID("00000000-0000-0000-0001-000000000006")
TYPE_EMAIL_STR_ID = UUID("00000000-0000-0000-0001-000000000007")
TYPE_HTTP_URL_ID = UUID("00000000-0000-0000-0001-000000000008")

# Seed data for types
TYPES_DATA = [
    {
        "id": TYPE_STR_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "str",
        "python_type": "str",
        "description": "String type for text data",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_INT_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "int",
        "python_type": "int",
        "description": "Integer type for whole numbers",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_FLOAT_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "float",
        "python_type": "float",
        "description": "Floating point type for decimal numbers",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_BOOL_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "bool",
        "python_type": "bool",
        "description": "Boolean type for true/false values",
        "import_path": None,
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_DATETIME_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "datetime",
        "python_type": "datetime.datetime",
        "description": "Date and time type",
        "import_path": "from datetime import datetime",
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_UUID_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "uuid",
        "python_type": "uuid.UUID",
        "description": "Universally unique identifier",
        "import_path": "from uuid import UUID",
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_EMAIL_STR_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "EmailStr",
        "python_type": "EmailStr",
        "description": "Email address validated using Pydantic EmailStr",
        "import_path": "from pydantic import EmailStr",
        "user_id": None,
        "parent_type_id": TYPE_STR_ID,
    },
    {
        "id": TYPE_HTTP_URL_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "HttpUrl",
        "python_type": "HttpUrl",
        "description": "HTTP URL validated using Pydantic HttpUrl",
        "import_path": "from pydantic import HttpUrl",
        "user_id": None,
        "parent_type_id": TYPE_STR_ID,
    },
]

# Seed data for field constraints (Pydantic Field constraints)
CONSTRAINTS_DATA = [
    # String constraints
    {
        "id": UUID("00000000-0000-0000-0002-000000000001"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "max_length",
        "description": "Validates that string length does not exceed maximum",
        "parameter_type": "int",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000002"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "min_length",
        "description": "Validates that string length is at least minimum",
        "parameter_type": "int",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000003"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "pattern",
        "description": "Validates string matches a regular expression pattern",
        "parameter_type": "str",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    # Numeric constraints
    {
        "id": UUID("00000000-0000-0000-0002-000000000006"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "gt",
        "description": "Validates that number is greater than specified value",
        "parameter_type": "number",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000007"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "ge",
        "description": "Validates that number is greater than or equal to specified value",
        "parameter_type": "number",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000008"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "lt",
        "description": "Validates that number is less than specified value",
        "parameter_type": "number",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000009"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "le",
        "description": "Validates that number is less than or equal to specified value",
        "parameter_type": "number",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000010"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "multiple_of",
        "description": "Validates that number is a multiple of specified value",
        "parameter_type": "number",
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float"],
    },
]


def upgrade() -> None:
    # Seed system namespace (required for FK constraints on types/constraints)
    op.execute(
        f"""
        INSERT INTO namespaces (id, user_id, name, description, locked, is_default)
        VALUES ('{SYSTEM_NAMESPACE_ID}'::uuid, NULL, 'Global', 'Built-in types and field constraints', true, false)
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

    # Seed field constraints data
    constraints_table = sa.table(
        "field_constraints",
        sa.column("id", postgresql.UUID),
        sa.column("namespace_id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("parameter_type", sa.Text),
        sa.column("docs_url", sa.Text),
        sa.column("compatible_types", postgresql.ARRAY(sa.Text)),
    )
    op.bulk_insert(constraints_table, CONSTRAINTS_DATA)


def downgrade() -> None:
    # Delete seed data in reverse order (field_constraints, types, namespace)
    op.execute(
        f"DELETE FROM field_constraints WHERE namespace_id = '{SYSTEM_NAMESPACE_ID}'::uuid"
    )
    op.execute(f"DELETE FROM types WHERE namespace_id = '{SYSTEM_NAMESPACE_ID}'::uuid")
    op.execute(f"DELETE FROM namespaces WHERE id = '{SYSTEM_NAMESPACE_ID}'::uuid")
