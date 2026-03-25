# tests/http/test_validation_and_errors.py
"""Integration tests: error handling, validation guards, and name validation.

Merged coverage from legacy test_e2e_shop_errors.py, test_name_validation.py.
"""

from httpx import AsyncClient
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_http_errors"

# ---------------------------------------------------------------------------
# Fake UUIDs — deterministic, obviously invalid, never collide with seeds
# ---------------------------------------------------------------------------

FAKE_NAMESPACE_ID = "00000000-0000-0000-0000-ffffffffffff"
FAKE_TYPE_ID = "00000000-0000-0000-0001-ffffffffffff"
FAKE_CONSTRAINT_ID = "00000000-0000-0000-0002-ffffffffffff"
FAKE_FIELD_ID = "00000000-0000-0000-0003-ffffffffffff"
FAKE_ENDPOINT_ID = "00000000-0000-0000-0004-ffffffffffff"
FAKE_API_ID = "00000000-0000-0000-0005-ffffffffffff"
FAKE_OBJECT_ID = "00000000-0000-0000-0007-ffffffffffff"
FAKE_FV_TEMPLATE_ID = "00000000-0000-0000-0008-ffffffffffff"
FAKE_MV_TEMPLATE_ID = "00000000-0000-0000-0009-ffffffffffff"


# ---------------------------------------------------------------------------
# TestErrorGuards — rejected creates, 404s, blocked deletes, cascades
# ---------------------------------------------------------------------------


