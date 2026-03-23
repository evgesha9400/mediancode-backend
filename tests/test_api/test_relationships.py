# tests/test_api/test_relationships.py
"""Integration tests for object relationships with auto-inverse."""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]


class TestObjectRelationships:
    """Tests for relationship CRUD and auto-inverse logic."""

    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    user_obj_id: str = ""
    post_obj_id: str = ""
    tag_obj_id: str = ""
    str_type_id: str = ""
    int_type_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and objects for relationship testing."""
        cls = TestObjectRelationships

        # Get types
        resp = await client.get("/types")
        assert resp.status_code == 200
        types = resp.json()
        cls.str_type_id = next(t["id"] for t in types if t["name"] == "str")
        cls.int_type_id = next(t["id"] for t in types if t["name"] == "int")

        # Namespace
        resp = await client.post(
            "/namespaces", json={"name": "RelTestNs", "description": "test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        # Data fields (str type)
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

        # PK fields (int type — PK requires int or uuid)
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

        # Objects with PK fields
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
                    "fields": [
                        {"fieldId": cls.field_ids[pk_field], "role": "pk"},
                        {"fieldId": cls.field_ids[data_field]},
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

    async def test_create_has_many_relationship(self, client: AsyncClient):
        """has_many creates inverse 'references' and returns graph mutation."""
        cls = TestObjectRelationships

        resp = await client.post(
            f"/objects/{cls.user_obj_id}/relationships",
            json={
                "targetObjectId": cls.post_obj_id,
                "name": "posts",
                "cardinality": "has_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        # Response is a RelationshipMutationResponse
        assert "updatedObjects" in body
        assert "createdFields" in body
        assert "deletedFieldIds" in body
        assert len(body["updatedObjects"]) == 2

        # Find the source (User) in updated objects
        source = next(
            o for o in body["updatedObjects"] if o["id"] == cls.user_obj_id
        )
        user_rel = next(
            r for r in source["relationships"] if r["name"] == "posts"
        )
        assert user_rel["cardinality"] == "has_many"
        assert user_rel["isInferred"] is False
        assert user_rel["inverseId"] is not None

        # Find the target (Post) — should have inverse
        target = next(
            o for o in body["updatedObjects"] if o["id"] == cls.post_obj_id
        )
        assert len(target["relationships"]) == 1
        inverse = target["relationships"][0]
        assert inverse["name"] == "user"
        assert inverse["cardinality"] == "references"
        assert inverse["isInferred"] is True

    async def test_create_many_to_many_relationship(self, client: AsyncClient):
        """many_to_many creates inverse many_to_many and returns graph mutation."""
        cls = TestObjectRelationships

        resp = await client.post(
            f"/objects/{cls.post_obj_id}/relationships",
            json={
                "targetObjectId": cls.tag_obj_id,
                "name": "tags",
                "cardinality": "many_to_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        assert len(body["updatedObjects"]) == 2
        assert body["createdFields"] == []

        # Verify inverse on Tag
        tag = next(
            o for o in body["updatedObjects"] if o["id"] == cls.tag_obj_id
        )
        m2m_rels = [
            r for r in tag["relationships"] if r["cardinality"] == "many_to_many"
        ]
        assert len(m2m_rels) == 1
        assert m2m_rels[0]["name"] == "posts"

    async def test_relationships_in_object_response(self, client: AsyncClient):
        """Object GET includes relationships array."""
        cls = TestObjectRelationships

        resp = await client.get(f"/objects/{cls.user_obj_id}")
        assert resp.status_code == 200
        user = resp.json()
        assert "relationships" in user
        assert len(user["relationships"]) == 1
        assert user["relationships"][0]["name"] == "posts"

    async def test_delete_relationship_returns_graph_mutation(
        self, client: AsyncClient
    ):
        """Deleting a relationship returns graph mutation with updated objects."""
        cls = TestObjectRelationships

        # Get the User->Post relationship
        resp = await client.get(f"/objects/{cls.user_obj_id}")
        user = resp.json()
        rel = user["relationships"][0]
        rel_id = rel["id"]

        # Delete it
        resp = await client.delete(
            f"/objects/{cls.user_obj_id}/relationships/{rel_id}"
        )
        assert resp.status_code == 200
        body = resp.json()

        # Response is a RelationshipMutationResponse
        assert "updatedObjects" in body
        assert "createdFields" in body
        assert "deletedFieldIds" in body
        assert len(body["updatedObjects"]) == 2

        # Both objects should have the relationship removed
        source = next(
            o for o in body["updatedObjects"] if o["id"] == cls.user_obj_id
        )
        assert len(source["relationships"]) == 0

        target = next(
            o for o in body["updatedObjects"] if o["id"] == cls.post_obj_id
        )
        refs_rels = [
            r for r in target["relationships"] if r["cardinality"] == "references"
        ]
        assert len(refs_rels) == 0

    async def test_delete_object_cascades_relationships(self, client: AsyncClient):
        """Deleting an object cascades to its relationships."""
        cls = TestObjectRelationships

        # Post still has m2m relationship to Tag — delete Post
        # First need to remove Post from any endpoint usage, but it's not in endpoints
        resp = await client.delete(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 204

        # Tag's m2m inverse should be gone too (CASCADE on source_object_id)
        resp = await client.get(f"/objects/{cls.tag_obj_id}")
        assert resp.status_code == 200
        tag = resp.json()
        assert len(tag["relationships"]) == 0

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestObjectRelationships

        for obj_id in [cls.user_obj_id, cls.tag_obj_id]:
            if obj_id:
                resp = await client.delete(f"/objects/{obj_id}")
                # May already be deleted, accept 204 or 404
                assert resp.status_code in (204, 404)

        for field_id in cls.field_ids.values():
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code in (204, 404)

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code in (204, 404)
