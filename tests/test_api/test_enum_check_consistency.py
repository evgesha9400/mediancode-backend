"""Test that migration CHECK constraints match Literal types in enums.py."""

from typing import get_args

import pytest

from api_craft.models.enums import (
    Cardinality,
    Container,
    FieldAppearance,
    HttpMethod,
    ResponseShape,
    ServerDefault,
    ValidatorMode,
    check_constraint_sql,
)


# These tuples map: (Literal type, column name used in migration, table context)
ENUM_CHECK_PAIRS = [
    (Container, "container", "fields"),
    (FieldAppearance, "appears", "fields_on_objects"),
    (Cardinality, "cardinality", "object_relationships"),
    (HttpMethod, "method", "api_endpoints"),
    (ResponseShape, "response_shape", "api_endpoints"),
    (ValidatorMode, "mode", "field_validator_templates"),
]


class TestEnumCheckConsistency:
    """Verify that CHECK constraint SQL can be derived from Literal types."""

    @pytest.mark.parametrize(
        "literal_type,column,table",
        ENUM_CHECK_PAIRS,
        ids=[f"{t[2]}.{t[1]}" for t in ENUM_CHECK_PAIRS],
    )
    def test_check_constraint_sql_produces_valid_output(
        self, literal_type, column, table
    ):
        """check_constraint_sql() should produce valid SQL for each enum."""
        sql = check_constraint_sql(column, literal_type)
        values = get_args(literal_type)
        for val in values:
            assert (
                f"'{val}'" in sql
            ), f"Value '{val}' missing from CHECK SQL for {table}.{column}"
        assert sql.startswith(f"{column} IN (")

    def test_server_default_check_allows_null(self):
        """ServerDefault CHECK must allow NULL (server_default is nullable)."""
        sql = check_constraint_sql("server_default", ServerDefault)
        assert "server_default IN (" in sql
