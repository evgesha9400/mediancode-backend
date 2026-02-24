"""Seed system data

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
TYPE_DECIMAL_ID = UUID("00000000-0000-0000-0001-000000000009")
TYPE_DATE_ID = UUID("00000000-0000-0000-0001-000000000010")
TYPE_TIME_ID = UUID("00000000-0000-0000-0001-000000000011")

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
    {
        "id": TYPE_DECIMAL_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "Decimal",
        "python_type": "Decimal",
        "description": "Decimal type for precise financial values",
        "import_path": "from decimal import Decimal",
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_DATE_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "date",
        "python_type": "datetime.date",
        "description": "Date type for date-only values",
        "import_path": "from datetime import date",
        "user_id": None,
        "parent_type_id": None,
    },
    {
        "id": TYPE_TIME_ID,
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "time",
        "python_type": "datetime.time",
        "description": "Time type for time-only values",
        "import_path": "from datetime import time",
        "user_id": None,
        "parent_type_id": None,
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
        "parameter_types": ["int"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000002"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "min_length",
        "description": "Validates that string length is at least minimum",
        "parameter_types": ["int"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000003"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "pattern",
        "description": "Validates string matches a regular expression pattern",
        "parameter_types": ["str"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#string-constraints",
        "compatible_types": ["str", "uuid"],
    },
    # Numeric constraints
    {
        "id": UUID("00000000-0000-0000-0002-000000000006"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "gt",
        "description": "Validates that number is greater than specified value",
        "parameter_types": ["int", "float", "Decimal"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float", "Decimal", "date", "time", "datetime"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000007"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "ge",
        "description": "Validates that number is greater than or equal to specified value",
        "parameter_types": ["int", "float", "Decimal"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float", "Decimal", "date", "time", "datetime"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000008"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "lt",
        "description": "Validates that number is less than specified value",
        "parameter_types": ["int", "float", "Decimal"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float", "Decimal", "date", "time", "datetime"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000009"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "le",
        "description": "Validates that number is less than or equal to specified value",
        "parameter_types": ["int", "float", "Decimal"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float", "Decimal", "date", "time", "datetime"],
    },
    {
        "id": UUID("00000000-0000-0000-0002-000000000010"),
        "namespace_id": SYSTEM_NAMESPACE_ID,
        "name": "multiple_of",
        "description": "Validates that number is a multiple of specified value",
        "parameter_types": ["int", "float", "Decimal"],
        "docs_url": "https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints",
        "compatible_types": ["int", "float", "Decimal"],
    },
]

# Fixed UUIDs for field validator templates
FVT_TRIM_ID = UUID("00000000-0000-0000-0003-000000000001")
FVT_NORMALIZE_CASE_ID = UUID("00000000-0000-0000-0003-000000000002")
FVT_NORMALIZE_WHITESPACE_ID = UUID("00000000-0000-0000-0003-000000000003")
FVT_TRIM_TO_LENGTH_ID = UUID("00000000-0000-0000-0003-000000000004")
FVT_ROUND_DECIMAL_ID = UUID("00000000-0000-0000-0003-000000000005")
FVT_EMPTY_TO_NONE_ID = UUID("00000000-0000-0000-0003-000000000006")
FVT_CLAMP_TO_RANGE_ID = UUID("00000000-0000-0000-0003-000000000007")
FVT_STRIP_CHARACTERS_ID = UUID("00000000-0000-0000-0003-000000000008")

FIELD_VALIDATOR_TEMPLATES_DATA = [
    {
        "id": FVT_TRIM_ID,
        "name": "Trim",
        "description": "Removes leading and trailing whitespace",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [],
        "body_template": "    v = v.strip()\n    return v",
    },
    {
        "id": FVT_NORMALIZE_CASE_ID,
        "name": "Normalize Case",
        "description": "Converts text to a consistent case format",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "case",
                "label": "Case format",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "lower", "label": "lowercase"},
                    {"value": "upper", "label": "UPPERCASE"},
                    {"value": "title", "label": "Title Case"},
                ],
                "required": True,
            }
        ],
        "body_template": "    v = v.{{ case }}()\n    return v",
    },
    {
        "id": FVT_NORMALIZE_WHITESPACE_ID,
        "name": "Normalize Whitespace",
        "description": "Collapses multiple whitespace characters into single spaces and strips edges",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [],
        "body_template": "    import re\n    v = re.sub(r'\\s+', ' ', v).strip()\n    return v",
    },
    {
        "id": FVT_TRIM_TO_LENGTH_ID,
        "name": "Trim To Length",
        "description": "Truncates string to maximum length instead of rejecting",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "max_length",
                "label": "Maximum length",
                "type": "number",
                "placeholder": "255",
                "required": True,
            }
        ],
        "body_template": "    v = v[:{{ max_length }}]\n    return v",
    },
    {
        "id": FVT_ROUND_DECIMAL_ID,
        "name": "Round Decimal",
        "description": "Rounds numeric value to specified decimal places",
        "compatible_types": ["float", "Decimal"],
        "mode": "before",
        "parameters": [
            {
                "key": "places",
                "label": "Decimal places",
                "type": "number",
                "placeholder": "2",
                "required": True,
            }
        ],
        "body_template": "    v = round(v, {{ places }})\n    return v",
    },
    {
        "id": FVT_EMPTY_TO_NONE_ID,
        "name": "Empty String to None",
        "description": "Converts empty or whitespace-only strings to None for optional fields",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [],
        "body_template": "    if isinstance(v, str) and not v.strip():\n        return None\n    return v",
    },
    {
        "id": FVT_CLAMP_TO_RANGE_ID,
        "name": "Clamp to Range",
        "description": "Clamps numeric value to min/max bounds instead of rejecting",
        "compatible_types": ["int", "float", "Decimal"],
        "mode": "before",
        "parameters": [
            {
                "key": "min_value",
                "label": "Minimum value",
                "type": "number",
                "placeholder": "0",
                "required": True,
            },
            {
                "key": "max_value",
                "label": "Maximum value",
                "type": "number",
                "placeholder": "100",
                "required": True,
            },
        ],
        "body_template": "    v = max({{ min_value }}, min({{ max_value }}, v))\n    return v",
    },
    {
        "id": FVT_STRIP_CHARACTERS_ID,
        "name": "Strip Characters",
        "description": "Removes specified characters from the entire string",
        "compatible_types": ["str"],
        "mode": "before",
        "parameters": [
            {
                "key": "characters",
                "label": "Characters to remove",
                "type": "text",
                "placeholder": "()-+ ",
                "required": True,
            }
        ],
        "body_template": '    v = v.translate(str.maketrans("", "", "{{ characters }}"))\n    return v',
    },
]

# Fixed UUIDs for model validator templates
MVT_PASSWORD_CONFIRM_ID = UUID("00000000-0000-0000-0004-000000000001")
MVT_DATE_RANGE_ID = UUID("00000000-0000-0000-0004-000000000002")
MVT_MUTUAL_EXCLUSIVITY_ID = UUID("00000000-0000-0000-0004-000000000003")
MVT_CONDITIONAL_REQUIRED_ID = UUID("00000000-0000-0000-0004-000000000004")
MVT_NUMERIC_COMPARISON_ID = UUID("00000000-0000-0000-0004-000000000005")
MVT_AT_LEAST_ONE_ID = UUID("00000000-0000-0000-0004-000000000006")

MODEL_VALIDATOR_TEMPLATES_DATA = [
    {
        "id": MVT_PASSWORD_CONFIRM_ID,
        "name": "Password Confirmation",
        "description": "Ensures password and confirmation fields match",
        "mode": "after",
        "parameters": [],
        "field_mappings": [
            {
                "key": "password_field",
                "label": "Password field",
                "compatibleTypes": ["str"],
                "required": True,
            },
            {
                "key": "confirm_field",
                "label": "Confirmation field",
                "compatibleTypes": ["str"],
                "required": True,
            },
        ],
        "body_template": "    if self.{{ password_field }} != self.{{ confirm_field }}:\n        raise ValueError('Password and confirmation do not match')\n    return self",
    },
    {
        "id": MVT_DATE_RANGE_ID,
        "name": "Date Range",
        "description": "Validates that start date is before end date",
        "mode": "after",
        "parameters": [
            {
                "key": "comparison",
                "label": "Comparison mode",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "<", "label": "Strict (start < end)"},
                    {"value": "<=", "label": "Inclusive (start <= end)"},
                ],
                "required": True,
            }
        ],
        "field_mappings": [
            {
                "key": "start_field",
                "label": "Start date field",
                "compatibleTypes": ["datetime", "date"],
                "required": True,
            },
            {
                "key": "end_field",
                "label": "End date field",
                "compatibleTypes": ["datetime", "date"],
                "required": True,
            },
        ],
        "body_template": "    if not (self.{{ start_field }} {{ comparison }} self.{{ end_field }}):\n        raise ValueError('Start date must be before end date')\n    return self",
    },
    {
        "id": MVT_MUTUAL_EXCLUSIVITY_ID,
        "name": "Mutual Exclusivity",
        "description": "Ensures exactly one of two fields is set (not both, not neither)",
        "mode": "after",
        "parameters": [],
        "field_mappings": [
            {
                "key": "field_a",
                "label": "Field A",
                "compatibleTypes": [],
                "required": True,
            },
            {
                "key": "field_b",
                "label": "Field B",
                "compatibleTypes": [],
                "required": True,
            },
        ],
        "body_template": "    a_set = self.{{ field_a }} is not None\n    b_set = self.{{ field_b }} is not None\n    if a_set == b_set:\n        raise ValueError('Exactly one of {{ field_a }} or {{ field_b }} must be provided')\n    return self",
    },
    {
        "id": MVT_CONDITIONAL_REQUIRED_ID,
        "name": "Conditional Required",
        "description": "Makes a field required when a trigger field meets a condition",
        "mode": "after",
        "parameters": [
            {
                "key": "condition",
                "label": "Condition",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "equals", "label": "Equals value"},
                    {"value": "not_equals", "label": "Does not equal value"},
                    {"value": "is_truthy", "label": "Is truthy"},
                ],
                "required": True,
            },
            {
                "key": "trigger_value",
                "label": "Trigger value",
                "type": "text",
                "placeholder": "value to compare against",
                "required": False,
            },
        ],
        "field_mappings": [
            {
                "key": "trigger_field",
                "label": "Trigger field",
                "compatibleTypes": [],
                "required": True,
            },
            {
                "key": "required_field",
                "label": "Required field",
                "compatibleTypes": [],
                "required": True,
            },
        ],
        "body_template": "    trigger = self.{{ trigger_field }}\n    condition_met = False\n    if '{{ condition }}' == 'equals':\n        condition_met = str(trigger) == '{{ trigger_value }}'\n    elif '{{ condition }}' == 'not_equals':\n        condition_met = str(trigger) != '{{ trigger_value }}'\n    elif '{{ condition }}' == 'is_truthy':\n        condition_met = bool(trigger)\n    if condition_met and self.{{ required_field }} is None:\n        raise ValueError('{{ required_field }} is required when {{ trigger_field }} condition is met')\n    return self",
    },
    {
        "id": MVT_NUMERIC_COMPARISON_ID,
        "name": "Numeric Comparison",
        "description": "Validates that one numeric field is less than another",
        "mode": "after",
        "parameters": [
            {
                "key": "comparison",
                "label": "Comparison mode",
                "type": "select",
                "placeholder": "",
                "options": [
                    {"value": "<", "label": "Strict (lesser < greater)"},
                    {"value": "<=", "label": "Inclusive (lesser <= greater)"},
                ],
                "required": True,
            }
        ],
        "field_mappings": [
            {
                "key": "lesser_field",
                "label": "Lesser field",
                "compatibleTypes": ["int", "float", "Decimal"],
                "required": True,
            },
            {
                "key": "greater_field",
                "label": "Greater field",
                "compatibleTypes": ["int", "float", "Decimal"],
                "required": True,
            },
        ],
        "body_template": "    if self.{{ lesser_field }} is not None and self.{{ greater_field }} is not None:\n        if not (self.{{ lesser_field }} {{ comparison }} self.{{ greater_field }}):\n            raise ValueError('{{ lesser_field }} must be less than {{ greater_field }}')\n    return self",
    },
    {
        "id": MVT_AT_LEAST_ONE_ID,
        "name": "At Least One Required",
        "description": "Ensures at least one of two fields is provided",
        "mode": "before",
        "parameters": [],
        "field_mappings": [
            {
                "key": "field_a",
                "label": "Field A",
                "compatibleTypes": [],
                "required": True,
            },
            {
                "key": "field_b",
                "label": "Field B",
                "compatibleTypes": [],
                "required": True,
            },
        ],
        "body_template": "    if data.get('{{ field_a }}') is None and data.get('{{ field_b }}') is None:\n        raise ValueError('At least one of {{ field_a }} or {{ field_b }} must be provided')\n    return data",
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
        sa.column("user_id", postgresql.UUID),
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
        sa.column("parameter_types", postgresql.ARRAY(sa.Text)),
        sa.column("docs_url", sa.Text),
        sa.column("compatible_types", postgresql.ARRAY(sa.Text)),
    )
    op.bulk_insert(constraints_table, CONSTRAINTS_DATA)

    # Seed field validator templates
    fvt_table = sa.table(
        "field_validator_templates",
        sa.column("id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("compatible_types", postgresql.ARRAY(sa.Text)),
        sa.column("mode", sa.Text),
        sa.column("parameters", postgresql.JSONB),
        sa.column("body_template", sa.Text),
    )
    op.bulk_insert(fvt_table, FIELD_VALIDATOR_TEMPLATES_DATA)

    # Seed model validator templates
    mvt_table = sa.table(
        "model_validator_templates",
        sa.column("id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("mode", sa.Text),
        sa.column("parameters", postgresql.JSONB),
        sa.column("field_mappings", postgresql.JSONB),
        sa.column("body_template", sa.Text),
    )
    op.bulk_insert(mvt_table, MODEL_VALIDATOR_TEMPLATES_DATA)


def downgrade() -> None:
    # Delete template seed data first (reverse order)
    op.execute("DELETE FROM model_validator_templates")
    op.execute("DELETE FROM field_validator_templates")

    # Delete seed data in reverse order (field_constraints, types, namespace)
    op.execute(
        f"DELETE FROM field_constraints WHERE namespace_id = '{SYSTEM_NAMESPACE_ID}'::uuid"
    )
    op.execute(f"DELETE FROM types WHERE namespace_id = '{SYSTEM_NAMESPACE_ID}'::uuid")
    op.execute(f"DELETE FROM namespaces WHERE id = '{SYSTEM_NAMESPACE_ID}'::uuid")
