"""Create Shop API entities and generate code, then analyze the output.

Usage: PYTHONPATH=src poetry run python scripts/test_generation.py
"""

import asyncio
import io
import os
import zipfile

from httpx import ASGITransport, AsyncClient

from api.auth import get_current_user
from api.main import app

TEST_CLERK_ID = "test_generation_user"
OUTPUT_DIR = "/tmp/shop-api-generated"

# ---------------------------------------------------------------------------
# Field definitions (same as test_e2e_shop.py)
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
    {"name": "sale_end_date", "type": "date", "constraints": [], "validators": []},
    {
        "name": "weight",
        "type": "float",
        "constraints": [("ge", "0"), ("lt", "1000")],
        "validators": [("Clamp to Range", {"min_value": "0", "max_value": "1000"})],
    },
    {"name": "quantity", "type": "int", "constraints": [("ge", "0")], "validators": []},
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
    {"name": "in_stock", "type": "bool", "constraints": [], "validators": []},
    {"name": "product_url", "type": "HttpUrl", "constraints": [], "validators": []},
    {"name": "release_date", "type": "date", "constraints": [], "validators": []},
    {"name": "created_at", "type": "datetime", "constraints": [], "validators": []},
    {"name": "tracking_id", "type": "uuid", "constraints": [], "validators": []},
]

