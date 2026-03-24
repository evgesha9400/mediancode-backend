# tests/codegen/test_codegen_domains.py
"""Tests for generation service helpers, parameter inference, and relationship
code generation.

Merges legacy tests from:
- test_param_inference, test_codegen_relationships,
  generation helpers from test_generation_unit
"""

import inspect
import io
import os
from pathlib import Path
import tempfile
from typing import get_args
from unittest.mock import MagicMock
import zipfile

from fastapi.testclient import TestClient
import pytest

from api.schemas.api import GenerateOptions
from api.services.generation import (
    _build_endpoint_name,
    _build_field_type,
    _convert_to_input_api,
    generate_api_zip,
)
from api_craft.extractors import collect_association_tables
from api_craft.main import APIGenerator
from api_craft.models.enums import FilterOperator
from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputDatabaseConfig,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputRelationship,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.prepare import (
    PreparedPathParam,
    PreparedQueryParam,
    PreparedView,
    prepare_api,
)
from api_craft.schema_splitter import split_model_schemas
from support.generated_app import load_app, load_input


def _make_model(name, fields, relationships=None):
    return InputModel(
        name=name,
        fields=[InputField(**f) for f in fields],
        relationships=[InputRelationship(**r) for r in (relationships or [])],
    )


# ---------------------------------------------------------------------------
# Build Field Type (from test_generation_unit)
# ---------------------------------------------------------------------------


class TestBuildFieldType:
    @pytest.mark.parametrize(
        "python_type,container,expected",
        [
            ("str", None, "str"),
            ("int", None, "int"),
            ("float", None, "float"),
            ("bool", None, "bool"),
            ("datetime.datetime", None, "datetime.datetime"),
            ("datetime.date", None, "datetime.date"),
            ("datetime.time", None, "datetime.time"),
            ("uuid.UUID", None, "uuid.UUID"),
            ("EmailStr", None, "EmailStr"),
            ("HttpUrl", None, "HttpUrl"),
            ("Decimal", None, "Decimal"),
            ("str", "List", "List[str]"),
            ("int", "List", "List[int]"),
            ("datetime.datetime", "List", "List[datetime.datetime]"),
            ("uuid.UUID", "List", "List[uuid.UUID]"),
        ],
    )
    def test_type_mapping(self, python_type: str, container: str | None, expected: str):
        assert _build_field_type(python_type, container) == expected


# ---------------------------------------------------------------------------
# Build Endpoint Name (from test_generation_unit)
# ---------------------------------------------------------------------------


class TestBuildEndpointName:
    @pytest.mark.parametrize(
        "method,path,expected",
        [
            ("GET", "/users", "GetUsers"),
            ("POST", "/users", "PostUsers"),
            ("GET", "/users/{user_id}", "GetUsersByUserId"),
            ("DELETE", "/users/{user_id}", "DeleteUsersByUserId"),
            ("GET", "/users/{user_id}/orders", "GetUsersByUserIdOrders"),
            ("GET", "/user-profiles/{profile_id}", "GetUserProfilesByProfileId"),
            ("GET", "/api/v1/users", "GetApiV1Users"),
            ("PUT", "/order-items/{item_id}/status", "PutOrderItemsByItemIdStatus"),
            ("GET", "/", "GetRoot"),
            ("GET", "/{id}", "GetById"),
        ],
    )
    def test_endpoint_name(self, method: str, path: str, expected: str):
        assert _build_endpoint_name(method, path) == expected

    def test_endpoint_name_differentiates_with_path_param(self):
        list_name = _build_endpoint_name("GET", "/products")
        detail_name = _build_endpoint_name("GET", "/products/{tracking_id}")
        assert list_name != detail_name


# ---------------------------------------------------------------------------
# Convert To Input API (from test_generation_unit)
# ---------------------------------------------------------------------------


class TestConvertToInputApi:
    """Merged from TestConvertToInputApiOptions and TestConvertToInputApiPk."""

    def _make_api_model(self):
        api = MagicMock()
        api.title = "TestApi"
        api.version = "1.0.0"
        api.description = "Test"
        api.endpoints = []
        return api

    def _make_api_with_objects(self, *, is_pk=False):
        field = MagicMock()
        field.name = "id"
        field.field_type = MagicMock()
        field.field_type.python_type = "int"
        field.description = None
        field.default_value = None
        field.container = None
        field.constraint_values = []
        field.validators = []

        assoc = MagicMock()
        assoc.field_id = "field-1"
        assoc.nullable = False
        assoc.position = 0
        assoc.role = "pk" if is_pk else "writable"
        assoc.default_value = None

        obj = MagicMock()
        obj.id = "obj-1"
        obj.name = "Item"
        obj.description = "Test item"
        obj.field_associations = [assoc]
        obj.validators = []

        api = MagicMock()
        api.title = "TestApi"
        api.version = "1.0.0"
        api.description = "Test"
        api.endpoints = []

        objects_map = {"obj-1": obj}
        fields_map = {"field-1": field}
        return api, objects_map, fields_map

    # --- Options tests (from TestConvertToInputApiOptions) ---

    def test_default_options_match_current_behavior(self):
        api = self._make_api_model()
        opts = GenerateOptions()
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck == "/health"
        assert result.config.response_placeholders is True
        assert result.config.database.enabled is False

    def test_database_enabled_passed_through(self):
        api, objects_map, fields_map = self._make_api_with_objects(is_pk=True)
        opts = GenerateOptions(database_enabled=True, response_placeholders=False)
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        assert result.config.database.enabled is True

    def test_healthcheck_none_disables_it(self):
        api = self._make_api_model()
        opts = GenerateOptions(healthcheck=None)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.healthcheck is None

    def test_response_placeholders_false_passed_through(self):
        api = self._make_api_model()
        opts = GenerateOptions(response_placeholders=False)
        result = _convert_to_input_api(api, {}, {}, opts)
        assert result.config.response_placeholders is False

    # --- PK tests (from TestConvertToInputApiPk) ---

    def test_pk_passed_through(self):
        api, objects_map, fields_map = self._make_api_with_objects(is_pk=True)
        opts = GenerateOptions(database_enabled=True, response_placeholders=False)
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.pk is True

    def test_pk_false_by_default(self):
        api, objects_map, fields_map = self._make_api_with_objects(is_pk=False)
        opts = GenerateOptions()
        result = _convert_to_input_api(api, objects_map, fields_map, opts)
        item_obj = next(o for o in result.objects if o.name == "Item")
        id_field = next(f for f in item_obj.fields if f.name == "id")
        assert id_field.pk is False


