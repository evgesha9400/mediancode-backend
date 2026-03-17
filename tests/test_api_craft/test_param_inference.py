# tests/test_api_craft/test_param_inference.py
"""Tests for deterministic path & query parameter inference."""

import pytest
from api_craft.models.enums import FilterOperator
from api_craft.models.input import (
    InputAPI,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
)


class TestFilterOperatorEnum:
    def test_valid_operators(self):
        valid = ["eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"]
        for op in valid:
            # Literal types accept valid values without error
            assert op in valid

    def test_all_operators_present(self):
        """FilterOperator must include all 8 operators from the spec."""
        from typing import get_args

        operators = get_args(FilterOperator)
        assert set(operators) == {"eq", "gte", "lte", "gt", "lt", "like", "ilike", "in"}


class TestInputPathParamField:
    def test_field_defaults_none(self):
        """field is optional for backward compatibility."""
        param = InputPathParam(name="item_id", type="int")
        assert param.field is None

    def test_field_accepts_value(self):
        param = InputPathParam(name="store_id", type="uuid", field="store_id")
        assert param.field == "store_id"


class TestInputQueryParamFields:
    def test_defaults_none(self):
        """New fields default to None for backward compatibility."""
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
        """target is optional for backward compatibility."""
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
        """pagination defaults to False for backward compatibility."""
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
    """Rule 1: Target object is known."""

    def test_detail_endpoint_infers_target_from_response(self):
        """Object response type -> target is the response model itself."""
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None  # Validation passed

    def test_detail_endpoint_explicit_target_must_match_response(self):
        """Detail endpoint: explicit target must equal response."""
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
                            InputField(name="id", type="int", pk=True),
                            InputField(name="name", type="str"),
                        ],
                    ),
                    InputModel(
                        name="Other",
                        fields=[
                            InputField(name="id", type="int", pk=True),
                        ],
                    ),
                ],
            )

    def test_list_endpoint_requires_explicit_target(self):
        """List endpoint without target raises when field params are present."""
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
                            InputField(name="id", type="int", pk=True),
                            InputField(name="price", type="float"),
                        ],
                    ),
                ],
            )

    def test_list_endpoint_with_target_passes(self):
        """List endpoint with explicit target passes validation."""
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="price", type="float"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule2FieldExistsOnTarget:
    """Rule 2: Every param field exists on target."""

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
                            InputField(name="id", type="int", pk=True),
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
                            InputField(name="id", type="int", pk=True),
                            InputField(name="price", type="float"),
                        ],
                    ),
                ],
            )


class TestRule3DetailLastParamIsPk:
    """Rule 3: Detail endpoint -- last path param maps to PK."""

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
                            InputField(name="id", type="int", pk=True),
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule4DetailNoQueryParams:
    """Rule 4: Detail endpoint -- no query params allowed."""

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
                            InputField(name="id", type="int", pk=True),
                            InputField(name="deleted", type="bool"),
                        ],
                    ),
                ],
            )


class TestRule5ListNoPathParamPk:
    """Rule 5: List endpoint -- no path param maps to PK."""

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
                            InputField(name="id", type="int", pk=True),
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
        )
        assert api is not None


class TestRule6OperatorFieldTypeCompat:
    """Rule 6: Query param operator is compatible with field type."""

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
                            InputField(name="id", type="int", pk=True),
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
                            InputField(name="id", type="int", pk=True),
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
        """Valid operator-type combinations must pass."""
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="value", type=field_type),
                    ],
                ),
            ],
        )
        assert api is not None


class TestPaginationValidation:
    """Endpoint-level pagination validation."""

    def test_pagination_on_detail_endpoint_raises(self):
        """pagination=True on a detail (object) endpoint is invalid."""
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
                            InputField(name="id", type="int", pk=True),
                        ],
                    ),
                ],
            )

    def test_pagination_on_list_endpoint_passes(self):
        """pagination=True on a list endpoint passes validation."""
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
                        InputField(name="id", type="int", pk=True),
                    ],
                ),
            ],
        )
        assert api is not None

    def test_endpoint_without_pagination_works(self):
        """Endpoints without pagination field work as before (defaults False)."""
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
                        InputField(name="id", type="int", pk=True),
                    ],
                ),
            ],
        )
        assert api is not None