CUSTOMER_FIELDS = [
    {
        "name": "customer_name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "100")],
        "validators": [("Trim", None), ("Normalize Case", {"case": "title"})],
    },
    {"name": "email", "type": "EmailStr", "constraints": [], "validators": []},
    {
        "name": "phone",
        "type": "str",
        "constraints": [("min_length", "7"), ("max_length", "15")],
        "validators": [],
    },
    {"name": "date_of_birth", "type": "date", "constraints": [], "validators": []},
    {"name": "last_login_time", "type": "time", "constraints": [], "validators": []},
    {"name": "is_active", "type": "bool", "constraints": [], "validators": []},
    {"name": "registered_at", "type": "datetime", "constraints": [], "validators": []},
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


async def main():
    app.dependency_overrides[get_current_user] = lambda: TEST_CLERK_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/v1",
    ) as client:
        # --- Phase 1: Read catalogues ---
        print("Phase 1: Reading catalogues...")
        resp = await client.get("/types")
        assert resp.status_code == 200, f"GET /types failed: {resp.text}"
        type_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        constraint_ids = {c["name"]: c["id"] for c in resp.json()}

        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        fv_template_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        mv_template_ids = {t["name"]: t["id"] for t in resp.json()}
        print(
            f"  Types: {len(type_ids)}, Constraints: {len(constraint_ids)}, FV templates: {len(fv_template_ids)}, MV templates: {len(mv_template_ids)}"
        )

        # --- Phase 1.5: Cleanup any leftover data ---
        print("Phase 1.5: Cleaning up leftover data...")
        resp = await client.get("/namespaces")
        if resp.status_code == 200:
            for ns in resp.json():
                if ns["name"] == "Shop":
                    # Delete everything under this namespace
                    ns_id = ns["id"]
                    # Delete endpoints first
                    ep_resp = await client.get("/endpoints")
                    if ep_resp.status_code == 200:
                        for ep in ep_resp.json():
                            await client.delete(f"/endpoints/{ep['id']}")
                    # Delete APIs
                    api_resp = await client.get("/apis")
                    if api_resp.status_code == 200:
                        for a in api_resp.json():
                            await client.delete(f"/apis/{a['id']}")
                    # Delete objects
                    obj_resp = await client.get(f"/objects?namespace_id={ns_id}")
                    if obj_resp.status_code == 200:
                        for o in obj_resp.json():
                            await client.delete(f"/objects/{o['id']}")
                    # Delete fields
                    field_resp = await client.get(f"/fields?namespace_id={ns_id}")
                    if field_resp.status_code == 200:
                        for f in field_resp.json():
                            await client.delete(f"/fields/{f['id']}")
                    # Delete namespace
                    await client.delete(f"/namespaces/{ns_id}")
                    print("  Cleaned up existing Shop namespace")

        # --- Phase 2: Create namespace ---
        print("Phase 2: Creating namespace...")
        resp = await client.post("/namespaces", json={"name": "Shop"})
        assert resp.status_code == 201, f"Create namespace failed: {resp.text}"
        namespace_id = resp.json()["id"]

        # --- Phase 3: Create fields ---
        print("Phase 3: Creating 23 fields...")
        field_ids = {}
        for field_def in ALL_FIELDS:
            payload = {
                "namespaceId": namespace_id,
                "name": field_def["name"],
                "typeId": type_ids[field_def["type"]],
                "constraints": [
                    {"constraintId": constraint_ids[name], "value": value}
                    for name, value in field_def["constraints"]
                ],
                "validators": [
                    {"templateId": fv_template_ids[name], "parameters": params}
                    for name, params in field_def["validators"]
                ],
            }
            resp = await client.post("/fields", json=payload)
            assert (
                resp.status_code == 201
            ), f"Create field '{field_def['name']}' failed: {resp.text}"
            field_ids[field_def["name"]] = resp.json()["id"]
        print(f"  Created {len(field_ids)} fields")

        # --- Phase 4: Create objects ---
        print("Phase 4: Creating objects...")

        # Product
        product_fields = [
            {"fieldId": field_ids[f["name"]], "optional": f["name"] in PRODUCT_OPTIONAL}
            for f in PRODUCT_FIELDS
        ]
        product_validators = [
            {
                "templateId": mv_template_ids["Field Comparison"],
                "parameters": {"operator": "<"},
                "fieldMappings": {
                    "field_a": "min_order_quantity",
                    "field_b": "max_order_quantity",
                },
            },
            {
                "templateId": mv_template_ids["Mutual Exclusivity"],
                "fieldMappings": {
                    "field_a": "discount_percent",
                    "field_b": "discount_amount",
                },
            },
            {
                "templateId": mv_template_ids["All Or None"],
                "fieldMappings": {"field_a": "sale_price", "field_b": "sale_end_date"},
            },
            {
                "templateId": mv_template_ids["Conditional Required"],
                "fieldMappings": {
                    "trigger_field": "discount_percent",
                    "dependent_field": "sale_price",
                },
            },
        ]

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": namespace_id,
                "name": "Product",
                "description": "Shop product",
                "fields": product_fields,
                "validators": product_validators,
            },
        )
        assert resp.status_code == 201, f"Create Product failed: {resp.text}"
        product_id = resp.json()["id"]
        print(
            f"  Product: {len(resp.json()['fields'])} fields, {len(resp.json()['validators'])} validators"
        )

        # Customer
        customer_fields = [
            {
                "fieldId": field_ids[f["name"]],
                "optional": f["name"] in CUSTOMER_OPTIONAL,
            }
            for f in CUSTOMER_FIELDS
        ]
        customer_validators = [
            {
                "templateId": mv_template_ids["At Least One Required"],
                "fieldMappings": {"field_a": "email", "field_b": "phone"},
            },
        ]

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": namespace_id,
                "name": "Customer",
                "description": "Shop customer",
                "fields": customer_fields,
                "validators": customer_validators,
            },
        )
        assert resp.status_code == 201, f"Create Customer failed: {resp.text}"
        customer_id = resp.json()["id"]
        print(
            f"  Customer: {len(resp.json()['fields'])} fields, {len(resp.json()['validators'])} validators"
        )

        # --- Phase 5: Create API ---
        print("Phase 5: Creating API...")
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": namespace_id,
                "title": "ShopApi",
                "version": "1.0.0",
                "description": "Online shop with products and customers",
            },
        )
        assert resp.status_code == 201, f"Create API failed: {resp.text}"
        api_id = resp.json()["id"]

        # --- Phase 6: Create endpoints ---
        print("Phase 6: Creating 7 endpoints...")
        endpoints = [
            {
                "apiId": api_id,
                "method": "GET",
                "path": "/products",
                "description": "List all products",
                "tagName": "Products",
                "pathParams": [],
                "objectId": product_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
            {
                "apiId": api_id,
                "method": "GET",
                "path": "/products/{tracking_id}",
                "description": "Get product by tracking ID",
                "tagName": "Products",
                "pathParams": [
                    {"name": "tracking_id", "fieldId": field_ids["tracking_id"]}
                ],
                "objectId": product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": api_id,
                "method": "POST",
                "path": "/products",
                "description": "Create a product",
                "tagName": "Products",
                "pathParams": [],
                "objectId": product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": api_id,
                "method": "PUT",
                "path": "/products/{tracking_id}",
                "description": "Update a product",
                "tagName": "Products",
                "pathParams": [
                    {"name": "tracking_id", "fieldId": field_ids["tracking_id"]}
                ],
                "objectId": product_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": api_id,
                "method": "DELETE",
                "path": "/products/{tracking_id}",
                "description": "Delete a product",
                "tagName": "Products",
                "pathParams": [
                    {"name": "tracking_id", "fieldId": field_ids["tracking_id"]}
                ],
                "useEnvelope": False,
                "responseShape": "object",
            },
            {
                "apiId": api_id,
                "method": "GET",
                "path": "/customers",
                "description": "List all customers",
                "tagName": "Customers",
                "pathParams": [],
                "objectId": customer_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
            {
                "apiId": api_id,
                "method": "PATCH",
                "path": "/customers/{email}",
                "description": "Update a customer by email",
                "tagName": "Customers",
                "pathParams": [{"name": "email", "fieldId": field_ids["email"]}],
                "objectId": customer_id,
                "useEnvelope": False,
                "responseShape": "object",
            },
        ]
        for ep in endpoints:
            resp = await client.post("/endpoints", json=ep)
            assert (
                resp.status_code == 201
            ), f"Create {ep['method']} {ep['path']} failed: {resp.text}"
        print(f"  Created {len(endpoints)} endpoints")

        # --- Phase 7: Generate code ---
        print("\nPhase 7: Generating code...")
        resp = await client.post(f"/apis/{api_id}/generate")
        assert (
            resp.status_code == 200
        ), f"Generate failed ({resp.status_code}): {resp.text}"

        # Extract ZIP
        zip_data = io.BytesIO(resp.content)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        with zipfile.ZipFile(zip_data, "r") as zf:
            zf.extractall(OUTPUT_DIR)
            file_list = zf.namelist()

        print(f"\nGenerated {len(file_list)} files to {OUTPUT_DIR}:")
        for f in sorted(file_list):
            print(f"  {f}")

        # --- Phase 8: Print generated files ---
        print("\n" + "=" * 80)
        print("GENERATED FILE CONTENTS")
        print("=" * 80)
        for f in sorted(file_list):
            filepath = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(filepath) and not f.endswith((".pyc", ".pyo")):
                print(f"\n{'─' * 80}")
                print(f"FILE: {f}")
                print(f"{'─' * 80}")
                with open(filepath) as fh:
                    print(fh.read())

        # --- Phase 9: Cleanup DB entities ---
        print("\n\nPhase 9: Cleaning up...")
        for ep in endpoints:
            # We didn't save endpoint IDs, delete via API listing
            pass
        resp = await client.get("/endpoints")
        if resp.status_code == 200:
            for ep in resp.json():
                await client.delete(f"/endpoints/{ep['id']}")
        await client.delete(f"/apis/{api_id}")
        for obj_id in (product_id, customer_id):
            await client.delete(f"/objects/{obj_id}")
        for fid in field_ids.values():
            await client.delete(f"/fields/{fid}")
        await client.delete(f"/namespaces/{namespace_id}")
        print("  Cleanup complete.")

    app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    asyncio.run(main())
