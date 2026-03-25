"""Shop API seed runner — creates/deletes Shop structure via API calls."""

from __future__ import annotations

from dataclasses import dataclass, field

from httpx import AsyncClient

from seeding.shop_data import (
    ALL_FIELDS,
    API,
    CUSTOMER_RELATIONSHIP_MEMBERS,
    ENDPOINTS,
    OBJECTS,
)


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
    namespace_id: str = ""
    field_ids: dict[str, str] = field(default_factory=dict)
    object_ids: dict[str, str] = field(default_factory=dict)
    api_id: str = ""
    endpoint_ids: dict[str, str] = field(default_factory=dict)
    relationship_ids: list[str] = field(default_factory=list)


def _check(resp, entity_type: str, name: str, expected: int = 201) -> dict:
    """Check response status and return JSON, or raise SeedError."""
    if resp.status_code != expected:
        raise SeedError(entity_type, name, resp.status_code, resp.text)
    return resp.json()


def _check_delete(resp, entity_type: str, name: str) -> None:
    """Check that a DELETE (or similar) succeeded, or raise SeedError with the response body."""
    if resp.status_code not in (200, 204):
        raise SeedError(entity_type, name, resp.status_code, resp.text)


async def _read_catalogues(client: AsyncClient) -> dict[str, dict[str, str]]:
    """Fetch all read-only catalogues and return name-to-ID maps."""
    catalogues = {}
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


async def seed_shop(client: AsyncClient, log=None) -> SeedResult:
    """Create the full Shop API structure via API calls.

    The client must be pre-configured with base_url and auth headers
    (or ASGI transport with dependency overrides for tests).

    :param log: Optional callable for progress output (e.g. print). Silent by default.
    """
    if log is None:
        log = lambda *_: None

    result = SeedResult()
    cat = await _read_catalogues(client)

    # 1. Namespace
    log("Creating namespace 'Shop'...")
    resp = await client.post("/namespaces", json={"name": "Shop", "isDefault": False})
    ns = _check(resp, "namespace", "Shop")
    result.namespace_id = ns["id"]

    # 2. Fields
    for field_def in ALL_FIELDS:
        log(f"  Creating field '{field_def['name']}' ({field_def['type']})...")
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

    # 3. Objects (scalar members only on first pass)
    for obj_def in OBJECTS:
        log(f"Creating object '{obj_def['name']}'...")
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

    # 4. Relationship members (add to Customer via PUT)
    customer_id = result.object_ids["Customer"]
    log("Adding relationship members to Customer...")
    resp = await client.get(f"/objects/{customer_id}")
    customer_obj = _check(resp, "object", "Customer (fetch)", expected=200)
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

    # 5. API
    log(f"Creating API '{API['title']}'...")
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

    # 6. Endpoints
    for ep_def in ENDPOINTS:
        log(f"  Creating endpoint {ep_def['method']} {ep_def['path']}...")
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


async def clean_shop(client: AsyncClient, log=None) -> None:
    """Delete the Shop namespace and all its contents.

    Deletes in reverse dependency order:
    endpoints -> APIs -> objects (cascade deletes relationships) -> fields -> namespace.

    :param log: Optional callable for progress output (e.g. print). Silent by default.
    """
    if log is None:
        log = lambda *_: None

    # Find Shop namespace
    resp = await client.get("/namespaces")
    if resp.status_code != 200:
        raise SeedError("catalogue", "namespaces", resp.status_code, resp.text)
    all_namespaces = resp.json()
    shop_ns = next((ns for ns in all_namespaces if ns["name"] == "Shop"), None)
    if shop_ns is None:
        log("Nothing to clean — 'Shop' namespace not found.")
        return

    ns_id = shop_ns["id"]

    # Always promote Global as default before deletion.
    # The backend blocks deletion of the default namespace, so we ensure
    # Global (always present) is default regardless of the current state.
    global_ns = next((ns for ns in all_namespaces if ns["name"] == "Global"), None)
    if global_ns is None:
        raise SeedError("namespace", "Global", 404, "Global namespace not found")
    log("Setting 'Global' as default namespace...")
    resp = await client.put(f"/namespaces/{global_ns['id']}", json={"isDefault": True})
    if resp.status_code not in (200, 204):
        raise SeedError("namespace", "Global", resp.status_code, resp.text)

    # Delete endpoints (only those belonging to Shop APIs)
    resp = await client.get(f"/apis?namespace_id={ns_id}")
    shop_apis = []
    if resp.status_code == 200:
        shop_apis = resp.json()
    api_ids = {api["id"] for api in shop_apis}

    resp = await client.get("/endpoints")
    if resp.status_code == 200:
        for ep in resp.json():
            if ep.get("apiId") in api_ids:
                ep_name = f"{ep.get('method', '')} {ep.get('path', ep['id'])}"
                log(f"  Deleting endpoint {ep_name}...")
                r = await client.delete(f"/endpoints/{ep['id']}")
                _check_delete(r, "endpoint", ep_name)

    # Delete APIs
    for api in shop_apis:
        api_name = api.get("title", api["id"])
        log(f"Deleting API '{api_name}'...")
        r = await client.delete(f"/apis/{api['id']}")
        _check_delete(r, "api", api_name)

    # Delete objects (cascade deletes relationships)
    resp = await client.get(f"/objects?namespace_id={ns_id}")
    if resp.status_code == 200:
        for obj in resp.json():
            obj_name = obj.get("name", obj["id"])
            log(f"Deleting object '{obj_name}'...")
            r = await client.delete(f"/objects/{obj['id']}")
            _check_delete(r, "object", obj_name)

    # Delete fields
    resp = await client.get(f"/fields?namespace_id={ns_id}")
    if resp.status_code == 200:
        for f in resp.json():
            field_name = f.get("name", f["id"])
            log(f"  Deleting field '{field_name}'...")
            r = await client.delete(f"/fields/{f['id']}")
            _check_delete(r, "field", field_name)

    # Delete namespace
    log("Deleting namespace 'Shop'...")
    r = await client.delete(f"/namespaces/{ns_id}")
    _check_delete(r, "namespace", "Shop")
