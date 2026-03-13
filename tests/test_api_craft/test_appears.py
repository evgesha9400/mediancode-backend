# tests/test_api_craft/test_appears.py
"""Tests for the `appears` flag in schema derivation."""

import pytest

from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputEndpoint,
    InputField,
    InputModel,
)
from api_craft.schema_splitter import split_model_schemas
from api_craft.transformers import transform_api


def _make_field(name: str, type_: str = "str", **kwargs) -> InputField:
    """Helper to create a minimal InputField."""
    return InputField(name=name, type=type_, **kwargs)


class TestSplitModelSchemas:
    """Tests for split_model_schemas()."""

    def test_basic_split_produces_three_schemas(self):
        model = InputModel(
            name="User",
            fields=[
                _make_field("email"),
                _make_field("password", appears="request"),
                _make_field("created_at", type_="datetime", appears="response"),
                _make_field("id", type_="int", pk=True),
            ],
        )
        schemas = split_model_schemas(model)
        assert len(schemas) == 3
        assert schemas[0].name == "UserCreate"
        assert schemas[1].name == "UserUpdate"
        assert schemas[2].name == "UserResponse"

    def test_pk_excluded_from_create_and_update(self):
        model = InputModel(
            name="Item",
            fields=[
                _make_field("id", type_="int", pk=True),
                _make_field("name"),
            ],
        )
        schemas = split_model_schemas(model)
        create_names = [f.name for f in schemas[0].fields]
        update_names = [f.name for f in schemas[1].fields]
        response_names = [f.name for f in schemas[2].fields]

        assert "id" not in create_names
        assert "id" not in update_names
        assert "id" in response_names

    def test_request_only_field_excluded_from_response(self):
        model = InputModel(
            name="Account",
            fields=[
                _make_field("username"),
                _make_field("password", appears="request"),
            ],
        )
        schemas = split_model_schemas(model)
        response_names = [f.name for f in schemas[2].fields]
        create_names = [f.name for f in schemas[0].fields]

        assert "password" in create_names
        assert "password" not in response_names

    def test_response_only_field_excluded_from_create(self):
        model = InputModel(
            name="Post",
            fields=[
                _make_field("title"),
                _make_field("created_at", type_="datetime", appears="response"),
            ],
        )
        schemas = split_model_schemas(model)
        create_names = [f.name for f in schemas[0].fields]
        response_names = [f.name for f in schemas[2].fields]

        assert "created_at" not in create_names
        assert "created_at" in response_names

    def test_update_fields_are_all_optional(self):
        model = InputModel(
            name="Product",
            fields=[
                _make_field("name"),  # required
                _make_field("price", type_="float"),  # required
            ],
        )
        schemas = split_model_schemas(model)
        update_schema = schemas[1]
        for field in update_schema.fields:
            assert (
                field.optional is True
            ), f"Update field '{field.name}' should be optional"

    def test_both_appears_in_all_schemas(self):
        model = InputModel(
            name="Tag",
            fields=[
                _make_field("label", appears="both"),
            ],
        )
        schemas = split_model_schemas(model)
        assert len(schemas[0].fields) == 1  # Create
        assert len(schemas[1].fields) == 1  # Update
        assert len(schemas[2].fields) == 1  # Response


class TestTransformApiWithAppears:
    """Tests for transform_api() with appears flags triggering split mode."""

    def _make_api(self, objects, endpoints):
        return InputAPI(
            name="TestApi",
            objects=objects,
            endpoints=endpoints,
        )

    def test_split_mode_activates_when_pk_present(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Widget",
                    fields=[
                        _make_field("id", type_="int", pk=True),
                        _make_field("name"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetWidgets",
                    path="/widgets",
                    method="GET",
                    response="Widget",
                )
            ],
        )
        template = transform_api(api)
        model_names = [m.name for m in template.models]
        assert "WidgetCreate" in model_names
        assert "WidgetUpdate" in model_names
        assert "WidgetResponse" in model_names
        assert "Widget" not in model_names

    def test_response_model_remapped_to_response_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        _make_field("id", type_="int", pk=True),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="Item",
                )
            ],
        )
        template = transform_api(api)
        view = template.views[0]
        assert view.response_model == "ItemResponse"

    def test_post_request_uses_create_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="CreateTask",
                    path="/tasks",
                    method="POST",
                    request="Task",
                    response="Task",
                )
            ],
        )
        template = transform_api(api)
        view = template.views[0]
        assert view.request_model == "TaskCreate"
        assert view.response_model == "TaskResponse"

    def test_put_request_uses_update_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="UpdateTask",
                    path="/tasks/{id}",
                    method="PUT",
                    request="Task",
                    response="Task",
                    path_params=[{"name": "id", "type": "int"}],
                )
            ],
        )
        template = transform_api(api)
        view = template.views[0]
        assert view.request_model == "TaskUpdate"

    def test_patch_request_uses_update_schema(self):
        api = self._make_api(
            objects=[
                InputModel(
                    name="Task",
                    fields=[
                        _make_field("id", type_="int", pk=True),
                        _make_field("title"),
                    ],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="PatchTask",
                    path="/tasks/{id}",
                    method="PATCH",
                    request="Task",
                    response="Task",
                    path_params=[{"name": "id", "type": "int"}],
                )
            ],
        )
        template = transform_api(api)
        view = template.views[0]
        assert view.request_model == "TaskUpdate"

    def test_no_split_when_no_appears_or_pk(self):
        """When no field has appears != 'both' and no pk, use single model."""
        api = self._make_api(
            objects=[
                InputModel(
                    name="Simple",
                    fields=[_make_field("name")],
                )
            ],
            endpoints=[
                InputEndpoint(
                    name="GetSimple",
                    path="/simple",
                    method="GET",
                    response="Simple",
                )
            ],
        )
        template = transform_api(api)
        model_names = [m.name for m in template.models]
        assert "Simple" in model_names
        assert "SimpleCreate" not in model_names
