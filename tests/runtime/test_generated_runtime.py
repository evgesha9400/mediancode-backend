# tests/runtime/test_generated_runtime.py
"""Runtime tests for generated APIs.

Generate APIs from YAML specs, boot them in-process with an in-memory
SQLite backend, and exercise every HTTP endpoint.  A successful request
proves syntax validity, model correctness, view definitions, parameter
handling, import correctness, and validator constraints.

Merges the HTTP-behavior tests that previously lived in
``test_api_craft/test_codegen.py`` and ``test_api_craft/test_shop_codegen.py``.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from api_craft.main import APIGenerator
from support.generated_app import load_app, load_input

pytestmark = pytest.mark.codegen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def items_api_client(tmp_path_factory):
    """Generate Items API once per session and return a TestClient."""
    tmp_path = tmp_path_factory.mktemp("items_api")
    api_input = load_input("items_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    src_path = tmp_path / "items-api" / "src"
    app = load_app(src_path)
    return TestClient(app)


@pytest.fixture(scope="session")
def shop_api_client(tmp_path_factory):
    """Generate Shop API once per session and return a TestClient."""
    tmp_path = tmp_path_factory.mktemp("shop_api")
    api_input = load_input("shop_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    src_path = tmp_path / "shop-api" / "src"
    app = load_app(src_path)
    return TestClient(app)


@pytest.fixture(scope="session")
def products_filter_api_client(tmp_path_factory):
    """Generate Products Filter API once per session and return a TestClient."""
    tmp_path = tmp_path_factory.mktemp("products_filter_api")
    api_input = load_input("products_api_filters.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    src_path = tmp_path / "products-filter-api" / "src"
    app = load_app(src_path)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_valid_response(response, expected_status: int = 200):
    """Assert response has expected status with helpful error message."""
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
    """Assert response is 422 with optional field-name check."""
    if response.status_code != 422:
        pytest.fail(
            f"Expected: 422 Validation Error\n"
            f"Got: {response.status_code}\n"
            f"Body: {response.text}"
        )

    detail = response.json().get("detail", [])

    if expected_field:
        field_names = [err.get("loc", [])[-1] for err in detail if "loc" in err]
        if expected_field not in field_names:
            pytest.fail(
                f"Expected validation error for field: {expected_field}\n"
                f"Got errors for fields: {field_names}\n"
                f"Detail: {detail}"
            )

    for err in detail:
        field = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "")
        logger.info(f"  -> PASS: 422 on '{field}': {msg}")


# =============================================================================
# Items API — basic endpoint tests
# =============================================================================


class TestItemsApi:
    """HTTP behavior tests for the Items API."""

    def test_healthcheck(self, items_api_client: TestClient):
        """Healthcheck endpoint returns OK."""
        response = items_api_client.get("/healthcheck")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_get_item(self, items_api_client: TestClient):
        """GET /items/{item_id} returns a single item."""
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
        response = items_api_client.get("/items")
        assert_valid_response(response)

        data = response.json()
        assert "items" in data, "Response missing 'items' field"
        assert "total" in data, "Response missing 'total' field"

    def test_get_items_with_query_params(self, items_api_client: TestClient):
        """GET /items accepts query parameters."""
        response = items_api_client.get("/items?limit=10&offset=5&min_price=10.0")
        assert_valid_response(response)

    def test_delete_item(self, items_api_client: TestClient):
        """DELETE /items/{item_id} deletes an item."""
        response = items_api_client.delete("/items/1")
        assert_valid_response(response)


# =============================================================================
# Items API — CreateItemRequest validation
# =============================================================================


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
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    # --- SKU Validators: min_length=3, max_length=20, pattern=^[A-Z0-9-]+$ ---

    def test_create_item_sku_too_short(self, items_api_client: TestClient):
        """SKU shorter than min_length=3 is rejected."""
        payload = {"sku": "AB", "name": "Test", "price": 10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    def test_create_item_sku_too_long(self, items_api_client: TestClient):
        """SKU longer than max_length=20 is rejected."""
        long_sku = "A" * 21
        payload = {"sku": long_sku, "name": "Test", "price": 10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    def test_create_item_sku_invalid_pattern(self, items_api_client: TestClient):
        """SKU not matching pattern ^[A-Z0-9-]+$ is rejected."""
        payload = {"sku": "invalid_sku", "name": "Test", "price": 10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="sku")

    # --- Name Validators: min_length=1, max_length=100 ---

    def test_create_item_name_empty(self, items_api_client: TestClient):
        """Empty name (min_length=1 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "", "price": 10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="name")

    def test_create_item_name_too_long(self, items_api_client: TestClient):
        """Name longer than max_length=100 is rejected."""
        long_name = "A" * 101
        payload = {"sku": "TEST-001", "name": long_name, "price": 10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="name")

    # --- Price Validators: gt=0, le=1000000 ---

    def test_create_item_price_zero(self, items_api_client: TestClient):
        """Price of 0 (gt=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_negative(self, items_api_client: TestClient):
        """Negative price (gt=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": -10.0, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_too_high(self, items_api_client: TestClient):
        """Price over 1M (le=1000000 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 1000001, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_create_item_price_at_max(self, items_api_client: TestClient):
        """Price exactly at 1M (le=1000000) is accepted."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 1000000, "quantity": 1}
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    # --- Quantity Validators: ge=0, le=100000 ---

    def test_create_item_quantity_negative(self, items_api_client: TestClient):
        """Negative quantity (ge=0 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": -1}
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="quantity")

    def test_create_item_quantity_zero(self, items_api_client: TestClient):
        """Quantity of 0 (ge=0) is accepted."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": 0}
        response = items_api_client.post("/items", json=payload)
        assert_valid_response(response)

    def test_create_item_quantity_too_high(self, items_api_client: TestClient):
        """Quantity over 100000 (le=100000 violation) is rejected."""
        payload = {"sku": "TEST-001", "name": "Test", "price": 10.0, "quantity": 100001}
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
        response = items_api_client.post("/items", json=payload)
        assert_validation_error(response, expected_field="description")