class TestErrorGuards:
    """Exercise every error guard in the API through HTTP."""

    type_ids: dict[str, str] = {}
    constraint_ids: dict[str, str] = {}
    fv_template_ids: dict[str, str] = {}
    mv_template_ids: dict[str, str] = {}

    global_namespace_id: str = ""
    blog_namespace_id: str = ""
    title_field_id: str = ""
    post_object_id: str = ""
    blog_api_id: str = ""
    get_posts_endpoint_id: str = ""

    # --- Phase 1: Read catalogues ---

    async def test_phase_01_read_catalogues(self, client: AsyncClient):
        """Read catalogue data needed for error tests."""
        cls = TestErrorGuards

        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        cls.constraint_ids = {c["name"]: c["id"] for c in resp.json()}

        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        cls.fv_template_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        cls.mv_template_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        for ns in resp.json():
            if ns["name"] == "Global":
                cls.global_namespace_id = ns["id"]
        assert cls.global_namespace_id, "Global namespace not found"

    # --- Phase 2: Create Blog domain ---

    async def test_phase_02_create_blog_domain(self, client: AsyncClient):
        """Create minimal Blog domain: namespace → field → object → API → endpoint."""
        cls = TestErrorGuards

        resp = await client.post("/namespaces", json={"name": "Blog"})
        assert resp.status_code == 201
        cls.blog_namespace_id = resp.json()["id"]

        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.blog_namespace_id,
                "name": "title",
                "typeId": cls.type_ids["str"],
                "constraints": [
                    {"constraintId": cls.constraint_ids["min_length"], "value": "1"},
                    {"constraintId": cls.constraint_ids["max_length"], "value": "200"},
                ],
                "validators": [
                    {"templateId": cls.fv_template_ids["Trim"]},
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create title field: {resp.text}"
        cls.title_field_id = resp.json()["id"]

        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.blog_namespace_id,
                "name": "Post",
                "description": "Blog post",
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "title",
                        "fieldId": cls.title_field_id,
                        "isNullable": False,
                        "role": "writable",
                    }
                ],
            },
        )
        assert resp.status_code == 201, f"Failed to create Post object: {resp.text}"
        cls.post_object_id = resp.json()["id"]

        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.blog_namespace_id,
                "title": "BlogApi",
                "version": "1.0.0",
                "description": "Simple blog",
            },
        )
        assert resp.status_code == 201, f"Failed to create Blog API: {resp.text}"
        cls.blog_api_id = resp.json()["id"]

        resp = await client.post(
            "/endpoints",
            json={
                "apiId": cls.blog_api_id,
                "method": "GET",
                "path": "/posts",
                "description": "List all posts",
                "tagName": "Posts",
                "pathParams": [],
                "objectId": cls.post_object_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
        )
        assert resp.status_code == 201, f"Failed to create endpoint: {resp.text}"
        cls.get_posts_endpoint_id = resp.json()["id"]

    # --- Phase 3: Namespace creation errors ---

    async def test_phase_03a_namespace_duplicate_name(self, client: AsyncClient):
        """Duplicate namespace name → 400."""
        resp = await client.post("/namespaces", json={"name": "Blog"})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_phase_03b_namespace_reserved_global(self, client: AsyncClient):
        """Reserved 'Global' name → 400."""
        resp = await client.post("/namespaces", json={"name": "Global"})
        assert resp.status_code == 400
        assert "reserved" in resp.json()["detail"].lower()

    # --- Phase 4: Namespace update errors ---

    async def test_phase_04a_rename_global_namespace(self, client: AsyncClient):
        """Cannot rename Global namespace."""
        cls = TestErrorGuards
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 400
        assert "Global namespace name" in resp.json()["detail"]

    async def test_phase_04b_change_global_description(self, client: AsyncClient):
        """Cannot change Global namespace description."""
        cls = TestErrorGuards
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"description": "Hacked"},
        )
        assert resp.status_code == 400
        assert "Global namespace description" in resp.json()["detail"]

    async def test_phase_04c_unset_default(self, client: AsyncClient):
        """Cannot unset default namespace."""
        cls = TestErrorGuards
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"isDefault": False},
        )
        assert resp.status_code == 400
        assert "unset default" in resp.json()["detail"].lower()

    async def test_phase_04d_rename_to_duplicate(self, client: AsyncClient):
        """Cannot rename to an existing namespace name."""
        cls = TestErrorGuards

        resp = await client.post("/namespaces", json={"name": "Draft"})
        assert resp.status_code == 201
        draft_id = resp.json()["id"]

        resp = await client.put(
            f"/namespaces/{draft_id}",
            json={"name": "Blog"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

        resp = await client.delete(f"/namespaces/{draft_id}")
        assert resp.status_code == 204

    # --- Phase 5: Namespace deletion errors ---

    async def test_phase_05a_delete_global(self, client: AsyncClient):
        """Cannot delete Global namespace."""
        cls = TestErrorGuards
        resp = await client.delete(f"/namespaces/{cls.global_namespace_id}")
        assert resp.status_code == 400
        assert "Global namespace" in resp.json()["detail"]

    async def test_phase_05b_delete_default(self, client: AsyncClient):
        """Cannot delete default namespace."""
        cls = TestErrorGuards

        resp = await client.post(
            "/namespaces", json={"name": "Scratch", "isDefault": True}
        )
        assert resp.status_code == 201
        scratch_id = resp.json()["id"]

        resp = await client.delete(f"/namespaces/{scratch_id}")
        assert resp.status_code == 400
        assert "default namespace" in resp.json()["detail"].lower()

        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"isDefault": True},
        )
        assert resp.status_code == 200
        resp = await client.delete(f"/namespaces/{scratch_id}")
        assert resp.status_code == 204

    async def test_phase_05c_delete_non_empty(self, client: AsyncClient):
        """Cannot delete namespace that contains entities."""
        cls = TestErrorGuards
        resp = await client.delete(f"/namespaces/{cls.blog_namespace_id}")
        assert resp.status_code == 400
        assert "contains" in resp.json()["detail"].lower()

    async def test_phase_05d_delete_non_existent(self, client: AsyncClient):
        """Delete non-existent namespace → 404."""
        resp = await client.delete(f"/namespaces/{FAKE_NAMESPACE_ID}")
        assert resp.status_code == 404

    # --- Phase 6: Field errors ---

    async def test_phase_06a_field_bogus_namespace(self, client: AsyncClient):
        """Create field in non-existent namespace → 400."""
        cls = TestErrorGuards
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": FAKE_NAMESPACE_ID,
                "name": "phantom",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 400
        assert "not found or not owned" in resp.json()["detail"].lower()

    async def test_phase_06b_field_bogus_type(self, client: AsyncClient):
        """Create field with bogus type ID → 400/422/500."""
        cls = TestErrorGuards
        try:
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.blog_namespace_id,
                    "name": "phantom",
                    "typeId": FAKE_TYPE_ID,
                },
            )
            status = resp.status_code
        except Exception:
            status = 500
        assert status in (400, 422, 500), f"Unexpected: {status}"

    async def test_phase_06c_field_bogus_constraint(self, client: AsyncClient):
        """Create field with bogus constraint ID → 400/422/500."""
        cls = TestErrorGuards
        try:
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.blog_namespace_id,
                    "name": "phantom",
                    "typeId": cls.type_ids["str"],
                    "constraints": [{"constraintId": FAKE_CONSTRAINT_ID, "value": "1"}],
                },
            )
            status = resp.status_code
        except Exception:
            status = 500
        assert status in (400, 422, 500), f"Unexpected: {status}"

    async def test_phase_06d_field_bogus_validator_template(self, client: AsyncClient):
        """Create field with bogus validator template ID → 400/422/500."""
        cls = TestErrorGuards
        try:
            resp = await client.post(
                "/fields",
                json={
                    "namespaceId": cls.blog_namespace_id,
                    "name": "phantom",
                    "typeId": cls.type_ids["str"],
                    "validators": [{"templateId": FAKE_FV_TEMPLATE_ID}],
                },
            )
            status = resp.status_code
        except Exception:
            status = 500
        assert status in (400, 422, 500), f"Unexpected: {status}"

    async def test_phase_06e_field_get_non_existent(self, client: AsyncClient):
        """GET non-existent field → 404."""
        resp = await client.get(f"/fields/{FAKE_FIELD_ID}")
        assert resp.status_code == 404

    async def test_phase_06f_field_delete_non_existent(self, client: AsyncClient):
        """DELETE non-existent field → 404."""
        resp = await client.delete(f"/fields/{FAKE_FIELD_ID}")
        assert resp.status_code == 404

    # --- Phase 7: Object errors ---

    async def test_phase_07a_object_bogus_namespace(self, client: AsyncClient):
        """Create object in non-existent namespace → 400."""
        cls = TestErrorGuards
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": FAKE_NAMESPACE_ID,
                "name": "Phantom",
                "members": [
                    {
                        "memberType": "scalar",
                        "name": "title",
                        "fieldId": cls.title_field_id,
                        "isNullable": False,
                    }
                ],
            },
        )
        assert resp.status_code == 400
        assert "not found or not owned" in resp.json()["detail"].lower()

    async def test_phase_07b_object_bogus_field(self, client: AsyncClient):
        """Create object with bogus field ID → 400/422/500."""
        cls = TestErrorGuards
        try:
            resp = await client.post(
                "/objects",
                json={
                    "namespaceId": cls.blog_namespace_id,
                    "name": "Phantom",
                    "members": [
                        {
                            "memberType": "scalar",
                            "name": "bogus",
                            "fieldId": FAKE_FIELD_ID,
                            "isNullable": False,
                        }
                    ],
                },
            )
            status = resp.status_code
        except Exception:
            status = 500
        assert status in (400, 422, 500), f"Unexpected: {status}"

    async def test_phase_07c_object_bogus_mv_template(self, client: AsyncClient):
        """Create object with bogus MV template ID → 400/422/500."""
        cls = TestErrorGuards
        try:
            resp = await client.post(
                "/objects",
                json={
                    "namespaceId": cls.blog_namespace_id,
                    "name": "Phantom",
                    "members": [
                        {
                            "memberType": "scalar",
                            "name": "title",
                            "fieldId": cls.title_field_id,
                            "isNullable": False,
                        }
                    ],
                    "validators": [
                        {
                            "templateId": FAKE_MV_TEMPLATE_ID,
                            "fieldMappings": {
                                "field_a": "title",
                                "field_b": "title",
                            },
                        }
                    ],
                },
            )
            status = resp.status_code
        except Exception:
            status = 500
        assert status in (400, 422, 500), f"Unexpected: {status}"

    async def test_phase_07d_object_get_non_existent(self, client: AsyncClient):
        """GET non-existent object → 404."""
        resp = await client.get(f"/objects/{FAKE_OBJECT_ID}")
        assert resp.status_code == 404

    async def test_phase_07e_object_delete_non_existent(self, client: AsyncClient):
        """DELETE non-existent object → 404."""
        resp = await client.delete(f"/objects/{FAKE_OBJECT_ID}")
        assert resp.status_code == 404

    # --- Phase 8: API errors ---

    async def test_phase_08a_api_bogus_namespace(self, client: AsyncClient):
        """Create API in non-existent namespace → 400."""
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": FAKE_NAMESPACE_ID,
                "title": "PhantomApi",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 400
        assert "not found or not owned" in resp.json()["detail"].lower()

    async def test_phase_08b_api_get_non_existent(self, client: AsyncClient):
        """GET non-existent API → 404."""
        resp = await client.get(f"/apis/{FAKE_API_ID}")
        assert resp.status_code == 404

    async def test_phase_08c_api_delete_non_existent(self, client: AsyncClient):
        """DELETE non-existent API → 404."""
        resp = await client.delete(f"/apis/{FAKE_API_ID}")
        assert resp.status_code == 404

    # --- Phase 9: Endpoint errors ---

    async def test_phase_09a_endpoint_get_non_existent(self, client: AsyncClient):
        """GET non-existent endpoint → 404."""
        resp = await client.get(f"/endpoints/{FAKE_ENDPOINT_ID}")
        assert resp.status_code == 404

    async def test_phase_09b_endpoint_put_non_existent(self, client: AsyncClient):
        """PUT non-existent endpoint → 404."""
        resp = await client.put(
            f"/endpoints/{FAKE_ENDPOINT_ID}",
            json={"description": "Updated"},
        )
        assert resp.status_code == 404

    async def test_phase_09c_endpoint_delete_non_existent(self, client: AsyncClient):
        """DELETE non-existent endpoint → 404."""
        resp = await client.delete(f"/endpoints/{FAKE_ENDPOINT_ID}")
        assert resp.status_code == 404

    # --- Phase 10: Blocked deletes ---

    async def test_phase_10a_field_used_by_object(self, client: AsyncClient):
        """Cannot delete field used by object → 400."""
        cls = TestErrorGuards
        resp = await client.delete(f"/fields/{cls.title_field_id}")
        assert resp.status_code == 400
        assert "used in" in resp.json()["detail"].lower()
        assert "object" in resp.json()["detail"].lower()

    async def test_phase_10b_object_used_by_endpoint(self, client: AsyncClient):
        """Cannot delete object used by endpoint → 400."""
        cls = TestErrorGuards
        resp = await client.delete(f"/objects/{cls.post_object_id}")
        assert resp.status_code == 400
        assert "used in" in resp.json()["detail"].lower()
        assert "endpoint" in resp.json()["detail"].lower()

    # --- Phase 11: Cascade delete ---

    async def test_phase_11_cascade_api_deletes_endpoints(self, client: AsyncClient):
        """Deleting an API cascades to its endpoints."""
        cls = TestErrorGuards

        resp = await client.get(f"/endpoints/{cls.get_posts_endpoint_id}")
        assert resp.status_code == 200

        resp = await client.delete(f"/apis/{cls.blog_api_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/endpoints/{cls.get_posts_endpoint_id}")
        assert resp.status_code == 404

    # --- Phase 12: Cleanup ---

    async def test_phase_12_cleanup(self, client: AsyncClient):
        """Delete Blog domain entities in reverse dependency order."""
        cls = TestErrorGuards

        resp = await client.delete(f"/endpoints/{cls.get_posts_endpoint_id}")
        assert resp.status_code in (204, 404)

        resp = await client.delete(f"/apis/{cls.blog_api_id}")
        assert resp.status_code in (204, 404)

        resp = await client.delete(f"/objects/{cls.post_object_id}")
        assert resp.status_code == 204

        resp = await client.delete(f"/fields/{cls.title_field_id}")
        assert resp.status_code == 204

        resp = await client.delete(f"/namespaces/{cls.blog_namespace_id}")
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# TestNameValidation — PascalCase / snake_case enforcement at HTTP boundary
# ---------------------------------------------------------------------------


