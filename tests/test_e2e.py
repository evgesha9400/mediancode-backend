# tests/test_e2e.py
"""E2E integration tests for api_craft code generation.

These tests generate APIs, launch them, and make real HTTP requests.
A successful request proves:
- Syntax validity (import would fail otherwise)
- Model correctness (Pydantic would error)
- View definitions (FastAPI would error)
- Parameter handling (requests would fail)
- Import correctness (module loading would fail)
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_craft.main import APIGenerator
from conftest import SPECS_PATH, load_input


@pytest.mark.manual
def test_generate_to_output():
    """Generate all APIs from tests/data/*.yaml to tests/output/."""
    output_path = Path(__file__).parent / "output"
    for yaml_file in SPECS_PATH.glob("*.yaml"):
        api_input = load_input(yaml_file.name)
        APIGenerator().generate(api_input, path=str(output_path))


class TestItemsApi:
    """E2E tests for the Items API."""

    def test_healthcheck(self, items_api_client: TestClient):
        """Healthcheck endpoint returns OK."""
        response = items_api_client.get("/healthcheck")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_get_item(self, items_api_client: TestClient):
        """GET /items/{item_id} returns a single item."""
        response = items_api_client.get("/items/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "example 2"

    def test_get_items(self, items_api_client: TestClient):
        """GET /items returns a list of items."""
        response = items_api_client.get("/items")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2

    def test_get_items_with_query_params(self, items_api_client: TestClient):
        """GET /items accepts query parameters."""
        response = items_api_client.get("/items?limit=10&offset=5")
        assert response.status_code == 200

    def test_create_item(self, items_api_client: TestClient):
        """POST /items creates an item."""
        response = items_api_client.post("/items", json={"name": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data

    def test_update_item(self, items_api_client: TestClient):
        """PUT /items/{item_id} updates an item."""
        response = items_api_client.put("/items/1", json={"name": "updated"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_delete_item(self, items_api_client: TestClient):
        """DELETE /items/{item_id} deletes an item."""
        response = items_api_client.delete("/items/1")
        assert response.status_code == 200
