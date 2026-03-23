"""Integration test for the seed module runner."""

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
    pytest.mark.asyncio(loop_scope="session"),
]

TEST_CLERK_ID = "test_user_seeding"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def client():
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
                delete(GenerationModel).where(GenerationModel.user_id == uid)
            )
            await session.execute(delete(ApiModel).where(ApiModel.user_id == uid))
            await session.execute(
                delete(ObjectDefinition).where(ObjectDefinition.user_id == uid)
            )
            await session.execute(delete(FieldModel).where(FieldModel.user_id == uid))
            await session.execute(delete(Namespace).where(Namespace.user_id == uid))
            await session.execute(delete(UserModel).where(UserModel.id == uid))
            await session.commit()
    await engine.dispose()


class TestSeedRunner:
    async def test_seed_creates_full_shop_structure(self, client: AsyncClient):
        from seeding.runner import seed_shop
        from seeding.shop_data import ALL_FIELDS, ENDPOINTS, OBJECTS

        result = await seed_shop(client)

        assert result.namespace_id
        assert len(result.field_ids) == len(ALL_FIELDS)
        assert len(result.object_ids) == len(OBJECTS)
        assert result.api_id
        assert len(result.endpoint_ids) == len(ENDPOINTS)
        assert len(result.relationship_ids) >= 1

        # Verify via API reads
        # Auto-created FK fields add to the total (1 per references inverse)
        resp = await client.get(f"/fields?namespace_id={result.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= len(ALL_FIELDS)

        resp = await client.get(f"/objects?namespace_id={result.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == len(OBJECTS)

        # Verify role on Product.created_at
        resp = await client.get(f"/objects/{result.object_ids['Product']}")
        assert resp.status_code == 200
        product = resp.json()
        created_at_field = next(
            f
            for f in product["fields"]
            if f["fieldId"] == result.field_ids["created_at"]
        )
        assert created_at_field["role"] == "created_timestamp"

        # Verify relationship exists on Customer
        resp = await client.get(f"/objects/{result.object_ids['Customer']}")
        assert resp.status_code == 200
        customer = resp.json()
        assert len(customer.get("relationships", [])) >= 1

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == len(ENDPOINTS)

    async def test_clean_removes_all_shop_data(self, client: AsyncClient):
        from seeding.runner import clean_shop

        await clean_shop(client)

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_seed_after_clean_works(self, client: AsyncClient):
        """Verify replace mode (clean then seed) works."""
        from seeding.runner import clean_shop, seed_shop
        from seeding.shop_data import ALL_FIELDS

        result = await seed_shop(client)
        assert result.namespace_id
        assert len(result.field_ids) == len(ALL_FIELDS)

        await clean_shop(client)

        resp = await client.get("/namespaces")
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names
