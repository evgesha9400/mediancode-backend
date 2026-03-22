# tests/test_api_craft/test_prepare.py
"""Tests for prepare_api — verifies preparation produces correct structure."""

import pytest

pytestmark = pytest.mark.codegen

from api_craft.prepare import prepare_api
from .conftest import load_input


class TestPrepareApi:
    """Verify prepare_api produces correct template-facing data."""

    @pytest.fixture(
        params=["items_api.yaml", "shop_api.yaml", "products_api_filters.yaml"]
    )
    def api_input(self, request):
        return load_input(request.param)

    def test_name_variants_are_consistent(self, api_input):
        prepared = prepare_api(api_input)
        assert prepared.snake_name == prepared.camel_name[0].lower() + "".join(
            "_" + c.lower() if c.isupper() else c for c in prepared.camel_name[1:]
        )
        assert "-" not in prepared.snake_name
        assert "_" not in prepared.kebab_name

    def test_models_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        assert len(prepared.models) > 0

    def test_views_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        assert len(prepared.views) > 0

    def test_view_methods_lowercase(self, api_input):
        prepared = prepare_api(api_input)
        for view in prepared.views:
            assert view.method == view.method.lower()

    def test_view_names_non_empty(self, api_input):
        prepared = prepare_api(api_input)
        for view in prepared.views:
            assert view.snake_name
            assert view.camel_name


class TestPrepareApiShop:
    """Shop API specific tests for split schema mode."""

    def test_split_produces_six_models(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.models) == 6  # 2 objects × 3 schemas

    def test_split_model_names(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        names = [str(m.name) for m in prepared.models]
        assert "ProductCreate" in names
        assert "ProductUpdate" in names
        assert "ProductResponse" in names
        assert "CustomerCreate" in names

    def test_nine_views(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.views) == 9

    def test_database_config_present(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert prepared.database_config is not None
        assert prepared.database_config.enabled is True

    def test_orm_models_present(self):
        api_input = load_input("shop_api.yaml")
        prepared = prepare_api(api_input)
        assert len(prepared.orm_models) > 0
