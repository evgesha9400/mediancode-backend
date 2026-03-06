# tests/test_api_craft/test_codegen.py
"""Codegen tests for api_craft code generation.

These tests generate APIs, launch them, and make real HTTP requests.
A successful request proves:
- Syntax validity (import would fail otherwise)
- Model correctness (Pydantic would error)
- View definitions (FastAPI would error)
- Parameter handling (requests would fail)
- Import correctness (module loading would fail)
- Validator constraints (invalid data would be accepted)
"""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.codegen

from api_craft.main import APIGenerator
from .conftest import SPECS_PATH, load_input

logger = logging.getLogger(__name__)


def log_test(context: str):
    """Log what we're about to test."""
    logger.info(f"Testing: {context}")


def assert_valid_response(response, expected_status: int = 200):
    """Assert response is successful with helpful error message."""
    if response.status_code != expected_status:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        pytest.fail(
            f"Expected: {expected_status}\nGot: {response.status_code}\nDetail: {detail}"
        )
    logger.info(f"  -> PASS: {response.status_code} OK")


def assert_validation_error(response, expected_field: str | None = None):
    """Assert response is 422 validation error with helpful message."""
    if response.status_code != 422:
        pytest.fail(
            f"Expected: 422 Validation Error\n"
            f"Got: {response.status_code}\n"
            f"Body: {response.text}"
        )

    detail = response.json().get("detail", [])

    # Optionally verify the error mentions the expected field
    if expected_field:
        field_names = [err.get("loc", [])[-1] for err in detail if "loc" in err]
        if expected_field not in field_names:
            pytest.fail(
                f"Expected validation error for field: {expected_field}\n"
                f"Got errors for fields: {field_names}\n"
                f"Detail: {detail}"
            )

    # Log the validation error details
    for err in detail:
        field = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "")
        logger.info(f"  -> PASS: 422 on '{field}': {msg}")


@pytest.mark.manual
def test_generate_to_output():
    """Generate all APIs from tests/data/*.yaml to tests/output/."""
    output_path = Path(__file__).parent.parent / "output"
    for yaml_file in SPECS_PATH.glob("*.yaml"):
        api_input = load_input(yaml_file.name)
        APIGenerator().generate(api_input, path=str(output_path))


class TestItemsApi:
    """Codegen tests for the Items API."""

    def test_healthcheck(self, items_api_client: TestClient):
        """Healthcheck endpoint returns OK."""
        log_test("GET /healthcheck - Health check endpoint")
        response = items_api_client.get("/healthcheck")
        assert response.status_code == 200
        assert response.text == "OK"
        logger.info("  -> PASS: 200 OK")

    def test_get_item(self, items_api_client: TestClient):
        """GET /items/{item_id} returns a single item."""
        log_test("GET /items/1 - Fetch single item by ID")
        response = items_api_client.get("/items/1")
        assert_valid_response(response)

        data = response.json()
        assert "id" in data, "Response missing 'id' field"
        assert "sku" in data, "Response missing 'sku' field"
        assert "name" in data, "Response missing 'name' field"
        assert "price" in data, "Response missing 'price' field"
        assert "quantity" in data, "Response missing 'quantity' field"

    def test_get_items(self, items_api_client: TestClient):
        """GET /items returns a list of items."""
        log_test("GET /items - List all items")
        response = items_api_client.get("/items")
        assert_valid_response(response)

        data = response.json()
        assert "items" in data, "Response missing 'items' field"
        assert "total" in data, "Response missing 'total' field"

    def test_get_items_with_query_params(self, items_api_client: TestClient):
        """GET /items accepts query parameters."""
        log_test("GET /items?limit=10&offset=5&min_price=10.0 - List with filters")
        response = items_api_client.get("/items?limit=10&offset=5&min_price=10.0")
        assert_valid_response(response)

    def test_delete_item(self, items_api_client: TestClient):
        """DELETE /items/{item_id} deletes an item."""
        log_test("DELETE /items/1 - Delete item by ID")
        response = items_api_client.delete("/items/1")
        assert_valid_response(response)


