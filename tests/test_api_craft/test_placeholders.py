# tests/test_api_craft/test_placeholders.py
"""Unit tests for the placeholder generation module."""

import pytest

pytestmark = pytest.mark.unit

from api_craft.models.input import InputField as TemplateField
from api_craft.models.input import InputValidator as TemplateValidator
from api_craft.placeholders import (
    PlaceholderGenerator,
    extract_constraints,
    generate_bool,
    generate_date,
    generate_datetime,
    generate_float,
    generate_int,
    generate_string,
    generate_uuid,
    parse_type,
)


class TestParseType:
    """Tests for type string parsing."""

    def test_simple_types(self):
        assert parse_type("str") == ("str", [])
        assert parse_type("int") == ("int", [])
        assert parse_type("float") == ("float", [])
        assert parse_type("bool") == ("bool", [])

    def test_list_types(self):
        assert parse_type("List[str]") == ("List", ["str"])
        assert parse_type("List[int]") == ("List", ["int"])
        assert parse_type("List[Item]") == ("List", ["Item"])

    def test_nested_list_types(self):
        assert parse_type("List[List[str]]") == ("List", ["List[str]"])
        assert parse_type("List[List[List[int]]]") == ("List", ["List[List[int]]"])

    def test_dict_types(self):
        assert parse_type("Dict[str, int]") == ("Dict", ["str", "int"])
        assert parse_type("Dict[str, List[int]]") == ("Dict", ["str", "List[int]"])

    def test_optional_types(self):
        assert parse_type("Optional[str]") == ("Optional", ["str"])
        assert parse_type("Optional[Item]") == ("Optional", ["Item"])

    def test_union_syntax(self):
        assert parse_type("str | None") == ("Optional", ["str"])
        assert parse_type("None | str") == ("Optional", ["str"])
        assert parse_type("Item | None") == ("Optional", ["Item"])

    def test_complex_nested(self):
        assert parse_type("Dict[str, Dict[str, int]]") == (
            "Dict",
            ["str", "Dict[str, int]"],
        )
        assert parse_type("List[Dict[str, int]]") == ("List", ["Dict[str, int]"])


class TestExtractConstraints:
    """Tests for constraint extraction from validators."""

    def test_empty_validators(self):
        assert extract_constraints([]) == {}

    def test_single_constraint(self):
        validators = [TemplateValidator(name="min_length", params={"value": 3})]
        assert extract_constraints(validators) == {"min_length": 3}

    def test_multiple_constraints(self):
        validators = [
            TemplateValidator(name="ge", params={"value": 0}),
            TemplateValidator(name="le", params={"value": 100}),
            TemplateValidator(name="multiple_of", params={"value": 5}),
        ]
        assert extract_constraints(validators) == {"ge": 0, "le": 100, "multiple_of": 5}

    def test_validator_without_value(self):
        validators = [TemplateValidator(name="some_validator", params=None)]
        assert extract_constraints(validators) == {}


class TestGenerateString:
    """Tests for string generation with constraints."""

    def test_basic_string(self):
        result = generate_string(1, {})
        assert isinstance(result, str)
        assert len(result) >= 1

    def test_min_length(self):
        result = generate_string(1, {"min_length": 20})
        assert len(result) >= 20

    def test_max_length(self):
        result = generate_string(1, {"max_length": 5})
        assert len(result) <= 5

    def test_pattern_sku(self):
        result = generate_string(1, {"pattern": "^[A-Z0-9-]+$"})
        assert result.isupper() or "-" in result or result.isalnum()

    def test_pattern_email(self):
        result = generate_string(1, {"pattern": "email"})
        assert "@" in result


class TestGenerateInt:
    """Tests for integer generation with constraints."""

    def test_basic_int(self):
        result = generate_int(1, {})
        assert isinstance(result, int)

    def test_ge_constraint(self):
        result = generate_int(1, {"ge": 10})
        assert result >= 10

    def test_gt_constraint(self):
        result = generate_int(1, {"gt": 10})
        assert result > 10

    def test_le_constraint(self):
        result = generate_int(1, {"le": 5})
        assert result <= 5

    def test_lt_constraint(self):
        result = generate_int(1, {"lt": 5})
        assert result < 5

    def test_multiple_of(self):
        result = generate_int(1, {"multiple_of": 5})
        assert result % 5 == 0

    def test_multiple_of_with_range(self):
        result = generate_int(1, {"ge": 0, "le": 100, "multiple_of": 5})
        assert result >= 0
        assert result <= 100
        assert result % 5 == 0


class TestGenerateFloat:
    """Tests for float generation with constraints."""

    def test_basic_float(self):
        result = generate_float(1, {})
        assert isinstance(result, float)

    def test_ge_constraint(self):
        result = generate_float(1, {"ge": 10.0})
        assert result >= 10.0

    def test_gt_constraint(self):
        result = generate_float(1, {"gt": 0})
        assert result > 0

    def test_le_constraint(self):
        result = generate_float(1, {"le": 5.0})
        assert result <= 5.0


class TestGenerateBool:
    """Tests for boolean generation."""

    def test_alternates(self):
        assert generate_bool(1) is True
        assert generate_bool(2) is False
        assert generate_bool(3) is True