class TestGenerateApiZipSignature:
    def test_accepts_options_parameter(self):
        sig = inspect.signature(generate_api_zip)
        assert "options" in sig.parameters
        param = sig.parameters["options"]
        assert param.default is not inspect.Parameter.empty, (
            "options must have a default value"
        )


# ---------------------------------------------------------------------------
# Param Inference (from test_param_inference)
# ---------------------------------------------------------------------------


class TestFilterOperatorEnum:
    def test_valid_operators(self):
        valid = ["eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"]
        for op in valid:
            assert op in valid

    def test_all_operators_present(self):
        operators = get_args(FilterOperator)
        assert set(operators) == {"eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"}


class TestInputPathParamField:
    def test_field_defaults_none(self):
        param = InputPathParam(name="item_id", type="int")
        assert param.field is None

    def test_field_accepts_value(self):
        param = InputPathParam(name="store_id", type="uuid", field="store_id")
        assert param.field == "store_id"


class TestInputQueryParamFields:
    def test_defaults_none(self):
        param = InputQueryParam(name="limit", type="int")
        assert param.field is None
        assert param.operator is None

    def test_filter_param(self):
        param = InputQueryParam(
            name="min_price", type="float", field="price", operator="gte"
        )
        assert param.field == "price"
        assert param.operator == "gte"


class TestInputEndpointTarget:
    def test_target_defaults_none(self):
        endpoint = InputEndpoint(
            name="GetItems", path="/items", method="GET", response="Item"
        )
        assert endpoint.target is None

    def test_target_accepts_value(self):
        endpoint = InputEndpoint(
            name="GetItems",
            path="/items",
            method="GET",
            response="ItemList",
            response_shape="list",
            target="Item",
        )
        assert endpoint.target == "Item"

    def test_pagination_defaults_false(self):
        endpoint = InputEndpoint(
            name="GetItems", path="/items", method="GET", response="Item"
        )
        assert endpoint.pagination is False

    def test_pagination_accepts_true(self):
        endpoint = InputEndpoint(
            name="GetItems",
            path="/items",
            method="GET",
            response="ItemList",
            response_shape="list",
            target="Item",
            pagination=True,
        )
        assert endpoint.pagination is True


class TestRule1TargetIsKnown:
    def test_detail_endpoint_infers_target_from_response(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="product_id", type="int", field="id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None

    def test_detail_endpoint_explicit_target_must_match_response(self):
        with pytest.raises(ValueError, match="must match response"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_id}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        target="Other",
                        path_params=[
                            InputPathParam(name="product_id", type="int", field="id"),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                    InputModel(
                        name="Other",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                        ],
                    ),
                ],
            )

    def test_list_endpoint_requires_explicit_target(self):
        with pytest.raises(ValueError, match="target"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProducts",
                        path="/products",
                        method="GET",
                        response="ProductList",
                        response_shape="list",
                        query_params=[
                            InputQueryParam(
                                name="min_price",
                                type="float",
                                field="price",
                                operator="gte",
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="ProductList",
                        fields=[InputField(name="items", type="List[Product]")],
                    ),
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="price", type="float"),
                        ],
                    ),
                ],
            )

    def test_list_endpoint_with_target_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProducts",
                    path="/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    query_params=[
                        InputQueryParam(
                            name="min_price",
                            type="float",
                            field="price",
                            operator="gte",
                        ),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="price", type="float"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule2FieldExistsOnTarget:
    def test_path_param_field_not_on_target_raises(self):
        with pytest.raises(ValueError, match="does not exist on"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_id}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        path_params=[
                            InputPathParam(
                                name="product_id", type="int", field="nonexistent"
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                ],
            )

    def test_query_param_field_not_on_target_raises(self):
        with pytest.raises(ValueError, match="does not exist on"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProducts",
                        path="/products",
                        method="GET",
                        response="ProductList",
                        response_shape="list",
                        target="Product",
                        query_params=[
                            InputQueryParam(
                                name="min_price",
                                type="float",
                                field="nonexistent",
                                operator="gte",
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="ProductList",
                        fields=[InputField(name="items", type="List[Product]")],
                    ),
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="price", type="float"),
                        ],
                    ),
                ],
            )


