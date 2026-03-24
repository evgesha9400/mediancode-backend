# tests/runtime/test_generated_stack.py
"""End-to-end stack test: generate ShopApi, run via Docker Compose, validate.

Catches runtime bugs invisible to unit tests: missing dependencies, broken
imports, port conflicts, ORM mapping errors, validator failures, and timezone
handling.  Uses ``httpx`` against a real containerised service (not TestClient).

Migrated from ``test_api_craft/test_e2e_generated.py``.
"""

from pathlib import Path
import subprocess
import time
import uuid

import httpx
import pytest
import yaml

from api_craft.main import generate_fastapi
from api_craft.models.input import InputAPI
from support.generated_app import SPECS_PATH

pytestmark = pytest.mark.e2e

E2E_APP_PORT = 8002
E2E_DB_PORT = 5434
BASE_URL = f"http://localhost:{E2E_APP_PORT}"
STARTUP_TIMEOUT = 120  # seconds


def _load_input(filename: str) -> InputAPI:
    with open(SPECS_PATH / filename) as f:
        data = yaml.safe_load(f)
    return InputAPI(**data)


# ---------------------------------------------------------------------------
# Session-scoped fixture: generate, docker compose up, yield, tear down
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def generated_shop_api(tmp_path_factory):
    """Generate ShopApi, start with Docker Compose, yield base URL, tear down."""
    tmp_dir = tmp_path_factory.mktemp("e2e_shop")
    input_api = _load_input("shop_api.yaml")

    generate_fastapi(input_api, str(tmp_dir))
    project_dir = tmp_dir / "shop-api"
    assert project_dir.exists(), f"Generated project not found at {project_dir}"

    (project_dir / ".env").write_text(
        f"DB_PORT={E2E_DB_PORT}\nAPP_PORT={E2E_APP_PORT}\n"
    )

    try:
        subprocess.run(
            ["poetry", "lock"],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"poetry lock failed:\nstdout: {e.stdout}\nstderr: {e.stderr}")

    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"docker compose up failed:\nstdout: {e.stdout}\nstderr: {e.stderr}"
        )

    deadline = time.time() + STARTUP_TIMEOUT
    ready = False
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/openapi.json", timeout=3)
            if r.status_code == 200:
                ready = True
                break
        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ):
            pass
        time.sleep(2)

    if not ready:
        logs = subprocess.run(
            ["docker", "compose", "logs"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=str(project_dir),
            capture_output=True,
        )
        pytest.fail(
            f"Generated API not ready within {STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs.stdout}\n{logs.stderr}"
        )

    yield BASE_URL

    subprocess.run(
        ["docker", "compose", "down", "-v", "--remove-orphans"],
        cwd=str(project_dir),
        capture_output=True,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def valid_product(**overrides) -> dict:
    """Build a valid product payload with all required fields."""
    base = {
        "name": "Test Widget",
        "sku": "AB-1234",
        "price": 29.99,
        "weight": 0.5,
        "quantity": 100,
        "min_order_quantity": 1,
        "in_stock": True,
        "product_url": "https://example.com/widget",
        "release_date": "2026-01-15",
        "created_at": "2026-01-01T00:00:00",
        "tracking_id": str(uuid.uuid4()),
    }
    base.update(overrides)
    return base


def valid_customer(**overrides) -> dict:
    """Build a valid customer payload with all required fields."""
    base = {
        "customer_id": 1,
        "customer_name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890",
        "date_of_birth": "1990-05-15",
        "last_login_time": "14:30:00",
        "is_active": True,
        "registered_at": "2026-01-01T00:00:00",
    }
    base.update(overrides)
    return base


# =============================================================================
# CRUD round-trip tests
# =============================================================================


class TestCrudRoundTrip:
    """CRUD operations: create, read, update, delete with data verification."""

    product_tracking_id: str | None = None
    customer_id: int | None = None
    customer_email: str = "john@example.com"

    def test_phase_01_create_product(self, generated_shop_api):
        payload = valid_product()
        r = httpx.post(f"{generated_shop_api}/products", json=payload)
        assert r.status_code == 200, f"Create product failed: {r.status_code} {r.text}"
        data = r.json()
        TestCrudRoundTrip.product_tracking_id = data["tracking_id"]
        assert data["name"] == payload["name"]

    def test_phase_02_list_products(self, generated_shop_api):
        r = httpx.get(f"{generated_shop_api}/products")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_phase_03_get_product(self, generated_shop_api):
        tid = TestCrudRoundTrip.product_tracking_id
        r = httpx.get(f"{generated_shop_api}/products/{tid}")
        assert r.status_code == 200
        data = r.json()
        assert data["tracking_id"] == tid
        assert data["name"] == "Test Widget"

    def test_phase_04_update_product(self, generated_shop_api):
        tid = TestCrudRoundTrip.product_tracking_id
        updated = valid_product(name="Updated Widget", price=39.99, tracking_id=tid)
        r = httpx.put(f"{generated_shop_api}/items/{tid}", json=updated)
        assert r.status_code == 200, f"Update product failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["name"] == "Updated Widget"

    def test_phase_05_delete_product(self, generated_shop_api):
        tid = TestCrudRoundTrip.product_tracking_id
        r = httpx.delete(f"{generated_shop_api}/products/{tid}")
        assert r.status_code == 204, f"Delete failed: {r.status_code} {r.text}"

    def test_phase_06_get_deleted_product(self, generated_shop_api):
        tid = TestCrudRoundTrip.product_tracking_id
        r = httpx.get(f"{generated_shop_api}/products/{tid}")
        assert r.status_code == 404

    def test_phase_07_create_customer(self, generated_shop_api):
        r = httpx.post(f"{generated_shop_api}/customers", json=valid_customer())
        assert r.status_code == 200, f"Create customer failed: {r.status_code} {r.text}"
        data = r.json()
        assert "customer_id" in data
        TestCrudRoundTrip.customer_id = data["customer_id"]

    def test_phase_08_list_customers(self, generated_shop_api):
        r = httpx.get(f"{generated_shop_api}/customers")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_phase_09_get_customer(self, generated_shop_api):
        customer_id = TestCrudRoundTrip.customer_id
        r = httpx.get(f"{generated_shop_api}/customers/{customer_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["customer_name"] == "John Doe"

    def test_phase_10_update_customer(self, generated_shop_api):
        customer_id = TestCrudRoundTrip.customer_id
        r = httpx.patch(
            f"{generated_shop_api}/customers/{customer_id}",
            json=valid_customer(customer_name="Jane Smith", phone="9876543210"),
        )
        assert r.status_code == 200, f"Update customer failed: {r.status_code} {r.text}"

    def test_phase_11_get_updated_customer(self, generated_shop_api):
        customer_id = TestCrudRoundTrip.customer_id
        r = httpx.get(f"{generated_shop_api}/customers/{customer_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["customer_name"] == "Jane Smith"


# =============================================================================
# Constraint violation tests (each expects 422)
# =============================================================================


class TestConstraintViolations:
    def _post_product(self, base_url, **overrides):
        return httpx.post(f"{base_url}/products", json=valid_product(**overrides))

    def _post_customer(self, base_url, **overrides):
        return httpx.post(f"{base_url}/customers", json=valid_customer(**overrides))

    def test_name_min_length(self, generated_shop_api):
        assert self._post_product(generated_shop_api, name="").status_code == 422

    def test_name_max_length(self, generated_shop_api):
        assert self._post_product(generated_shop_api, name="A" * 151).status_code == 422

    def test_sku_pattern(self, generated_shop_api):
        assert self._post_product(generated_shop_api, sku="test-01").status_code == 422

    def test_price_gt_zero(self, generated_shop_api):
        assert self._post_product(generated_shop_api, price=0).status_code == 422

    def test_sale_price_ge_zero(self, generated_shop_api):
        assert self._post_product(generated_shop_api, sale_price=-1).status_code == 422

    def test_weight_ge_zero(self, generated_shop_api):
        r = self._post_product(generated_shop_api, weight=-0.1)
        assert r.status_code == 200

    def test_weight_lt_1000(self, generated_shop_api):
        assert self._post_product(generated_shop_api, weight=1000).status_code == 422

    def test_quantity_ge_zero(self, generated_shop_api):
        assert self._post_product(generated_shop_api, quantity=-1).status_code == 422

    def test_min_order_ge_one(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, min_order_quantity=0).status_code
            == 422
        )

    def test_max_order_le_1000(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, max_order_quantity=1001).status_code
            == 422
        )

    def test_discount_percent_ge_zero(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, discount_percent=-5).status_code
            == 422
        )

    def test_discount_percent_le_100(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, discount_percent=105).status_code
            == 422
        )

    def test_discount_percent_multiple_of_5(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, discount_percent=3).status_code
            == 422
        )

    def test_discount_amount_ge_zero(self, generated_shop_api):
        assert (
            self._post_product(generated_shop_api, discount_amount=-1).status_code
            == 422
        )

    def test_customer_name_min_length(self, generated_shop_api):
        assert (
            self._post_customer(generated_shop_api, customer_name="").status_code == 422
        )

    def test_phone_min_length(self, generated_shop_api):
        assert self._post_customer(generated_shop_api, phone="123").status_code == 422

    def test_phone_max_length(self, generated_shop_api):
        assert (
            self._post_customer(generated_shop_api, phone="1" * 16).status_code == 422
        )


