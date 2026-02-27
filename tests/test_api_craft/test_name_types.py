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


from api_craft.models.types import PascalCaseName, SnakeCaseName


class TestSnakeCaseName:
    """Tests for SnakeCaseName type."""

    def test_valid_creation(self):
        name = SnakeCaseName("user_email")
        assert name == "user_email"

    def test_single_word(self):
        name = SnakeCaseName("email")
        assert name == "email"

    def test_camel_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.camel_name == "Email"

    def test_camel_name_multi_word(self):
        name = SnakeCaseName("user_email")
        assert name.camel_name == "UserEmail"

    def test_pascal_name(self):
        name = SnakeCaseName("user_email")
        assert name.pascal_name == "UserEmail"

    def test_kebab_name(self):
        name = SnakeCaseName("user_email")
        assert name.kebab_name == "user-email"

    def test_kebab_name_single_word(self):
        name = SnakeCaseName("email")
        assert name.kebab_name == "email"

    def test_rejects_camel_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("userEmail")

    def test_rejects_pascal_case(self):
        with pytest.raises(ValueError):
            SnakeCaseName("UserEmail")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            SnakeCaseName("")

    def test_is_str_subclass(self):
        name = SnakeCaseName("email")
        assert isinstance(name, str)


class TestPascalCaseName:
    """Regression tests for PascalCaseName (renamed from Name)."""

    def test_valid_creation(self):
        name = PascalCaseName("UserEmail")
        assert name == "UserEmail"

    def test_snake_name(self):
        name = PascalCaseName("UserEmail")
        assert name.snake_name == "user_email"

    def test_camel_name(self):
        name = PascalCaseName("UserEmail")
        assert name.camel_name == "userEmail"

    def test_kebab_name(self):
        name = PascalCaseName("UserEmail")
        assert name.kebab_name == "user-email"

    def test_pascal_name_returns_self(self):
        name = PascalCaseName("UserEmail")
        assert name.pascal_name == "UserEmail"

    def test_rejects_snake_case(self):
        with pytest.raises(ValueError):
            PascalCaseName("user_email")

    def test_rejects_lowercase_start(self):
        with pytest.raises(ValueError):
            PascalCaseName("userEmail")

    def test_is_str_subclass(self):
        name = PascalCaseName("User")
        assert isinstance(name, str)
