"""Integration tests: name validation on create/update endpoints.

Verifies that PascalCase and SnakeCaseName rules are enforced at the
HTTP boundary for objects, APIs, and fields.

Requires PostgreSQL (docker compose up -d).
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
    Namespace,
    ObjectDefinition,
    UserModel,
)

TEST_CLERK_ID = "test_user_name_validation"

FAKE_NAMESPACE_ID = "00000000-0000-0000-9999-000000000001"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def client():
    """Module-scoped HTTP client with auth override and cleanup."""
    app.dependency_overrides[get_current_user] = lambda: TEST_CLERK_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/v1",
    ) as c:
        yield c

    app.dependency_overrides.pop(get_current_user, None)

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
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()

    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestNameValidation:
    """Name case validation on REST endpoints."""

    namespace_id: str = ""
    type_ids: dict[str, str] = {}
    valid_field_id: str = ""
    valid_object_id: str = ""
    valid_api_id: str = ""

    # --- Setup ---

    async def test_phase_00_setup(self, client: AsyncClient):
        """Create namespace and read type catalogue for subsequent tests."""
        cls = TestNameValidation

        # Read types
        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        # Create namespace
        resp = await client.post("/namespaces", json={"name": "Validation"})
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

    # --- Object name validation (PascalCase) ---

    async def test_object_create_rejects_snake_case(self, client: AsyncClient):
        """snake_case object name -> 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "user_profile",
                "fields": [],
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("PascalCaseName" in str(e) for e in detail)

    async def test_object_create_rejects_camel_case(self, client: AsyncClient):
        """camelCase object name -> 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "userProfile",
                "fields": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_create_rejects_consecutive_uppercase(
        self, client: AsyncClient
    ):
        """Consecutive uppercase (e.g. UserAPI) -> 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "UserAPI",
                "fields": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_create_rejects_empty_name(self, client: AsyncClient):
        """Empty name -> 422."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "",
                "fields": [],
            },
        )
        assert resp.status_code == 422

    async def test_object_create_accepts_valid_pascal_case(self, client: AsyncClient):
        """Valid PascalCase name -> 201."""
        cls = TestNameValidation
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "UserProfile",
                "fields": [],
            },
        )
        assert resp.status_code == 201, f"Unexpected: {resp.text}"
        cls.valid_object_id = resp.json()["id"]

    async def test_object_update_rejects_invalid_name(self, client: AsyncClient):
        """Invalid name on update -> 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/objects/{cls.valid_object_id}",
            json={"name": "user_profile"},
        )
        assert resp.status_code == 422

    async def test_object_update_accepts_valid_name(self, client: AsyncClient):
        """Valid PascalCase name on update -> 200."""
        cls = TestNameValidation
        resp = await client.put(
            f"/objects/{cls.valid_object_id}",
            json={"name": "UpdatedProfile"},
        )
        assert resp.status_code == 200

    # --- API title validation (PascalCase) ---

    async def test_api_create_rejects_snake_case(self, client: AsyncClient):
        """snake_case API title -> 422."""
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

    async def test_api_create_rejects_spaces(self, client: AsyncClient):
        """Spaces in API title -> 422."""
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

    async def test_api_create_rejects_consecutive_uppercase(self, client: AsyncClient):
        """Consecutive uppercase in API title -> 422."""
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

    async def test_api_create_accepts_valid_pascal_case(self, client: AsyncClient):
        """Valid PascalCase API title -> 201."""
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

    async def test_api_update_rejects_invalid_title(self, client: AsyncClient):
        """Invalid title on update -> 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/apis/{cls.valid_api_id}",
            json={"title": "shop_api"},
        )
        assert resp.status_code == 422

    async def test_api_update_accepts_valid_title(self, client: AsyncClient):
        """Valid PascalCase title on update -> 200."""
        cls = TestNameValidation
        resp = await client.put(
            f"/apis/{cls.valid_api_id}",
            json={"title": "UpdatedShopApi"},
        )
        assert resp.status_code == 200

    # --- Field name validation (SnakeCaseName) ---

    async def test_field_create_rejects_pascal_case(self, client: AsyncClient):
        """PascalCase field name -> 422."""
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

    async def test_field_create_rejects_camel_case(self, client: AsyncClient):
        """camelCase field name -> 422."""
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

    async def test_field_create_rejects_leading_underscore(self, client: AsyncClient):
        """Leading underscore field name -> 422."""
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

    async def test_field_create_rejects_double_underscore(self, client: AsyncClient):
        """Double underscore field name -> 422."""
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

    async def test_field_create_rejects_hyphenated(self, client: AsyncClient):
        """Hyphenated field name -> 422."""
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

    async def test_field_create_accepts_valid_snake_case(self, client: AsyncClient):
        """Valid snake_case field name -> 201."""
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

    async def test_field_update_rejects_invalid_name(self, client: AsyncClient):
        """Invalid name on update -> 422."""
        cls = TestNameValidation
        resp = await client.put(
            f"/fields/{cls.valid_field_id}",
            json={"name": "UserEmail"},
        )
        assert resp.status_code == 422

    async def test_field_update_accepts_valid_name(self, client: AsyncClient):
        """Valid snake_case on update -> 200."""
        cls = TestNameValidation
        resp = await client.put(
            f"/fields/{cls.valid_field_id}",
            json={"name": "updated_email"},
        )
        assert resp.status_code == 200

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