# =============================================================================
# Field validator tests
# =============================================================================


class TestFieldValidators:
    def test_name_trim_normalize(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(name="  hello   world  "),
        )
        assert r.status_code == 200
        assert r.json()["name"] == "hello world"

    def test_sku_uppercase(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(sku="ab-1234"),
        )
        assert r.status_code == 200
        assert r.json()["sku"] == "AB-1234"

    def test_price_round_decimal(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(price=9.999),
        )
        assert r.status_code == 200
        assert float(r.json()["price"]) == 10.0

    def test_weight_clamp_negative(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(weight=-5),
        )
        assert r.status_code == 200
        assert float(r.json()["weight"]) == 0.0

    def test_customer_name_trim_title(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/customers",
            json=valid_customer(customer_id=100, customer_name="  john doe  "),
        )
        assert r.status_code == 200
        assert r.json()["customer_name"] == "John Doe"


# =============================================================================
# Model validator tests
# =============================================================================


class TestModelValidators:
    def test_field_comparison_rejects(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(min_order_quantity=10, max_order_quantity=5),
        )
        assert r.status_code == 422

    def test_mutual_exclusivity_rejects(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(discount_percent=10, discount_amount=5),
        )
        assert r.status_code == 422

    def test_all_or_none_rejects_partial(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(sale_price=10),
        )
        assert r.status_code == 422

    def test_conditional_required_rejects(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(discount_percent=10),
        )
        assert r.status_code == 422

    def test_at_least_one_required_rejects(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/customers",
            json=valid_customer(email=None, phone=None),
        )
        assert r.status_code == 422


