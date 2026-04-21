# tests/http/test_object_member_reconcile.py
"""Integration tests: PUT /objects/{id} member reconcile-by-id error cases.

These assert that the backend fails loudly (HTTP 400) when a client sends a
member id that does not exist or belongs to another object, rather than
silently no-op'ing and returning 200 with the members dropped. The latter
behaviour previously allowed a client-side regression to go unnoticed for
10 nightlies; the frontend fix prevents the bad payload, and this suite
prevents any other client from recreating the same silent-loss failure mode.
"""

from httpx import AsyncClient
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_object_member_reconcile"

UNKNOWN_MEMBER_ID = "00000000-0000-0000-0000-0000deadbeef"


class TestObjectMemberReconcile:
    """Create two objects with one member each, then exercise PUT error modes."""

    type_ids: dict[str, str] = {}
    namespace_id: str = ""
    str_field_id: str = ""
    obj_a_id: str = ""
    obj_b_id: str = ""
    obj_a_member_id: str = ""
    obj_b_member_id: str = ""

    # --- Setup ---

    async def test_phase_01_read_catalogues(self, client: AsyncClient):
        """Read types needed to create fields."""
        cls = TestObjectMemberReconcile

        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

    async def test_phase_02_create_namespace(self, client: AsyncClient):
        """Create a namespace to scope the fixtures."""
        cls = TestObjectMemberReconcile
        resp = await client.post(
            "/namespaces",
            json={"name": "ReconcileNs", "description": "reconcile tests"},
        )
        assert resp.status_code == 201, resp.text
        cls.namespace_id = resp.json()["id"]

    async def test_phase_03_create_field(self, client: AsyncClient):
        """Create a scalar field to attach to both objects."""
        cls = TestObjectMemberReconcile
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "reconcile_title",
                "typeId": cls.type_ids["str"],
                "description": "",
            },
        )
        assert resp.status_code == 201, resp.text
        cls.str_field_id = resp.json()["id"]

    async def test_phase_04_create_object_a(self, client: AsyncClient):
        """Create object A with one member; capture its server-assigned id."""
        cls = TestObjectMemberReconcile
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "ReconcileObjectA",
                "description": "",
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": False,
                    }
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        cls.obj_a_id = body["id"]
        assert len(body["members"]) == 1
        cls.obj_a_member_id = body["members"][0]["id"]

    async def test_phase_05_create_object_b(self, client: AsyncClient):
        """Create object B with one member; capture its server-assigned id."""
        cls = TestObjectMemberReconcile
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "ReconcileObjectB",
                "description": "",
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": False,
                    }
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        cls.obj_b_id = body["id"]
        cls.obj_b_member_id = body["members"][0]["id"]

    # --- Error cases ---

    async def test_phase_06_unknown_member_id_rejects_with_400(
        self, client: AsyncClient
    ):
        """PUT with an unknown member id returns 400, not a silent drop."""
        cls = TestObjectMemberReconcile
        resp = await client.put(
            f"/objects/{cls.obj_a_id}",
            json={
                "members": [
                    {
                        "memberType": "scalar",
                        "id": UNKNOWN_MEMBER_ID,
                        "name": "title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": False,
                    }
                ],
            },
        )
        assert resp.status_code == 400, resp.text
        assert "unknown member id" in resp.json()["detail"].lower()

    async def test_phase_07_mis_owned_member_id_rejects_with_400(
        self, client: AsyncClient
    ):
        """PUT with a member id owned by another object returns 400."""
        cls = TestObjectMemberReconcile
        resp = await client.put(
            f"/objects/{cls.obj_a_id}",
            json={
                "members": [
                    {
                        "memberType": "scalar",
                        "id": cls.obj_b_member_id,
                        "name": "title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": False,
                    }
                ],
            },
        )
        assert resp.status_code == 400, resp.text
        assert "different object" in resp.json()["detail"].lower()

    # --- Happy path after rejected updates ---

    async def test_phase_08_happy_path_keeps_updating_existing_and_inserting_new(
        self, client: AsyncClient
    ):
        """PUT with real id (update) + fresh member without id (insert) → 200."""
        cls = TestObjectMemberReconcile
        resp = await client.put(
            f"/objects/{cls.obj_a_id}",
            json={
                "members": [
                    {
                        "memberType": "scalar",
                        "id": cls.obj_a_member_id,
                        "name": "renamed_title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": True,
                    },
                    {
                        "memberType": "scalar",
                        "name": "fresh_title",
                        "fieldId": cls.str_field_id,
                        "role": "writable",
                        "isNullable": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        members = resp.json()["members"]
        assert len(members) == 2
        names = {m["name"] for m in members}
        assert names == {"renamed_title", "fresh_title"}

    # --- Teardown ---

    async def test_phase_99_cleanup(self, client: AsyncClient):
        """Delete all fixtures created by this class."""
        cls = TestObjectMemberReconcile

        if cls.obj_a_id:
            resp = await client.delete(f"/objects/{cls.obj_a_id}")
            assert resp.status_code == 204
        if cls.obj_b_id:
            resp = await client.delete(f"/objects/{cls.obj_b_id}")
            assert resp.status_code == 204
        if cls.str_field_id:
            resp = await client.delete(f"/fields/{cls.str_field_id}")
            assert resp.status_code == 204
        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