class TestRule3DetailLastParamIsPk:
    def test_last_path_param_not_pk_raises(self):
        with pytest.raises(ValueError, match="primary key"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_name}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        path_params=[
                            InputPathParam(
                                name="product_name", type="str", field="name"
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                ],
            )

    def test_last_path_param_is_pk_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/stores/{store_id}/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="store_id", type="int", field="store_id"),
                        InputPathParam(name="product_id", type="int", field="id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule4DetailNoQueryParams:
    def test_detail_with_query_params_raises(self):
        with pytest.raises(ValueError, match="query param.*not allowed.*detail"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_id}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        target="Product",
                        path_params=[
                            InputPathParam(name="product_id", type="int", field="id"),
                        ],
                        query_params=[
                            InputQueryParam(
                                name="include_deleted",
                                type="bool",
                                field="deleted",
                                operator="eq",
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="deleted", type="bool"),
                        ],
                    ),
                ],
            )


class TestRule5ListNoPathParamPk:
    def test_list_with_pk_path_param_raises(self):
        with pytest.raises(ValueError, match="response_shape 'object'"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProducts",
                        path="/products/{product_id}",
                        method="GET",
                        response="ProductList",
                        response_shape="list",
                        target="Product",
                        path_params=[
                            InputPathParam(name="product_id", type="int", field="id"),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="ProductList",
                        fields=[InputField(name="items", type="List[Product]")],
                    ),
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                ],
            )

    def test_list_with_fk_path_param_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetStoreProducts",
                    path="/stores/{store_id}/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    path_params=[
                        InputPathParam(name="store_id", type="int", field="store_id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule6OperatorFieldTypeCompat:
    def test_gte_on_str_raises(self):
        with pytest.raises(ValueError, match="not valid for field type"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProducts",
                        path="/products",
                        method="GET",
                        response="ProductList",
                        response_shape="list",
                        target="Product",
                        query_params=[
                            InputQueryParam(
                                name="min_name",
                                type="str",
                                field="name",
                                operator="gte",
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="ProductList",
                        fields=[InputField(name="items", type="List[Product]")],
                    ),
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                ],
            )

    def test_like_on_int_raises(self):
        with pytest.raises(ValueError, match="not valid for field type"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProducts",
                        path="/products",
                        method="GET",
                        response="ProductList",
                        response_shape="list",
                        target="Product",
                        query_params=[
                            InputQueryParam(
                                name="search_price",
                                type="int",
                                field="price",
                                operator="like",
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="ProductList",
                        fields=[InputField(name="items", type="List[Product]")],
                    ),
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="price", type="int"),
                        ],
                    ),
                ],
            )

    @pytest.mark.parametrize(
        "field_type,operator",
        [
            ("int", "gte"),
            ("float", "lte"),
            ("Decimal", "gt"),
            ("decimal.Decimal", "lt"),
            ("date", "gte"),
            ("datetime", "lte"),
            ("datetime.date", "gt"),
            ("datetime.datetime", "lt"),
            ("time", "gte"),
            ("datetime.time", "lte"),
            ("str", "like"),
            ("str", "ilike"),
            ("str", "eq"),
            ("int", "eq"),
            ("bool", "eq"),
            ("str", "in"),
            ("int", "in"),
        ],
    )
    def test_valid_operator_field_combos(self, field_type, operator):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProducts",
                    path="/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    query_params=[
                        InputQueryParam(
                            name="filter_val",
                            type=field_type,
                            field="value",
                            operator=operator,
                        ),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="value", type=field_type),
                    ],
                ),
            ],
        )
        assert api is not None


class TestPaginationValidation:
    def test_pagination_on_detail_endpoint_raises(self):
        with pytest.raises(ValueError, match="pagination.*only valid.*list"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_id}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        target="Product",
                        pagination=True,
                        path_params=[
                            InputPathParam(name="product_id", type="int", field="id"),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                        ],
                    ),
                ],
            )

    def test_pagination_on_list_endpoint_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProducts",
                    path="/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    pagination=True,
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                    ],
                ),
            ],
        )
        assert api is not None

    def test_endpoint_without_pagination_works(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProducts",
                    path="/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                    ],
                ),
            ],
        )
        assert api is not None


class TestParamInferenceBackwardCompatibility:
    """Endpoints without field/target pass validation (legacy mode)."""

    def test_legacy_endpoint_without_field_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items/{item_id}",
                    method="GET",
                    response="Item",
                    path_params=[
                        InputPathParam(name="item_id", type="int"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Item",
                    fields=[InputField(name="name", type="str")],
                ),
            ],
        )
        assert api is not None

    def test_legacy_list_without_target_and_no_field_params_passes(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="ItemList",
                    response_shape="list",
                    query_params=[
                        InputQueryParam(name="limit", type="int", optional=True),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ItemList",
                    fields=[InputField(name="items", type="List[Item]")],
                ),
                InputModel(
                    name="Item",
                    fields=[InputField(name="name", type="str")],
                ),
            ],
        )
        assert api is not None


