# tests/http/test_happy_path_and_seeding.py
"""Integration tests: seed/clean lifecycle and full Shop API happy path.

Merged coverage from legacy test_e2e_shop.py, test_e2e_shop_full.py,
test_seeding.py.
"""

import io
from pathlib import Path
import shutil
import tempfile
import zipfile

from httpx import AsyncClient
import pytest

from support.shop_contract import (
    ALL_FIELDS,
    ENDPOINTS,
    OBJECTS,
    SeedResult,
    clean_shop,
    seed_shop,
)

pytestmark = pytest.mark.integration

TEST_CLERK_ID = "test_user_http_happy"


# ---------------------------------------------------------------------------
# TestSeedRunner — seed_shop / clean_shop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestSeedRunner:
    """Verify seed_shop / clean_shop create and remove the full Shop domain."""

    seed: SeedResult | None = None

    async def test_seed_creates_full_structure(self, client: AsyncClient):
        """seed_shop creates all entities with correct counts."""
        cls = TestSeedRunner
        result = await seed_shop(client)
        cls.seed = result

        assert result.namespace_id
        assert len(result.field_ids) == len(ALL_FIELDS)
        assert len(result.object_ids) == len(OBJECTS)
        assert result.api_id
        assert len(result.endpoint_ids) == len(ENDPOINTS)
        assert len(result.relationship_ids) >= 1

        resp = await client.get(f"/fields?namespace_id={result.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= len(ALL_FIELDS)

        resp = await client.get(f"/objects?namespace_id={result.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == len(OBJECTS)

        resp = await client.get(f"/objects/{result.object_ids['Product']}")
        assert resp.status_code == 200
        product = resp.json()
        created_at = next(
            f
            for f in product["fields"]
            if f["fieldId"] == result.field_ids["created_at"]
        )
        assert created_at["role"] == "created_timestamp"

        resp = await client.get(f"/objects/{result.object_ids['Customer']}")
        assert resp.status_code == 200
        customer = resp.json()
        assert len(customer.get("relationships", [])) >= 1

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == len(ENDPOINTS)

    async def test_clean_removes_everything(self, client: AsyncClient):
        """clean_shop removes the Shop namespace and all contents."""
        await clean_shop(client)

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_seed_after_clean_works(self, client: AsyncClient):
        """Re-seeding after a clean produces a valid structure."""
        result = await seed_shop(client)
        assert result.namespace_id
        assert len(result.field_ids) == len(ALL_FIELDS)

        await clean_shop(client)

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names


# ---------------------------------------------------------------------------
# TestShopLifecycle — thin phased CRUD + generation verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestShopLifecycle:
    """Seed → verify → generate → verify generated code → clean."""

    seed: SeedResult | None = None
    zip_bytes: bytes = b""
    generated_dir: str = ""

    # --- Phase 1: Seed ---

    async def test_phase_01_seed(self, client: AsyncClient):
        """Seed the full Shop domain."""
        cls = TestShopLifecycle
        cls.seed = await seed_shop(client)
        assert cls.seed.namespace_id

    # --- Phase 2: Verify fields ---

    async def test_phase_02_verify_fields(self, client: AsyncClient):
        """Verify field counts and spot-check the 'name' field."""
        cls = TestShopLifecycle
        seed = cls.seed

        resp = await client.get(f"/fields?namespace_id={seed.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= len(ALL_FIELDS)

        resp = await client.get(f"/fields/{seed.field_ids['name']}")
        assert resp.status_code == 200
        field = resp.json()
        assert field["name"] == "name"
        assert len(field["constraints"]) == 2
        assert len(field["validators"]) == 2

    # --- Phase 3: Verify objects ---

    async def test_phase_03_verify_objects(self, client: AsyncClient):
        """Product has 16 fields and 4 validators; Customer has 8 fields."""
        cls = TestShopLifecycle
        seed = cls.seed

        resp = await client.get(f"/objects?namespace_id={seed.namespace_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = await client.get(f"/objects/{seed.object_ids['Product']}")
        assert resp.status_code == 200
        product = resp.json()
        assert product["name"] == "Product"
        assert len(product["fields"]) >= 16
        assert len(product["validators"]) == 4

        resp = await client.get(f"/objects/{seed.object_ids['Customer']}")
        assert resp.status_code == 200
        customer = resp.json()
        assert customer["name"] == "Customer"
        assert len(customer["fields"]) == 8

    # --- Phase 4: Verify endpoints ---

    async def test_phase_04_verify_endpoints(self, client: AsyncClient):
        """Verify endpoint count and UUID path param JSONB round-trip."""
        cls = TestShopLifecycle
        seed = cls.seed

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == len(ENDPOINTS)

        ep_id = seed.endpoint_ids["GET /products/{tracking_id}"]
        resp = await client.get(f"/endpoints/{ep_id}")
        assert resp.status_code == 200
        ep = resp.json()
        assert ep["method"] == "GET"
        assert ep["path"] == "/products/{tracking_id}"
        assert len(ep["pathParams"]) == 1
        assert ep["pathParams"][0]["fieldId"] == seed.field_ids["tracking_id"]

    # --- Phase 5: Update endpoint (UUID-in-JSONB regression) ---

    async def test_phase_05_update_endpoint(self, client: AsyncClient):
        """Update endpoint path and verify UUID survives JSONB round-trip."""
        cls = TestShopLifecycle
        seed = cls.seed
        put_ep_id = seed.endpoint_ids["PUT /items/{tracking_id}"]

        resp = await client.put(
            f"/endpoints/{put_ep_id}",
            json={
                "path": "/items/v2/{tracking_id}",
                "pathParams": [
                    {
                        "name": "tracking_id",
                        "fieldId": seed.field_ids["tracking_id"],
                    }
                ],
            },
        )
        assert resp.status_code == 200

        resp = await client.get(f"/endpoints/{put_ep_id}")
        assert resp.status_code == 200
        ep = resp.json()
        assert ep["path"] == "/items/v2/{tracking_id}"
        assert ep["pathParams"][0]["fieldId"] == seed.field_ids["tracking_id"]

    # --- Phase 6: Generate API ---

    async def test_phase_06_generate_api(self, client: AsyncClient):
        """Generate API with databaseEnabled=True and verify ZIP response."""
        cls = TestShopLifecycle
        seed = cls.seed

        resp = await client.post(
            f"/apis/{seed.api_id}/generate",
            json={
                "databaseEnabled": True,
                "responsePlaceholders": False,
            },
        )
        assert resp.status_code == 200, f"Generate failed: {resp.text}"
        assert "application/zip" in resp.headers.get("content-type", "")
        assert "content-disposition" in resp.headers
        assert "shop-api" in resp.headers["content-disposition"].lower()
        assert len(resp.content) > 0
        cls.zip_bytes = resp.content

    # --- Phase 7: Verify ZIP structure ---

    async def test_phase_07_verify_zip_structure(self):
        """ZIP contains all required files, no __pycache__, and compiles."""
        cls = TestShopLifecycle

        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            names = zf.namelist()

            assert not any("__pycache__" in n for n in names), (
                f"Found __pycache__: {[n for n in names if '__pycache__' in n]}"
            )

            required_files = [
                "src/models.py",
                "src/views.py",
                "src/main.py",
                "src/path.py",
                "src/orm_models.py",
                "src/database.py",
                "pyproject.toml",
                "Makefile",
                "Dockerfile",
                "docker-compose.yml",
                "alembic.ini",
                "migrations/env.py",
            ]
            for required in required_files:
                assert required in names, f"Missing file in ZIP: {required}"

        cls.generated_dir = tempfile.mkdtemp(prefix="shop_api_gen_")
        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            zf.extractall(cls.generated_dir)

        for py_file in Path(cls.generated_dir).rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")

    # --- Phase 8: Verify ORM models ---

    async def test_phase_08_verify_orm_models(self):
        """ProductRecord has UUID PK; CustomerRecord has int PK."""
        cls = TestShopLifecycle
        content = (Path(cls.generated_dir) / "src" / "orm_models.py").read_text()

        assert "class ProductRecord(Base):" in content
        assert '__tablename__ = "products"' in content
        assert "import uuid" in content
        assert "default=uuid.uuid4" in content
        assert "primary_key=True" in content

        assert "class CustomerRecord(Base):" in content
        assert '__tablename__ = "customers"' in content
        assert "autoincrement=True" in content

        assert "Numeric" in content
        assert "Boolean" in content

    # --- Phase 9: Verify Pydantic constraints survived generation ---

    async def test_phase_09_verify_pydantic_constraints(self):
        """Generated Pydantic models retain field constraints and validators."""
        cls = TestShopLifecycle
        content = (Path(cls.generated_dir) / "src" / "models.py").read_text()

        assert "class ProductCreate(" in content
        assert "class ProductUpdate(" in content
        assert "class ProductResponse(" in content

        assert "class CustomerCreate(" in content
        assert "class CustomerResponse(" in content

        assert "min_length=" in content
        assert "max_length=" in content
        assert "gt=" in content
        assert "ge=" in content
        assert "pattern=" in content
        assert "multiple_of=" in content

        assert "model_validator" in content

    # --- Phase 10: Cleanup ---

    async def test_phase_10_cleanup(self, client: AsyncClient):
        """Remove generated dir and clean Shop data."""
        cls = TestShopLifecycle
        if cls.generated_dir and Path(cls.generated_dir).exists():
            shutil.rmtree(cls.generated_dir)
        await clean_shop(client)
