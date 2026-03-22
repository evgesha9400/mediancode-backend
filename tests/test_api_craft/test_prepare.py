# tests/test_api_craft/test_prepare.py
"""Tests verifying prepare_api produces equivalent output to transform_api."""

import pytest

pytestmark = pytest.mark.codegen

from api_craft.prepare import prepare_api
from api_craft.transformers import transform_api
from .conftest import load_input


class TestPrepareApiEquivalence:
    """Verify prepare_api produces the same template-facing data as transform_api."""

    @pytest.fixture(
        params=["items_api.yaml", "shop_api.yaml", "products_api_filters.yaml"]
    )
    def api_input(self, request):
        return load_input(request.param)

    def test_name_variants(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert prepared.snake_name == template.snake_name
        assert prepared.camel_name == template.camel_name
        assert prepared.kebab_name == template.kebab_name
        assert prepared.spaced_name == template.spaced_name

    def test_metadata(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert prepared.version == template.version
        assert prepared.author == template.author
        assert prepared.description == template.description
        assert prepared.app_port == template.app_port

    def test_config(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert prepared.config.healthcheck == template.config.healthcheck
        assert (
            prepared.config.response_placeholders
            == template.config.response_placeholders
        )

    def test_model_count(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert len(prepared.models) == len(template.models)

    def test_model_names(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        prep_names = [str(m.name) for m in prepared.models]
        tmpl_names = [m.name for m in template.models]
        assert prep_names == tmpl_names

    def test_model_field_names(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_model, t_model in zip(prepared.models, template.models):
            p_names = [str(f.name) for f in p_model.fields]
            t_names = [f.name for f in t_model.fields]
            assert p_names == t_names, f"Field mismatch in {p_model.name}"

    def test_model_field_types(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_model, t_model in zip(prepared.models, template.models):
            p_types = [f.type for f in p_model.fields]
            t_types = [f.type for f in t_model.fields]
            assert p_types == t_types, f"Type mismatch in {p_model.name}"

    def test_model_field_optional(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_model, t_model in zip(prepared.models, template.models):
            p_opt = [f.optional for f in p_model.fields]
            t_opt = [f.optional for f in t_model.fields]
            assert p_opt == t_opt, f"Optional mismatch in {p_model.name}"

    def test_model_validator_count(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_model, t_model in zip(prepared.models, template.models):
            assert len(p_model.model_validators) == len(
                t_model.model_validators
            ), f"Validator count mismatch in {p_model.name}"

    def test_view_count(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert len(prepared.views) == len(template.views)

    def test_view_names(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        prep_names = [(v.snake_name, v.camel_name) for v in prepared.views]
        tmpl_names = [(v.snake_name, v.camel_name) for v in template.views]
        assert prep_names == tmpl_names

    def test_view_methods_and_paths(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_view, t_view in zip(prepared.views, template.views):
            assert p_view.method == t_view.method
            assert p_view.path == t_view.path

    def test_view_models(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_view, t_view in zip(prepared.views, template.views):
            assert (
                p_view.response_model == t_view.response_model
            ), f"response_model mismatch for {p_view.snake_name}"
            assert (
                p_view.request_model == t_view.request_model
            ), f"request_model mismatch for {p_view.snake_name}"

    def test_view_query_params(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_view, t_view in zip(prepared.views, template.views):
            p_qp = [
                (q.snake_name, q.camel_name, q.type, q.optional)
                for q in p_view.query_params
            ]
            t_qp = [
                (q.snake_name, q.camel_name, q.type, q.optional)
                for q in t_view.query_params
            ]
            assert p_qp == t_qp, f"Query param mismatch for {p_view.snake_name}"

    def test_view_path_params(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_view, t_view in zip(prepared.views, template.views):
            p_pp = [
                (p.snake_name, p.camel_name, p.type, p.field)
                for p in p_view.path_params
            ]
            t_pp = [
                (p.snake_name, p.camel_name, p.type, p.field)
                for p in t_view.path_params
            ]
            assert p_pp == t_pp, f"Path param mismatch for {p_view.snake_name}"

    def test_view_placeholders(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        for p_view, t_view in zip(prepared.views, template.views):
            assert (
                p_view.response_placeholders == t_view.response_placeholders
            ), f"Placeholder mismatch for {p_view.snake_name}"

    def test_tag_count(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert len(prepared.tags) == len(template.tags)

    def test_tag_names(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        p_names = [t.name for t in prepared.tags]
        t_names = [t.name for t in template.tags]
        assert p_names == t_names

    def test_orm_model_count(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        assert len(prepared.orm_models) == len(template.orm_models)

    def test_database_config(self, api_input):
        prepared = prepare_api(api_input)
        template = transform_api(api_input)
        if template.database_config is None:
            assert prepared.database_config is None
        else:
            assert prepared.database_config is not None
            assert prepared.database_config.enabled == template.database_config.enabled
            assert (
                prepared.database_config.default_url
                == template.database_config.default_url
            )
            assert prepared.database_config.db_port == template.database_config.db_port
