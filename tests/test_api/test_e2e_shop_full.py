"""E2E test: full Shop API lifecycle — CRUD, generate, verify generated code.

Phases:
 1. Read catalogues (types, constraints, validator templates)
 2. Create namespace
 3. Create 23 fields with constraints and validators
 4. Read and verify fields
 5. Update fields (constraint change + add validator)
 6. Create objects with field references and model validators
 7. Read and verify objects
 8. Update object (change field optionality)
 9. Create API
10. Update API
11. Create 7 endpoints (UUID path params → JSONB round-trip)
12. Read and verify endpoints
13. Update endpoint (UUID-in-JSONB regression test)
14. Generate API
15. Verify ZIP structure
16. Load generated app and verify all endpoints
17. Product field constraint validation
18. Customer field constraint validation
19. Product model validators
20. Customer model validator
21-26. Cleanup
"""

import importlib.util
import io
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_current_user
from api.main import app
from api.models.database import (
    ApiModel,
    FieldModel,
    GenerationModel,
    Namespace,
    ObjectDefinition,
    UserModel,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_e2e_shop_full"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def client():
    """Module-scoped HTTP client with auth override and DB cleanup."""
    app.dependency_overrides[get_current_user] = lambda: TEST_CLERK_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/v1",
    ) as c:
        yield c

    app.dependency_overrides.pop(get_current_user, None)

    # --- DB cleanup (handles both success and partial-failure cases) ---
    from api.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.clerk_id == TEST_CLERK_ID)
        )
        user = result.scalar_one_or_none()
        if user:
            uid = user.id
            await session.execute(
                delete(GenerationModel).where(GenerationModel.user_id == uid)
            )
            await session.execute(delete(ApiModel).where(ApiModel.user_id == uid))
            await session.execute(
                delete(ObjectDefinition).where(ObjectDefinition.user_id == uid)
            )
            await session.execute(delete(FieldModel).where(FieldModel.user_id == uid))
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

PRODUCT_FIELDS = [
    {
        "name": "name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "200")],
        "validators": [("Trim", None), ("Normalize Whitespace", None)],
    },
    {
        "name": "sku",
        "type": "str",
        "constraints": [("pattern", r"^[A-Z]{2}-\d{4}$")],
        "validators": [("Normalize Case", {"case": "upper"})],
    },
    {
        "name": "price",
        "type": "Decimal",
        "constraints": [("gt", "0")],
        "validators": [("Round Decimal", {"places": "2"})],
    },
    {
        "name": "sale_price",
        "type": "Decimal",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "sale_end_date",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "weight",
        "type": "float",
        "constraints": [("ge", "0"), ("lt", "1000")],
        "validators": [("Clamp to Range", {"min_value": "0", "max_value": "1000"})],
    },
    {
        "name": "quantity",
        "type": "int",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "min_order_quantity",
        "type": "int",
        "constraints": [("ge", "1")],
        "validators": [],
    },
    {
        "name": "max_order_quantity",
        "type": "int",
        "constraints": [("le", "1000")],
        "validators": [],
    },
    {
        "name": "discount_percent",
        "type": "int",
        "constraints": [("ge", "0"), ("le", "100"), ("multiple_of", "5")],
        "validators": [],
    },
    {
        "name": "discount_amount",
        "type": "Decimal",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "in_stock",
        "type": "bool",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "product_url",
        "type": "HttpUrl",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "release_date",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "created_at",
        "type": "datetime",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "tracking_id",
        "type": "uuid",
        "constraints": [],
        "validators": [],
    },
]

CUSTOMER_FIELDS = [
    {
        "name": "customer_name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "100")],
        "validators": [("Trim", None), ("Normalize Case", {"case": "title"})],
    },
    {
        "name": "email",
        "type": "EmailStr",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "phone",
        "type": "str",
        "constraints": [("min_length", "7"), ("max_length", "15")],
        "validators": [],
    },
    {
        "name": "date_of_birth",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "last_login_time",
        "type": "time",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "is_active",
        "type": "bool",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "registered_at",
        "type": "datetime",
        "constraints": [],
        "validators": [],
    },
]

ALL_FIELDS = PRODUCT_FIELDS + CUSTOMER_FIELDS