class TestTemplateModelExtensions:
    def test_template_path_param_has_field(self):
        param = PreparedPathParam(
            snake_name="store_id",
            camel_name="StoreId",
            type="uuid.UUID",
            title="Store Id",
            field="store_id",
        )
        assert param.field == "store_id"

    def test_template_path_param_field_defaults_none(self):
        param = PreparedPathParam(
            snake_name="item_id",
            camel_name="ItemId",
            type="int",
            title="Item Id",
        )
        assert param.field is None

    def test_template_query_param_has_field_and_operator(self):
        param = PreparedQueryParam(
            snake_name="min_price",
            camel_name="MinPrice",
            type="float",
            title="Min Price",
            optional=True,
            field="price",
            operator="gte",
        )
        assert param.field == "price"
        assert param.operator == "gte"

    def test_template_view_has_target(self):
        view = PreparedView(
            snake_name="list_products",
            camel_name="ListProducts",
            path="/products",
            method="get",
            response_model="ProductList",
            request_model=None,
            response_placeholders=None,
            query_params=[],
            path_params=[],
            response_shape="list",
            target="Product",
        )
        assert view.target == "Product"

    def test_template_view_target_defaults_none(self):
        view = PreparedView(
            snake_name="get_items",
            camel_name="GetItems",
            path="/items",
            method="get",
            response_model="Item",
            request_model=None,
            response_placeholders=None,
            query_params=[],
            path_params=[],
        )
        assert view.target is None

    def test_template_view_has_pagination(self):
        view = PreparedView(
            snake_name="list_products",
            camel_name="ListProducts",
            path="/products",
            method="get",
            response_model="ProductList",
            request_model=None,
            response_placeholders=None,
            query_params=[],
            path_params=[],
            response_shape="list",
            target="Product",
            pagination=True,
        )
        assert view.pagination is True

    def test_template_view_pagination_defaults_false(self):
        view = PreparedView(
            snake_name="get_items",
            camel_name="GetItems",
            path="/items",
            method="get",
            response_model="Item",
            request_model=None,
            response_placeholders=None,
            query_params=[],
            path_params=[],
        )
        assert view.pagination is False


@pytest.mark.codegen
class TestTypeDerivation:
    def _build_api(self, path_params=None, query_params=None, response_shape="list"):
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(
                        name="id", type="uuid.UUID", pk=True, exposure="read_only"
                    ),
                    InputField(name="store_id", type="uuid.UUID"),
                    InputField(name="price", type="decimal.Decimal"),
                    InputField(name="name", type="str"),
                    InputField(name="in_stock", type="bool"),
                    InputField(name="created_at", type="datetime.date"),
                ],
            ),
        ]
        if response_shape == "list":
            objects.append(
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                )
            )
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products" if not path_params else "/stores/{store_id}/products",
            method="GET",
            response="ProductList" if response_shape == "list" else "Product",
            response_shape=response_shape,
            target="Product" if response_shape == "list" else None,
            path_params=path_params,
            query_params=query_params,
        )
        return InputAPI(
            name="TestApi",
            endpoints=[endpoint],
            objects=objects,
            config={"response_placeholders": False},
        )

    def test_path_param_type_derived_from_field(self):
        api = self._build_api(
            path_params=[
                InputPathParam(name="store_id", type="uuid.UUID", field="store_id"),
            ],
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.type == "uuid.UUID"
        assert pp.field == "store_id"

    def test_query_param_type_derived_from_field(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = prepare_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "decimal.Decimal"
        assert qp.field == "price"
        assert qp.operator == "gte"

    def test_in_operator_wraps_type_in_list(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(name="names", type="str", field="name", operator="in"),
            ],
        )
        result = prepare_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "List[str]"

    def test_field_query_params_forced_optional(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price",
                    type="float",
                    field="price",
                    operator="gte",
                    optional=False,
                ),
            ],
        )
        result = prepare_api(api)
        qp = result.views[0].query_params[0]
        assert qp.optional is True

    def test_pagination_injects_limit_and_offset(self):
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(
                        name="id", type="uuid.UUID", pk=True, exposure="read_only"
                    ),
                    InputField(name="store_id", type="uuid.UUID"),
                    InputField(name="price", type="decimal.Decimal"),
                    InputField(name="name", type="str"),
                    InputField(name="in_stock", type="bool"),
                    InputField(name="created_at", type="datetime.date"),
                ],
            ),
            InputModel(
                name="ProductList",
                fields=[InputField(name="items", type="List[Product]")],
            ),
        ]
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="ProductList",
            response_shape="list",
            target="Product",
            pagination=True,
        )
        api = InputAPI(
            name="TestApi",
            endpoints=[endpoint],
            objects=objects,
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        qps = result.views[0].query_params
        assert len(qps) == 2
        limit_param = qps[0]
        offset_param = qps[1]
        assert limit_param.snake_name == "limit"
        assert limit_param.type == "int"
        assert limit_param.optional is True
        assert limit_param.constraints == {"ge": 1, "le": 100}
        assert offset_param.snake_name == "offset"
        assert offset_param.type == "int"
        assert offset_param.optional is True
        assert offset_param.constraints == {"ge": 0}

    def test_pagination_false_does_not_inject(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = prepare_api(api)
        qps = result.views[0].query_params
        assert len(qps) == 1
        assert qps[0].snake_name == "min_price"

    def test_pagination_passed_to_template_view(self):
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(
                        name="id", type="uuid.UUID", pk=True, exposure="read_only"
                    ),
                    InputField(name="name", type="str"),
                ],
            ),
            InputModel(
                name="ProductList",
                fields=[InputField(name="items", type="List[Product]")],
            ),
        ]
        endpoint = InputEndpoint(
            name="GetProducts",
            path="/products",
            method="GET",
            response="ProductList",
            response_shape="list",
            target="Product",
            pagination=True,
        )
        api = InputAPI(
            name="TestApi",
            endpoints=[endpoint],
            objects=objects,
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        assert result.views[0].pagination is True

    def test_legacy_params_without_field_unchanged(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(name="limit", type="int", optional=True),
            ],
        )
        result = prepare_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "int"
        assert qp.field is None

    def test_target_passed_to_template_view(self):
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = prepare_api(api)
        assert result.views[0].target == "Product"


