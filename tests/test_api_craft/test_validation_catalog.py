"""Tests for validation catalog consistency.

Verifies that the catalog constants are internally consistent and
match the patterns used across the codebase.
"""

from typing import get_args

from api_craft.models.enums import FilterOperator, ServerDefault
from api_craft.models.validation_catalog import (
    ALLOWED_PK_TYPES,
    OPERATOR_VALID_TYPES,
    PASCAL_CASE_PATTERN,
    SERVER_DEFAULT_VALID_TYPES,
    SNAKE_CASE_PATTERN,
)


class TestNamePatterns:
    """Name regex patterns must match documented rules."""

    def test_snake_case_accepts_valid(self):
        valid = ["user", "user_name", "a1", "field_1_value"]
        for name in valid:
            assert SNAKE_CASE_PATTERN.match(name), f"Should accept: {name}"

    def test_snake_case_rejects_invalid(self):
        invalid = [
            "User",
            "userName",
            "_user",
            "user_",
            "user__name",
            "1user",
            "user-name",
        ]
        for name in invalid:
            assert not SNAKE_CASE_PATTERN.match(name), f"Should reject: {name}"

    def test_pascal_case_accepts_valid(self):
        valid = ["User", "UserProfile", "A", "Ab", "Item1"]
        for name in valid:
            assert PASCAL_CASE_PATTERN.match(name), f"Should accept: {name}"

    def test_pascal_case_rejects_invalid(self):
        invalid = ["user", "userProfile", "UserAPI", "User_Name", "123"]
        for name in invalid:
            assert not PASCAL_CASE_PATTERN.match(name), f"Should reject: {name!r}"
        # Empty string: regex.match("") returns None
        assert not PASCAL_CASE_PATTERN.match("")


class TestServerDefaultCoverage:
    """SERVER_DEFAULT_VALID_TYPES must cover all ServerDefault enum values."""

    def test_all_server_defaults_have_valid_types(self):
        for sd in get_args(ServerDefault):
            assert (
                sd in SERVER_DEFAULT_VALID_TYPES
            ), f"ServerDefault '{sd}' missing from SERVER_DEFAULT_VALID_TYPES"


class TestOperatorCoverage:
    """OPERATOR_VALID_TYPES must cover all FilterOperator enum values."""

    def test_all_operators_have_valid_types(self):
        for op in get_args(FilterOperator):
            assert (
                op in OPERATOR_VALID_TYPES
            ), f"FilterOperator '{op}' missing from OPERATOR_VALID_TYPES"


class TestPkTypes:
    """PK types must be a small, known set."""

    def test_pk_types_are_expected(self):
        assert ALLOWED_PK_TYPES == {"int", "uuid"}
