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
    type_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and objects for relationship testing."""
        cls = TestObjectRelationships

        # Get str type
        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_id = next(t["id"] for t in resp.json() if t["name"] == "str")

        # Namespace
        resp = await client.post(
            "/namespaces", json={"name": "RelTestNs", "description": "test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        # Fields
        for name in ("username", "title", "tag_name"):
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": name,
                    "typeId": cls.type_id,
                },
            )
            assert resp.status_code == 201
            cls.field_ids[name] = resp.json()["id"]

        # Objects
        for obj_name, field_name in [
            ("User", "username"),
            ("Post", "title"),
            ("Tag", "tag_name"),
        ]:
            resp = await client.post(
                "/objects",
                json={
                    "namespaceId": cls.namespace_id,
                    "name": obj_name,
                    "fields": [{"fieldId": cls.field_ids[field_name]}],
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
        """has_many creates inverse 'references' relationship."""
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
        rel = resp.json()
        assert rel["name"] == "posts"
        assert rel["cardinality"] == "has_many"
        assert rel["isInferred"] is False
        assert rel["inverseId"] is not None

        # Verify inverse on target object
        resp = await client.get(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 200
        post = resp.json()
        assert len(post["relationships"]) == 1
        inverse = post["relationships"][0]
        assert inverse["name"] == "user"
        assert inverse["cardinality"] == "references"
        assert inverse["isInferred"] is True

    async def test_create_many_to_many_relationship(self, client: AsyncClient):
        """many_to_many creates inverse many_to_many relationship."""
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
        rel = resp.json()
        assert rel["cardinality"] == "many_to_many"

        # Verify inverse
        resp = await client.get(f"/objects/{cls.tag_obj_id}")
        assert resp.status_code == 200
        tag = resp.json()
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

    async def test_delete_relationship_cascades_inverse(self, client: AsyncClient):
        """Deleting a relationship also deletes its inverse."""
        cls = TestObjectRelationships

        # Get the User->Post relationship
        resp = await client.get(f"/objects/{cls.user_obj_id}")
        user = resp.json()
        rel = user["relationships"][0]
        rel_id = rel["id"]

        # Delete it
        resp = await client.delete(f"/objects/{cls.user_obj_id}/relationships/{rel_id}")
        assert resp.status_code == 204

        # Verify inverse is also gone from Post
        resp = await client.get(f"/objects/{cls.post_obj_id}")
        post = resp.json()
        refs_rels = [
            r for r in post["relationships"] if r["cardinality"] == "references"
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
