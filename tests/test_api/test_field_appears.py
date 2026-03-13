# tests/test_api/test_field_appears.py
"""Integration tests for the `appears` field on object field references."""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]


class TestFieldAppears:
    """Tests for the `appears` column on fields_on_objects."""

    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    object_id: str = ""
    type_id: str = ""

    async def test_setup_namespace_and_fields(self, client: AsyncClient):
        """Create a namespace and three fields for testing."""
        cls = TestFieldAppears

        # Get system type (str)
        resp = await client.get("/types")
        assert resp.status_code == 200
        types = resp.json()
        cls.type_id = next(t["id"] for t in types if t["name"] == "str")

        # Create namespace
        resp = await client.post(
            "/namespaces", json={"name": "AppearTestNs", "description": "test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        # Create fields
        for name in ("email", "password", "created_at"):
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": name,
                    "typeId": cls.type_id,
                },
            )
            assert (
                resp.status_code == 201
            ), f"Failed to create field {name}: {resp.text}"
            cls.field_ids[name] = resp.json()["id"]

    async def test_create_object_with_appears(self, client: AsyncClient):
        """Create an object with mixed appears values."""
        cls = TestFieldAppears

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Account",
                "description": "Test object with appears flags",
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "optional": False,
                        "isPk": False,
                        "appears": "both",
                    },
                    {
                        "fieldId": cls.field_ids["password"],
                        "optional": False,
                        "isPk": False,
                        "appears": "request",
                    },
                    {
                        "fieldId": cls.field_ids["created_at"],
                        "optional": False,
                        "isPk": False,
                        "appears": "response",
                    },
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create object: {resp.text}"
        obj = resp.json()
        cls.object_id = obj["id"]

        # Verify appears values in create response
        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["appears"] == "both"
        assert fields_by_id[cls.field_ids["password"]]["appears"] == "request"
        assert fields_by_id[cls.field_ids["created_at"]]["appears"] == "response"

    async def test_get_object_returns_appears(self, client: AsyncClient):
        """Verify appears values are returned on GET."""
        cls = TestFieldAppears

        resp = await client.get(f"/objects/{cls.object_id}")
        assert resp.status_code == 200
        obj = resp.json()

        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["appears"] == "both"
        assert fields_by_id[cls.field_ids["password"]]["appears"] == "request"
        assert fields_by_id[cls.field_ids["created_at"]]["appears"] == "response"

    async def test_default_appears_is_both(self, client: AsyncClient):
        """When appears is not specified, it defaults to 'both'."""
        cls = TestFieldAppears

        # Update object with fields that don't specify appears
        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "optional": False,
                        "isPk": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        obj = resp.json()
        assert len(obj["fields"]) == 1
        assert obj["fields"][0]["appears"] == "both"

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestFieldAppears

        if cls.object_id:
            resp = await client.delete(f"/objects/{cls.object_id}")
            assert resp.status_code == 204

        for field_id in cls.field_ids.values():
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code == 204

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
