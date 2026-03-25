# tests/support/shop_contract.py
"""Canonical Shop API domain definition — single source of truth.

Every HTTP integration test and the seeding runner consume these
constants.  This replaces the previous ``tests/seeding/shop_data.py``
and the inline field definitions that used to live in the E2E test
modules.

All symbolic field/object references are resolved to UUIDs at runtime
by :func:`seed_shop`.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

PRODUCT_FIELDS = [
    {
        "name": "name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "150")],
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
        "name": "id",
        "type": "int",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "customer_name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "100")],
        "validators": [
            ("Trim", None),
            ("Normalize Case", {"case": "title"}),
            ("Trim To Length", {"max_length": "100"}),
        ],
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
    "max_order_quantity",
    "discount_percent",
    "discount_amount",
}

CUSTOMER_OPTIONAL = {"phone"}

# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

PRODUCT_OBJECT = {
    "name": "Product",
    "description": "Shop product",
    "fields": [
        {"field_name": "tracking_id", "role": "pk"},
        {"field_name": "name", "optional": False, "role": "writable"},
        {"field_name": "sku", "optional": False, "role": "writable"},
        {"field_name": "price", "optional": False, "role": "writable"},
        {"field_name": "sale_price", "optional": True, "role": "writable"},
        {"field_name": "sale_end_date", "optional": True, "role": "writable"},
        {"field_name": "weight", "optional": False, "role": "writable"},
        {"field_name": "quantity", "optional": False, "role": "writable"},
        {"field_name": "min_order_quantity", "optional": False, "role": "writable"},
        {"field_name": "max_order_quantity", "optional": True, "role": "writable"},
        {"field_name": "discount_percent", "optional": True, "role": "writable"},
        {"field_name": "discount_amount", "optional": True, "role": "writable"},
        {"field_name": "in_stock", "optional": False, "role": "writable"},
        {"field_name": "product_url", "optional": False, "role": "writable"},
        {"field_name": "release_date", "optional": False, "role": "writable"},
        {"field_name": "created_at", "role": "created_timestamp"},
    ],
    "validators": [
        {
            "template": "Field Comparison",
            "parameters": {"operator": "<"},
            "field_mappings": {
                "field_a": "min_order_quantity",
                "field_b": "max_order_quantity",
            },
        },
        {
            "template": "Mutual Exclusivity",
            "parameters": None,
            "field_mappings": {
                "field_a": "discount_percent",
                "field_b": "discount_amount",
            },
        },
        {
            "template": "All Or None",
            "parameters": None,
            "field_mappings": {
                "field_a": "sale_price",
                "field_b": "sale_end_date",
            },
        },
        {
            "template": "Conditional Required",
            "parameters": None,
            "field_mappings": {
                "trigger_field": "discount_percent",
                "dependent_field": "sale_price",
            },
        },
    ],
}

CUSTOMER_OBJECT = {
    "name": "Customer",
    "description": "Shop customer",
    "fields": [
        {"field_name": "id", "role": "pk"},
        {"field_name": "customer_name", "optional": False, "role": "writable"},
        {"field_name": "email", "optional": False, "role": "writable"},
        {"field_name": "phone", "optional": True, "role": "writable"},
        {"field_name": "date_of_birth", "optional": False, "role": "writable"},
        {"field_name": "last_login_time", "optional": False, "role": "writable"},
        {"field_name": "is_active", "optional": False, "role": "writable"},
        {"field_name": "registered_at", "role": "created_timestamp"},
    ],
    "validators": [],
}

OBJECTS = [PRODUCT_OBJECT, CUSTOMER_OBJECT]

# ---------------------------------------------------------------------------
# Relationship (now authored as a member on Customer)
# ---------------------------------------------------------------------------

CUSTOMER_RELATIONSHIP_MEMBERS = [
    {
        "member_type": "relationship",
        "name": "products",
        "target_object": "Product",
        "kind": "one_to_many",
        "inverse_name": "customer",
        "required": False,
    },
]

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

API = {
    "title": "ShopApi",
    "version": "1.0.0",
    "description": "Complete online shop API",
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

ENDPOINTS = [
    {
        "method": "GET",
        "path": "/products",
        "description": "List all products",
        "tag": "Products",
        "object": "Product",
        "path_params": [],
        "response_shape": "list",
    },
    {
        "method": "GET",
        "path": "/products/{tracking_id}",
        "description": "Get product by tracking ID",
        "tag": "Products",
        "object": "Product",
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "POST",
        "path": "/products",
        "description": "Create a product",
        "tag": "Products",
        "object": "Product",
        "path_params": [],
        "response_shape": "object",
    },
    {
        "method": "PUT",
        "path": "/items/{tracking_id}",
        "description": "Update a product",
        "tag": "Products",
        "object": "Product",
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "DELETE",
        "path": "/products/{tracking_id}",
        "description": "Delete a product",
        "tag": "Products",
        "object": None,
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "GET",
        "path": "/customers",
        "description": "List all customers",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [],
        "response_shape": "list",
    },
    {
        "method": "POST",
        "path": "/customers",
        "description": "Create a customer",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [],
        "response_shape": "object",
    },
    {
        "method": "GET",
        "path": "/customers/{id}",
        "description": "Get customer by ID",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [{"name": "id", "field": "id"}],
        "response_shape": "object",
    },
    {
        "method": "PATCH",
        "path": "/customers/{id}",
        "description": "Update a customer by ID",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [{"name": "id", "field": "id"}],
        "response_shape": "object",
    },
]


# ---------------------------------------------------------------------------
# Seed / Clean helpers
# ---------------------------------------------------------------------------


class SeedError(Exception):
    """Raised when a seed API call fails."""

    def __init__(self, entity_type: str, name: str, status_code: int, detail: str):
        self.entity_type = entity_type
        self.name = name
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"Failed to create {entity_type} '{name}': HTTP {status_code} — {detail}"
        )


@dataclass
class SeedResult:
    """IDs of all entities created by :func:`seed_shop`."""

    namespace_id: str = ""
    field_ids: dict[str, str] = dataclass_field(default_factory=dict)
    object_ids: dict[str, str] = dataclass_field(default_factory=dict)
    api_id: str = ""
    endpoint_ids: dict[str, str] = dataclass_field(default_factory=dict)
    relationship_ids: list[str] = dataclass_field(default_factory=list)


def _check(resp, entity_type: str, name: str, expected: int = 201) -> dict:
    if resp.status_code != expected:
        raise SeedError(entity_type, name, resp.status_code, resp.text)
    return resp.json()


def _check_delete(resp, entity_type: str, name: str) -> None:
    if resp.status_code not in (200, 204):
        raise SeedError(entity_type, name, resp.status_code, resp.text)


async def _read_catalogues(client: AsyncClient) -> dict[str, dict[str, str]]:
    catalogues: dict[str, dict[str, str]] = {}
    for endpoint, key in [
        ("/types", "types"),
        ("/field-constraints", "constraints"),
        ("/field-validator-templates", "fv_templates"),
        ("/model-validator-templates", "mv_templates"),
    ]:
        resp = await client.get(endpoint)
        if resp.status_code != 200:
            raise SeedError("catalogue", endpoint, resp.status_code, resp.text)
        catalogues[key] = {item["name"]: item["id"] for item in resp.json()}
    return catalogues


async def seed_shop(client: AsyncClient) -> SeedResult:
    """Create the full Shop domain via HTTP calls.

    :param client: Authenticated ``AsyncClient`` with ``base_url`` set.
    :returns: :class:`SeedResult` with all created entity IDs.
    """
    result = SeedResult()
    cat = await _read_catalogues(client)

    resp = await client.post("/namespaces", json={"name": "Shop", "isDefault": False})
    ns = _check(resp, "namespace", "Shop")
    result.namespace_id = ns["id"]

    for field_def in ALL_FIELDS:
        payload = {
            "namespaceId": result.namespace_id,
            "name": field_def["name"],
            "typeId": cat["types"][field_def["type"]],
            "constraints": [
                {"constraintId": cat["constraints"][cname], "value": cval}
                for cname, cval in field_def["constraints"]
            ],
            "validators": [
                {"templateId": cat["fv_templates"][tname], "parameters": params}
                for tname, params in field_def["validators"]
            ],
        }
        resp = await client.post("/fields", json=payload)
        f = _check(resp, "field", field_def["name"])
        result.field_ids[field_def["name"]] = f["id"]

    # First pass: create objects without relationship members
    # (target objects must exist before we can reference them)
    for obj_def in OBJECTS:
        members = []
        for fref in obj_def["fields"]:
            member: dict = {
                "memberType": "scalar",
                "name": fref["field_name"],
                "fieldId": result.field_ids[fref["field_name"]],
                "role": fref["role"],
            }
            if "optional" in fref:
                member["isNullable"] = fref["optional"]
            if fref.get("default_value") is not None:
                member["defaultValue"] = fref["default_value"]
            members.append(member)
        obj_validators = [
            {
                "templateId": cat["mv_templates"][vdef["template"]],
                "parameters": vdef["parameters"],
                "fieldMappings": vdef["field_mappings"],
            }
            for vdef in obj_def["validators"]
        ]
        payload = {
            "namespaceId": result.namespace_id,
            "name": obj_def["name"],
            "description": obj_def["description"],
            "members": members,
            "validators": obj_validators,
        }
        resp = await client.post("/objects", json=payload)
        obj = _check(resp, "object", obj_def["name"])
        result.object_ids[obj_def["name"]] = obj["id"]

    # Second pass: add relationship members to Customer via PUT
    customer_id = result.object_ids["Customer"]
    resp = await client.get(f"/objects/{customer_id}")
    customer_obj = resp.json()
    existing_members = customer_obj["members"]
    for rel_def in CUSTOMER_RELATIONSHIP_MEMBERS:
        existing_members.append(
            {
                "memberType": "relationship",
                "name": rel_def["name"],
                "targetObjectId": result.object_ids[rel_def["target_object"]],
                "kind": rel_def["kind"],
                "inverseName": rel_def["inverse_name"],
                "required": rel_def["required"],
            }
        )
    resp = await client.put(
        f"/objects/{customer_id}",
        json={"members": existing_members},
    )
    updated = _check(resp, "object", "Customer (update)", expected=200)
    rel_members = [m for m in updated["members"] if m["memberType"] == "relationship"]
    for rm in rel_members:
        result.relationship_ids.append(rm["id"])

    resp = await client.post(
        "/apis",
        json={
            "namespaceId": result.namespace_id,
            "title": API["title"],
            "version": API["version"],
            "description": API["description"],
        },
    )
    api = _check(resp, "api", API["title"])
    result.api_id = api["id"]

    for ep_def in ENDPOINTS:
        path_params = [
            {"name": pp["name"], "fieldId": result.field_ids[pp["field"]]}
            for pp in ep_def["path_params"]
        ]
        payload = {
            "apiId": result.api_id,
            "method": ep_def["method"],
            "path": ep_def["path"],
            "description": ep_def["description"],
            "tagName": ep_def["tag"],
            "pathParams": path_params,
            "useEnvelope": False,
            "responseShape": ep_def["response_shape"],
        }
        if ep_def["object"] is not None:
            payload["objectId"] = result.object_ids[ep_def["object"]]
        resp = await client.post("/endpoints", json=payload)
        ep = _check(resp, "endpoint", f"{ep_def['method']} {ep_def['path']}")
        result.endpoint_ids[f"{ep_def['method']} {ep_def['path']}"] = ep["id"]

    return result


async def clean_shop(client: AsyncClient) -> None:
    """Delete the Shop namespace and all its contents.

    Deletes in reverse dependency order:
    endpoints -> APIs -> objects (cascade deletes relationships) -> fields -> namespace.

    :param client: Authenticated ``AsyncClient`` with ``base_url`` set.
    """
    resp = await client.get("/namespaces")
    if resp.status_code != 200:
        raise SeedError("catalogue", "namespaces", resp.status_code, resp.text)
    all_namespaces = resp.json()
    shop_ns = next((ns for ns in all_namespaces if ns["name"] == "Shop"), None)
    if shop_ns is None:
        return

    ns_id = shop_ns["id"]

    global_ns = next((ns for ns in all_namespaces if ns["name"] == "Global"), None)
    if global_ns is None:
        raise SeedError("namespace", "Global", 404, "Global namespace not found")
    resp = await client.put(f"/namespaces/{global_ns['id']}", json={"isDefault": True})
    if resp.status_code not in (200, 204):
        raise SeedError("namespace", "Global", resp.status_code, resp.text)

    resp = await client.get(f"/apis?namespace_id={ns_id}")
    shop_apis = resp.json() if resp.status_code == 200 else []
    api_ids = {api["id"] for api in shop_apis}

    resp = await client.get("/endpoints")
    if resp.status_code == 200:
        for ep in resp.json():
            if ep.get("apiId") in api_ids:
                r = await client.delete(f"/endpoints/{ep['id']}")
                _check_delete(r, "endpoint", ep["id"])

    for api in shop_apis:
        r = await client.delete(f"/apis/{api['id']}")
        _check_delete(r, "api", api["id"])

    resp = await client.get(f"/objects?namespace_id={ns_id}")
    if resp.status_code == 200:
        for obj in resp.json():
            r = await client.delete(f"/objects/{obj['id']}")
            _check_delete(r, "object", obj["id"])

    resp = await client.get(f"/fields?namespace_id={ns_id}")
    if resp.status_code == 200:
        for f in resp.json():
            r = await client.delete(f"/fields/{f['id']}")
            _check_delete(r, "field", f["id"])

    r = await client.delete(f"/namespaces/{ns_id}")
    _check_delete(r, "namespace", "Shop")