# =============================================================================
# Items API — UpdateItemRequest validation
# =============================================================================


class TestUpdateItemValidation:
    """Tests for UpdateItemRequest validators."""

    def test_update_item_valid(self, items_api_client: TestClient):
        """PUT /items/{id} with valid data succeeds."""
        payload = {"name": "Updated Name", "price": 49.99}
        response = items_api_client.put("/items/1", json=payload)
        assert_valid_response(response)

    def test_update_item_price_zero(self, items_api_client: TestClient):
        """Update with price=0 (gt=0 violation) is rejected."""
        payload = {"price": 0}
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="price")

    def test_update_item_discount_not_multiple(self, items_api_client: TestClient):
        """Update with discount not multiple of 5 is rejected."""
        payload = {"discount_percent": 13}
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="discount_percent")

    def test_update_item_name_empty(self, items_api_client: TestClient):
        """Update with empty name (min_length=1 violation) is rejected."""
        payload = {"name": ""}
        response = items_api_client.put("/items/1", json=payload)
        assert_validation_error(response, expected_field="name")


# =============================================================================
# Shop API — basic endpoint tests
# =============================================================================


class TestShopApiEndpoints:
    """Basic endpoint connectivity tests for the generated Shop API."""

    def test_healthcheck(self, shop_api_client: TestClient):
        response = shop_api_client.get("/healthcheck")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_list_products(self, shop_api_client: TestClient):
        response = shop_api_client.get("/products")
        assert_valid_response(response)
        data = response.json()
        assert isinstance(data, list)

    def test_get_product_not_found(self, shop_api_client: TestClient):
        response = shop_api_client.get(
            "/products/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 404

    def test_create_product_valid(self, shop_api_client: TestClient):
        payload = {
            "name": "Widget",
            "sku": "WD-0001",
            "price": 29.99,
            "weight": 1.5,
            "quantity": 100,
            "min_order_quantity": 1,
            "in_stock": True,
            "product_url": "https://example.com/widget",
            "release_date": "2026-01-01",
            "created_at": "2026-01-01T00:00:00",
            "tracking_id": "00000000-0000-0000-0000-000000000099",
        }
        response = shop_api_client.post("/products", json=payload)
        assert_valid_response(response)

    def test_list_customers(self, shop_api_client: TestClient):
        response = shop_api_client.get("/customers")
        assert_valid_response(response)
        data = response.json()
        assert isinstance(data, list)

    def test_create_customer_valid(self, shop_api_client: TestClient):
        payload = {
            "customer_id": 1,
            "customer_name": "Jane Doe",
            "email": "jane@example.com",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
        }
        response = shop_api_client.post("/customers", json=payload)
        assert_valid_response(response)

    def test_get_customer_not_found(self, shop_api_client: TestClient):
        response = shop_api_client.get("/customers/999")
        assert response.status_code == 404

    def test_update_customer_not_found(self, shop_api_client: TestClient):
        payload = {
            "customer_id": 1,
            "customer_name": "Jane Doe",
            "email": "jane@example.com",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
        }
        response = shop_api_client.patch("/customers/999", json=payload)
        assert response.status_code == 404


# =============================================================================
# Shop API — Product constraint validation
# =============================================================================


class TestProductConstraints:
    """Tests for Product field constraint validation."""

    def _valid_product(self, **overrides) -> dict:
        base = {
            "name": "Test Product",
            "sku": "TS-0001",
            "price": 29.99,
            "weight": 1.5,
            "quantity": 50,
            "min_order_quantity": 1,
            "in_stock": True,
            "product_url": "https://example.com/product",
            "release_date": "2026-01-01",
            "created_at": "2026-01-01T00:00:00",
            "tracking_id": "00000000-0000-0000-0000-000000000001",
        }
        base.update(overrides)
        return base

    def test_name_empty_rejected(self, shop_api_client: TestClient):
        """Empty name (min_length=1) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(name="")
        )
        assert_validation_error(response, expected_field="name")

    def test_name_too_long_rejected(self, shop_api_client: TestClient):
        """Name over 150 chars (max_length=150) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(name="A" * 151)
        )
        assert_validation_error(response, expected_field="name")

    def test_sku_invalid_pattern_rejected(self, shop_api_client: TestClient):
        r"""SKU not matching ^[A-Z]{2}-\d{4}$ is rejected (after uppercase normalization)."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(sku="invalid sku!")
        )
        assert_validation_error(response, expected_field="sku")

    def test_price_zero_rejected(self, shop_api_client: TestClient):
        """Price of 0 (gt=0) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(price=0)
        )
        assert_validation_error(response, expected_field="price")

    def test_price_negative_rejected(self, shop_api_client: TestClient):
        """Negative price (gt=0) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(price=-10.0)
        )
        assert_validation_error(response, expected_field="price")

    def test_quantity_negative_rejected(self, shop_api_client: TestClient):
        """Negative quantity (ge=0) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(quantity=-1)
        )
        assert_validation_error(response, expected_field="quantity")

    def test_min_order_zero_rejected(self, shop_api_client: TestClient):
        """min_order_quantity of 0 (ge=1) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(min_order_quantity=0)
        )
        assert_validation_error(response, expected_field="min_order_quantity")

    def test_max_order_over_limit_rejected(self, shop_api_client: TestClient):
        """max_order_quantity over 1000 (le=1000) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(max_order_quantity=1001)
        )
        assert_validation_error(response, expected_field="max_order_quantity")

    def test_discount_not_multiple_of_5_rejected(self, shop_api_client: TestClient):
        """Discount not multiple of 5 is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(
                discount_percent=7,
                sale_price=19.99,
                sale_end_date="2026-06-01",
            ),
        )
        assert_validation_error(response, expected_field="discount_percent")

    def test_discount_over_100_rejected(self, shop_api_client: TestClient):
        """Discount over 100 (le=100) is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(
                discount_percent=105,
                sale_price=19.99,
                sale_end_date="2026-06-01",
            ),
        )
        assert_validation_error(response, expected_field="discount_percent")

    def test_weight_clamped_by_validator(self, shop_api_client: TestClient):
        """Negative weight is clamped to 0 by the clamp_weight field validator."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(weight=-1.0)
        )
        assert_valid_response(response)


# =============================================================================
# Shop API — Customer constraint validation
# =============================================================================


class TestCustomerConstraints:
    """Tests for Customer field constraint validation."""

    def _valid_customer(self, **overrides) -> dict:
        base = {
            "customer_id": 1,
            "customer_name": "Test Customer",
            "email": "test@example.com",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
        }
        base.update(overrides)
        return base

    def test_name_empty_rejected(self, shop_api_client: TestClient):
        """Empty customer_name (min_length=1) is rejected."""
        response = shop_api_client.post(
            "/customers", json=self._valid_customer(customer_name="")
        )
        assert_validation_error(response, expected_field="customer_name")

    def test_phone_too_short_rejected(self, shop_api_client: TestClient):
        """Phone shorter than min_length=7 is rejected."""
        response = shop_api_client.post(
            "/customers", json=self._valid_customer(phone="123")
        )
        assert_validation_error(response, expected_field="phone")


# =============================================================================
# Shop API — Product model validators
# =============================================================================


class TestProductModelValidators:
    """Tests for Product model validators."""

    def _valid_product(self, **overrides) -> dict:
        base = {
            "name": "Test Product",
            "sku": "TS-0001",
            "price": 29.99,
            "weight": 1.5,
            "quantity": 50,
            "min_order_quantity": 1,
            "in_stock": True,
            "product_url": "https://example.com/product",
            "release_date": "2026-01-01",
            "created_at": "2026-01-01T00:00:00",
            "tracking_id": "00000000-0000-0000-0000-000000000001",
        }
        base.update(overrides)
        return base

    def test_order_quantity_comparison_rejects(self, shop_api_client: TestClient):
        """min_order_quantity >= max_order_quantity is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(min_order_quantity=500, max_order_quantity=500),
        )
        assert_validation_error(response)

    def test_discount_mutual_exclusivity_rejects_both(
        self, shop_api_client: TestClient
    ):
        """Having both discount_percent and discount_amount is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(
                discount_percent=10,
                discount_amount=5.00,
                sale_price=19.99,
                sale_end_date="2026-06-01",
            ),
        )
        assert_validation_error(response)

    def test_sale_fields_all_or_none_rejects_partial(
        self, shop_api_client: TestClient
    ):
        """Providing sale_price without sale_end_date is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(sale_price=19.99),
        )
        assert_validation_error(response)

    def test_discount_conditional_required_rejects(self, shop_api_client: TestClient):
        """discount_percent without sale_price set is rejected."""
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(discount_percent=10),
        )
        assert_validation_error(response)
