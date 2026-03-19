"""Canonical validation constants for all structural rules.

Single source of truth consumed by:
- validators.py (generation-time validation)
- api service layer (CRUD-time validation)
- CI contract tests (cross-repo consistency checks)

Extends the pattern established in enums.py.
"""

import re

# --- Name validation ---

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
"""Regex for valid snake_case identifiers. Must match frontend isValidSnakeCaseName()."""

PASCAL_CASE_PATTERN = re.compile(r"^[A-Z](?:[a-z0-9]+[A-Z])*[a-z0-9]*$")
"""Regex for valid PascalCase identifiers. Must match frontend isValidPascalCaseName()."""

# --- Primary key types ---

ALLOWED_PK_TYPES: set[str] = {"int", "uuid"}
"""Types allowed for primary key fields. Must match frontend ALLOWED_PK_TYPES."""

# --- Server default compatibility ---

SERVER_DEFAULT_VALID_TYPES: dict[str, set[str]] = {
    "uuid4": {"uuid", "UUID"},
    "now": {"datetime", "date"},
    "now_on_update": {"datetime", "date"},
    "auto_increment": {"int"},
    "literal": {"str", "bool", "int", "float", "decimal", "EmailStr", "HttpUrl"},
}
"""Maps server_default strategy to compatible field types.
Must match frontend SERVER_DEFAULT_OPTIONS (transposed direction)."""

# --- Operator compatibility ---

NUMERIC_TYPES: set[str] = {"int", "float", "Decimal", "decimal", "decimal.Decimal"}
DATE_TIME_TYPES: set[str] = {
    "date",
    "datetime",
    "datetime.date",
    "datetime.datetime",
    "time",
    "datetime.time",
}
ORDERED_TYPES: set[str] = NUMERIC_TYPES | DATE_TIME_TYPES
STRING_TYPES: set[str] = {"str"}

OPERATOR_VALID_TYPES: dict[str, set[str]] = {
    "eq": set(),  # empty = all types valid
    "in": set(),  # empty = all types valid
    "gte": ORDERED_TYPES,
    "lte": ORDERED_TYPES,
    "gt": ORDERED_TYPES,
    "lt": ORDERED_TYPES,
    "like": STRING_TYPES,
    "ilike": STRING_TYPES,
}
"""Maps filter operators to compatible field types.
Empty set means all types are valid.
Must match frontend OPERATOR_TYPE_COMPATIBILITY."""
