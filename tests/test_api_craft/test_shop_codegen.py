# tests/test_api_craft/test_shop_codegen.py
"""Shop API codegen tests for api_craft code generation.

Tests the full generation pipeline with a rich Shop API featuring:
- Product and Customer entities with diverse field types
- Field validators (trim, normalize, clamp)
- Model validators (range comparison, mutual exclusivity, all-or-none, conditional)
- Multiple type support (decimal.Decimal, datetime.time, EmailStr, HttpUrl)
- Database generation (ORM models, migrations, docker-compose)
"""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.codegen

from api_craft.main import APIGenerator
from api_craft.transformers import transform_api
from .conftest import SPECS_PATH, load_input

logger = logging.getLogger(__name__)


def log_test(context: str):
    logger.info(f"Testing: {context}")


def assert_valid_response(response, expected_status: int = 200):
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
# Artifact dump tests
# =============================================================================


class TestShopApiArtifacts:
    """Tests that verify InputAPI, TemplateAPI, and generated file structure."""

    def test_input_api_dump(self):
        """Load YAML and verify InputAPI structure."""
        api_input = load_input("shop_api.yaml")
        data = api_input.model_dump()

        assert data["name"] == "ShopApi"
        assert len(data["objects"]) == 2
        assert len(data["endpoints"]) == 9
        assert len(data["tags"]) == 2

        # Verify Product has 16 fields
        product = next(o for o in data["objects"] if o["name"] == "Product")
        assert len(product["fields"]) == 16

        # Verify Customer has 8 fields
        customer = next(o for o in data["objects"] if o["name"] == "Customer")
        assert len(customer["fields"]) == 8

        # Verify model validators on Product
        assert len(product["model_validators"]) == 4

        # Customer has 1 model validator
        assert len(customer["model_validators"]) == 1

        logger.info("InputAPI dump verified: 2 objects, 9 endpoints, 2 tags")

    def test_template_api_dump(self):
        """Transform InputAPI and verify TemplateAPI naming conventions."""
        api_input = load_input("shop_api.yaml")
        template_api = transform_api(api_input)
        data = template_api.model_dump()

        assert data["snake_name"] == "shop_api"
        assert data["kebab_name"] == "shop-api"
        assert data["camel_name"] == "ShopApi"

        assert len(data["models"]) == 2
        assert len(data["views"]) == 9

        logger.info("TemplateAPI dump verified: naming and counts correct")

    def test_generated_files(self, tmp_path: Path):
        """Generate project and verify all expected files exist."""
        api_input = load_input("shop_api.yaml")
        APIGenerator().generate(api_input, path=str(tmp_path))

        project_dir = tmp_path / "shop-api"
        src_dir = project_dir / "src"

        expected_files = [
            # Standard src files
            src_dir / "models.py",
            src_dir / "views.py",
            src_dir / "main.py",
            src_dir / "path.py",
            # Database files
            src_dir / "orm_models.py",
            src_dir / "database.py",
            # Project root files
            project_dir / "pyproject.toml",
            project_dir / "Makefile",
            project_dir / "Dockerfile",
            project_dir / "docker-compose.yml",
            project_dir / "alembic.ini",
            # Migrations
            project_dir / "migrations" / "env.py",
        ]

        for f in expected_files:
            assert f.exists(), f"Missing generated file: {f}"

        # Verify pyproject.toml includes extra deps required by model types
        pyproject_content = (project_dir / "pyproject.toml").read_text()
        models_content = (src_dir / "models.py").read_text()

        from api_craft.extractors import TYPE_EXTRA_DEPENDENCIES

        for type_name, dep in TYPE_EXTRA_DEPENDENCIES.items():
            if type_name in models_content:
                pkg_name = dep.split(" ")[0]
                assert pkg_name in pyproject_content, (
                    f"Generated models.py uses {type_name} but pyproject.toml "
                    f"is missing required dependency: {dep}"
                )

        # Log generated content for debugging
        logger.info(f"Generated models.py:\n{models_content}")

        views_content = (src_dir / "views.py").read_text()
        logger.info(f"Generated views.py:\n{views_content}")