PRODUCT_OPTIONAL = {
    "sale_price",
    "sale_end_date",
    "min_order_quantity",
    "max_order_quantity",
    "discount_percent",
    "discount_amount",
}

CUSTOMER_OPTIONAL = {"email", "phone"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_app(src_path: Path):
    """Dynamically import the FastAPI app from a generated project."""
    prefix = f"_gen_{uuid.uuid4().hex[:8]}"
    sys.path.insert(0, str(src_path))

    modules_to_cleanup = []
    try:
        module_files = ["models", "path", "query", "views", "main"]
        for module_name in module_files:
            module_path = src_path / f"{module_name}.py"
            if not module_path.exists():
                continue

            unique_name = f"{prefix}_{module_name}"
            spec = importlib.util.spec_from_file_location(unique_name, module_path)
            module = importlib.util.module_from_spec(spec)

            sys.modules[unique_name] = module
            sys.modules[module_name] = module
            modules_to_cleanup.append(unique_name)
            modules_to_cleanup.append(module_name)

            spec.loader.exec_module(module)

        return sys.modules["main"].app
    finally:
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))
        for mod_name in modules_to_cleanup:
            sys.modules.pop(mod_name, None)


def assert_gen_response(response, expected_status: int = 200):
    """Assert response status code with helpful error messages."""
    if response.status_code != expected_status:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        pytest.fail(
            f"Expected: {expected_status}\nGot: {response.status_code}\nDetail: {detail}"
        )


