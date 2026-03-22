# tests/test_api/test_field_appears.py
"""Integration tests for the `exposure` field on object field references."""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]


class TestFieldExposure:
    """Tests for the `exposure` column on fields_on_objects."""

    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    object_id: str = ""
    type_id: str = ""

    async def test_setup_namespace_and_fields(self, client: AsyncClient):
        """Create a namespace and three fields for testing."""
        cls = TestFieldExposure

        # Get system type (str)
        resp = await client.get("/types")
        assert resp.status_code == 200
        types = resp.json()
        cls.type_id = next(t["id"] for t in types if t["name"] == "str")

        # Create namespace
        resp = await client.post(
            "/namespaces", json={"name": "ExposureTestNs", "description": "test"}
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

    async def test_create_object_with_exposure(self, client: AsyncClient):
        """Create an object with mixed exposure values."""
        cls = TestFieldExposure

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Account",
                "description": "Test object with exposure flags",
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "nullable": False,
                        "isPk": False,
                        "exposure": "read_write",
                    },
                    {
                        "fieldId": cls.field_ids["password"],
                        "nullable": False,
                        "isPk": False,
                        "exposure": "write_only",
                    },
                    {
                        "fieldId": cls.field_ids["created_at"],
                        "nullable": False,
                        "isPk": False,
                        "exposure": "read_only",
                    },
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create object: {resp.text}"
        obj = resp.json()
        cls.object_id = obj["id"]

        # Verify exposure values in create response
        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["exposure"] == "read_write"
        assert fields_by_id[cls.field_ids["password"]]["exposure"] == "write_only"
        assert fields_by_id[cls.field_ids["created_at"]]["exposure"] == "read_only"

    async def test_get_object_returns_exposure(self, client: AsyncClient):
        """Verify exposure values are returned on GET."""
        cls = TestFieldExposure

        resp = await client.get(f"/objects/{cls.object_id}")
        assert resp.status_code == 200
        obj = resp.json()

        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["exposure"] == "read_write"
        assert fields_by_id[cls.field_ids["password"]]["exposure"] == "write_only"
        assert fields_by_id[cls.field_ids["created_at"]]["exposure"] == "read_only"

    async def test_default_exposure_is_read_write(self, client: AsyncClient):
        """When exposure is not specified, it defaults to 'read_write'."""
        cls = TestFieldExposure

        # Update object with fields that don't specify exposure
        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "nullable": False,
                        "isPk": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        obj = resp.json()
        assert len(obj["fields"]) == 1
        assert obj["fields"][0]["exposure"] == "read_write"

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestFieldExposure

        if cls.object_id:
            resp = await client.delete(f"/objects/{cls.object_id}")
            assert resp.status_code == 204

        for field_id in cls.field_ids.values():
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code == 204

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