class TestCreateItemValidation:
    """Tests for CreateItemRequest validators."""

    def test_create_item_valid(self, items_api_client: TestClient):
        """POST /items with valid data succeeds."""
        payload = {
            "sku": "TEST-123",
            "name": "Test Item",
            "price": 29.99,
            "quantity": 100,
        }
        log_test(f"POST /items - Valid item creation: {payload}")
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

        data = response.json()
        assert "sku" in data, "Response missing 'sku' field"
        assert "name" in data, "Response missing 'name' field"
        assert "price" in data, "Response missing 'price' field"

    def test_create_item_valid_with_optional_fields(self, items_api_client: TestClient):
        """POST /items with all fields including optional ones."""
        payload = {
            "sku": "FULL-001",
            "name": "Full Item",
            "description": "A complete item with all fields",
            "price": 99.99,
            "quantity": 50,
            "discount_percent": 15,
        }
        log_test(f"POST /items - With optional fields: {payload}")
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    # --- SKU Validators: min_length=3, max_length=20, pattern=^[A-Z0-9-]+$ ---

    def test_create_item_sku_too_short(self, items_api_client: TestClient):
        """SKU shorter than min_length=3 is rejected."""
        payload = {"sku": "AB", "name": "Test", "price": 10.0, "quantity": 1}
        log_test(f"POST /items - SKU='AB' should fail min_length=3")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    def test_create_item_sku_too_long(self, items_api_client: TestClient):
        """SKU longer than max_length=20 is rejected."""
        long_sku = "A" * 21
        payload = {"sku": long_sku, "name": "Test", "price": 10.0, "quantity": 1}
        log_test(f"POST /items - SKU length=21 should fail max_length=20")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    def test_create_item_sku_invalid_pattern(self, items_api_client: TestClient):
        """SKU not matching pattern ^[A-Z0-9-]+$ is rejected."""
        payload = {"sku": "invalid_sku", "name": "Test", "price": 10.0, "quantity": 1}
        log_test("POST /items - SKU='invalid_sku' should fail pattern ^[A-Z0-9-]+$")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    # --- Name Validators: min_length=1, max_length=100 ---

    def test_create_item_name_empty(self, items_api_client: TestClient):
        """Empty name (min_length=1 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "", "price": 10.0, "quantity": 1}
        log_test("POST /items - Empty name should fail min_length=1")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="name")

    def test_create_item_name_too_long(self, items_api_client: TestClient):
        """Name longer than max_length=100 is rejected."""
        long_name = "A" * 101
        payload = {"sku": "TEST-001", "name": long_name, "price": 10.0, "quantity": 1}
        log_test("POST /items - Name length=101 should fail max_length=100")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="name")

    # --- Price Validators: gt=0, le=1000000 ---

    def test_create_item_price_zero(self, items_api_client: TestClient):
        """Price of 0 (gt=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 0, "quantity": 1}
        log_test("POST /items - Price=0 should fail gt=0")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_negative(self, items_api_client: TestClient):
        """Negative price (gt=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": -10.0, "quantity": 1}
        log_test("POST /items - Price=-10 should fail gt=0")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_too_high(self, items_api_client: TestClient):
        """Price over 1M (le=1000000 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 1000001, "quantity": 1}
        log_test("POST /items - Price=1000001 should fail le=1000000")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_at_max(self, items_api_client: TestClient):
        """Price exactly at 1M (le=1000000) is accepted."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 1000000, "quantity": 1}
        log_test("POST /items - Price=1000000 should pass le=1000000 (boundary)")
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    # --- Quantity Validators: ge=0, le=100000 ---

    def test_create_item_quantity_negative(self, items_api_client: TestClient):
        """Negative quantity (ge=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": -1}
        log_test("POST /items - Quantity=-1 should fail ge=0")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="quantity")

    def test_create_item_quantity_zero(self, items_api_client: TestClient):
        """Quantity of 0 (ge=0) is accepted."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": 0}
        log_test("POST /items - Quantity=0 should pass ge=0 (boundary)")
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    def test_create_item_quantity_too_high(self, items_api_client: TestClient):
        """Quantity over 100000 (le=100000 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": 100001}
        log_test("POST /items - Quantity=100001 should fail le=100000")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="quantity")

    # --- Discount Percent Validators: ge=0, le=100, multiple_of=5 ---

    def test_create_item_discount_valid_multiples(self, items_api_client: TestClient):
        """Discount percentages that are multiples of 5 are accepted."""
        for discount in [0, 5, 10, 25, 50, 100]:
            payload = {
                "sku": "TEST-001",
                "name": "Test",
                "price": 10.0,
                "quantity": 1,
                "discount_percent": discount,
            }
            log_test(f"POST /items - Discount={discount} should pass multiple_of=5")
            response = items_api_client.post("/items", json=payload)
            assert_valid_response(response)

    def test_create_item_discount_not_multiple_of_5(self, items_api_client: TestClient):
        """Discount not a multiple of 5 (multiple_of=5 violation) is rejected."""
        payload = {
            "sku": "TEST-001",
            "name": "Test",
            "price": 10.0,
            "quantity": 1,
            "discount_percent": 7,
        }
        log_test("POST /items - Discount=7 should fail multiple_of=5")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="discount_percent")

    def test_create_item_discount_negative(self, items_api_client: TestClient):
        """Negative discount (ge=0 violation) is rejected."""
        payload = {
            "sku": "TEST-001",
            "name": "Test",
            "price": 10.0,
            "quantity": 1,
            "discount_percent": -5,
        }
        log_test("POST /items - Discount=-5 should fail ge=0")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="discount_percent")

    def test_create_item_discount_over_100(self, items_api_client: TestClient):
        """Discount over 100% (le=100 violation) is rejected."""
        payload = {
            "sku": "TEST-001",
            "name": "Test",
            "price": 10.0,
            "quantity": 1,
            "discount_percent": 105,
        }
        log_test("POST /items - Discount=105 should fail le=100")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="discount_percent")

    # --- Description Validator: max_length=1000 ---

    def test_create_item_description_too_long(self, items_api_client: TestClient):
        """Description longer than max_length=1000 is rejected."""
        long_desc = "A" * 1001
        payload = {
            "sku": "TEST-001",
            "name": "Test",
            "price": 10.0,
            "quantity": 1,
            "description": long_desc,
        }
        log_test("POST /items - Description length=1001 should fail max_length=1000")
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="description")


