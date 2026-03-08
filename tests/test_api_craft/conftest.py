# tests/test_api_craft/conftest.py
"""Fixtures for api_craft code generation tests."""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api_craft.main import APIGenerator
from api_craft.models.input import InputAPI

SPECS_PATH = Path(__file__).parent.parent / "specs"


def load_input(filename: str) -> InputAPI:
    """Load and validate an API input from YAML file."""
    yaml_path = SPECS_PATH / filename
    with open(yaml_path, "r") as f:
        api_data = yaml.safe_load(f)
    return InputAPI.model_validate(api_data)


def load_app(src_path: Path):
    """Dynamically import the FastAPI app from a generated project.

    Uses unique module names to avoid conflicts between different
    generated projects in the same test session.
    """
    # Generate unique prefix for this import
    prefix = f"_gen_{uuid.uuid4().hex[:8]}"

    # Add src_path to sys.path so relative imports work
    sys.path.insert(0, str(src_path))

    modules_to_cleanup = []
    try:
        # Load modules in dependency order with unique names
        module_files = [
            "orm_models",
            "database",
            "seed",
            "models",
            "path",
            "query",
            "views",
            "main",
        ]

        for module_name in module_files:
            module_path = src_path / f"{module_name}.py"
            if not module_path.exists():
                continue

            unique_name = f"{prefix}_{module_name}"
            spec = importlib.util.spec_from_file_location(unique_name, module_path)
            module = importlib.util.module_from_spec(spec)

            # Register with both unique and simple names for import resolution
            sys.modules[unique_name] = module
            sys.modules[module_name] = module
            modules_to_cleanup.append(unique_name)
            modules_to_cleanup.append(module_name)

            spec.loader.exec_module(module)

        return sys.modules["main"].app
    finally:
        # Clean up sys.path
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))

        # Clean up sys.modules to prevent cross-test pollution
        for mod_name in modules_to_cleanup:
            sys.modules.pop(mod_name, None)


@pytest.fixture(scope="session")
def items_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Items API once per test session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("items_api")

    api_input = load_input("items_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))

    src_path = tmp_path / "items-api" / "src"
    app = load_app(src_path)

    return TestClient(app)


@pytest.fixture(scope="session")
def shop_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Shop API once per test session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("shop_api")

    api_input = load_input("shop_api.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))

    src_path = tmp_path / "shop-api" / "src"
    app = load_app(src_path)

    return TestClient(app)
