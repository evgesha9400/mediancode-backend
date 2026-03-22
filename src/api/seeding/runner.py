"""Shop API seed runner — creates/deletes Shop structure via API calls."""

from __future__ import annotations

from dataclasses import dataclass, field

from httpx import AsyncClient

from api.seeding.shop_data import (
    ALL_FIELDS,
    API,
    ENDPOINTS,
    OBJECTS,
    RELATIONSHIP,
)


class SeedError(Exception):
    """Raised when a seed API call fails."""

    def __init__(self, entity_type: str, name: str, status_code: int, detail: str):
        self.entity_type = entity_type
        self.name = name
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"Failed to create {entity_type} '{name}': "
            f"HTTP {status_code} — {detail}"
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


async def seed_shop(client: AsyncClient) -> SeedResult:
    """Create the full Shop API structure via API calls.

    The client must be pre-configured with base_url and auth headers
    (or ASGI transport with dependency overrides for tests).
    """
    result = SeedResult()
    cat = await _read_catalogues(client)

    # 1. Namespace
    resp = await client.post("/namespaces", json={"name": "Shop", "isDefault": True})
    ns = _check(resp, "namespace", "Shop")
    result.namespace_id = ns["id"]

    # 2. Fields
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

    # 3. Objects
    for obj_def in OBJECTS:
        obj_fields = []
        for fref in obj_def["fields"]:
            field_payload: dict = {
                "fieldId": result.field_ids[fref["field_name"]],
                "optional": fref["optional"],
                "isPk": fref["is_pk"],
                "appears": fref["appears"],
            }
            if fref.get("server_default") is not None:
                field_payload["serverDefault"] = fref["server_default"]
            if fref.get("default_literal") is not None:
                field_payload["defaultLiteral"] = fref["default_literal"]
            obj_fields.append(field_payload)
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
            "fields": obj_fields,
            "validators": obj_validators,
        }
        resp = await client.post("/objects", json=payload)
        obj = _check(resp, "object", obj_def["name"])
        result.object_ids[obj_def["name"]] = obj["id"]

    # 4. Relationship (API auto-creates bidirectional inverse)
    source_id = result.object_ids[RELATIONSHIP["source_object"]]
    resp = await client.post(
        f"/objects/{source_id}/relationships",
        json={
            "targetObjectId": result.object_ids[RELATIONSHIP["target_object"]],
            "name": RELATIONSHIP["name"],
            "cardinality": RELATIONSHIP["cardinality"],
        },
    )
    rel = _check(resp, "relationship", RELATIONSHIP["name"])
    result.relationship_ids.append(rel["id"])
    if rel.get("inverseId"):
        result.relationship_ids.append(rel["inverseId"])

    # 5. API
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
    """
    # Find Shop namespace
    resp = await client.get("/namespaces")
    if resp.status_code != 200:
        raise SeedError("catalogue", "namespaces", resp.status_code, resp.text)
    shop_ns = None
    for ns in resp.json():
        if ns["name"] == "Shop":
            shop_ns = ns
            break
    if shop_ns is None:
        return  # Nothing to clean

    ns_id = shop_ns["id"]

    # Delete endpoints (only those belonging to Shop APIs)
    resp = await client.get(f"/apis?namespace_id={ns_id}")
    api_ids = set()
    if resp.status_code == 200:
        api_ids = {api["id"] for api in resp.json()}

    resp = await client.get("/endpoints")
    if resp.status_code == 200:
        for ep in resp.json():
            if ep.get("apiId") in api_ids:
                await client.delete(f"/endpoints/{ep['id']}")

    # Delete APIs
    for api_id in api_ids:
        await client.delete(f"/apis/{api_id}")

    # Delete objects (cascade deletes relationships)
    resp = await client.get(f"/objects?namespace_id={ns_id}")
    if resp.status_code == 200:
        for obj in resp.json():
            await client.delete(f"/objects/{obj['id']}")

    # Delete fields
    resp = await client.get(f"/fields?namespace_id={ns_id}")
    if resp.status_code == 200:
        for f in resp.json():
            await client.delete(f"/fields/{f['id']}")

    # Delete namespace
    await client.delete(f"/namespaces/{ns_id}")