def test_field_validator_body_indentation(tmp_path):
    """Field validator bodies must be indented inside the class method."""
    from api_craft.models.input import (
        InputAPI,
        InputApiConfig,
        InputEndpoint,
        InputField,
        InputModel,
        InputResolvedFieldValidator,
    )

    api = InputAPI(
        name="IndentTest",
        endpoints=[
            InputEndpoint(
                name="GetItems",
                path="/items",
                method="GET",
                response="Item",
            )
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[
                    InputField(
                        name="value",
                        type="str",
                        field_validators=[
                            InputResolvedFieldValidator(
                                function_name="trim_value",
                                mode="before",
                                function_body="    v = v.strip()\n    return v",
                            )
                        ],
                    )
                ],
            )
        ],
        config=InputApiConfig(
            response_placeholders=False,
            format_code=False,
            generate_swagger=False,
        ),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "indent-test" / "src" / "models.py").read_text()

    # Must compile without IndentationError
    compile(models_py, "models.py", "exec")

    # Each body line must be indented at least 8 spaces (class + method)
    for line in models_py.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("v = v.strip()") or stripped.startswith("return v"):
            indent = len(line) - len(stripped)
            assert indent >= 8, f"Insufficient indent ({indent}): {line!r}"


def test_decimal_type_generates_import(tmp_path):
    """Decimal fields must produce 'from decimal import Decimal' import."""
    from api_craft.models.input import (
        InputAPI,
        InputApiConfig,
        InputEndpoint,
        InputField,
        InputModel,
    )

    api = InputAPI(
        name="DecimalTest",
        endpoints=[
            InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="price", type="decimal.Decimal")],
            )
        ],
        config=InputApiConfig(
            response_placeholders=False,
            format_code=False,
            generate_swagger=False,
        ),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "decimal-test" / "src" / "models.py").read_text()

    assert "import decimal" in models_py or "from decimal import Decimal" in models_py
    compile(models_py, "models.py", "exec")