# =============================================================================
# Timezone-aware datetime tests
# =============================================================================


class TestDatetimeTimezones:
    """Datetime fields must accept timezone-aware ISO 8601 strings.

    Real API clients typically send timezone-aware strings.  The generated
    API must handle these without asyncpg raising ``can't subtract
    offset-naive and offset-aware datetimes``.
    """

    def test_product_datetime_utc_offset(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(created_at="2026-06-01T12:00:00+00:00"),
        )
        assert r.status_code == 200, f"UTC offset failed: {r.status_code} {r.text}"

    def test_product_datetime_z_suffix(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(created_at="2026-06-01T12:00:00Z"),
        )
        assert r.status_code == 200, f"Z suffix failed: {r.status_code} {r.text}"

    def test_product_datetime_positive_offset(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(created_at="2026-06-01T17:30:00+05:30"),
        )
        assert r.status_code == 200, f"Positive offset failed: {r.status_code} {r.text}"

    def test_product_datetime_negative_offset(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/products",
            json=valid_product(created_at="2026-06-01T07:00:00-05:00"),
        )
        assert r.status_code == 200, f"Negative offset failed: {r.status_code} {r.text}"

    def test_customer_datetime_utc_offset(self, generated_shop_api):
        r = httpx.post(
            f"{generated_shop_api}/customers",
            json=valid_customer(
                customer_id=500, registered_at="2026-06-01T12:00:00+00:00"
            ),
        )
        assert r.status_code == 200, (
            f"Customer UTC offset failed: {r.status_code} {r.text}"
        )