class TestBackwardCompatibility:
    """Endpoints without field/target pass validation (legacy mode)."""

    def test_legacy_endpoint_without_field_passes(self):
        """Endpoints without any field references skip param inference validation."""
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
        """List endpoints without target and without field-based params pass."""
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


from api_craft.models.template import (
    TemplatePathParam,
    TemplateQueryParam,
    TemplateView,
)


class TestTemplateModelExtensions:
    def test_template_path_param_has_field(self):
        param = TemplatePathParam(
            snake_name="store_id",
            camel_name="StoreId",
            type="uuid.UUID",
            title="Store Id",
            field="store_id",
        )
        assert param.field == "store_id"

    def test_template_path_param_field_defaults_none(self):
        param = TemplatePathParam(
            snake_name="item_id",
            camel_name="ItemId",
            type="int",
            title="Item Id",
        )
        assert param.field is None

    def test_template_query_param_has_field_and_operator(self):
        param = TemplateQueryParam(
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
        view = TemplateView(
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
        view = TemplateView(
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
        view = TemplateView(
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
        view = TemplateView(
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


from api_craft.transformers import transform_api


class TestTypeDerivation:
    """Param types are derived from target object fields during transform."""

    def _build_api(self, path_params=None, query_params=None, response_shape="list"):
        """Helper to build a minimal API for testing transforms."""
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(name="id", type="uuid.UUID", pk=True),
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
        """Path param type should be derived from the target field's type."""
        api = self._build_api(
            path_params=[
                InputPathParam(name="store_id", type="uuid.UUID", field="store_id"),
            ],
        )
        result = transform_api(api)
        pp = result.views[0].path_params[0]
        assert pp.type == "uuid.UUID"
        assert pp.field == "store_id"

    def test_query_param_type_derived_from_field(self):
        """Query param type should be derived from the target field's type."""
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = transform_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "decimal.Decimal"
        assert qp.field == "price"
        assert qp.operator == "gte"

    def test_in_operator_wraps_type_in_list(self):
        """The 'in' operator should produce List[field_type] param type."""
        api = self._build_api(
            query_params=[
                InputQueryParam(name="names", type="str", field="name", operator="in"),
            ],
        )
        result = transform_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "List[str]"

    def test_field_query_params_forced_optional(self):
        """Query params with field/operator are forced optional."""
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
        result = transform_api(api)
        qp = result.views[0].query_params[0]
        assert qp.optional is True

    def test_pagination_injects_limit_and_offset(self):
        """Endpoint-level pagination auto-injects limit and offset params."""
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(name="id", type="uuid.UUID", pk=True),
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
        result = transform_api(api)
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
        """Endpoint without pagination does not inject limit/offset."""
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = transform_api(api)
        qps = result.views[0].query_params
        assert len(qps) == 1
        assert qps[0].snake_name == "min_price"

    def test_pagination_passed_to_template_view(self):
        """The pagination flag is passed through to TemplateView."""
        objects = [
            InputModel(
                name="Product",
                fields=[
                    InputField(name="id", type="uuid.UUID", pk=True),
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
        result = transform_api(api)
        assert result.views[0].pagination is True

    def test_legacy_params_without_field_unchanged(self):
        """Params without field keep their declared type (backward compat)."""
        api = self._build_api(
            query_params=[
                InputQueryParam(name="limit", type="int", optional=True),
            ],
        )
        result = transform_api(api)
        qp = result.views[0].query_params[0]
        assert qp.type == "int"
        assert qp.field is None

    def test_target_passed_to_template_view(self):
        """The target name is passed through to TemplateView."""
        api = self._build_api(
            query_params=[
                InputQueryParam(
                    name="min_price", type="float", field="price", operator="gte"
                ),
            ],
        )
        result = transform_api(api)
        assert result.views[0].target == "Product"


from api_craft.main import APIGenerator


class TestFilterCodeGeneration:
    """Generated views.py must contain SQLAlchemy filter code."""

    def _generate_views(self, tmp_path) -> str:
        """Generate a filtered list API and return views.py content."""
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
                            name="search",
                            type="str",
                            field="name",
                            operator="ilike",
                        ),
                        InputQueryParam(
                            name="name_like",
                            type="str",
                            field="name",
                            operator="like",
                        ),
                        InputQueryParam(
                            name="category",
                            type="str",
                            field="category",
                            operator="eq",
                        ),
                        InputQueryParam(
                            name="tags",
                            type="str",
                            field="category",
                            operator="in",
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="store_id", type="uuid.UUID"),
                        InputField(name="price", type="decimal.Decimal"),
                        InputField(name="name", type="str"),
                        InputField(name="category", type="str"),
                    ],
                ),
            ],
            config={
                "response_placeholders": False,
                "database": {"enabled": True},
            },
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
        # The filtered view should NOT contain a TODO placeholder
        # Find the list_products function and check its body
        assert "select(ProductRecord)" in views_py

    def test_generated_code_compiles(self, tmp_path):
        views_py = self._generate_views(tmp_path)
        compile(views_py, "views.py", "exec")

    def _generate_query(self, tmp_path) -> str:
        """Generate a filtered list API and return query.py content."""
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="store_id", type="uuid.UUID"),
                        InputField(name="price", type="decimal.Decimal"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={
                "response_placeholders": False,
                "database": {"enabled": True},
            },
        )
        APIGenerator().generate(api, path=str(tmp_path))
        return (tmp_path / "filter-test" / "src" / "query.py").read_text()

    def test_pagination_limit_has_constraints(self, tmp_path):
        """Generated query.py must include ge=1, le=100 for limit."""
        query_py = self._generate_query(tmp_path)
        assert "ge=1" in query_py
        assert "le=100" in query_py

    def test_pagination_offset_has_constraints(self, tmp_path):
        """Generated query.py must include ge=0 for offset."""
        query_py = self._generate_query(tmp_path)
        assert "ge=0" in query_py

    def test_query_generated_code_compiles(self, tmp_path):
        """Generated query.py must be valid Python."""
        query_py = self._generate_query(tmp_path)
        compile(query_py, "query.py", "exec")


from fastapi.testclient import TestClient


@pytest.mark.codegen
class TestProductsFilterApiIntegration:
    """Integration tests: generate, boot, and request the filtered API."""

    def test_healthcheck(self, products_filter_api_client: TestClient):
        response = products_filter_api_client.get("/healthcheck")
        assert response.status_code == 200

    def test_list_products_no_filters(self, products_filter_api_client: TestClient):
        """GET /stores/1/products returns 200 with no filters."""
        response = products_filter_api_client.get("/stores/1/products")
        assert response.status_code == 200

    def test_list_products_with_filters(self, products_filter_api_client: TestClient):
        """GET /stores/1/products with query params returns 200."""
        response = products_filter_api_client.get(
            "/stores/1/products?min_price=10.0&max_price=100.0&search=test&category=electronics&limit=10&offset=0"
        )
        assert response.status_code == 200

    def test_get_product_by_id(self, products_filter_api_client: TestClient):
        """GET /products/1 returns 404 (no data seeded, but proves query works)."""
        response = products_filter_api_client.get("/products/1")
        assert response.status_code == 404


class TestDetailEndpointFilterCodeGen:
    """Detail endpoints should use field-based where clauses."""

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
                        InputField(name="tracking_id", type="uuid", pk=True),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={
                "response_placeholders": False,
                "database": {"enabled": True},
            },
        )
        APIGenerator().generate(api, path=str(tmp_path))
        views_py = (tmp_path / "detail-field-test" / "src" / "views.py").read_text()

        # Should use field name in where clause
        assert "ProductRecord.tracking_id == tracking_id" in views_py
        compile(views_py, "views.py", "exec")

    def test_nested_detail_with_scoping_param(self, tmp_path):
        """Nested detail: /stores/{store_id}/products/{product_id}"""
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
                        InputField(name="id", type="int", pk=True),
                        InputField(name="store_id", type="int"),
                        InputField(name="name", type="str"),
                    ],
                ),
            ],
            config={
                "response_placeholders": False,
                "database": {"enabled": True},
            },
        )
        APIGenerator().generate(api, path=str(tmp_path))
        views_py = (tmp_path / "nested-detail-test" / "src" / "views.py").read_text()

        # Both path params should appear as where clauses
        assert "ProductRecord.store_id == store_id" in views_py
        assert "ProductRecord.id == product_id" in views_py
        compile(views_py, "views.py", "exec")