def test_clamp_to_range_renders_values(tmp_path):
    """Clamp to Range must render actual min/max values, not empty args."""
    from api_craft.models.input import (
        InputAPI,
        InputApiConfig,
        InputEndpoint,
        InputField,
        InputModel,
        InputResolvedFieldValidator,
    )

    api = InputAPI(
        name="ClampTest",
        endpoints=[
            InputEndpoint(name="GetItems", path="/items", method="GET", response="Item")
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[
                    InputField(
                        name="weight",
                        type="float",
                        field_validators=[
                            InputResolvedFieldValidator(
                                function_name="clamp_to_range_weight",
                                mode="before",
                                function_body="    v = max(0, min(1000, v))\n    return v",
                            )
                        ],
                    )
                ],
            )
        ],
        config=InputApiConfig(
            response_placeholders=False,
            format_code=False,
            generate_swagger=False,
        ),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    models_py = (tmp_path / "clamp-test" / "src" / "models.py").read_text()
    assert "max(0, min(1000, v))" in models_py
    assert "max(, min(, v))" not in models_py


def test_list_response_shape_generates_list_type(tmp_path):
    """Endpoints with response_shape='list' must use list[Model] as response_model."""
    from api_craft.models.input import (
        InputAPI,
        InputApiConfig,
        InputEndpoint,
        InputField,
        InputModel,
    )

    api = InputAPI(
        name="ListTest",
        endpoints=[
            InputEndpoint(
                name="GetItems",
                path="/items",
                method="GET",
                response="Item",
                response_shape="list",
            )
        ],
        objects=[
            InputModel(
                name="Item",
                fields=[InputField(name="name", type="str")],
            )
        ],
        config=InputApiConfig(
            response_placeholders=False,
            format_code=False,
            generate_swagger=False,
        ),
    )

    APIGenerator().generate(api, path=str(tmp_path))
    views_py = (tmp_path / "list-test" / "src" / "views.py").read_text()

    assert "response_model=list[Item]" in views_py
    assert "return [Item(" in views_py or "return []" in views_py


class TestUpdateItemValidation:
    """Tests for UpdateItemRequest validators."""

    def test_update_item_valid(self, items_api_client: TestClient):
        """PUT /items/{id} with valid data succeeds."""
        payload = {"name": "Updated Name", "price": 49.99}
        log_test(f"PUT /items/1 - Valid update: {payload}")
        response = items_api_client.put("/items/1", json=payload)
        assert_valid_response(response)

    def test_update_item_price_zero(self, items_api_client: TestClient):
        """Update with price=0 (gt=0 violation) is rejected."""
        payload = {"price": 0}
        log_test("PUT /items/1 - Price=0 should fail gt=0")
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_update_item_discount_not_multiple(self, items_api_client: TestClient):
        """Update with discount not multiple of 5 is rejected."""
        payload = {"discount_percent": 13}
        log_test("PUT /items/1 - Discount=13 should fail multiple_of=5")
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="discount_percent")

    def test_update_item_name_empty(self, items_api_client: TestClient):
        """Update with empty name (min_length=1 violation) is rejected."""
        payload = {"name": ""}
        log_test("PUT /items/1 - Empty name should fail min_length=1")
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="name")
