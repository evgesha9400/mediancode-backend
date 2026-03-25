# src/api_craft/models/enums.py
"""Canonical Literal types for all ENUM-like fields.

Single source of truth consumed by:
- Pydantic schemas (type annotations)
- SQLAlchemy models (column types reference these indirectly)
- Alembic migrations (CHECK constraint SQL values must match)
- OpenAPI spec (Pydantic auto-generates enum arrays from Literals)
"""

from typing import Literal, get_args

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ResponseShape = Literal["object", "list"]
Container = Literal["List"]
ValidatorMode = Literal["before", "after"]
OnDeleteAction = Literal["cascade", "restrict", "set_null"]
FieldExposure = Literal["read_write", "write_only", "read_only"]
FieldAppearance = FieldExposure  # deprecated alias, remove after full migration
RelationshipKind = Literal["one_to_one", "one_to_many", "many_to_many"]
FilterOperator = Literal["eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"]
GeneratedStrategy = Literal["uuid4", "now", "now_on_update", "auto_increment"]
ServerDefault = GeneratedStrategy  # deprecated alias, remove after full migration
DefaultKind = Literal["literal", "generated"]
FieldRole = Literal[
    "pk",
    "writable",
    "write_only",
    "read_only",
    "created_timestamp",
    "updated_timestamp",
    "generated_uuid",
]

# Legacy types kept only for existing Alembic migrations that reference them.
Cardinality = Literal["has_one", "has_many", "references", "many_to_many"]


def check_constraint_sql(column: str, literal_type: type) -> str:
    """Generate a CHECK constraint SQL clause from a Literal type.

    :param column: The database column name.
    :param literal_type: A Literal type alias (e.g. HttpMethod).
    :returns: SQL string like "column IN ('val1', 'val2')".
    """
    values = ", ".join(f"'{v}'" for v in get_args(literal_type))
    return f"{column} IN ({values})"