def assert_gen_validation_error(response, expected_field: str | None = None):
    """Assert 422 with optional field name check."""
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


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestShopApiFullE2E:
    """Full Shop API E2E: CRUD -> Generate -> Verify Generated Code."""

    # Shared state across test phases
    type_ids: dict[str, str] = {}
    constraint_ids: dict[str, str] = {}
    fv_template_ids: dict[str, str] = {}
    mv_template_ids: dict[str, str] = {}
    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    product_id: str = ""
    customer_id: str = ""
    api_id: str = ""
    endpoint_ids: dict[str, str] = {}
    zip_bytes: bytes = b""
    generated_dir: str = ""
    gen_client: TestClient | None = None

    # --- Phase 1: Read catalogues ---

    async def test_phase_01_read_catalogues(self, client: AsyncClient):
        """Read all catalogue data and store IDs for later phases."""
        cls = TestShopApiFullE2E

        # Types (expect all 11)
        resp = await client.get("/types")
        assert resp.status_code == 200
        types = resp.json()
        assert len(types) >= 11
        cls.type_ids = {t["name"]: t["id"] for t in types}
        for name in (
            "str",
            "int",
            "float",
            "bool",
            "datetime",
            "uuid",
            "EmailStr",
            "HttpUrl",
            "Decimal",
            "date",
            "time",
        ):
            assert name in cls.type_ids, f"Missing type: {name}"

        # Field constraints (expect all 8)
        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        constraints = resp.json()
        assert len(constraints) >= 8
        cls.constraint_ids = {c["name"]: c["id"] for c in constraints}
        for name in (
            "max_length",
            "min_length",
            "pattern",
            "gt",
            "ge",
            "lt",
            "le",
            "multiple_of",
        ):
            assert name in cls.constraint_ids, f"Missing constraint: {name}"

        # Field validator templates (expect all 10)
        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        fv_templates = resp.json()
        assert len(fv_templates) >= 10
        cls.fv_template_ids = {t["name"]: t["id"] for t in fv_templates}
        for name in (
            "Trim",
            "Normalize Whitespace",
            "Normalize Case",
            "Round Decimal",
            "Clamp to Range",
            "Trim To Length",
        ):
            assert name in cls.fv_template_ids, f"Missing FV template: {name}"

        # Model validator templates (expect all 5)
        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        mv_templates = resp.json()
        assert len(mv_templates) >= 5
        cls.mv_template_ids = {t["name"]: t["id"] for t in mv_templates}
        for name in (
            "Field Comparison",
            "Mutual Exclusivity",
            "All Or None",
            "Conditional Required",
            "At Least One Required",
        ):
            assert name in cls.mv_template_ids, f"Missing MV template: {name}"

    # --- Phase 2: Create namespace ---

    async def test_phase_02_create_namespace(self, client: AsyncClient):
        """Create the Shop namespace and verify it appears in the list."""
        cls = TestShopApiFullE2E

        resp = await client.post("/namespaces", json={"name": "Shop"})
        assert resp.status_code == 201
        ns = resp.json()
        assert ns["name"] == "Shop"
        assert ns["isDefault"] is False
        cls.namespace_id = ns["id"]

        # Verify both namespaces present
        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" in names
        assert "Global" in names

    # --- Phase 3: Create fields ---

    async def test_phase_03_create_fields(self, client: AsyncClient):
        """Create all 23 fields with types, constraints, and validators."""
        cls = TestShopApiFullE2E

        for field_def in ALL_FIELDS:
            payload = {
                "namespaceId": cls.namespace_id,
                "name": field_def["name"],
                "typeId": cls.type_ids[field_def["type"]],
                "constraints": [
                    {"constraintId": cls.constraint_ids[name], "value": value}
                    for name, value in field_def["constraints"]
                ],
                "validators": [
                    {"templateId": cls.fv_template_ids[name], "parameters": params}
                    for name, params in field_def["validators"]
                ],
            }
            resp = await client.post("/fields", json=payload)
            assert (
                resp.status_code == 201
            ), f"Failed to create field '{field_def['name']}': {resp.text}"
            field = resp.json()
            assert field["typeId"] == cls.type_ids[field_def["type"]]
            assert len(field["constraints"]) == len(field_def["constraints"])
            assert len(field["validators"]) == len(field_def["validators"])
            cls.field_ids[field_def["name"]] = field["id"]

        assert len(cls.field_ids) == 23

    # --- Phase 4: Read and verify fields ---

    async def test_phase_04_read_fields(self, client: AsyncClient):
        """Verify all 23 fields via list and individual GET."""
        cls = TestShopApiFullE2E

        resp = await client.get(f"/fields?namespace_id={cls.namespace_id}")
        assert resp.status_code == 200
        fields = resp.json()
        assert len(fields) == 23

        # Spot-check individual field detail
        resp = await client.get(f"/fields/{cls.field_ids['name']}")
        assert resp.status_code == 200
        field = resp.json()
        assert field["name"] == "name"
        assert field["typeId"] == cls.type_ids["str"]
        assert len(field["constraints"]) == 2  # min_length, max_length
        assert len(field["validators"]) == 2  # Trim, Normalize Whitespace

    # --- Phase 5: Update fields ---

    async def test_phase_05_update_fields(self, client: AsyncClient):
        """Update name field constraints and add validator to customer_name."""
        cls = TestShopApiFullE2E

        # Update name: change max_length from 200 to 150
        resp = await client.put(
            f"/fields/{cls.field_ids['name']}",
            json={
                "constraints": [
                    {
                        "constraintId": cls.constraint_ids["min_length"],
                        "value": "1",
                    },
                    {
                        "constraintId": cls.constraint_ids["max_length"],
                        "value": "150",
                    },
                ],
            },
        )
        assert resp.status_code == 200

        # Verify via GET
        resp = await client.get(f"/fields/{cls.field_ids['name']}")
        assert resp.status_code == 200
        field = resp.json()
        max_len = next(c for c in field["constraints"] if c["name"] == "max_length")
        assert max_len["value"] == "150"

        # Update customer_name: add Trim To Length (3 validators total)
        resp = await client.put(
            f"/fields/{cls.field_ids['customer_name']}",
            json={
                "validators": [
                    {"templateId": cls.fv_template_ids["Trim"]},
                    {
                        "templateId": cls.fv_template_ids["Normalize Case"],
                        "parameters": {"case": "title"},
                    },
                    {
                        "templateId": cls.fv_template_ids["Trim To Length"],
                        "parameters": {"max_length": "100"},
                    },
                ],
            },
        )
        assert resp.status_code == 200

        # Verify via GET
        resp = await client.get(f"/fields/{cls.field_ids['customer_name']}")
        assert resp.status_code == 200
        field = resp.json()
        assert len(field["validators"]) == 3

    # --- Phase 6: Create objects ---

    async def test_phase_06_create_objects(self, client: AsyncClient):
        """Create Product (16 fields, 4 model validators) and Customer (7 fields, 1 model validator)."""
        cls = TestShopApiFullE2E

        # --- Product ---
        product_fields = [
            {
                "fieldId": cls.field_ids[f["name"]],
                "optional": f["name"] in PRODUCT_OPTIONAL,
            }
            for f in PRODUCT_FIELDS
        ]
        product_validators = [
            {
                "templateId": cls.mv_template_ids["Field Comparison"],
                "parameters": {"operator": "<"},
                "fieldMappings": {
                    "field_a": "min_order_quantity",
                    "field_b": "max_order_quantity",
                },
            },
            {
                "templateId": cls.mv_template_ids["Mutual Exclusivity"],
                "fieldMappings": {
                    "field_a": "discount_percent",
                    "field_b": "discount_amount",
                },
            },
            {
                "templateId": cls.mv_template_ids["All Or None"],
                "fieldMappings": {
                    "field_a": "sale_price",
                    "field_b": "sale_end_date",
                },
            },
            {
                "templateId": cls.mv_template_ids["Conditional Required"],
                "fieldMappings": {
                    "trigger_field": "discount_percent",
                    "dependent_field": "sale_price",
                },
            },
        ]

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Product",
                "description": "Shop product",
                "fields": product_fields,
                "validators": product_validators,
            },
        )
        assert resp.status_code == 201, f"Failed to create Product: {resp.text}"
        product = resp.json()
        assert len(product["fields"]) == 16
        assert len(product["validators"]) == 4
        cls.product_id = product["id"]

        # --- Customer ---
        customer_fields = [
            {
                "fieldId": cls.field_ids[f["name"]],
                "optional": f["name"] in CUSTOMER_OPTIONAL,
            }
            for f in CUSTOMER_FIELDS
        ]
        customer_validators = [
            {
                "templateId": cls.mv_template_ids["At Least One Required"],
                "fieldMappings": {
                    "field_a": "email",
                    "field_b": "phone",
                },
            },
        ]

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Customer",
                "description": "Shop customer",
                "fields": customer_fields,
                "validators": customer_validators,
            },
        )
        assert resp.status_code == 201, f"Failed to create Customer: {resp.text}"
        customer = resp.json()
        assert len(customer["fields"]) == 7
        assert len(customer["validators"]) == 1
        cls.customer_id = customer["id"]

    # --- Phase 7: Read and verify objects ---

    async def test_phase_07_read_objects(self, client: AsyncClient):
        """Verify both objects via list and individual GET."""
        cls = TestShopApiFullE2E

        resp = await client.get(f"/objects?namespace_id={cls.namespace_id}")
        assert resp.status_code == 200
        objects = resp.json()
        assert len(objects) == 2

        # Product detail
        resp = await client.get(f"/objects/{cls.product_id}")
        assert resp.status_code == 200
        product = resp.json()
        assert product["name"] == "Product"
        assert len(product["fields"]) == 16
        assert len(product["validators"]) == 4

        # Customer detail
        resp = await client.get(f"/objects/{cls.customer_id}")
        assert resp.status_code == 200
        customer = resp.json()
        assert customer["name"] == "Customer"
        assert len(customer["fields"]) == 7
        assert len(customer["validators"]) == 1

    # --- Phase 8: Update object ---

    async def test_phase_08_update_object(self, client: AsyncClient):
        """Make min_order_quantity required (was optional) on Product."""
        cls = TestShopApiFullE2E

        # Get current fields to preserve them
        resp = await client.get(f"/objects/{cls.product_id}")
        product = resp.json()
        updated_fields = []
        for f in product["fields"]:
            optional = f["optional"]
            if f["fieldId"] == cls.field_ids["min_order_quantity"]:
                optional = False
            updated_fields.append({"fieldId": f["fieldId"], "optional": optional})

        resp = await client.put(
            f"/objects/{cls.product_id}",
            json={"fields": updated_fields},
        )
        assert resp.status_code == 200

        # Verify change persisted
        resp = await client.get(f"/objects/{cls.product_id}")
        assert resp.status_code == 200
        product = resp.json()
        moq = next(
            f
            for f in product["fields"]
            if f["fieldId"] == cls.field_ids["min_order_quantity"]
        )
        assert moq["optional"] is False

    # --- Phase 9: Create API ---

    async def test_phase_09_create_api(self, client: AsyncClient):
        """Create the Shop API and verify it appears in the list."""
        cls = TestShopApiFullE2E

        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.namespace_id,
                "title": "ShopApi",
                "version": "1.0.0",
                "description": "Online shop with products and customers",
            },
        )
        assert resp.status_code == 201, f"Failed to create API: {resp.text}"
        api = resp.json()
        assert api["title"] == "ShopApi"
        assert api["version"] == "1.0.0"
        cls.api_id = api["id"]

        # Verify in list
        resp = await client.get("/apis")
        assert resp.status_code == 200
        assert any(a["id"] == cls.api_id for a in resp.json())

    # --- Phase 10: Update API ---

    async def test_phase_10_update_api(self, client: AsyncClient):
        """Update the API description and verify via GET."""
        cls = TestShopApiFullE2E

        resp = await client.put(
            f"/apis/{cls.api_id}",
            json={"description": "Complete online shop API"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Complete online shop API"

        resp = await client.get(f"/apis/{cls.api_id}")
        assert resp.status_code == 200
        assert resp.json()["description"] == "Complete online shop API"

    # --- Phase 11: Create endpoints ---

    async def test_phase_11_create_endpoints(self, client: AsyncClient):
        """Create all 7 endpoints with UUID path params (JSONB round-trip)."""
        cls = TestShopApiFullE2E

        endpoints = [
            {
                "apiId": cls.api_id,
                "method": "GET",
                "path": "/products",
                "description": "List all products",
                "tagName": "Products",
                "pathParams": [],
                "responseBodyObjectId": cls.product_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
            {
                "apiId": cls.api_id,
                "method": "GET",
                "path": "/products/{tracking_id}",
                "description": "Get product by tracking ID",
                "tagName": "Products",
                "pathParams": [
                    {
                        "name": "tracking_id",
                        "fieldId": cls.field_ids["tracking_id"],
                    }
                ],
                "responseBodyObjectId": cls.product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": cls.api_id,
                "method": "POST",
                "path": "/products",
                "description": "Create a product",
                "tagName": "Products",
                "pathParams": [],
                "requestBodyObjectId": cls.product_id,
                "responseBodyObjectId": cls.product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": cls.api_id,
                "method": "PUT",
                "path": "/products/{tracking_id}",
                "description": "Update a product",
                "tagName": "Products",
                "pathParams": [
                    {
                        "name": "tracking_id",
                        "fieldId": cls.field_ids["tracking_id"],
                    }
                ],
                "requestBodyObjectId": cls.product_id,
                "responseBodyObjectId": cls.product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": cls.api_id,
                "method": "DELETE",
                "path": "/products/{tracking_id}",
                "description": "Delete a product",
                "tagName": "Products",
                "pathParams": [
                    {
                        "name": "tracking_id",
                        "fieldId": cls.field_ids["tracking_id"],
                    }
                ],
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": cls.api_id,
                "method": "GET",
                "path": "/customers",
                "description": "List all customers",
                "tagName": "Customers",
                "pathParams": [],
                "responseBodyObjectId": cls.customer_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
            {
                "apiId": cls.api_id,
                "method": "PATCH",
                "path": "/customers/{email}",
                "description": "Update a customer by email",
                "tagName": "Customers",
                "pathParams": [
                    {
                        "name": "email",
                        "fieldId": cls.field_ids["email"],
                    }
                ],
                "requestBodyObjectId": cls.customer_id,
                "responseBodyObjectId": cls.customer_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
        ]

        for ep in endpoints:
            resp = await client.post("/endpoints", json=ep)
            assert (
                resp.status_code == 201
            ), f"Failed: {ep['method']} {ep['path']}: {resp.text}"
            created = resp.json()
            assert created["method"] == ep["method"]
            assert created["path"] == ep["path"]
            assert created["responseShape"] == ep["responseShape"]
            # Verify path params UUID round-trip through JSONB
            assert len(created["pathParams"]) == len(ep["pathParams"])
            for i, pp in enumerate(ep["pathParams"]):
                assert created["pathParams"][i]["name"] == pp["name"]
                assert created["pathParams"][i]["fieldId"] == pp["fieldId"]
            cls.endpoint_ids[f"{ep['method']} {ep['path']}"] = created["id"]

        assert len(cls.endpoint_ids) == 7

    # --- Phase 12: Read and verify endpoints ---

    async def test_phase_12_read_endpoints(self, client: AsyncClient):
        """Verify all 7 endpoints via list and individual GET."""
        cls = TestShopApiFullE2E

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        endpoints = resp.json()
        assert len(endpoints) == 7

        # Verify endpoint with UUID path param
        ep_id = cls.endpoint_ids["GET /products/{tracking_id}"]
        resp = await client.get(f"/endpoints/{ep_id}")
        assert resp.status_code == 200
        ep = resp.json()
        assert ep["method"] == "GET"
        assert ep["path"] == "/products/{tracking_id}"
        assert len(ep["pathParams"]) == 1
        assert ep["pathParams"][0]["fieldId"] == cls.field_ids["tracking_id"]

    # --- Phase 13: Update endpoint (UUID-in-JSONB regression) ---

    async def test_phase_13_update_endpoint(self, client: AsyncClient):
        """Update endpoint path — the exact operation that caused the UUID bug."""
        cls = TestShopApiFullE2E
        put_ep_id = cls.endpoint_ids["PUT /products/{tracking_id}"]

        resp = await client.put(
            f"/endpoints/{put_ep_id}",
            json={
                "path": "/items/{tracking_id}",
                "pathParams": [
                    {
                        "name": "tracking_id",
                        "fieldId": cls.field_ids["tracking_id"],
                    }
                ],
            },
        )
        assert resp.status_code == 200

        # Verify path changed and UUID survived JSONB round-trip
        resp = await client.get(f"/endpoints/{put_ep_id}")
        assert resp.status_code == 200
        ep = resp.json()
        assert ep["path"] == "/items/{tracking_id}"
        assert ep["pathParams"][0]["fieldId"] == cls.field_ids["tracking_id"]

    # --- Phase 14: Generate API ---

    async def test_phase_14_generate_api(self, client: AsyncClient):
        """Call the generate endpoint and receive the ZIP file."""
        cls = TestShopApiFullE2E

        resp = await client.post(f"/apis/{cls.api_id}/generate")
        assert resp.status_code == 200, f"Generate failed: {resp.text}"
        assert "application/zip" in resp.headers.get("content-type", "")
        assert "content-disposition" in resp.headers
        assert "shopapi" in resp.headers["content-disposition"].lower()
        assert len(resp.content) > 0
        cls.zip_bytes = resp.content

    # --- Phase 15: Verify ZIP structure ---

    async def test_phase_15_verify_zip_structure(self, client: AsyncClient):
        """Extract ZIP and verify file structure, no __pycache__, .py compiles."""
        cls = TestShopApiFullE2E

        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            names = zf.namelist()

            # No __pycache__ directories
            assert not any(
                "__pycache__" in n for n in names
            ), f"Found __pycache__ in ZIP: {[n for n in names if '__pycache__' in n]}"

            # Required files present
            required_files = [
                "src/models.py",
                "src/views.py",
                "src/main.py",
                "src/path.py",
                "pyproject.toml",
                "Makefile",
                "Dockerfile",
            ]
            for required in required_files:
                assert required in names, f"Missing file in ZIP: {required}"

        # Extract to temp directory
        cls.generated_dir = tempfile.mkdtemp(prefix="shop_api_gen_")
        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            zf.extractall(cls.generated_dir)

        # All .py files must compile without errors
        gen_path = Path(cls.generated_dir)
        for py_file in gen_path.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")

    # --- Static helpers for generated API payloads ---

    @staticmethod
    def _valid_product(**overrides) -> dict:
        """Build a valid Product payload for the generated API."""
        base = {
            "tracking_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Test Product",
            "sku": "AB-1234",
            "price": 29.99,
            "weight": 5.0,
            "quantity": 50,
            "min_order_quantity": 1,
            "in_stock": True,
            "product_url": "https://example.com/product",
            "release_date": "2026-01-15",
            "created_at": "2026-01-01T00:00:00",
        }
        base.update(overrides)
        return base

    @staticmethod
    def _valid_customer(**overrides) -> dict:
        """Build a valid Customer payload for the generated API."""
        base = {
            "customer_name": "Jane Doe",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
            "email": "jane@example.com",
        }
        base.update(overrides)
        return base