class TestGenerateDatetime:
    """Tests for datetime generation."""

    def test_format(self):
        result = generate_datetime(1)
        assert "T" in result
        assert len(result) == 19  # YYYY-MM-DDTHH:MM:SS


class TestGenerateDate:
    """Tests for date generation."""

    def test_format(self):
        result = generate_date(1)
        assert "-" in result
        assert len(result) == 10  # YYYY-MM-DD


class TestGenerateUUID:
    """Tests for UUID generation."""

    def test_format(self):
        result = generate_uuid(1)
        parts = result.split("-")
        assert len(parts) == 5
        assert len(result) == 36


class TestPlaceholderGenerator:
    """Tests for the PlaceholderGenerator class."""

    @pytest.fixture
    def simple_models(self):
        """Simple model with primitive fields."""
        return {
            "Item": [
                TemplateField(
                    type="int",
                    name="id",
                    nullable=False,
                    validators=[TemplateValidator(name="ge", params={"value": 1})],
                ),
                TemplateField(
                    type="str",
                    name="name",
                    nullable=False,
                    validators=[
                        TemplateValidator(name="min_length", params={"value": 1})
                    ],
                ),
                TemplateField(
                    type="float",
                    name="price",
                    nullable=False,
                    validators=[TemplateValidator(name="gt", params={"value": 0})],
                ),
                TemplateField(
                    type="str", name="description", nullable=True, validators=[]
                ),
            ]
        }

    @pytest.fixture
    def nested_models(self):
        """Models with nesting relationships."""
        return {
            "Address": [
                TemplateField(type="str", name="street", nullable=False, validators=[]),
                TemplateField(type="str", name="city", nullable=False, validators=[]),
            ],
            "Person": [
                TemplateField(type="str", name="name", nullable=False, validators=[]),
                TemplateField(
                    type="Address", name="address", nullable=False, validators=[]
                ),
            ],
        }

    @pytest.fixture
    def list_models(self):
        """Models with list fields."""
        return {
            "Tag": [
                TemplateField(type="str", name="name", nullable=False, validators=[]),
            ],
            "Article": [
                TemplateField(type="str", name="title", nullable=False, validators=[]),
                TemplateField(
                    type="List[Tag]", name="tags", nullable=False, validators=[]
                ),
            ],
        }

    def test_simple_model(self, simple_models):
        generator = PlaceholderGenerator(simple_models)
        result = generator.generate_for_model("Item")

        assert "id" in result
        assert "name" in result
        assert "price" in result
        assert "description" not in result  # Nullable field skipped

        assert isinstance(result["id"], int)
        assert result["id"] >= 1

        assert isinstance(result["name"], str)
        assert len(result["name"]) >= 1

        assert isinstance(result["price"], float)
        assert result["price"] > 0

    def test_nested_model(self, nested_models):
        generator = PlaceholderGenerator(nested_models)
        result = generator.generate_for_model("Person")

        assert "name" in result
        assert "address" in result
        assert isinstance(result["address"], dict)
        assert "street" in result["address"]
        assert "city" in result["address"]

    def test_list_field(self, list_models):
        generator = PlaceholderGenerator(list_models)
        result = generator.generate_for_model("Article")

        assert "title" in result
        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert len(result["tags"]) == 2
        assert isinstance(result["tags"][0], dict)
        assert "name" in result["tags"][0]

    def test_unknown_model(self, simple_models):
        generator = PlaceholderGenerator(simple_models)
        result = generator.generate_for_model("Unknown")
        assert result == {}

    def test_circular_reference(self):
        """Test that circular references don't cause infinite loops."""
        circular_models = {
            "Node": [
                TemplateField(type="str", name="value", nullable=False, validators=[]),
                TemplateField(type="Node", name="child", nullable=False, validators=[]),
            ]
        }
        generator = PlaceholderGenerator(circular_models)
        result = generator.generate_for_model("Node")

        # Should generate outer node but stop at circular ref
        assert "value" in result
        assert "child" in result
        assert result["child"] == {}  # Circular ref returns empty


class TestComplexTypes:
    """Tests for complex/nested type generation."""

    def test_list_of_primitives(self):
        models = {
            "Numbers": [
                TemplateField(
                    type="List[int]", name="values", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Numbers")

        assert isinstance(result["values"], list)
        assert all(isinstance(v, int) for v in result["values"])

    def test_dict_type(self):
        models = {
            "Config": [
                TemplateField(
                    type="Dict[str, int]",
                    name="settings",
                    nullable=False,
                    validators=[],
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Config")

        assert isinstance(result["settings"], dict)
        assert len(result["settings"]) == 1

    def test_optional_type(self):
        models = {
            "Item": [
                TemplateField(
                    type="str | None", name="value", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Item")

        # Optional with nullable=False generates the inner type
        assert isinstance(result["value"], str)

    def test_nested_list(self):
        models = {
            "Matrix": [
                TemplateField(
                    type="List[List[int]]", name="rows", nullable=False, validators=[]
                ),
            ]
        }
        generator = PlaceholderGenerator(models)
        result = generator.generate_for_model("Matrix")

        assert isinstance(result["rows"], list)
        assert isinstance(result["rows"][0], list)
        assert isinstance(result["rows"][0][0], int)
