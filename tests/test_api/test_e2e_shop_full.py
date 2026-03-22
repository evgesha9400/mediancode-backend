"""E2E test: full Shop API lifecycle — CRUD, generate with DB backend, verify generated code.

Phases:
 1. Read catalogues (types, constraints, validator templates)
 2. Create namespace
 3. Create 23 fields with constraints and validators
 4. Read and verify fields
 5. Update fields (constraint change + add validator)
 6. Create objects with primary keys, field references, and model validators
 7. Read and verify objects
 8. Update object (change field optionality)
 9. Create API
10. Update API
11. Create 9 endpoints (UUID path params → JSONB round-trip)
12. Read and verify endpoints
13. Update endpoint (UUID-in-JSONB regression test)
14. Generate API with database backend
15. Verify ZIP structure (includes DB files)
16. Verify ORM models content
17. Verify database integration in generated code
18. Verify generated Pydantic models retain constraints
19-25. Cleanup
"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
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
from api.seeding.shop_data import (
    CUSTOMER_FIELDS,
    CUSTOMER_OPTIONAL,
    PRODUCT_FIELDS,
    PRODUCT_OPTIONAL,
)

# Map seed data OPTIONAL sets to NULLABLE for test payloads
PRODUCT_NULLABLE = PRODUCT_OPTIONAL
CUSTOMER_NULLABLE = CUSTOMER_OPTIONAL

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
# Field definitions imported from shared seed data (see imports above).
# shop_data defines the FINAL state. For update testing, we override initial values.
# ---------------------------------------------------------------------------

ALL_FIELDS = PRODUCT_FIELDS + CUSTOMER_FIELDS

# Phase 3 creates with these overrides; Phase 5 updates to final (from shop_data).
FIELD_CREATION_OVERRIDES = {
    "name": {"constraints": [("min_length", "1"), ("max_length", "200")]},
    "customer_name": {
        "validators": [("Trim", None), ("Normalize Case", {"case": "title"})]
    },
}

# Phase 6 creates Product with min_order_quantity nullable; Phase 8 makes it required.
PRODUCT_NULLABLE_INITIAL = PRODUCT_NULLABLE | {"min_order_quantity"}


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
    relationship_id: str = ""
    endpoint_ids: dict[str, str] = {}
    zip_bytes: bytes = b""
    generated_dir: str = ""

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
            overrides = FIELD_CREATION_OVERRIDES.get(field_def["name"], {})
            constraints = overrides.get("constraints", field_def["constraints"])
            validators = overrides.get("validators", field_def["validators"])
            payload = {
                "namespaceId": cls.namespace_id,
                "name": field_def["name"],
                "typeId": cls.type_ids[field_def["type"]],
                "constraints": [
                    {"constraintId": cls.constraint_ids[name], "value": value}
                    for name, value in constraints
                ],
                "validators": [
                    {"templateId": cls.fv_template_ids[name], "parameters": params}
                    for name, params in validators
                ],
            }
            resp = await client.post("/fields", json=payload)
            assert (
                resp.status_code == 201
            ), f"Failed to create field '{field_def['name']}': {resp.text}"
            field = resp.json()
            assert field["typeId"] == cls.type_ids[field_def["type"]]
            assert len(field["constraints"]) == len(constraints)
            assert len(field["validators"]) == len(validators)
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
        """Create Product (16 fields, 4 validators, uuid PK) and Customer (8 fields, 1 validator, int PK)."""
        cls = TestShopApiFullE2E

        # --- Product ---
        product_exposure = {"created_at": "read_only"}
        product_defaults = {"created_at": {"kind": "generated", "strategy": "now"}}
        product_fields = [
            {
                "fieldId": cls.field_ids[f["name"]],
                "nullable": f["name"] in PRODUCT_NULLABLE_INITIAL,
                "isPk": f["name"] == "tracking_id",
                "exposure": product_exposure.get(f["name"], "read_write"),
                **(
                    {"default": product_defaults[f["name"]]}
                    if f["name"] in product_defaults
                    else {}
                ),
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
        customer_exposure = {"registered_at": "read_only"}
        customer_defaults = {
            "registered_at": {"kind": "generated", "strategy": "now"},
        }
        customer_fields = [
            {
                "fieldId": cls.field_ids[f["name"]],
                "nullable": f["name"] in CUSTOMER_NULLABLE,
                "isPk": f["name"] == "customer_id",
                "exposure": customer_exposure.get(f["name"], "read_write"),
                **(
                    {"default": customer_defaults[f["name"]]}
                    if f["name"] in customer_defaults
                    else {}
                ),
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
        assert len(customer["fields"]) == 8
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
        assert len(customer["fields"]) == 8
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
            nullable = f["nullable"]
            if f["fieldId"] == cls.field_ids["min_order_quantity"]:
                nullable = False
            entry = {
                "fieldId": f["fieldId"],
                "nullable": nullable,
                "isPk": f.get("isPk", False),
                "exposure": f.get("exposure", "read_write"),
            }
            if f.get("default"):
                entry["default"] = f["default"]
            updated_fields.append(entry)

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
        assert moq["nullable"] is False

    # --- Phase 8b: Create relationship ---

    async def test_phase_08b_create_relationship(self, client: AsyncClient):
        """Create Customer has_many Products relationship."""
        cls = TestShopApiFullE2E
        resp = await client.post(
            f"/objects/{cls.customer_id}/relationships",
            json={
                "targetObjectId": cls.product_id,
                "name": "products",
                "cardinality": "has_many",
            },
        )
        assert resp.status_code == 201
        rel = resp.json()
        assert rel["name"] == "products"
        assert rel["cardinality"] == "has_many"
        assert rel["isInferred"] is False
        assert rel.get("inverseId") is not None
        cls.relationship_id = rel["id"]

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
        """Create all 9 endpoints with UUID path params (JSONB round-trip)."""
        cls = TestShopApiFullE2E

        endpoints = [
            {
                "apiId": cls.api_id,
                "method": "GET",
                "path": "/products",
                "description": "List all products",
                "tagName": "Products",
                "pathParams": [],
                "objectId": cls.product_id,
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
                "objectId": cls.product_id,
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
                "objectId": cls.product_id,
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
                "objectId": cls.product_id,
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
                "objectId": cls.customer_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
            {
                "apiId": cls.api_id,
                "method": "POST",
                "path": "/customers",
                "description": "Create a customer",
                "tagName": "Customers",
                "pathParams": [],
                "objectId": cls.customer_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": cls.api_id,
                "method": "GET",
                "path": "/customers/{email}",
                "description": "Get customer by email",
                "tagName": "Customers",
                "pathParams": [
                    {
                        "name": "email",
                        "fieldId": cls.field_ids["email"],
                    }
                ],
                "objectId": cls.customer_id,
                "useEnvelope": False,
                "responseShape": "object",
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
                "objectId": cls.customer_id,
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

        assert len(cls.endpoint_ids) == 9

    # --- Phase 12: Read and verify endpoints ---

    async def test_phase_12_read_endpoints(self, client: AsyncClient):
        """Verify all 9 endpoints via list and individual GET."""
        cls = TestShopApiFullE2E

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        endpoints = resp.json()
        assert len(endpoints) == 9

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
        """Call the generate endpoint with database backend enabled."""
        cls = TestShopApiFullE2E

        resp = await client.post(
            f"/apis/{cls.api_id}/generate",
            json={
                "databaseEnabled": True,
                "responsePlaceholders": False,
            },
        )
        assert resp.status_code == 200, f"Generate failed: {resp.text}"
        assert "application/zip" in resp.headers.get("content-type", "")
        assert "content-disposition" in resp.headers
        assert "shopapi" in resp.headers["content-disposition"].lower()
        assert len(resp.content) > 0
        cls.zip_bytes = resp.content

    # --- Phase 15: Verify ZIP structure ---

    async def test_phase_15_verify_zip_structure(self, client: AsyncClient):
        """Extract ZIP and verify file structure includes database files."""
        cls = TestShopApiFullE2E

        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            names = zf.namelist()

            # No __pycache__ directories
            assert not any(
                "__pycache__" in n for n in names
            ), f"Found __pycache__ in ZIP: {[n for n in names if '__pycache__' in n]}"

            # Required files present (including database files)
            required_files = [
                "src/models.py",
                "src/views.py",
                "src/main.py",
                "src/path.py",
                "src/orm_models.py",
                "src/database.py",
                "pyproject.toml",
                "Makefile",
                "Dockerfile",
                "docker-compose.yml",
                "alembic.ini",
                "migrations/env.py",
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

    # --- Phase 16: Verify ORM models content ---

    def test_phase_16_orm_models(self):
        """Verify ORM models have correct PKs, table names, and column types."""
        cls = TestShopApiFullE2E
        content = (Path(cls.generated_dir) / "src" / "orm_models.py").read_text()

        # Base class
        assert "class Base(DeclarativeBase):" in content

        # Product ORM model
        assert "class ProductRecord(Base):" in content
        assert '__tablename__ = "products"' in content

        # Product UUID PK: import uuid, default=uuid.uuid4, primary_key=True
        assert "import uuid" in content
        assert "default=uuid.uuid4" in content
        assert "primary_key=True" in content

        # Customer ORM model
        assert "class CustomerRecord(Base):" in content
        assert '__tablename__ = "customers"' in content

        # Customer int PK: autoincrement=True
        assert "autoincrement=True" in content

        # Verify Decimal fields map to Numeric
        assert "Numeric" in content

        # Verify Boolean fields map to Boolean
        assert "Boolean" in content

    # --- Phase 17: Verify database integration ---

    def test_phase_17_database_integration(self):
        """Verify database.py, views.py, and main.py have DB integration."""
        cls = TestShopApiFullE2E
        gen_path = Path(cls.generated_dir)

        # database.py
        db_content = (gen_path / "src" / "database.py").read_text()
        assert "create_async_engine" in db_content
        assert "async def get_session" in db_content
        assert "DATABASE_URL" in db_content

        # views.py uses DB session injection
        views_content = (gen_path / "src" / "views.py").read_text()
        assert "Depends(get_session)" in views_content
        assert "AsyncSession" in views_content
        assert "select(" in views_content
        assert "session.execute" in views_content
        assert "ProductRecord" in views_content
        assert "CustomerRecord" in views_content

        # main.py has lifespan and database import
        main_content = (gen_path / "src" / "main.py").read_text()
        assert "lifespan" in main_content
        assert "from database import" in main_content

    # --- Phase 18: Verify generated Pydantic models ---

    def test_phase_18_pydantic_models(self):
        """Verify generated models.py retains field constraints and validators."""
        cls = TestShopApiFullE2E
        content = (Path(cls.generated_dir) / "src" / "models.py").read_text()

        # Product schemas exist (split into Create/Update/Response)
        assert "class ProductCreate(" in content
        assert "class ProductUpdate(" in content
        assert "class ProductResponse(" in content

        # Customer schemas exist
        assert "class CustomerCreate(" in content
        assert "class CustomerResponse(" in content

        # Field constraints survived generation
        assert "min_length=" in content  # name, customer_name, phone
        assert "max_length=" in content  # name, customer_name, phone
        assert "gt=" in content  # price
        assert "ge=" in content  # weight, quantity, etc.
        assert "pattern=" in content  # sku
        assert "multiple_of=" in content  # discount_percent

        # Model validators present on Create schemas
        assert "model_validator" in content

    # --- Phase 19: Verify infrastructure files ---

    def test_phase_20_infrastructure(self):
        """Verify docker-compose, alembic, pyproject.toml have DB config."""
        cls = TestShopApiFullE2E
        gen_path = Path(cls.generated_dir)

        # docker-compose.yml
        dc_content = (gen_path / "docker-compose.yml").read_text()
        assert "postgres" in dc_content
        assert "DATABASE_URL" in dc_content

        # alembic.ini
        alembic_content = (gen_path / "alembic.ini").read_text()
        assert "sqlalchemy.url" in alembic_content

        # pyproject.toml has DB dependencies
        pyproject_content = (gen_path / "pyproject.toml").read_text()
        assert "sqlalchemy" in pyproject_content
        assert "asyncpg" in pyproject_content
        assert "alembic" in pyproject_content

        # Makefile has db targets
        makefile_content = (gen_path / "Makefile").read_text()
        assert "db-up:" in makefile_content

    # --- Phase 21: Clean up generated app ---

    def test_phase_21_cleanup_generated(self):
        """Clean up the generated app temp directory."""
        cls = TestShopApiFullE2E
        if cls.generated_dir and Path(cls.generated_dir).exists():
            shutil.rmtree(cls.generated_dir)

    # --- Phase 22: Delete endpoints ---

    async def test_phase_22_delete_endpoints(self, client: AsyncClient):
        """Delete all 9 endpoints and verify list is empty."""
        cls = TestShopApiFullE2E

        for key, ep_id in cls.endpoint_ids.items():
            resp = await client.delete(f"/endpoints/{ep_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete endpoint {key}: {resp.text}"

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 23: Delete API ---

    async def test_phase_23_delete_api(self, client: AsyncClient):
        """Delete the Shop API and verify list is empty."""
        cls = TestShopApiFullE2E

        resp = await client.delete(f"/apis/{cls.api_id}")
        assert resp.status_code == 204

        resp = await client.get("/apis")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 24: Delete objects ---

    async def test_phase_24_delete_objects(self, client: AsyncClient):
        """Delete both objects and verify list is empty."""
        cls = TestShopApiFullE2E

        for obj_id in (cls.product_id, cls.customer_id):
            resp = await client.delete(f"/objects/{obj_id}")
            assert resp.status_code == 204

        resp = await client.get("/objects")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 25: Delete fields ---

    async def test_phase_25_delete_fields(self, client: AsyncClient):
        """Delete all 23 fields and verify list is empty."""
        cls = TestShopApiFullE2E

        for name, field_id in cls.field_ids.items():
            resp = await client.delete(f"/fields/{field_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete field '{name}': {resp.text}"

        resp = await client.get("/fields")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 26: Delete namespace ---

    async def test_phase_26_delete_namespace(self, client: AsyncClient):
        """Delete Shop namespace and verify only Global remains."""
        cls = TestShopApiFullE2E

        resp = await client.delete(f"/namespaces/{cls.namespace_id}")
        assert resp.status_code == 204

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names
        assert "Global" in names
