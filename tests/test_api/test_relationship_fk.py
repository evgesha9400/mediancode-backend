# tests/test_api/test_relationship_fk.py
"""Integration tests for FK field auto-creation on relationships."""

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]


class TestRelationshipFkAutoCreation:
    """Tests for automatic FK field creation/deletion on relationships."""

    namespace_id: str = ""
    type_id: str = ""
    field_ids: dict[str, str] = {}
    order_obj_id: str = ""
    customer_obj_id: str = ""
    product_obj_id: str = ""
    category_obj_id: str = ""

    async def test_setup(self, client: AsyncClient):
        """Create namespace, fields, and objects with PK fields for FK testing."""
        cls = TestRelationshipFkAutoCreation

        # Get int type (for PK fields)
        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_id = next(t["id"] for t in resp.json() if t["name"] == "int")

        # Namespace
        resp = await client.post(
            "/namespaces", json={"name": "FkTestNs", "description": "FK test"}
        )
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        # Fields
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

        # PK fields
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

        # Objects with PK fields
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
        """Creating a references relationship auto-creates a {name}_id field."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.order_obj_id}/relationships",
            json={
                "targetObjectId": cls.customer_obj_id,
                "name": "customer",
                "cardinality": "references",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        rel = resp.json()
        assert rel["fkFieldId"] is not None

        # Verify FK field appears on the source object
        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_fields = [f for f in order["fields"] if f["role"] == "fk"]
        assert len(fk_fields) == 1
        assert fk_fields[0]["fieldId"] == rel["fkFieldId"]

    async def test_references_fk_type_matches_target_pk(self, client: AsyncClient):
        """The FK field's type matches the target object's PK field type."""
        cls = TestRelationshipFkAutoCreation

        # Get the FK field ID from the Order object
        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_assoc = next(f for f in order["fields"] if f["role"] == "fk")
        fk_field_id = fk_assoc["fieldId"]

        # Get the FK field details
        resp = await client.get(f"/fields/{fk_field_id}")
        assert resp.status_code == 200
        fk_field = resp.json()
        assert fk_field["name"] == "customer_id"

        # Get the target PK field details
        resp = await client.get(f"/fields/{cls.field_ids['customer_id']}")
        assert resp.status_code == 200
        pk_field = resp.json()

        # Types must match
        assert fk_field["typeId"] == pk_field["typeId"]

    async def test_references_fk_field_id_stored_on_relationship(
        self, client: AsyncClient
    ):
        """The relationship's fkFieldId points to the created FK field."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()

        refs_rel = next(
            r for r in order["relationships"] if r["cardinality"] == "references"
        )
        fk_assoc = next(f for f in order["fields"] if f["role"] == "fk")
        assert refs_rel["fkFieldId"] == fk_assoc["fieldId"]

    async def test_has_many_creates_fk_on_inverse(self, client: AsyncClient):
        """Creating a has_many relationship auto-creates FK on the target via inverse."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.customer_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "products",
                "cardinality": "has_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        rel = resp.json()
        # has_many itself does not own an FK
        assert rel["fkFieldId"] is None

        # The inverse (references on Product) should have an FK field
        resp = await client.get(f"/objects/{cls.product_obj_id}")
        assert resp.status_code == 200
        product = resp.json()
        inverse = next(
            r for r in product["relationships"] if r["cardinality"] == "references"
        )
        assert inverse["fkFieldId"] is not None

        # FK field should exist on Product
        fk_fields = [f for f in product["fields"] if f["role"] == "fk"]
        assert len(fk_fields) == 1
        assert fk_fields[0]["fieldId"] == inverse["fkFieldId"]

    async def test_has_one_creates_fk_on_inverse(self, client: AsyncClient):
        """Creating a has_one relationship auto-creates FK on the target via inverse."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.category_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "featured_product",
                "cardinality": "has_one",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        rel = resp.json()
        # has_one itself does not own an FK
        assert rel["fkFieldId"] is None

        # The inverse (references on Product) should have an FK field
        resp = await client.get(f"/objects/{cls.product_obj_id}")
        assert resp.status_code == 200
        product = resp.json()
        inverse = next(
            r
            for r in product["relationships"]
            if r["cardinality"] == "references"
            and r["targetObjectId"] == cls.category_obj_id
        )
        assert inverse["fkFieldId"] is not None

    async def test_many_to_many_no_fk(self, client: AsyncClient):
        """Creating a many_to_many relationship does NOT create FK fields."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.post(
            f"/objects/{cls.order_obj_id}/relationships",
            json={
                "targetObjectId": cls.product_obj_id,
                "name": "items",
                "cardinality": "many_to_many",
            },
        )
        assert resp.status_code == 201, f"Failed: {resp.text}"
        rel = resp.json()
        assert rel["fkFieldId"] is None

        # Inverse should also have no FK
        inverse_id = rel["inverseId"]
        resp = await client.get(f"/objects/{cls.product_obj_id}")
        assert resp.status_code == 200
        product = resp.json()
        m2m_inverse = next(
            r
            for r in product["relationships"]
            if r["cardinality"] == "many_to_many"
            and r["targetObjectId"] == cls.order_obj_id
        )
        assert m2m_inverse["fkFieldId"] is None

    async def test_fk_field_nullable_default_false(self, client: AsyncClient):
        """Auto-created FK fields default to nullable=False."""
        cls = TestRelationshipFkAutoCreation

        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_assoc = next(f for f in order["fields"] if f["role"] == "fk")
        assert fk_assoc["optional"] is False

    async def test_delete_relationship_deletes_fk_field(self, client: AsyncClient):
        """Deleting a relationship with fkFieldId removes the FK field."""
        cls = TestRelationshipFkAutoCreation

        # Get the Order->Customer references relationship
        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        refs_rel = next(
            r for r in order["relationships"] if r["cardinality"] == "references"
        )
        rel_id = refs_rel["id"]
        fk_field_id = refs_rel["fkFieldId"]
        assert fk_field_id is not None

        # Delete the relationship
        resp = await client.delete(
            f"/objects/{cls.order_obj_id}/relationships/{rel_id}"
        )
        assert resp.status_code == 204

        # FK field should be gone from the object
        resp = await client.get(f"/objects/{cls.order_obj_id}")
        assert resp.status_code == 200
        order = resp.json()
        fk_fields = [f for f in order["fields"] if f["role"] == "fk"]
        assert len(fk_fields) == 0

        # FK field entity should be deleted
        resp = await client.get(f"/fields/{fk_field_id}")
        assert resp.status_code == 404

    async def test_delete_relationship_deletes_inverse_fk(self, client: AsyncClient):
        """Deleting a has_many relationship also cleans up the inverse's FK field."""
        cls = TestRelationshipFkAutoCreation

        # Get the Customer->Product has_many relationship
        resp = await client.get(f"/objects/{cls.customer_obj_id}")
        assert resp.status_code == 200
        customer = resp.json()
        has_many_rel = next(
            r for r in customer["relationships"] if r["cardinality"] == "has_many"
        )
        rel_id = has_many_rel["id"]

        # Get the inverse FK field ID from Product
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

        # Delete the has_many relationship
        resp = await client.delete(
            f"/objects/{cls.customer_obj_id}/relationships/{rel_id}"
        )
        assert resp.status_code == 204

        # Inverse FK field should be gone
        resp = await client.get(f"/fields/{inverse_fk_field_id}")
        assert resp.status_code == 404

    async def test_cleanup(self, client: AsyncClient):
        """Clean up test data."""
        cls = TestRelationshipFkAutoCreation

        # Delete remaining relationships first to clean up FK fields
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