# =============================================================================
# Make target lifecycle tests (install → run-local → cleanup)
# =============================================================================

MAKE_APP_PORT = 8003
MAKE_DB_PORT = 5435
MAKE_STARTUP_TIMEOUT = 120  # seconds


@pytest.fixture(scope="module")
def make_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the ShopApi project tree for make-target tests."""
    tmp_dir = tmp_path_factory.mktemp("e2e_make")
    input_api = _load_input("shop_api.yaml")
    generate_fastapi(input_api, str(tmp_dir))
    project_dir = tmp_dir / "shop-api"
    assert project_dir.exists(), f"Generated project not found at {project_dir}"
    (project_dir / ".env").write_text(
        f"DB_PORT={MAKE_DB_PORT}\nAPP_PORT={MAKE_APP_PORT}\n"
    )
    return project_dir


def _run_make(
    target: str, project_dir: Path, timeout: int = 180
) -> subprocess.CompletedProcess:
    """Run a make target in the generated project directory."""
    return subprocess.run(
        ["make", target],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_make_background(target: str, project_dir: Path) -> subprocess.Popen:
    """Start a long-running make target in a background subprocess."""
    return subprocess.Popen(
        ["make", target],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_api(base_url: str, timeout: int) -> bool:
    """Poll the OpenAPI endpoint until the API is ready or timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/openapi.json", timeout=3)
            if r.status_code == 200:
                return True
        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ):
            pass
        time.sleep(2)
    return False


class TestMakeTargets:
    """Validate generated Makefile lifecycle: install, run-local, cleanup."""

    def test_make_install(self, make_project: Path):
        """make install completes without error (poetry install succeeds)."""
        try:
            _run_make("install", make_project, timeout=180)
        except subprocess.CalledProcessError as e:
            pytest.fail(f"make install failed:\nstdout: {e.stdout}\nstderr: {e.stderr}")

    def test_make_run_local_starts_api(self, make_project: Path):
        """make run-local brings up the DB and API; openapi.json is reachable."""
        base_url = f"http://localhost:{MAKE_APP_PORT}"
        proc = _run_make_background("run-local", make_project)
        try:
            ready = _wait_for_api(base_url, MAKE_STARTUP_TIMEOUT)
            if not ready:
                proc.terminate()
                proc.wait(timeout=10)
                stdout, stderr = proc.communicate()
                pytest.fail(
                    f"API not ready after {MAKE_STARTUP_TIMEOUT}s via make run-local.\n"
                    f"stdout: {stdout}\nstderr: {stderr}"
                )
            r = httpx.get(f"{base_url}/openapi.json", timeout=5)
            assert r.status_code == 200
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_make_cleanup_removes_resources(self, make_project: Path):
        """make cleanup tears down Compose stack, volumes, and image idempotently."""
        try:
            _run_make("cleanup", make_project, timeout=60)
        except subprocess.CalledProcessError as e:
            pytest.fail(f"make cleanup failed:\nstdout: {e.stdout}\nstderr: {e.stderr}")

        # Compose stack should be fully down after cleanup.
        ps_result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            cwd=str(make_project),
            capture_output=True,
            text=True,
        )
        running_services = ps_result.stdout.strip()
        assert running_services == "", (
            f"Expected no running Compose services after cleanup, got: {running_services!r}"
        )

    def test_make_cleanup_is_idempotent(self, make_project: Path):
        """A second make cleanup run must not fail when nothing is running."""
        try:
            _run_make("cleanup", make_project, timeout=60)
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"Second make cleanup invocation failed:\nstdout: {e.stdout}\nstderr: {e.stderr}"
            )
