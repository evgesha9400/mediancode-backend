# Comprehensive E2E Shop Test Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a single comprehensive e2e test that exercises the full Shop API lifecycle: CRUD entities via the API, call the generate endpoint, unzip the result, and verify the generated FastAPI app works with correct constraints and validators.

**Architecture:** One test class `TestShopApiFullE2E` in `tests/test_api/test_e2e_shop_full.py` with 25 ordered phases sharing state via class variables. CRUD phases (1-13) use async httpx. Generated code verification phases (14-20) mix async (generate endpoint) and sync (TestClient against generated app). Cleanup phases (21-25) use async httpx. The test uses its own `TEST_CLERK_ID` to avoid conflicts with the existing `test_e2e_shop.py`.

**Tech Stack:** pytest, pytest-asyncio, httpx, FastAPI TestClient, zipfile, importlib

**Design doc:** `docs/plans/2026-03-06-e2e-shop-full-design.md`

---

## Task 1: Create test file with fixtures, field definitions, and CRUD phases 1-13

**Files:**
- Create: `tests/test_api/test_e2e_shop_full.py`
- Reference: `tests/test_api/test_e2e_shop.py` (CRUD phases source)

### Step 1: Create the test file

Create `tests/test_api/test_e2e_shop_full.py` with the following structure:

1. **Module docstring and imports** — same imports as `test_e2e_shop.py` plus: `io`, `shutil`, `tempfile`, `zipfile`, `importlib.util`, `uuid`, `Path`, `TestClient`
2. **pytest marks** — `pytest.mark.integration` and `pytest.mark.asyncio(loop_scope="session")`
3. **`TEST_CLERK_ID`** — set to `"test_user_e2e_shop_full"` (different from the existing test's `"test_user_e2e_shop"`)
4. **`client` fixture** — copy from `tests/test_api/conftest.py` but define it directly in the test file using the new `TEST_CLERK_ID`. Must be `module`-scoped with `loop_scope="session"`. Include the same DB cleanup teardown logic (delete APIs, objects, fields, generations, namespaces, user).
5. **Field definitions** — copy `PRODUCT_FIELDS`, `CUSTOMER_FIELDS`, `ALL_FIELDS`, `PRODUCT_OPTIONAL`, `CUSTOMER_OPTIONAL` exactly from `tests/test_api/test_e2e_shop.py` lines 32-187.
6. **`load_app` helper** — copy from `tests/test_api_craft/conftest.py` lines 27-69 (the `load_app` function). Cannot import it because `tests/` has no `__init__.py`.
7. **`assert_gen_response` helper** — assert response status code with helpful error messages (same pattern as `assert_valid_response` in `test_shop_codegen.py`).
8. **`assert_gen_validation_error` helper** — assert 422 with optional field name check (same pattern as `assert_validation_error` in `test_shop_codegen.py`).
9. **Class `TestShopApiFullE2E`** with class variables:

```python
class TestShopApiFullE2E:
    """Full Shop API E2E: CRUD -> Generate -> Verify Generated Code."""

    # Shared state across test phases
    type_ids: dict[str, str] = {}
    constraint_ids: dict[str, str] = {}
    fv_template_ids: dict[str, str] = {}
    mv_template_ids: dict[str, str] = {}
    namespace_id: str = ""
    field_ids: dict[str, str] = {}
    product_id: str = ""
    customer_id: str = ""
    api_id: str = ""
    endpoint_ids: dict[str, str] = {}
    zip_bytes: bytes = b""
    generated_dir: str = ""
    gen_client: TestClient | None = None
```

10. **CRUD phases 1-13** — copy each `test_phase_XX_*` method exactly from `tests/test_api/test_e2e_shop.py` lines 215-789, with ONE change: every occurrence of `cls = TestShopApiE2E` becomes `cls = TestShopApiFullE2E`.

11. **Two static helper methods** at the end of the class:

```python
    @staticmethod
    def _valid_product(**overrides) -> dict:
        """Build a valid Product payload for the generated API.

        Required fields based on PRODUCT_FIELDS minus PRODUCT_OPTIONAL
        (with min_order_quantity made required in phase 8).
        """
        base = {
            "tracking_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Test Product",
            "sku": "AB-1234",
            "price": 29.99,
            "weight": 5.0,
            "quantity": 50,
            "min_order_quantity": 1,
            "in_stock": True,
            "product_url": "https://example.com/product",
            "release_date": "2026-01-15",
            "created_at": "2026-01-01T00:00:00",
        }
        base.update(overrides)
        return base

    @staticmethod
    def _valid_customer(**overrides) -> dict:
        """Build a valid Customer payload for the generated API.

        Required fields based on CUSTOMER_FIELDS minus CUSTOMER_OPTIONAL.
        Must include at least email or phone (At Least One Required MV).
        """
        base = {
            "customer_name": "Jane Doe",
            "date_of_birth": "1990-01-15",
            "last_login_time": "14:30:00",
            "is_active": True,
            "registered_at": "2026-01-01T00:00:00",
            "email": "jane@example.com",
        }
        base.update(overrides)
        return base
```

### Step 2: Format and run CRUD phases

Run:
```bash
poetry run black tests/test_api/test_e2e_shop_full.py
poetry run pytest tests/test_api/test_e2e_shop_full.py -v -k "phase_01 or phase_02 or phase_03 or phase_04 or phase_05 or phase_06 or phase_07 or phase_08 or phase_09 or phase_10 or phase_11 or phase_12 or phase_13" --timeout=120
```

Expected: All 13 phases PASS. If any fail, debug — the code should be identical to the existing passing test aside from the class name.

### Step 3: Commit

```bash
git add tests/test_api/test_e2e_shop_full.py
git commit -m "test(api): add comprehensive e2e shop test — CRUD phases 1-13"
```

---

## Task 2: Add generation and ZIP verification (phases 14-15)

**Files:**
- Modify: `tests/test_api/test_e2e_shop_full.py`

### Step 1: Add phase 14 — generate API

Add this method to `TestShopApiFullE2E` after phase 13:

```python
    # --- Phase 14: Generate API ---

    async def test_phase_14_generate_api(self, client: AsyncClient):
        """Call the generate endpoint and receive the ZIP file."""
        cls = TestShopApiFullE2E

        resp = await client.post(f"/apis/{cls.api_id}/generate")
        assert resp.status_code == 200, f"Generate failed: {resp.text}"
        assert "application/zip" in resp.headers.get("content-type", "")
        assert "content-disposition" in resp.headers
        assert "shop-api" in resp.headers["content-disposition"].lower()
        assert len(resp.content) > 0
        cls.zip_bytes = resp.content
```

### Step 2: Add phase 15 — verify ZIP structure

```python
    # --- Phase 15: Verify ZIP structure ---

    async def test_phase_15_verify_zip_structure(self, client: AsyncClient):
        """Extract ZIP and verify file structure, no __pycache__, .py compiles."""
        cls = TestShopApiFullE2E

        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            names = zf.namelist()

            # No __pycache__ directories
            assert not any(
                "__pycache__" in n for n in names
            ), f"Found __pycache__ in ZIP: {[n for n in names if '__pycache__' in n]}"

            # Required files present
            required_files = [
                "src/models.py",
                "src/views.py",
                "src/main.py",
                "src/path.py",
                "pyproject.toml",
                "Makefile",
                "Dockerfile",
            ]
            for required in required_files:
                assert required in names, f"Missing file in ZIP: {required}"

        # Extract to temp directory
        cls.generated_dir = tempfile.mkdtemp(prefix="shop_api_gen_")
        with zipfile.ZipFile(io.BytesIO(cls.zip_bytes)) as zf:
            zf.extractall(cls.generated_dir)

        # All .py files must compile without errors
        gen_path = Path(cls.generated_dir)
        for py_file in gen_path.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")
```

### Step 3: Run phases 1-15

```bash
poetry run black tests/test_api/test_e2e_shop_full.py
poetry run pytest tests/test_api/test_e2e_shop_full.py -v -k "phase_01 or phase_02 or phase_03 or phase_04 or phase_05 or phase_06 or phase_07 or phase_08 or phase_09 or phase_10 or phase_11 or phase_12 or phase_13 or phase_14 or phase_15" --timeout=120
```

Expected: All 15 phases PASS. Phase 14 confirms the generate endpoint works. Phase 15 confirms the ZIP is well-formed and all Python files compile.

### Step 4: Commit

```bash
git add tests/test_api/test_e2e_shop_full.py
git commit -m "test(api): add generation and ZIP verification phases 14-15"
```

---

## Task 3: Add generated app loading and endpoint connectivity (phase 16)

**Files:**
- Modify: `tests/test_api/test_e2e_shop_full.py`

### Step 1: Add phase 16 — load generated app and test all endpoints

```python
    # --- Phase 16: Generated app endpoint connectivity ---

    def test_phase_16_generated_endpoints(self):
        """Load the generated FastAPI app and verify all endpoints respond."""
        cls = TestShopApiFullE2E

        src_path = Path(cls.generated_dir) / "src"
        generated_app = load_app(src_path)
        cls.gen_client = TestClient(generated_app)

        # Healthcheck
        resp = cls.gen_client.get("/health")
        assert resp.status_code == 200

        # GET /products (list, useEnvelope=False, responseShape=list)
        resp = cls.gen_client.get("/products")
        assert_gen_response(resp)
        data = resp.json()
        assert isinstance(data, list)

        # GET /products/{tracking_id}
        resp = cls.gen_client.get("/products/abc-123")
        assert_gen_response(resp)

        # POST /products (request + response body = Product)
        resp = cls.gen_client.post("/products", json=cls._valid_product())
        assert_gen_response(resp)

        # PUT /items/{tracking_id} (path changed in phase 13)
        resp = cls.gen_client.put("/items/abc-123", json=cls._valid_product())
        assert_gen_response(resp)

        # DELETE /products/{tracking_id}
        resp = cls.gen_client.delete("/products/abc-123")
        assert_gen_response(resp)

        # GET /customers (list)
        resp = cls.gen_client.get("/customers")
        assert_gen_response(resp)
        data = resp.json()
        assert isinstance(data, list)

        # PATCH /customers/{email}
        resp = cls.gen_client.patch(
            "/customers/test@example.com", json=cls._valid_customer()
        )
        assert_gen_response(resp)
```

**Note on the PUT path:** Phase 13 updates the PUT endpoint from `/products/{tracking_id}` to `/items/{tracking_id}`. The generated code will have `/items/{tracking_id}`. This is intentional — it validates that endpoint updates flow through to generation.

**Note on DELETE:** The DELETE endpoint has no response object, so it should return 204. `assert_gen_response` defaults to expecting 200. Adjust if the generated code returns 204:

```python
        # DELETE /products/{tracking_id} (no response object → 204)
        resp = cls.gen_client.delete("/products/abc-123")
        # May be 200 or 204 depending on template behavior
        assert resp.status_code in (200, 204), f"DELETE failed: {resp.status_code} {resp.text}"
```

### Step 2: Run phases 1-16

```bash
poetry run black tests/test_api/test_e2e_shop_full.py
poetry run pytest tests/test_api/test_e2e_shop_full.py -v -k "phase_01 or phase_02 or phase_03 or phase_04 or phase_05 or phase_06 or phase_07 or phase_08 or phase_09 or phase_10 or phase_11 or phase_12 or phase_13 or phase_14 or phase_15 or phase_16" --timeout=120
```

Expected: All 16 phases PASS. This proves the generated app loads and all 7 endpoints + healthcheck respond correctly.

**Debugging tips if phase 16 fails:**
- If `load_app` fails with ImportError: check the generated `models.py` for missing imports (read the file from `cls.generated_dir`)
- If an endpoint returns 404: check `views.py` for the route paths; the PUT endpoint should be `/items/{tracking_id}` not `/products/{tracking_id}`
- If an endpoint returns 422: the valid payload may be missing a required field; check `models.py` for which fields are optional
- If the `email` path param causes issues (EmailStr as path type): this is a known limitation; may need to adjust the test or fix generation

### Step 3: Commit

```bash
git add tests/test_api/test_e2e_shop_full.py
git commit -m "test(api): add generated app endpoint connectivity phase 16"
```

---

## Task 4: Add constraint and model validator phases (17-20)

**Files:**
- Modify: `tests/test_api/test_e2e_shop_full.py`

### Step 1: Add phase 17 — product field constraint validation

These test that the generated Pydantic models enforce the constraints set via the API.

**Important context for constraint testing:**
- Field validators with `mode="before"` run BEFORE Pydantic Field() constraints
- The `sku` field has a "Normalize Case" (upper) before-validator, so `"ab-1234"` becomes `"AB-1234"` before pattern check — use `"invalid!"` to test pattern failure
- The `name` field has "Trim" and "Normalize Whitespace" before-validators (strip + collapse spaces), but these don't affect length checks
- The `weight` field has "Clamp to Range" as after-validator, so constraint checks happen first

```python
    # --- Phase 17: Product field constraint validation ---

    def test_phase_17_product_constraints(self):
        """Verify Product field constraints in the generated API."""
        cls = TestShopApiFullE2E
        c = cls.gen_client

        # name: min_length=1 (empty rejected)
        resp = c.post("/products", json=cls._valid_product(name=""))
        assert_gen_validation_error(resp, expected_field="name")

        # name: max_length=150 (too long rejected; updated from 200 in phase 5)
        resp = c.post("/products", json=cls._valid_product(name="A" * 151))
        assert_gen_validation_error(resp, expected_field="name")

        # sku: pattern=^[A-Z]{2}-\d{4}$ (invalid rejected after uppercase normalization)
        resp = c.post("/products", json=cls._valid_product(sku="invalid!"))
        assert_gen_validation_error(resp, expected_field="sku")

        # price: gt=0 (zero rejected)
        resp = c.post("/products", json=cls._valid_product(price=0))
        assert_gen_validation_error(resp, expected_field="price")

        # price: gt=0 (negative rejected)
        resp = c.post("/products", json=cls._valid_product(price=-10.0))
        assert_gen_validation_error(resp, expected_field="price")

        # quantity: ge=0 (negative rejected)
        resp = c.post("/products", json=cls._valid_product(quantity=-1))
        assert_gen_validation_error(resp, expected_field="quantity")

        # min_order_quantity: ge=1 (zero rejected)
        resp = c.post("/products", json=cls._valid_product(min_order_quantity=0))
        assert_gen_validation_error(resp, expected_field="min_order_quantity")

        # max_order_quantity: le=1000 (over limit rejected)
        resp = c.post(
            "/products", json=cls._valid_product(max_order_quantity=1001)
        )
        assert_gen_validation_error(resp, expected_field="max_order_quantity")

        # discount_percent: multiple_of=5 (not multiple rejected)
        resp = c.post(
            "/products", json=cls._valid_product(discount_percent=7)
        )
        assert_gen_validation_error(resp, expected_field="discount_percent")

        # discount_percent: le=100 (over 100 rejected)
        resp = c.post(
            "/products", json=cls._valid_product(discount_percent=105)
        )
        assert_gen_validation_error(resp, expected_field="discount_percent")

        # weight: ge=0 (negative rejected)
        resp = c.post("/products", json=cls._valid_product(weight=-1.0))
        assert_gen_validation_error(resp, expected_field="weight")
```

### Step 2: Add phase 18 — customer field constraint validation

```python
    # --- Phase 18: Customer field constraint validation ---

    def test_phase_18_customer_constraints(self):
        """Verify Customer field constraints in the generated API."""
        cls = TestShopApiFullE2E
        c = cls.gen_client

        # customer_name: min_length=1 (empty rejected)
        resp = c.patch(
            "/customers/test@example.com",
            json=cls._valid_customer(customer_name=""),
        )
        assert_gen_validation_error(resp, expected_field="customer_name")

        # phone: min_length=7 (too short rejected)
        resp = c.patch(
            "/customers/test@example.com",
            json=cls._valid_customer(phone="123"),
        )
        assert_gen_validation_error(resp, expected_field="phone")
```

### Step 3: Add phase 19 — product model validators

**Context for model validators created via the API:**
- **Field Comparison** (operator `<`): `min_order_quantity` must be `<` `max_order_quantity`
- **Mutual Exclusivity**: `discount_percent` and `discount_amount` cannot both have values
- **All Or None**: `sale_price` and `sale_end_date` must both be present or both absent
- **Conditional Required**: if `discount_percent` is set, `sale_price` must also be set

```python
    # --- Phase 19: Product model validators ---

    def test_phase_19_product_model_validators(self):
        """Verify Product model validators in the generated API."""
        cls = TestShopApiFullE2E
        c = cls.gen_client

        # Field Comparison: min_order_quantity >= max_order_quantity rejected
        resp = c.post(
            "/products",
            json=cls._valid_product(
                min_order_quantity=500, max_order_quantity=500
            ),
        )
        assert_gen_validation_error(resp)

        # Mutual Exclusivity: both discount_percent and discount_amount rejected
        resp = c.post(
            "/products",
            json=cls._valid_product(
                discount_percent=10, discount_amount=5.00
            ),
        )
        assert_gen_validation_error(resp)

        # All Or None: sale_price without sale_end_date rejected
        resp = c.post(
            "/products",
            json=cls._valid_product(sale_price=19.99),
        )
        assert_gen_validation_error(resp)

        # Conditional Required: discount_percent without sale_price rejected
        resp = c.post(
            "/products",
            json=cls._valid_product(discount_percent=10),
        )
        assert_gen_validation_error(resp)
```

### Step 4: Add phase 20 — customer model validator

```python
    # --- Phase 20: Customer model validator ---

    def test_phase_20_customer_model_validator(self):
        """Verify Customer At Least One Required validator."""
        cls = TestShopApiFullE2E
        c = cls.gen_client

        # At Least One Required: neither email nor phone rejected
        payload = cls._valid_customer()
        payload.pop("email", None)
        payload.pop("phone", None)
        resp = c.patch("/customers/test@example.com", json=payload)
        assert_gen_validation_error(resp)
```

### Step 5: Run phases 1-20

```bash
poetry run black tests/test_api/test_e2e_shop_full.py
poetry run pytest tests/test_api/test_e2e_shop_full.py -v -k "phase_01 or phase_02 or phase_03 or phase_04 or phase_05 or phase_06 or phase_07 or phase_08 or phase_09 or phase_10 or phase_11 or phase_12 or phase_13 or phase_14 or phase_15 or phase_16 or phase_17 or phase_18 or phase_19 or phase_20" --timeout=120
```

Expected: All 20 phases PASS.

**Debugging tips for constraint/validator failures:**
- If a constraint test passes when it should fail (422): read the generated `models.py` from `cls.generated_dir` to see the actual Field() constraints and validators
- If a model validator test passes when it should fail: the validator function body may differ from expected — read `models.py` and check the `@model_validator` decorated methods
- If the Mutual Exclusivity test fails unexpectedly: the template may check `is not None` differently — inspect the generated function body
- If the All Or None test behaves unexpectedly: the template groups fields as a list and checks partial fills — verify which fields are grouped

### Step 6: Commit

```bash
git add tests/test_api/test_e2e_shop_full.py
git commit -m "test(api): add constraint and model validator verification phases 17-20"
```

---

## Task 5: Add cleanup phases 21-25 and run full test

**Files:**
- Modify: `tests/test_api/test_e2e_shop_full.py`

### Step 1: Add cleanup phases

These are the same as phases 14-18 in `test_e2e_shop.py` with renumbered phase names and the addition of temp directory cleanup. Add a phase 21 first to clean up the generated app resources:

```python
    # --- Phase 21: Clean up generated app ---

    def test_phase_21_cleanup_generated(self):
        """Clean up the generated app temp directory."""
        cls = TestShopApiFullE2E
        cls.gen_client = None
        if cls.generated_dir and Path(cls.generated_dir).exists():
            shutil.rmtree(cls.generated_dir)

    # --- Phase 22: Delete endpoints ---

    async def test_phase_22_delete_endpoints(self, client: AsyncClient):
        """Delete all 7 endpoints and verify list is empty."""
        cls = TestShopApiFullE2E

        for key, ep_id in cls.endpoint_ids.items():
            resp = await client.delete(f"/endpoints/{ep_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete endpoint {key}: {resp.text}"

        resp = await client.get("/endpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 23: Delete API ---

    async def test_phase_23_delete_api(self, client: AsyncClient):
        """Delete the Shop API and verify list is empty."""
        cls = TestShopApiFullE2E

        resp = await client.delete(f"/apis/{cls.api_id}")
        assert resp.status_code == 204

        resp = await client.get("/apis")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 24: Delete objects ---

    async def test_phase_24_delete_objects(self, client: AsyncClient):
        """Delete both objects and verify list is empty."""
        cls = TestShopApiFullE2E

        for obj_id in (cls.product_id, cls.customer_id):
            resp = await client.delete(f"/objects/{obj_id}")
            assert resp.status_code == 204

        resp = await client.get("/objects")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 25: Delete fields ---

    async def test_phase_25_delete_fields(self, client: AsyncClient):
        """Delete all 23 fields and verify list is empty."""
        cls = TestShopApiFullE2E

        for name, field_id in cls.field_ids.items():
            resp = await client.delete(f"/fields/{field_id}")
            assert (
                resp.status_code == 204
            ), f"Failed to delete field '{name}': {resp.text}"

        resp = await client.get("/fields")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    # --- Phase 26: Delete namespace ---

    async def test_phase_26_delete_namespace(self, client: AsyncClient):
        """Delete Shop namespace and verify only Global remains."""
        cls = TestShopApiFullE2E

        resp = await client.delete(f"/namespaces/{cls.namespace_id}")
        assert resp.status_code == 204

        resp = await client.get("/namespaces")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert "Shop" not in names
        assert "Global" in names
```

**Note:** Added phase 26 for namespace (was 25 in original design). Total is now 26 phases since we split cleanup into its own phase.

### Step 2: Run the complete test

```bash
poetry run black tests/test_api/test_e2e_shop_full.py
poetry run pytest tests/test_api/test_e2e_shop_full.py -v --timeout=180
```

Expected: All 26 phases PASS.

### Step 3: Run existing tests to verify nothing broke

```bash
poetry run pytest tests/ -v --timeout=180
```

Expected: All existing tests still pass. The new test runs independently with its own user.

### Step 4: Commit

```bash
git add tests/test_api/test_e2e_shop_full.py
git commit -m "test(api): add cleanup phases and complete comprehensive e2e shop test"
```

---

## Important Notes

### Field definitions used by the test

The CRUD phases create these entities via the API:

**Product (16 fields):**
| Field | Type | Required | Constraints | Field Validators |
|-------|------|----------|-------------|-----------------|
| name | str | yes | min_length=1, max_length=150* | Trim, Normalize Whitespace |
| sku | str | yes | pattern=^[A-Z]{2}-\d{4}$ | Normalize Case (upper) |
| price | Decimal | yes | gt=0 | Round Decimal (places=2) |
| sale_price | Decimal | no | ge=0 | — |
| sale_end_date | date | no | — | — |
| weight | float | yes | ge=0, lt=1000 | Clamp to Range (0, 1000) |
| quantity | int | yes | ge=0 | — |
| min_order_quantity | int | yes** | ge=1 | — |
| max_order_quantity | int | no | le=1000 | — |
| discount_percent | int | no | ge=0, le=100, multiple_of=5 | — |
| discount_amount | Decimal | no | ge=0 | — |
| in_stock | bool | yes | — | — |
| product_url | HttpUrl | yes | — | — |
| release_date | date | yes | — | — |
| created_at | datetime | yes | — | — |
| tracking_id | uuid | yes | — | — |

*max_length updated from 200 to 150 in phase 5
**min_order_quantity made required in phase 8 (was optional)

**Product model validators:**
1. Field Comparison: min_order_quantity < max_order_quantity
2. Mutual Exclusivity: discount_percent XOR discount_amount
3. All Or None: sale_price + sale_end_date
4. Conditional Required: discount_percent → sale_price

**Customer (7 fields):**
| Field | Type | Required | Constraints | Field Validators |
|-------|------|----------|-------------|-----------------|
| customer_name | str | yes | min_length=1, max_length=100 | Trim, Normalize Case (title), Trim To Length (100)* |
| email | EmailStr | no | — | — |
| phone | str | no | min_length=7, max_length=15 | — |
| date_of_birth | date | yes | — | — |
| last_login_time | time | yes | — | — |
| is_active | bool | yes | — | — |
| registered_at | datetime | yes | — | — |

*Trim To Length added in phase 5

**Customer model validator:**
1. At Least One Required: email OR phone

### Generated API endpoints

| Method | Path | Request Body | Response | Shape |
|--------|------|-------------|----------|-------|
| GET | /products | — | Product | list |
| GET | /products/{tracking_id} | — | Product | object |
| POST | /products | Product | Product | object |
| PUT | /items/{tracking_id}* | Product | Product | object |
| DELETE | /products/{tracking_id} | — | — (204) | — |
| GET | /customers | — | Customer | list |
| PATCH | /customers/{email} | Customer | Customer | object |

*Path changed from /products/{tracking_id} in phase 13

All endpoints have `useEnvelope=False`.