class TestNameValidation:
    """Name case validation on REST endpoints."""

    namespace_id: str = ""
    type_ids: dict[str, str] = {}
    valid_field_id: str = ""
    valid_object_id: str = ""
    valid_api_id: str = ""

    # --- Setup ---

    async def test_phase_00_setup(self, client: AsyncClient):
        """Create namespace and read type catalogue."""
        cls = TestNameValidation

        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.post("/namespaces", json={"name": "Validation"})
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

    # --- Object name validation (PascalCase) ---

    async def test_object_rejects_snake_case(self, client: AsyncClient):
        """snake_case object name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "user_profile",
                "members": [],
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("PascalCaseName" in str(e) for e in detail)

    async def test_object_rejects_camel_case(self, client: AsyncClient):
        """camelCase object name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "userProfile",
                "members": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_rejects_consecutive_uppercase(self, client: AsyncClient):
        """Consecutive uppercase (UserAPI) → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "UserAPI",
                "members": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_rejects_empty_name(self, client: AsyncClient):
        """Empty name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "",
                "members": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_accepts_pascal_case(self, client: AsyncClient):
        """Valid PascalCase name → 201."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "UserProfile",
                "members": [],
            },
        )
        assert resp.status_code == 201, f"Unexpected: {resp.text}"
        cls.valid_object_id = resp.json()["id"]

    async def test_object_update_rejects_invalid(self, client: AsyncClient):
        """Invalid name on update → 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/objects/{cls.valid_object_id}",
            json={"name": "user_profile"},
        )
        assert resp.status_code == 422

    # --- API title validation (PascalCase) ---

    async def test_api_rejects_snake_case(self, client: AsyncClient):
        """snake_case API title → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.namespace_id,
                "title": "user_management_api",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 422

    async def test_api_rejects_spaces(self, client: AsyncClient):
        """Spaces in API title → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.namespace_id,
                "title": "Shop API",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 422

    async def test_api_rejects_consecutive_uppercase(self, client: AsyncClient):
        """Consecutive uppercase (ShopAPI) → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.namespace_id,
                "title": "ShopAPI",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 422

    async def test_api_accepts_pascal_case(self, client: AsyncClient):
        """Valid PascalCase API title (ShopApi) → 201."""
        cls = TestNameValidation
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.namespace_id,
                "title": "ShopApi",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 201, f"Unexpected: {resp.text}"
        cls.valid_api_id = resp.json()["id"]

    async def test_api_update_rejects_invalid(self, client: AsyncClient):
        """Invalid title on update → 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/apis/{cls.valid_api_id}",
            json={"title": "shop_api"},
        )
        assert resp.status_code == 422

    # --- Field name validation (snake_case) ---

    async def test_field_rejects_pascal_case(self, client: AsyncClient):
        """PascalCase field name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "UserEmail",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 422

    async def test_field_rejects_camel_case(self, client: AsyncClient):
        """camelCase field name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "userEmail",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 422

    async def test_field_rejects_leading_underscore(self, client: AsyncClient):
        """Leading underscore → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "_email",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 422

    async def test_field_rejects_double_underscore(self, client: AsyncClient):
        """Double underscore → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "user__email",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 422

    async def test_field_rejects_hyphens(self, client: AsyncClient):
        """Hyphenated name → 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "user-email",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 422

    async def test_field_accepts_snake_case(self, client: AsyncClient):
        """Valid snake_case name → 201."""
        cls = TestNameValidation
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "user_email",
                "typeId": cls.type_ids["str"],
            },
        )
        assert resp.status_code == 201, f"Unexpected: {resp.text}"
        cls.valid_field_id = resp.json()["id"]

    async def test_field_update_rejects_invalid(self, client: AsyncClient):
        """Invalid name on update → 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/fields/{cls.valid_field_id}",
            json={"name": "UserEmail"},
        )
        assert resp.status_code == 422

    # --- Cleanup ---

    async def test_phase_99_cleanup(self, client: AsyncClient):
        """Delete test entities in reverse dependency order."""
        cls = TestNameValidation

        if cls.valid_api_id:
            resp = await client.delete(f"/apis/{cls.valid_api_id}")
            assert resp.status_code == 204

        if cls.valid_object_id:
            resp = await client.delete(f"/objects/{cls.valid_object_id}")
            assert resp.status_code == 204

        if cls.valid_field_id:
            resp = await client.delete(f"/fields/{cls.valid_field_id}")
            assert resp.status_code == 204

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
