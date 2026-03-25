# tests/http/test_relationships_and_fields.py
"""Integration tests: unified members, relationships, derived inverses, field roles.

Tests the unified member model: relationship members as part of object CRUD,
derived relationships, reconcile-by-ID, inverse_name validation, and field roles.
"""

from httpx import AsyncClient
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_http_rels"


# ---------------------------------------------------------------------------
# TestRelationshipMembers — unified member CRUD with relationships
# ---------------------------------------------------------------------------


class TestRelationshipMembers:
    """Tests for relationship members as part of object CRUD."""

    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    user_obj_id: str = ""
    post_obj_id: str = ""
    tag_obj_id: str = ""
    str_type_id: str = ""
    int_type_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and 3 objects (User/Post/Tag) with PKs."""
        cls = TestRelationshipMembers

        resp = await client.get("/types")
        assert resp.status_code == 200
        types = resp.json()
        cls.str_type_id = next(t["id"] for t in types if t["name"] == "str")
        cls.int_type_id = next(t["id"] for t in types if t["name"] == "int")

        resp = await client.post(
            "/namespaces", json={"name": "RelTestNs", "description": "test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        for name in ("username", "title", "tag_name"):
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": name,
                    "typeId": cls.str_type_id,
                },
            )
            assert resp.status_code == 201
            cls.field_ids[name] = resp.json()["id"]

        for name in ("user_id", "post_id", "tag_id"):
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": name,
                    "typeId": cls.int_type_id,
                },
            )
            assert resp.status_code == 201
            cls.field_ids[name] = resp.json()["id"]

        # Create objects with scalar members only first
        for obj_name, pk_field, data_field in [
            ("User", "user_id", "username"),
            ("Post", "post_id", "title"),
            ("Tag", "tag_id", "tag_name"),
        ]:
            resp = await client.post(
                "/objects",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": obj_name,
                    "members": [
                        {
                            "memberType": "scalar",
                            "name": pk_field,
                            "fieldId": cls.field_ids[pk_field],
                            "role": "pk",
                        },
                        {
                            "memberType": "scalar",
                            "name": data_field,
                            "fieldId": cls.field_ids[data_field],
                        },
                    ],
                },
            )
            assert resp.status_code == 201
            obj_id = resp.json()["id"]
            if obj_name == "User":
                cls.user_obj_id = obj_id
            elif obj_name == "Post":
                cls.post_obj_id = obj_id
            else:
                cls.tag_obj_id = obj_id

    async def test_one_to_many_via_update(self, client: AsyncClient):
        """Add a one_to_many relationship member via PUT, verify derived relationship on target."""
        cls = TestRelationshipMembers

        # Get current User members
        resp = await client.get(f"/objects/{cls.user_obj_id}")
        assert resp.status_code == 200
        user = resp.json()
        members = user["members"]

        # Add relationship member
        members.append(
            {
                "memberType": "relationship",
                "name": "posts",
                "targetObjectId": cls.post_obj_id,
                "kind": "one_to_many",
                "inverseName": "author",
                "required": True,
            }
        )

        resp = await client.put(
            f"/objects/{cls.user_obj_id}",
            json={"members": members},
        )
        assert resp.status_code == 200
        updated = resp.json()

        # Verify authored relationship is in members
        rel_members = [
            m for m in updated["members"] if m["memberType"] == "relationship"
        ]
        assert len(rel_members) == 1
        assert rel_members[0]["name"] == "posts"
        assert rel_members[0]["kind"] == "one_to_many"
        assert rel_members[0]["inverseName"] == "author"

        # Verify derived relationship on Post
        resp = await client.get(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 200
        post = resp.json()
        assert len(post["derivedRelationships"]) == 1
        derived = post["derivedRelationships"][0]
        assert derived["name"] == "author"
        assert derived["sourceObject"] == "User"
        assert derived["sourceObjectId"] is not None
        assert derived["sourceField"] == "posts"
        assert derived["kind"] == "one_to_many"
        assert derived["side"] == "many"
        assert derived["impliesFk"] == "author_id"
        assert derived["required"] is True

    async def test_many_to_many_via_update(self, client: AsyncClient):
        """Add a many_to_many relationship member, verify derived on target."""
        cls = TestRelationshipMembers

        resp = await client.get(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 200
        post = resp.json()
        members = post["members"]

        members.append(
            {
                "memberType": "relationship",
                "name": "tags",
                "targetObjectId": cls.tag_obj_id,
                "kind": "many_to_many",
                "inverseName": "posts",
                "required": False,
            }
        )

        resp = await client.put(
            f"/objects/{cls.post_obj_id}",
            json={"members": members},
        )
        assert resp.status_code == 200

        # Verify derived on Tag
        resp = await client.get(f"/objects/{cls.tag_obj_id}")
        assert resp.status_code == 200
        tag = resp.json()
        m2m_derived = [
            d for d in tag["derivedRelationships"] if d["kind"] == "many_to_many"
        ]
        assert len(m2m_derived) == 1
        assert m2m_derived[0]["name"] == "posts"
        assert m2m_derived[0]["impliesFk"] is None
        assert m2m_derived[0]["junctionTable"] is not None

    async def test_reconcile_by_id_preserves_members(self, client: AsyncClient):
        """PUT with member IDs updates in place, new members inserted, missing deleted."""
        cls = TestRelationshipMembers

        resp = await client.get(f"/objects/{cls.user_obj_id}")
        assert resp.status_code == 200
        user = resp.json()
        original_members = user["members"]
        assert len(original_members) == 3  # 2 scalar + 1 relationship

        # Keep only the first two (scalar) members, drop the relationship
        kept_members = [m for m in original_members if m["memberType"] == "scalar"]
        resp = await client.put(
            f"/objects/{cls.user_obj_id}",
            json={"members": kept_members},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert len(updated["members"]) == 2
        assert all(m["memberType"] == "scalar" for m in updated["members"])

        # Verify derived relationship removed from Post
        resp = await client.get(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 200
        post = resp.json()
        author_derived = [
            d for d in post["derivedRelationships"] if d["name"] == "author"
        ]
        assert len(author_derived) == 0

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestRelationshipMembers

        for obj_id in [cls.user_obj_id, cls.post_obj_id, cls.tag_obj_id]:
            if obj_id:
                resp = await client.delete(f"/objects/{obj_id}")
                assert resp.status_code in (204, 404)

        for field_id in cls.field_ids.values():
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code in (204, 404)

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code in (204, 404)


# ---------------------------------------------------------------------------
# TestFieldRolesAndDefaults — role persistence and defaultValue round-trip
# ---------------------------------------------------------------------------


class TestFieldRolesAndDefaults:
    """Field role and defaultValue persistence through object CRUD."""

    namespace_id: str = ""
    type_ids: dict[str, str] = {}
    field_ids: dict[str, str] = {}
    object_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace and fields (str, datetime, int types)."""
        cls = TestFieldRolesAndDefaults

        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.post(
            "/namespaces", json={"name": "RoleTestNs", "description": "test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        for name, type_name in [
            ("email", "str"),
            ("password", "str"),
            ("created_at", "datetime"),
            ("sort_order", "int"),
        ]:
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": name,
                    "typeId": cls.type_ids[type_name],
                },
            )
            assert resp.status_code == 201, (
                f"Failed to create field {name}: {resp.text}"
            )
            cls.field_ids[name] = resp.json()["id"]

    async def test_create_object_with_roles(self, client: AsyncClient):
        """Create object with writable, write_only, read_only roles via members."""
        cls = TestFieldRolesAndDefaults

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Account",
                "description": "Test object with role flags",
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "email",
                        "fieldId": cls.field_ids["email"],
                        "isNullable": False,
                        "role": "writable",
                    },
                    {
                        "memberType": "scalar",
                        "name": "password",
                        "fieldId": cls.field_ids["password"],
                        "isNullable": False,
                        "role": "write_only",
                    },
                    {
                        "memberType": "scalar",
                        "name": "created_at",
                        "fieldId": cls.field_ids["created_at"],
                        "isNullable": False,
                        "role": "read_only",
                    },
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create object: {resp.text}"
        obj = resp.json()
        cls.object_id = obj["id"]

        members_by_name = {m["name"]: m for m in obj["members"]}
        assert members_by_name["email"]["role"] == "writable"
        assert members_by_name["password"]["role"] == "write_only"
        assert members_by_name["created_at"]["role"] == "read_only"

    async def test_get_returns_roles(self, client: AsyncClient):
        """GET returns role values in members."""
        cls = TestFieldRolesAndDefaults

        resp = await client.get(f"/objects/{cls.object_id}")
        assert resp.status_code == 200
        obj = resp.json()

        members_by_name = {m["name"]: m for m in obj["members"]}
        assert members_by_name["email"]["role"] == "writable"
        assert members_by_name["password"]["role"] == "write_only"
        assert members_by_name["created_at"]["role"] == "read_only"

    async def test_created_timestamp_role_persisted(self, client: AsyncClient):
        """created_timestamp role is persisted on update."""
        cls = TestFieldRolesAndDefaults

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "created_at",
                        "fieldId": cls.field_ids["created_at"],
                        "role": "created_timestamp",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["members"]) == 1
        assert body["members"][0]["role"] == "created_timestamp"
        assert body["members"][0]["isNullable"] is False
        assert body["members"][0]["defaultValue"] is None

    async def test_literal_default_persisted_on_update(self, client: AsyncClient):
        """Literal defaultValue persisted on update."""
        cls = TestFieldRolesAndDefaults

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "sort_order",
                        "fieldId": cls.field_ids["sort_order"],
                        "isNullable": False,
                        "role": "read_only",
                        "defaultValue": "0",
                    }
                ],
            },
        )
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        body = resp.json()
        assert len(body["members"]) == 1
        assert body["members"][0]["defaultValue"] == "0"
        assert body["members"][0]["role"] == "read_only"

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestFieldRolesAndDefaults

        if cls.object_id:
            resp = await client.delete(f"/objects/{cls.object_id}")
            assert resp.status_code == 204

        for field_id in cls.field_ids.values():
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code == 204

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
