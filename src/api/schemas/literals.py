# src/api/schemas/literals.py
"""Re-exports canonical Literal types from api_craft.models.enums.

The single source of truth lives in api_craft so the generation library
has no dependency on the api service layer.  Downstream api code can
continue to import from here without changes.
"""

from api_craft.models.enums import (  # noqa: F401
    Cardinality,
    Container,
    FieldAppearance,
    HttpMethod,
    OnDeleteAction,
    ResponseShape,
    ValidatorMode,
    check_constraint_sql,
)
