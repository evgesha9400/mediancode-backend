"""E2E test: verify error handling, validation, and integrity guards.

Builds a minimal Blog domain, then exercises every error path:
- Rejected creates (bogus FKs, duplicate names, reserved names)
- 404s on non-existent entities
- Blocked deletes (field in use, object in use, namespace with entities)
- Cascade delete (API → endpoints)

Phases:
 1. Read catalogues (types, constraints, validator templates)
 2. Create Blog domain (namespace, field, object, API, endpoint)
 3. Namespace creation errors
 4. Namespace update errors
 5. Namespace deletion errors
 6. Field errors (bogus FKs + 404s)
 7. Object errors (bogus FKs + 404s)
 8. API errors (bogus namespace + 404s)
 9. Endpoint errors (404s)
10. Blocked deletes (field-in-use, object-in-use)
11. Cascade delete (API → endpoints)
12. Cleanup
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_current_user
from api.main import app
from api.models.database import (
    ApiModel,
    FieldModel,
    GenerationModel,
    Namespace,
    ObjectDefinition,
    UserModel,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="module"),
]

# ---------------------------------------------------------------------------
# Isolated test user (never collides with test_e2e_shop.py)
# ---------------------------------------------------------------------------

TEST_CLERK_ID = "test_user_e2e_errors"

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
# Module-scoped client (isolated from happy-path tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client():
    """Module-scoped HTTP client with auth override and DB cleanup."""
    app.dependency_overrides[get_current_user] = lambda: TEST_CLERK_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/v1",
    ) as c:
        yield c

    app.dependency_overrides.clear()

    # --- DB cleanup (handles both success and partial-failure cases) ---
    from api.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.clerk_id == TEST_CLERK_ID)
        )
        user = result.scalar_one_or_none()
        if user:
            uid = user.id
            await session.execute(delete(ApiModel).where(ApiModel.user_id == uid))
            await session.execute(
                delete(ObjectDefinition).where(ObjectDefinition.user_id == uid)
            )
            await session.execute(delete(FieldModel).where(FieldModel.user_id == uid))
            await session.execute(
                delete(GenerationModel).where(GenerationModel.user_id == uid)
            )
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestShopApiErrors:
    """Exercise every error guard in the API through HTTP.

    Tests are ordered by phase. Each phase stores IDs in class variables
    so subsequent phases can reference created entities.
    """

    # Shared state — catalogue IDs
    type_ids: dict[str, str] = {}
    constraint_ids: dict[str, str] = {}
    fv_template_ids: dict[str, str] = {}
    mv_template_ids: dict[str, str] = {}

    # Shared state — Blog domain entity IDs
    global_namespace_id: str = ""
    blog_namespace_id: str = ""
    title_field_id: str = ""
    post_object_id: str = ""
    blog_api_id: str = ""
    get_posts_endpoint_id: str = ""

    # --- Phase 1: Read catalogues ---

    async def test_phase_01_read_catalogues(self, client: AsyncClient):
        """Read catalogue data and store IDs needed for error tests."""
        cls = TestShopApiErrors

        # Types — just need str for the title field
        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        # Field constraints — need min_length, max_length for title field
        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        cls.constraint_ids = {c["name"]: c["id"] for c in resp.json()}

        # Field validator templates — need Trim for title field
        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        cls.fv_template_ids = {t["name"]: t["id"] for t in resp.json()}

        # Model validator templates — need one for bogus-FK test
        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        cls.mv_template_ids = {t["name"]: t["id"] for t in resp.json()}

        # Global namespace ID (needed for update/delete error tests)
        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        for ns in resp.json():
            if ns["name"] == "Global":
                cls.global_namespace_id = ns["id"]
        assert cls.global_namespace_id, "Global namespace not found"

    # --- Phase 2: Create Blog domain ---

    async def test_phase_02_create_blog_domain(self, client: AsyncClient):
        """Create minimal Blog domain: namespace → field → object → API → endpoint."""
        cls = TestShopApiErrors

        # Namespace
        resp = await client.post("/namespaces", json={"name": "Blog"})
        assert resp.status_code == 201
        cls.blog_namespace_id = resp.json()["id"]

        # Field: title (str, min_length=1, max_length=200, Trim validator)
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

        # Object: Post (references title, required)
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.blog_namespace_id,
                "name": "Post",
                "description": "Blog post",
                "fields": [{"fieldId": cls.title_field_id, "optional": False}],
            },
        )
        assert resp.status_code == 201, f"Failed to create Post object: {resp.text}"
        cls.post_object_id = resp.json()["id"]

        # API: Blog API
        resp = await client.post(
            "/apis",
            json={
                "namespaceId": cls.blog_namespace_id,
                "title": "Blog API",
                "version": "1.0.0",
                "description": "Simple blog",
            },
        )
        assert resp.status_code == 201, f"Failed to create Blog API: {resp.text}"
        cls.blog_api_id = resp.json()["id"]

        # Endpoint: GET /posts
        resp = await client.post(
            "/endpoints",
            json={
                "apiId": cls.blog_api_id,
                "method": "GET",
                "path": "/posts",
                "description": "List all posts",
                "tagName": "Posts",
                "pathParams": [],
                "responseBodyObjectId": cls.post_object_id,
                "useEnvelope": False,
                "responseShape": "list",
            },
        )
        assert resp.status_code == 201, f"Failed to create endpoint: {resp.text}"
        cls.get_posts_endpoint_id = resp.json()["id"]

    # --- Phase 3: Namespace creation errors ---

    async def test_phase_03_namespace_creation_errors(self, client: AsyncClient):
        """Duplicate name and reserved 'Global' name are rejected."""
        cls = TestShopApiErrors

        # Duplicate name
        resp = await client.post("/namespaces", json={"name": "Blog"})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

        # Reserved name
        resp = await client.post("/namespaces", json={"name": "Global"})
        assert resp.status_code == 400
        assert "reserved" in resp.json()["detail"].lower()

    # --- Phase 4: Namespace update errors ---

    async def test_phase_04_namespace_update_errors(self, client: AsyncClient):
        """Global namespace is immutable; cannot unset default; duplicate name blocked."""
        cls = TestShopApiErrors

        # Cannot rename Global namespace
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 400
        assert "Global namespace name" in resp.json()["detail"]

        # Cannot change Global namespace description
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"description": "Hacked"},
        )
        assert resp.status_code == 400
        assert "Global namespace description" in resp.json()["detail"]

        # Cannot unset default
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"isDefault": False},
        )
        assert resp.status_code == 400
        assert "unset default" in resp.json()["detail"].lower()

        # Cannot rename to duplicate name — create temp namespace, try to rename to "Blog"
        resp = await client.post("/namespaces", json={"name": "Draft"})
        assert resp.status_code == 201
        draft_id = resp.json()["id"]

        resp = await client.put(
            f"/namespaces/{draft_id}",
            json={"name": "Blog"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

        # Clean up temp namespace
        resp = await client.delete(f"/namespaces/{draft_id}")
        assert resp.status_code == 204

    # --- Phase 5: Namespace deletion errors ---

    async def test_phase_05_namespace_deletion_errors(self, client: AsyncClient):
        """Cannot delete Global, default, non-empty, or non-existent namespace."""
        cls = TestShopApiErrors

        # Cannot delete Global namespace
        resp = await client.delete(f"/namespaces/{cls.global_namespace_id}")
        assert resp.status_code == 400
        assert "Global namespace" in resp.json()["detail"]

        # Cannot delete default namespace — make a temp namespace default, then try to delete it
        resp = await client.post(
            "/namespaces", json={"name": "Scratch", "isDefault": True}
        )
        assert resp.status_code == 201
        scratch_id = resp.json()["id"]

        resp = await client.delete(f"/namespaces/{scratch_id}")
        assert resp.status_code == 400
        assert "default namespace" in resp.json()["detail"].lower()

        # Restore Global as default and delete Scratch
        resp = await client.put(
            f"/namespaces/{cls.global_namespace_id}",
            json={"isDefault": True},
        )
        assert resp.status_code == 200
        resp = await client.delete(f"/namespaces/{scratch_id}")
        assert resp.status_code == 204

        # Cannot delete namespace with entities (Blog has field, object, API, endpoint)
        resp = await client.delete(f"/namespaces/{cls.blog_namespace_id}")
        assert resp.status_code == 400
        assert "contains" in resp.json()["detail"].lower()

        # Cannot delete non-existent namespace
        resp = await client.delete(f"/namespaces/{FAKE_NAMESPACE_ID}")
        assert resp.status_code == 404

    # --- Phases 6–11: Error tests (added in subsequent tasks) ---

    # --- Phase 12: Cleanup ---

    async def test_phase_12_cleanup(self, client: AsyncClient):
        """Delete Blog domain entities in reverse dependency order."""
        cls = TestShopApiErrors

        # Endpoint may already be gone (cascade test in phase 11)
        resp = await client.delete(f"/endpoints/{cls.get_posts_endpoint_id}")
        assert resp.status_code in (204, 404)

        # API may already be gone (cascade test in phase 11)
        resp = await client.delete(f"/apis/{cls.blog_api_id}")
        assert resp.status_code in (204, 404)

        resp = await client.delete(f"/objects/{cls.post_object_id}")
        assert resp.status_code == 204

        resp = await client.delete(f"/fields/{cls.title_field_id}")
        assert resp.status_code == 204

        resp = await client.delete(f"/namespaces/{cls.blog_namespace_id}")
        assert resp.status_code == 204
