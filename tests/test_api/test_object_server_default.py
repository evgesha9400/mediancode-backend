"""Tests: default persistence through object CRUD."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_current_user
from api.main import app
from api.models.database import (
    FieldModel,
    Namespace,
    ObjectDefinition,
    UserModel,
)

TEST_CLERK_ID = "test_user_server_default"


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
class TestDefaultPersistence:
    """Default values must round-trip through object CRUD."""

    namespace_id: str = ""
    type_ids: dict[str, str] = {}
    field_ids: list[str] = []
    object_id: str = ""

    async def test_phase_00_setup(self, client: AsyncClient):
        cls = TestDefaultPersistence
        resp = await client.get("/types")
        assert resp.status_code == 200
        cls.type_ids = {t["name"]: t["id"] for t in resp.json()}

        resp = await client.post("/namespaces", json={"name": "SdTest"})
        assert resp.status_code == 201
        cls.namespace_id = resp.json()["id"]

        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "created_at",
                "typeId": cls.type_ids["datetime"],
            },
        )
        assert resp.status_code == 201
        cls.field_ids = [resp.json()["id"]]

    async def test_create_object_with_created_timestamp_role(self, client: AsyncClient):
        """created_timestamp role should be persisted and returned."""
        cls = TestDefaultPersistence
        resp = await client.post(
            "/objects",
            json={
                "namespaceId": cls.namespace_id,
                "name": "Timestamped",
                "fields": [
                    {
                        "fieldId": cls.field_ids[0],
                        "role": "created_timestamp",
                    }
                ],
            },
        )
        assert resp.status_code == 201, f"Unexpected: {resp.text}"
        body = resp.json()
        cls.object_id = body["id"]
        assert len(body["fields"]) == 1
        assert body["fields"][0]["role"] == "created_timestamp"
        # Generated roles normalize nullable to false and default_value to null
        assert body["fields"][0]["nullable"] is False
        assert body["fields"][0]["defaultValue"] is None

    async def test_update_object_with_literal_default(self, client: AsyncClient):
        """Literal default should be persisted and returned."""
        cls = TestDefaultPersistence
        int_type_id = cls.type_ids["int"]

        # Create an int field for literal default
        resp = await client.post(
            "/fields",
            json={
                "namespaceId": cls.namespace_id,
                "name": "sort_order",
                "typeId": int_type_id,
            },
        )
        assert resp.status_code == 201
        int_field_id = resp.json()["id"]
        cls.field_ids.append(int_field_id)

        resp = await client.put(
            f"/objects/{cls.object_id}",
            json={
                "fields": [
                    {
                        "fieldId": int_field_id,
                        "nullable": False,
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

    async def test_phase_99_cleanup(self, client: AsyncClient):
        cls = TestDefaultPersistence
        if cls.object_id:
            resp = await client.delete(f"/objects/{cls.object_id}")
            assert resp.status_code == 204

        for field_id in cls.field_ids:
            resp = await client.delete(f"/fields/{field_id}")
            assert resp.status_code == 204

        if cls.namespace_id:
            resp = await client.delete(f"/namespaces/{cls.namespace_id}")
            assert resp.status_code == 204
