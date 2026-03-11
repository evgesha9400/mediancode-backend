"""E2E test: build a complete Shop API through the HTTP layer.

Phases:
 1. Read catalogues (types, constraints, validator templates)
 2. Create namespace
 3. Create 24 fields with constraints and validators
 4. Read and verify fields
 5. Update fields (constraint change + add validator)
 6. Create objects with primary keys, field references, and model validators
 7. Read and verify objects
 8. Update object (change field optionality)
 9. Create API
10. Update API
11. Create 7 endpoints (UUID path params → JSONB round-trip)
12. Read and verify endpoints
13. Update endpoint (UUID-in-JSONB round-trip regression test)
14-18. Delete all entities in reverse order
"""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

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
        "name": "customer_id",
        "type": "int",
        "constraints": [],
        "validators": [],
    },
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
# Test class
# ---------------------------------------------------------------------------


class TestShopApiE2E:
    """Build a complete Shop API end-to-end through HTTP.

    Tests are ordered by phase. Each phase stores IDs in class variables
    so subsequent phases can reference created entities.
    """

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

    # --- Phase 1: Read catalogues ---

    async def test_phase_01_read_catalogues(self, client: AsyncClient):
        """Read all catalogue data and store IDs for later phases."""
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

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
        """Create all 24 fields with types, constraints, and validators."""
        cls = TestShopApiE2E

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

        assert len(cls.field_ids) == 24

    # --- Phase 4: Read and verify fields ---

    async def test_phase_04_read_fields(self, client: AsyncClient):
        """Verify all 24 fields via list and individual GET."""
        cls = TestShopApiE2E

        resp = await client.get(f"/fields?namespace_id={cls.namespace_id}")
        assert resp.status_code == 200
        fields = resp.json()
        assert len(fields) == 24

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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

        # --- Product ---
        product_fields = [
            {
                "fieldId": cls.field_ids[f["name"]],
                "optional": f["name"] in PRODUCT_OPTIONAL,
                "isPk": f["name"] == "tracking_id",
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
                "isPk": f["name"] == "customer_id",
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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

        # Get current fields to preserve them
        resp = await client.get(f"/objects/{cls.product_id}")
        product = resp.json()
        updated_fields = []
        for f in product["fields"]:
            optional = f["optional"]
            if f["fieldId"] == cls.field_ids["min_order_quantity"]:
                optional = False
            updated_fields.append(
                {
                    "fieldId": f["fieldId"],
                    "optional": optional,
                    "isPk": f.get("isPk", False),
                }
            )

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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E

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
        cls = TestShopApiE2E
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

    # --- Phase 14: Delete endpoints ---

    async def test_phase_14_delete_endpoints(self, client: AsyncClient):
        """Delete all 7 endpoints and verify list is empty."""
        cls = TestShopApiE2E

        for key, ep_id in cls.endpoint_ids.items():
            resp = await client.delete(f"/endpoints/{ep_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete endpoint {key}: {resp.text}"

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 15: Delete API ---

    async def test_phase_15_delete_api(self, client: AsyncClient):
        """Delete the Shop API and verify list is empty."""
        cls = TestShopApiE2E

        resp = await client.delete(f"/apis/{cls.api_id}")
        assert resp.status_code == 204

        resp = await client.get("/apis")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 16: Delete objects ---

    async def test_phase_16_delete_objects(self, client: AsyncClient):
        """Delete both objects and verify list is empty."""
        cls = TestShopApiE2E

        for obj_id in (cls.product_id, cls.customer_id):
            resp = await client.delete(f"/objects/{obj_id}")
            assert resp.status_code == 204

        resp = await client.get("/objects")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 17: Delete fields ---

    async def test_phase_17_delete_fields(self, client: AsyncClient):
        """Delete all 24 fields and verify list is empty."""
        cls = TestShopApiE2E

        for name, field_id in cls.field_ids.items():
            resp = await client.delete(f"/fields/{field_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete field '{name}': {resp.text}"

        resp = await client.get("/fields")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 18: Delete namespace ---

    async def test_phase_18_delete_namespace(self, client: AsyncClient):
        """Delete Shop namespace and verify only Global remains."""
        cls = TestShopApiE2E

        resp = await client.delete(f"/namespaces/{cls.namespace_id}")
        assert resp.status_code == 204

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names
        assert "Global" in names
