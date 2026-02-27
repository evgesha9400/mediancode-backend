"""Tests for PascalCaseName and SnakeCaseName types."""

import pytest

from api_craft.models.validators import validate_snake_case_name


class TestValidateSnakeCaseName:
    """Tests for validate_snake_case_name."""

    @pytest.mark.parametrize(
        "value",
        ["email", "user_email", "created_at", "field2", "a", "x1_y2_z3"],
    )
    def test_valid_snake_case(self, value: str):
        validate_snake_case_name(value)  # should not raise

    @pytest.mark.parametrize(
        "value,reason",
        [
            ("", "empty string"),
            ("Email", "starts with uppercase"),
            ("userEmail", "camelCase"),
            ("UserEmail", "PascalCase"),
            ("user__email", "double underscore"),
            ("_email", "leading underscore"),
            ("email_", "trailing underscore"),
            ("user-email", "contains hyphen"),
            ("user email", "contains space"),
            ("123field", "starts with digit"),
            ("user_Email", "uppercase after underscore"),
        ],
    )
    def test_invalid_snake_case(self, value: str, reason: str):
        with pytest.raises(ValueError):
            validate_snake_case_name(value)