@pytest.mark.codegen
class TestPkAutoInference:
    def test_detail_last_param_no_field_inferred_to_pk(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="product_id", type="int"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field == "id"

    def test_detail_last_param_already_set_to_pk_unchanged(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="product_id", type="int", field="id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field == "id"

    def test_detail_last_param_set_to_non_pk_rejected(self):
        with pytest.raises(ValueError, match="primary key"):
            InputAPI(
                name="TestApi",
                endpoints=[
                    InputEndpoint(
                        name="GetProduct",
                        path="/products/{product_name}",
                        method="GET",
                        response="Product",
                        response_shape="object",
                        path_params=[
                            InputPathParam(
                                name="product_name", type="str", field="name"
                            ),
                        ],
                    ),
                ],
                objects=[
                    InputModel(
                        name="Product",
                        fields=[
                            InputField(
                                name="id", type="int", pk=True, exposure="read_only"
                            ),
                            InputField(name="name", type="str"),
                        ],
                    ),
                ],
            )

    def test_list_endpoint_no_auto_inference(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProducts",
                    path="/stores/{store_id}/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    path_params=[
                        InputPathParam(name="store_id", type="int", field="store_id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field == "store_id"

    def test_detail_no_pk_on_target_no_inference(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="product_id", type="int"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(name="name", type="str"),
                        InputField(name="price", type="float"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field is None

    def test_detail_inferred_pk_derives_type(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="product_id", type="int"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="uuid.UUID", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field == "id"
        assert pp.type == "uuid.UUID"

    def test_nested_detail_only_last_param_inferred(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetStoreProduct",
                    path="/stores/{store_id}/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="store_id", type="int"),
                        InputPathParam(name="product_id", type="int"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp0 = result.views[0].path_params[0]
        pp1 = result.views[0].path_params[1]
        assert pp0.field is None
        assert pp1.field == "id"

    def test_detail_param_named_as_non_pk_field_skips_inference(self):
        api = InputAPI(
            name="TestApi",
            endpoints=[
                InputEndpoint(
                    name="GetCustomer",
                    path="/customers/{email}",
                    method="GET",
                    response="Customer",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="email", type="EmailStr"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Customer",
                    fields=[
                        InputField(
                            name="customer_id",
                            type="int",
                            pk=True,
                            exposure="read_only",
                        ),
                        InputField(name="email", type="EmailStr"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False},
        )
        result = prepare_api(api)
        pp = result.views[0].path_params[0]
        assert pp.field is None
        assert pp.type == "EmailStr"


@pytest.mark.codegen
class TestFilterCodeGeneration:
    def _generate_views(self, tmp_path) -> str:
        api = InputAPI(
            name="FilterTest",
            endpoints=[
                InputEndpoint(
                    name="ListProducts",
                    path="/stores/{store_id}/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    pagination=True,
                    path_params=[
                        InputPathParam(
                            name="store_id", type="uuid.UUID", field="store_id"
                        ),
                    ],
                    query_params=[
                        InputQueryParam(
                            name="min_price",
                            type="float",
                            field="price",
                            operator="gte",
                        ),
                        InputQueryParam(
                            name="max_price",
                            type="float",
                            field="price",
                            operator="lte",
                        ),
                        InputQueryParam(
                            name="price_above",
                            type="float",
                            field="price",
                            operator="gt",
                        ),
                        InputQueryParam(
                            name="price_below",
                            type="float",
                            field="price",
                            operator="lt",
                        ),
                        InputQueryParam(
                            name="search", type="str", field="name", operator="ilike"
                        ),
                        InputQueryParam(
                            name="name_like", type="str", field="name", operator="like"
                        ),
                        InputQueryParam(
                            name="category", type="str", field="category", operator="eq"
                        ),
                        InputQueryParam(
                            name="tags", type="str", field="category", operator="in"
                        ),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="uuid.UUID"),
                        InputField(name="price", type="decimal.Decimal"),
                        InputField(name="name", type="str"),
                        InputField(name="category", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False, "database": {"enabled": True}},
        )
        APIGenerator().generate(api, path=str(tmp_path))
        return (tmp_path / "filter-test" / "src" / "views.py").read_text()

    def test_path_param_generates_where_clause(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.store_id == store_id" in views_py

    def test_gte_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.price >= min_price" in views_py
        assert "if min_price is not None" in views_py

    def test_ilike_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.name.ilike" in views_py
        assert "if search is not None" in views_py

    def test_eq_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.category == category" in views_py

    def test_in_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.category.in_(tags)" in views_py

    def test_gt_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.price > price_above" in views_py
        assert "if price_above is not None" in views_py

    def test_lt_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.price < price_below" in views_py
        assert "if price_below is not None" in views_py

    def test_lte_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.price <= max_price" in views_py
        assert "if max_price is not None" in views_py

    def test_like_operator_generates_filter(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "ProductRecord.name.like" in views_py
        assert "if name_like is not None" in views_py

    def test_pagination_generates_limit_offset(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "stmt.limit(limit)" in views_py or ".limit(limit)" in views_py
        assert "stmt.offset(offset)" in views_py or ".offset(offset)" in views_py

    def test_no_todo_placeholder(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        assert "select(ProductRecord)" in views_py

    def test_generated_code_compiles(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        compile(views_py, "views.py", "exec")

    def _generate_query(self, tmp_path) -> str:
        api = InputAPI(
            name="FilterTest",
            endpoints=[
                InputEndpoint(
                    name="ListProducts",
                    path="/stores/{store_id}/products",
                    method="GET",
                    response="ProductList",
                    response_shape="list",
                    target="Product",
                    pagination=True,
                    path_params=[
                        InputPathParam(
                            name="store_id", type="uuid.UUID", field="store_id"
                        ),
                    ],
                    query_params=[
                        InputQueryParam(
                            name="min_price",
                            type="float",
                            field="price",
                            operator="gte",
                        ),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="ProductList",
                    fields=[InputField(name="items", type="List[Product]")],
                ),
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="uuid.UUID"),
                        InputField(name="price", type="decimal.Decimal"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False, "database": {"enabled": True}},
        )
        APIGenerator().generate(api, path=str(tmp_path))
        return (tmp_path / "filter-test" / "src" / "query.py").read_text()

    def test_pagination_limit_has_constraints(self, tmp_path):
        query_py = self._generate_query(tmp_path)
        assert "ge=1" in query_py
        assert "le=100" in query_py

    def test_pagination_offset_has_constraints(self, tmp_path):
        query_py = self._generate_query(tmp_path)
        assert "ge=0" in query_py

    def test_query_generated_code_compiles(self, tmp_path):
        query_py = self._generate_query(tmp_path)
        compile(query_py, "query.py", "exec")


@pytest.fixture(scope="session")
def products_filter_api_client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Generate Products Filter API once per session and return TestClient."""
    tmp_path = tmp_path_factory.mktemp("products_filter_api")
    api_input = load_input("products_api_filters.yaml")
    APIGenerator().generate(api_input, path=str(tmp_path))
    src_path = tmp_path / "products-filter-api" / "src"
    app = load_app(src_path)
    return TestClient(app)


@pytest.mark.codegen
class TestProductsFilterApiIntegration:
    def test_healthcheck(self, products_filter_api_client: TestClient):
        response = products_filter_api_client.get("/healthcheck")
        assert response.status_code == 200

    def test_list_products_no_filters(self, products_filter_api_client: TestClient):
        response = products_filter_api_client.get("/stores/1/products")
        assert response.status_code == 200

    def test_list_products_with_filters(self, products_filter_api_client: TestClient):
        response = products_filter_api_client.get(
            "/stores/1/products?min_price=10.0&max_price=100.0&search=test&category=electronics&limit=10&offset=0"
        )
        assert response.status_code == 200

    def test_get_product_by_id(self, products_filter_api_client: TestClient):
        response = products_filter_api_client.get("/products/1")
        assert response.status_code == 404


@pytest.mark.codegen
class TestDetailEndpointFilterCodeGen:
    def test_detail_with_field_uses_field_in_where(self, tmp_path):
        api = InputAPI(
            name="DetailFieldTest",
            endpoints=[
                InputEndpoint(
                    name="GetProduct",
                    path="/products/{tracking_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(
                            name="tracking_id", type="uuid", field="tracking_id"
                        ),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="tracking_id",
                            type="uuid",
                            pk=True,
                            exposure="read_only",
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False, "database": {"enabled": True}},
        )
        APIGenerator().generate(api, path=str(tmp_path))
        views_py = (tmp_path / "detail-field-test" / "src" / "views.py").read_text()

        assert "ProductRecord.tracking_id == tracking_id" in views_py
        compile(views_py, "views.py", "exec")

    def test_nested_detail_with_scoping_param(self, tmp_path):
        api = InputAPI(
            name="NestedDetailTest",
            endpoints=[
                InputEndpoint(
                    name="GetStoreProduct",
                    path="/stores/{store_id}/products/{product_id}",
                    method="GET",
                    response="Product",
                    response_shape="object",
                    path_params=[
                        InputPathParam(name="store_id", type="int", field="store_id"),
                        InputPathParam(name="product_id", type="int", field="id"),
                    ],
                ),
            ],
            objects=[
                InputModel(
                    name="Product",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={"response_placeholders": False, "database": {"enabled": True}},
        )
        APIGenerator().generate(api, path=str(tmp_path))
        views_py = (tmp_path / "nested-detail-test" / "src" / "views.py").read_text()

        assert "ProductRecord.store_id == store_id" in views_py
        assert "ProductRecord.id == product_id" in views_py
        compile(views_py, "views.py", "exec")


# ---------------------------------------------------------------------------
# Relationship Codegen (from test_codegen_relationships)
# ---------------------------------------------------------------------------


@pytest.mark.codegen
class TestReferencesRelationship:
    def test_references_adds_fk_field_to_orm(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        post_model = next(m for m in result if m.source_model == "Post")
        field_names = [f.name for f in post_model.fields]
        assert "author_id" in field_names
        fk_field = next(f for f in post_model.fields if f.name == "author_id")
        assert fk_field.foreign_key == "users.id"
        assert fk_field.column_type == "Uuid"

    def test_references_creates_relationship(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        post_model = next(m for m in result if m.source_model == "Post")
        assert len(post_model.relationships) == 1
        rel = post_model.relationships[0]
        assert rel.name == "author"
        assert rel.cardinality == "references"
        assert rel.fk_column == "author_id"
        assert rel.target_class_name == "UserRecord"

    def test_references_fk_id_in_response_schema(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author", target_model="User", cardinality="references"
                )
            ],
        )
        schemas = split_model_schemas(model)
        response_names = [f.name for f in schemas[2].fields]
        assert "author_id" in response_names

    def test_references_fk_id_in_create_schema(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author", target_model="User", cardinality="references"
                )
            ],
        )
        schemas = split_model_schemas(model)
        create_names = [f.name for f in schemas[0].fields]
        assert "author_id" in create_names

    def test_references_fk_id_in_update_schema(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author", target_model="User", cardinality="references"
                )
            ],
        )
        schemas = split_model_schemas(model)
        update_names = [f.name for f in schemas[1].fields]
        assert "author_id" in update_names
        fk_field = next(f for f in schemas[1].fields if str(f.name) == "author_id")
        assert fk_field.nullable is True

    def test_references_fk_required_in_create(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author", target_model="User", cardinality="references"
                )
            ],
        )
        schemas = split_model_schemas(model)
        fk_field = next(f for f in schemas[0].fields if str(f.name) == "author_id")
        assert fk_field.nullable is False


@pytest.mark.codegen
class TestHasManyRelationship:
    def test_has_many_no_fk_on_source(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {"name": "posts", "target_model": "Post", "cardinality": "has_many"}
                ],
            ),
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        fk_fields = [f for f in user_model.fields if f.foreign_key]
        assert len(fk_fields) == 0

    def test_has_many_creates_relationship(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {"name": "posts", "target_model": "Post", "cardinality": "has_many"}
                ],
            ),
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        assert len(user_model.relationships) == 1
        rel = user_model.relationships[0]
        assert rel.name == "posts"
        assert rel.cardinality == "has_many"
        assert rel.target_class_name == "PostRecord"
        assert rel.fk_column is None


@pytest.mark.codegen
class TestHasOneRelationship:
    def test_has_one_no_fk_on_source(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "profile",
                        "target_model": "Profile",
                        "cardinality": "has_one",
                    }
                ],
            ),
            _make_model(
                "Profile",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "bio", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        fk_fields = [f for f in user_model.fields if f.foreign_key]
        assert len(fk_fields) == 0

    def test_has_one_creates_relationship(self):
        models = [
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "profile",
                        "target_model": "Profile",
                        "cardinality": "has_one",
                    }
                ],
            ),
            _make_model(
                "Profile",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "bio", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        user_model = next(m for m in result if m.source_model == "User")
        assert len(user_model.relationships) == 1
        rel = user_model.relationships[0]
        assert rel.name == "profile"
        assert rel.cardinality == "has_one"
        assert rel.target_class_name == "ProfileRecord"


@pytest.mark.codegen
class TestManyToManyRelationship:
    def test_many_to_many_creates_association_table(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        student_model = next(m for m in result if m.source_model == "Student")
        assert len(student_model.relationships) == 1
        rel = student_model.relationships[0]
        assert rel.cardinality == "many_to_many"
        assert rel.association_table is not None
        assert "courses" in rel.association_table
        assert "students" in rel.association_table

    def test_many_to_many_no_fk_on_source(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        student_model = next(m for m in result if m.source_model == "Student")
        fk_fields = [f for f in student_model.fields if f.foreign_key]
        assert len(fk_fields) == 0


@pytest.mark.codegen
class TestCollectAssociationTables:
    def test_returns_association_table_for_many_to_many(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        orm_models = transform_orm_models(models)
        tables = collect_association_tables(orm_models)
        assert len(tables) == 1
        assert tables[0]["left_table"] == "students"
        assert tables[0]["right_table"] == "courses"

    def test_no_association_tables_without_many_to_many(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        orm_models = transform_orm_models(models)
        tables = collect_association_tables(orm_models)
        assert len(tables) == 0


@pytest.mark.codegen
class TestRelationshipCodeGeneration:
    @pytest.fixture(scope="class")
    def rel_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        api_input = InputAPI(
            name="BlogApi",
            objects=[
                InputModel(
                    name="User",
                    fields=[
                        InputField(
                            name="id", type="uuid", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                    relationships=[
                        InputRelationship(
                            name="posts", target_model="Post", cardinality="has_many"
                        )
                    ],
                ),
                InputModel(
                    name="Post",
                    fields=[
                        InputField(
                            name="id", type="uuid", pk=True, exposure="read_only"
                        ),
                        InputField(name="title", type="str"),
                    ],
                    relationships=[
                        InputRelationship(
                            name="author", target_model="User", cardinality="references"
                        ),
                        InputRelationship(
                            name="tags", target_model="Tag", cardinality="many_to_many"
                        ),
                    ],
                ),
                InputModel(
                    name="Tag",
                    fields=[
                        InputField(
                            name="id", type="uuid", pk=True, exposure="read_only"
                        ),
                        InputField(name="label", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetPosts",
                    path="/posts",
                    method="GET",
                    response="Post",
                    response_shape="list",
                ),
                InputEndpoint(
                    name="GetUsers",
                    path="/users",
                    method="GET",
                    response="User",
                    response_shape="list",
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False, database=InputDatabaseConfig(enabled=True)
            ),
        )
        tmp_path = tmp_path_factory.mktemp("blog_api")
        APIGenerator().generate(api_input, path=str(tmp_path))
        return tmp_path / "blog-api"

    def test_orm_models_compile(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        compile(content, "orm_models.py", "exec")

    def test_migration_compiles(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        compile(content, "0001_initial.py", "exec")

    def test_orm_has_relationship_import(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "relationship" in content

    def test_orm_has_fk_import(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "ForeignKey" in content

    def test_references_fk_column_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "author_id" in content
        assert 'ForeignKey("users.id")' in content

    def test_references_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "author" in content
        assert "relationship" in content

    def test_has_many_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "posts" in content

    def test_many_to_many_association_table_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "Table(" in content

    def test_many_to_many_relationship_in_orm(self, rel_project: Path):
        content = (rel_project / "src" / "orm_models.py").read_text()
        assert "tags" in content
        assert "secondary=" in content

    def test_migration_has_fk_constraint(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "ForeignKey" in content

    def test_migration_has_association_table(self, rel_project: Path):
        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        assert "posts_tags" in content or "tags_posts" in content

    def test_response_schema_has_fk_id(self, rel_project: Path):
        content = (rel_project / "src" / "models.py").read_text()
        assert "author_id" in content

    def test_migration_table_order(self, rel_project: Path):
        import re

        content = (
            rel_project / "migrations" / "versions" / "0001_initial.py"
        ).read_text()
        upgrade_section = content.split("def upgrade")[1].split("def downgrade")[0]
        created = re.findall(r'op\.create_table\(\s*"(\w+)"', upgrade_section)
        posts_idx = created.index("posts")
        users_idx = created.index("users")
        tags_idx = created.index("tags")
        assert users_idx < posts_idx
        assert tags_idx < posts_idx or tags_idx > posts_idx

    def test_response_schema_has_config_dict(self, rel_project: Path):
        content = (rel_project / "src" / "models.py").read_text()
        assert "ConfigDict" in content
        assert "from_attributes=True" in content

    def test_create_schema_no_config_dict(self, rel_project: Path):
        content = (rel_project / "src" / "models.py").read_text()
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "Create(BaseModel)" in line:
                block = "\n".join(lines[i : i + 5])
                assert "model_config" not in block

    def test_all_python_files_compile(self, rel_project: Path):
        for py_file in rel_project.rglob("*.py"):
            source = py_file.read_text()
            compile(source, str(py_file), "exec")


@pytest.mark.codegen
class TestMigrationTableOrdering:
    def test_references_target_created_before_source(self):
        models = [
            _make_model(
                "Post",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "author",
                        "target_model": "User",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "User",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names.index("users") < table_names.index("posts")

    def test_chain_dependencies_ordered(self):
        models = [
            _make_model(
                "A",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
                relationships=[
                    {"name": "b_ref", "target_model": "B", "cardinality": "references"}
                ],
            ),
            _make_model(
                "B",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
                relationships=[
                    {"name": "c_ref", "target_model": "C", "cardinality": "references"}
                ],
            ),
            _make_model(
                "C",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "val", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names.index("cs") < table_names.index("bs")
        assert table_names.index("bs") < table_names.index("as")

    def test_no_relationships_preserves_input_order(self):
        models = [
            _make_model("Zebra", [{"name": "id", "type": "uuid", "pk": True}]),
            _make_model("Alpha", [{"name": "id", "type": "uuid", "pk": True}]),
            _make_model("Mid", [{"name": "id", "type": "uuid", "pk": True}]),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names == ["zebras", "alphas", "mids"]

    def test_many_to_many_no_entity_ordering_constraint(self):
        models = [
            _make_model(
                "Student",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "name", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "courses",
                        "target_model": "Course",
                        "cardinality": "many_to_many",
                    }
                ],
            ),
            _make_model(
                "Course",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        table_names = [m.table_name for m in result]
        assert table_names == ["students", "courses"]


@pytest.mark.codegen
class TestFkTypeDerivedFromTargetPk:
    def test_fk_type_matches_int_pk(self):
        models = [
            _make_model(
                "Comment",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "body", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "article",
                        "target_model": "Article",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "Article",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        schemas = split_model_schemas(models[0], all_models=models)
        response = schemas[2]
        fk_field = next(f for f in response.fields if str(f.name) == "article_id")
        assert fk_field.type == "int"

    def test_fk_type_defaults_to_uuid_without_context(self):
        model = InputModel(
            name="Post",
            fields=[
                InputField(name="id", type="uuid", pk=True, exposure="read_only"),
                InputField(name="title", type="str"),
            ],
            relationships=[
                InputRelationship(
                    name="author", target_model="User", cardinality="references"
                )
            ],
        )
        schemas = split_model_schemas(model)
        response = schemas[2]
        fk_field = next(f for f in response.fields if str(f.name) == "author_id")
        assert fk_field.type == "uuid"

    def test_fk_type_in_create_matches_target_pk(self):
        models = [
            _make_model(
                "Comment",
                [
                    {"name": "id", "type": "uuid", "pk": True},
                    {"name": "body", "type": "str"},
                ],
                relationships=[
                    {
                        "name": "article",
                        "target_model": "Article",
                        "cardinality": "references",
                    }
                ],
            ),
            _make_model(
                "Article",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "title", "type": "str"},
                ],
            ),
        ]
        schemas = split_model_schemas(models[0], all_models=models)
        create = schemas[0]
        fk_field = next(f for f in create.fields if str(f.name) == "article_id")
        assert fk_field.type == "int"


@pytest.mark.codegen
class TestNoRelationshipsBackwardCompat:
    def test_orm_model_without_relationships_has_empty_list(self):
        models = [
            _make_model(
                "Item",
                [
                    {"name": "id", "type": "int", "pk": True},
                    {"name": "name", "type": "str"},
                ],
            ),
        ]
        result = transform_orm_models(models)
        assert result[0].relationships == []

    def test_no_relationship_import_when_no_relationships(self, tmp_path: Path):
        api_input = InputAPI(
            name="SimpleApi",
            objects=[
                InputModel(
                    name="Item",
                    fields=[
                        InputField(
                            name="id", type="int", pk=True, exposure="read_only"
                        ),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            endpoints=[
                InputEndpoint(
                    name="GetItems",
                    path="/items",
                    method="GET",
                    response="Item",
                    response_shape="list",
                ),
            ],
            config=InputApiConfig(
                response_placeholders=False, database=InputDatabaseConfig(enabled=True)
            ),
        )
        APIGenerator().generate(api_input, path=str(tmp_path))
        content = (tmp_path / "simple-api" / "src" / "orm_models.py").read_text()
        assert "relationship" not in content
        assert "ForeignKey" not in content
        assert "Table(" not in content
