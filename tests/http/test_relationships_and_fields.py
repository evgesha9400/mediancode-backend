# tests/http/test_relationships_and_fields.py
"""Integration tests: relationships, FK auto-creation, and field roles/defaults.

Merged coverage from legacy test_relationships.py, test_relationship_fk.py,
test_field_appears.py, test_object_server_default.py.
"""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_http_rels"


# ---------------------------------------------------------------------------
# TestRelationshipCrud — relationship CRUD with auto-inverse
# ---------------------------------------------------------------------------


class TestRelationshipCrud:
    """Tests for relationship CRUD and auto-inverse logic."""

    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    user_obj_id: str = ""
    post_obj_id: str = ""
    tag_obj_id: str = ""
    str_type_id: str = ""
    int_type_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and 3 objects (User/Post/Tag) with PKs."""
        cls = TestRelationshipCrud

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

    async def test_has_many_creates_inverse(self, client: AsyncClient):
        """has_many creates inverse 'references' and returns RelationshipMutationResponse."""
        cls = TestRelationshipCrud

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

        assert "updatedObjects" in body
        assert "createdFields" in body
        assert "deletedFieldIds" in body
        assert len(body["updatedObjects"]) == 2

        source = next(o for o in body["updatedObjects"] if o["id"] == cls.user_obj_id)
        user_rel = next(r for r in source["relationships"] if r["name"] == "posts")
        assert user_rel["cardinality"] == "has_many"
        assert user_rel["isInferred"] is False
        assert user_rel["inverseId"] is not None

        target = next(o for o in body["updatedObjects"] if o["id"] == cls.post_obj_id)
        assert len(target["relationships"]) == 1
        inverse = target["relationships"][0]
        assert inverse["name"] == "user"
        assert inverse["cardinality"] == "references"
        assert inverse["isInferred"] is True

    async def test_many_to_many_creates_inverse(self, client: AsyncClient):
        """many_to_many creates inverse many_to_many, no createdFields."""
        cls = TestRelationshipCrud

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

        tag = next(o for o in body["updatedObjects"] if o["id"] == cls.tag_obj_id)
        m2m_rels = [
            r for r in tag["relationships"] if r["cardinality"] == "many_to_many"
        ]
        assert len(m2m_rels) == 1
        assert m2m_rels[0]["name"] == "posts"

    async def test_relationships_in_object_response(self, client: AsyncClient):
        """Object GET includes relationships array."""
        cls = TestRelationshipCrud

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
        cls = TestRelationshipCrud

        resp = await client.get(f"/objects/{cls.user_obj_id}")
        user = resp.json()
        rel = user["relationships"][0]
        rel_id = rel["id"]

        resp = await client.delete(f"/objects/{cls.user_obj_id}/relationships/{rel_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert "updatedObjects" in body
        assert "createdFields" in body
        assert "deletedFieldIds" in body
        assert len(body["updatedObjects"]) == 2

        source = next(o for o in body["updatedObjects"] if o["id"] == cls.user_obj_id)
        assert len(source["relationships"]) == 0

        target = next(o for o in body["updatedObjects"] if o["id"] == cls.post_obj_id)
        refs_rels = [
            r for r in target["relationships"] if r["cardinality"] == "references"
        ]
        assert len(refs_rels) == 0

    async def test_delete_object_cascades_relationships(self, client: AsyncClient):
        """Deleting an object cascades to its relationships."""
        cls = TestRelationshipCrud

        resp = await client.delete(f"/objects/{cls.post_obj_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/objects/{cls.tag_obj_id}")
        assert resp.status_code == 200
        tag = resp.json()
        assert len(tag["relationships"]) == 0

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestRelationshipCrud

        for obj_id in [cls.user_obj_id, cls.tag_obj_id]:
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
# TestFkAutoCreation — FK field auto-creation on relationships
# ---------------------------------------------------------------------------


class TestFkAutoCreation:
    """Tests for automatic FK field creation/deletion on relationships."""

    namespace_id: str = ""
    type_id: str = ""
    field_ids: dict[str, str] = {}
    order_obj_id: str = ""
    customer_obj_id: str = ""
    product_obj_id: str = ""
    category_obj_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and 4 objects with int PKs."""
        cls = TestFkAutoCreation

        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_id = next(t["id"] for t in resp.json() if t["name"] == "int")

        resp = await client.post(
            "/namespaces", json={"name": "FkTestNs", "description": "FK test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        for name in ("order_name", "customer_name", "product_name", "category_name"):
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

        for name in ("order_id", "customer_id", "product_id", "category_id"):
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

        for obj_name, pk_field, data_field in [
            ("Order", "order_id", "order_name"),
            ("Customer", "customer_id", "customer_name"),
            ("Product", "product_id", "product_name"),
            ("Category", "category_id", "category_name"),
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
            assert resp.status_code == 201, f"Failed creating {obj_name}: {resp.text}"
            obj_id = resp.json()["id"]
            if obj_name == "Order":
                cls.order_obj_id = obj_id
            elif obj_name == "Customer":
                cls.customer_obj_id = obj_id
            elif obj_name == "Product":
                cls.product_obj_id = obj_id
            else:
                cls.category_obj_id = obj_id

    async def test_references_creates_fk_field(self, client: AsyncClient):
        """references relationship returns FK field in createdFields."""
        cls = TestFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.order_obj_id}/relationships",
            json={
                "targetObjectId": cls.customer_obj_id,
                "name": "customer",
                "cardinality": "references",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        assert len(body["createdFields"]) >= 1
        fk_field = body["createdFields"][0]
        assert fk_field["name"] == "customer_id"

        source = next(o for o in body["updatedObjects"] if o["id"] == cls.order_obj_id)
        fk_fields = [f for f in source["fields"] if f["role"] == "fk"]
        assert len(fk_fields) == 1
        assert fk_fields[0]["fieldId"] == fk_field["id"]

        refs_rel = next(
            r for r in source["relationships"] if r["cardinality"] == "references"
        )
        assert refs_rel["fkFieldId"] == fk_field["id"]

    async def test_fk_type_matches_target_pk(self, client: AsyncClient):
        """FK field type matches the target object's PK field type."""
        cls = TestFkAutoCreation

        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_assoc = next(f for f in order["fields"] if f["role"] == "fk")
        fk_field_id = fk_assoc["fieldId"]

        resp = await client.get(f"/fields/{fk_field_id}")
        assert resp.status_code == 200
        fk_field = resp.json()
        assert fk_field["name"] == "customer_id"

        resp = await client.get(f"/fields/{cls.field_ids['customer_id']}")
        assert resp.status_code == 200
        pk_field = resp.json()

        assert fk_field["typeId"] == pk_field["typeId"]

    async def test_has_many_inverse_fk_on_target(self, client: AsyncClient):
        """has_many: inverse FK on target (Product), not on source (Customer)."""
        cls = TestFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.customer_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "products",
                "cardinality": "has_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        source = next(
            o for o in body["updatedObjects"] if o["id"] == cls.customer_obj_id
        )
        has_many_rel = next(
            r for r in source["relationships"] if r["name"] == "products"
        )
        assert has_many_rel["fkFieldId"] is None

        target = next(
            o for o in body["updatedObjects"] if o["id"] == cls.product_obj_id
        )
        inverse = next(
            r for r in target["relationships"] if r["cardinality"] == "references"
        )
        assert inverse["fkFieldId"] is not None

        assert len(body["createdFields"]) >= 1
        fk_ids = [f["id"] for f in body["createdFields"]]
        assert inverse["fkFieldId"] in fk_ids

        fk_fields = [f for f in target["fields"] if f["role"] == "fk"]
        assert len(fk_fields) >= 1
        assert any(f["fieldId"] == inverse["fkFieldId"] for f in fk_fields)

    async def test_has_one_inverse_fk_on_target(self, client: AsyncClient):
        """has_one: inverse FK on target (Product), not on source (Category)."""
        cls = TestFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.category_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "featured_product",
                "cardinality": "has_one",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        source = next(
            o for o in body["updatedObjects"] if o["id"] == cls.category_obj_id
        )
        has_one_rel = next(
            r for r in source["relationships"] if r["name"] == "featured_product"
        )
        assert has_one_rel["fkFieldId"] is None

        target = next(
            o for o in body["updatedObjects"] if o["id"] == cls.product_obj_id
        )
        inverse = next(
            r
            for r in target["relationships"]
            if r["cardinality"] == "references"
            and r["targetObjectId"] == cls.category_obj_id
        )
        assert inverse["fkFieldId"] is not None

    async def test_many_to_many_no_fk(self, client: AsyncClient):
        """many_to_many: no createdFields, fkFieldId null on both sides."""
        cls = TestFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.order_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "items",
                "cardinality": "many_to_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        body = resp.json()

        assert body["createdFields"] == []

        source = next(o for o in body["updatedObjects"] if o["id"] == cls.order_obj_id)
        m2m_rel = next(r for r in source["relationships"] if r["name"] == "items")
        assert m2m_rel["fkFieldId"] is None

        target = next(
            o for o in body["updatedObjects"] if o["id"] == cls.product_obj_id
        )
        m2m_inverse = next(
            r
            for r in target["relationships"]
            if r["cardinality"] == "many_to_many"
            and r["targetObjectId"] == cls.order_obj_id
        )
        assert m2m_inverse["fkFieldId"] is None

    async def test_fk_field_nullable_default_false(self, client: AsyncClient):
        """Auto-created FK fields default to nullable=False."""
        cls = TestFkAutoCreation

        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_assoc = next(f for f in order["fields"] if f["role"] == "fk")
        assert fk_assoc["optional"] is False

    async def test_delete_references_returns_deleted_fk(self, client: AsyncClient):
        """Deleting a references relationship returns FK field in deletedFieldIds."""
        cls = TestFkAutoCreation

        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        refs_rel = next(
            r for r in order["relationships"] if r["cardinality"] == "references"
        )
        rel_id = refs_rel["id"]
        fk_field_id = refs_rel["fkFieldId"]
        assert fk_field_id is not None

        resp = await client.delete(
            f"/objects/{cls.order_obj_id}/relationships/{rel_id}"
        )
        assert resp.status_code == 200
        body = resp.json()

        assert fk_field_id in body["deletedFieldIds"]
        assert len(body["updatedObjects"]) == 2

        source = next(o for o in body["updatedObjects"] if o["id"] == cls.order_obj_id)
        fk_fields = [f for f in source["fields"] if f["role"] == "fk"]
        assert len(fk_fields) == 0

        resp = await client.get(f"/fields/{fk_field_id}")
        assert resp.status_code == 404

    async def test_delete_has_many_returns_inverse_fk(self, client: AsyncClient):
        """Deleting a has_many returns inverse FK field ID in deletedFieldIds."""
        cls = TestFkAutoCreation

        resp = await client.get(f"/objects/{cls.customer_obj_id}")
        assert resp.status_code == 200
        customer = resp.json()
        has_many_rel = next(
            r for r in customer["relationships"] if r["cardinality"] == "has_many"
        )
        rel_id = has_many_rel["id"]

        resp = await client.get(f"/objects/{cls.product_obj_id}")
        assert resp.status_code == 200
        product = resp.json()
        inverse_rel = next(
            r
            for r in product["relationships"]
            if r["cardinality"] == "references"
            and r["targetObjectId"] == cls.customer_obj_id
        )
        inverse_fk_field_id = inverse_rel["fkFieldId"]
        assert inverse_fk_field_id is not None

        resp = await client.delete(
            f"/objects/{cls.customer_obj_id}/relationships/{rel_id}"
        )
        assert resp.status_code == 200
        body = resp.json()

        assert inverse_fk_field_id in body["deletedFieldIds"]

        resp = await client.get(f"/fields/{inverse_fk_field_id}")
        assert resp.status_code == 404

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestFkAutoCreation

        for obj_id in [
            cls.order_obj_id,
            cls.customer_obj_id,
            cls.product_obj_id,
            cls.category_obj_id,
        ]:
            if obj_id:
                resp = await client.get(f"/objects/{obj_id}")
                if resp.status_code == 200:
                    for rel in resp.json().get("relationships", []):
                        await client.delete(
                            f"/objects/{obj_id}/relationships/{rel['id']}"
                        )

        for obj_id in [
            cls.order_obj_id,
            cls.customer_obj_id,
            cls.product_obj_id,
            cls.category_obj_id,
        ]:
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
            assert resp.status_code == 201, f"Failed to create field {name}: {resp.text}"
            cls.field_ids[name] = resp.json()["id"]

    async def test_create_object_with_roles(self, client: AsyncClient):
        """Create object with writable, write_only, read_only roles."""
        cls = TestFieldRolesAndDefaults

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Account",
                "description": "Test object with role flags",
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "optional": False,
                        "role": "writable",
                    },
                    {
                        "fieldId": cls.field_ids["password"],
                        "optional": False,
                        "role": "write_only",
                    },
                    {
                        "fieldId": cls.field_ids["created_at"],
                        "optional": False,
                        "role": "read_only",
                    },
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create object: {resp.text}"
        obj = resp.json()
        cls.object_id = obj["id"]

        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["role"] == "writable"
        assert fields_by_id[cls.field_ids["password"]]["role"] == "write_only"
        assert fields_by_id[cls.field_ids["created_at"]]["role"] == "read_only"

    async def test_get_returns_roles(self, client: AsyncClient):
        """GET returns role values."""
        cls = TestFieldRolesAndDefaults

        resp = await client.get(f"/objects/{cls.object_id}")
        assert resp.status_code == 200
        obj = resp.json()

        fields_by_id = {f["fieldId"]: f for f in obj["fields"]}
        assert fields_by_id[cls.field_ids["email"]]["role"] == "writable"
        assert fields_by_id[cls.field_ids["password"]]["role"] == "write_only"
        assert fields_by_id[cls.field_ids["created_at"]]["role"] == "read_only"

    async def test_default_role_is_writable(self, client: AsyncClient):
        """When role is not specified, it defaults to 'writable'."""
        cls = TestFieldRolesAndDefaults

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": cls.field_ids["email"],
                        "optional": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        obj = resp.json()
        assert len(obj["fields"]) == 1
        assert obj["fields"][0]["role"] == "writable"

    async def test_created_timestamp_role_persisted(self, client: AsyncClient):
        """created_timestamp role is persisted on create."""
        cls = TestFieldRolesAndDefaults

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": cls.field_ids["created_at"],
                        "role": "created_timestamp",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["fields"]) == 1
        assert body["fields"][0]["role"] == "created_timestamp"
        assert body["fields"][0]["optional"] is False
        assert body["fields"][0]["defaultValue"] is None

    async def test_literal_default_persisted_on_update(self, client: AsyncClient):
        """Literal defaultValue persisted on update (e.g. '0' for read_only int)."""
        cls = TestFieldRolesAndDefaults

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": cls.field_ids["sort_order"],
                        "optional": False,
                        "role": "read_only",
                        "defaultValue": "0",
                    }
                ],
            },
        )
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        body = resp.json()
        assert len(body["fields"]) == 1
        assert body["fields"][0]["defaultValue"] == "0"
        assert body["fields"][0]["role"] == "read_only"

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
