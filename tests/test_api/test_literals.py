# tests/test_api/test_literals.py
"""Unit tests for canonical Literal type definitions."""

from typing import get_args

from api.schemas.literals import (
    Container,
    HttpMethod,
    ResponseShape,
    ValidatorMode,
    check_constraint_sql,
)


class TestLiteralValues:
    """Verify each Literal type exposes the expected values."""

    def test_http_method_values(self):
        assert get_args(HttpMethod) == ("GET", "POST", "PUT", "PATCH", "DELETE")

    def test_response_shape_values(self):
        assert get_args(ResponseShape) == ("object", "list")

    def test_container_values(self):
        assert get_args(Container) == ("List",)

    def test_validator_mode_values(self):
        assert get_args(ValidatorMode) == ("before", "after")


class TestCheckConstraintSql:
    """Verify SQL generation from Literal types."""

    def test_http_method_sql(self):
        sql = check_constraint_sql("method", HttpMethod)
        assert sql == "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')"

    def test_response_shape_sql(self):
        sql = check_constraint_sql("response_shape", ResponseShape)
        assert sql == "response_shape IN ('object', 'list')"

    def test_container_sql(self):
        sql = check_constraint_sql("container", Container)
        assert sql == "container IN ('List')"

    def test_validator_mode_sql(self):
        sql = check_constraint_sql("mode", ValidatorMode)
        assert sql == "mode IN ('before', 'after')"