# =============================================================================
# Basic endpoint tests
# =============================================================================


class TestShopApiEndpoints:
    """Basic endpoint connectivity tests for the generated Shop API."""

    def test_healthcheck(self, shop_api_client: TestClient):
        log_test("GET /healthcheck")
        response = shop_api_client.get("/healthcheck")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_list_products(self, shop_api_client: TestClient):
        log_test("GET /products")
        response = shop_api_client.get("/products")
        assert_valid_response(response)
        data = response.json()
        assert isinstance(data, list)

    def test_get_product_not_found(self, shop_api_client: TestClient):
        log_test("GET /products/{tracking_id} - not found")
        response = shop_api_client.get("/products/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 404

    def test_create_product_valid(self, shop_api_client: TestClient):
        log_test("POST /products - valid payload")
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
        log_test("GET /customers")
        response = shop_api_client.get("/customers")
        assert_valid_response(response)
        data = response.json()
        assert isinstance(data, list)

    def test_create_customer_valid(self, shop_api_client: TestClient):
        log_test("POST /customers - valid payload")
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
        log_test("GET /customers/{email} - not found")
        response = shop_api_client.get("/customers/test@example.com")
        assert response.status_code == 404

    def test_update_customer_not_found(self, shop_api_client: TestClient):
        log_test("PATCH /customers/{email} - not found")
        payload = {
            "customer_id": 1,
            "customer_name": "Jane Doe",
            "email": "jane@example.com",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
        }
        response = shop_api_client.patch("/customers/test@example.com", json=payload)
        assert response.status_code == 404


# =============================================================================
# Product constraint validation tests
# =============================================================================


class TestProductConstraints:
    """Tests for Product field constraint validation."""

    def _valid_product(self, **overrides) -> dict:
        """Build a valid product payload with optional overrides."""
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
        response = shop_api_client.post("/products", json=self._valid_product(name=""))
        assert_validation_error(response, expected_field="name")

    def test_name_too_long_rejected(self, shop_api_client: TestClient):
        """Name over 150 chars (max_length=150) is rejected."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(name="A" * 151)
        )
        assert_validation_error(response, expected_field="name")

    def test_sku_invalid_pattern_rejected(self, shop_api_client: TestClient):
        """SKU not matching ^[A-Z]{2}-\\d{4}$ is rejected (after uppercase normalization)."""
        response = shop_api_client.post(
            "/products", json=self._valid_product(sku="invalid sku!")
        )
        assert_validation_error(response, expected_field="sku")

    def test_price_zero_rejected(self, shop_api_client: TestClient):
        """Price of 0 (gt=0) is rejected."""
        response = shop_api_client.post("/products", json=self._valid_product(price=0))
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
        # The clamp_weight field validator (mode=before) clamps the value to [0, 1000],
        # so -1.0 becomes 0.0, which passes the ge=0 constraint.
        assert_valid_response(response)


# =============================================================================
# Customer constraint validation tests
# =============================================================================


class TestCustomerConstraints:
    """Tests for Customer field constraint validation."""

    def _valid_customer(self, **overrides) -> dict:
        """Build a valid customer payload with optional overrides."""
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
# Product model validator tests
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
        log_test("Model validator: order quantity range")
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(min_order_quantity=500, max_order_quantity=500),
        )
        assert_validation_error(response)

    def test_discount_mutual_exclusivity_rejects_both(
        self, shop_api_client: TestClient
    ):
        """Having both discount_percent and discount_amount is rejected."""
        log_test("Model validator: discount exclusivity")
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

    def test_sale_fields_all_or_none_rejects_partial(self, shop_api_client: TestClient):
        """Providing sale_price without sale_end_date is rejected."""
        log_test("Model validator: sale fields all-or-none")
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(sale_price=19.99),
        )
        assert_validation_error(response)

    def test_discount_conditional_required_rejects(self, shop_api_client: TestClient):
        """discount_percent without sale_price set is rejected."""
        log_test("Model validator: discount requires sale_price")
        response = shop_api_client.post(
            "/products",
            json=self._valid_product(discount_percent=10),
        )
        assert_validation_error(response)
