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
        """New fields default to None/False for backward compatibility."""
        param = InputQueryParam(name="limit", type="int")
        assert param.field is None
        assert param.operator is None
        assert param.pagination is False

    def test_filter_param(self):
        param = InputQueryParam(
            name="min_price", type="float", field="price", operator="gte"
        )
        assert param.field == "price"
        assert param.operator == "gte"
        assert param.pagination is False

    def test_pagination_param(self):
        param = InputQueryParam(name="limit", type="int", pagination=True)
        assert param.pagination is True
        assert param.field is None
        assert param.operator is None


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
        with pytest.raises(ValueError, match="primary key.*list endpoint"):
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
    """Pagination params must not have field/operator; must be int."""

    def test_pagination_with_field_raises(self):
        """pagination=True with field set is invalid."""
        with pytest.raises(ValueError, match="pagination.*field"):
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
                                name="limit",
                                type="int",
                                pagination=True,
                                field="id",
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
                        ],
                    ),
                ],
            )

    def test_pagination_with_operator_raises(self):
        """pagination=True with operator set is invalid."""
        with pytest.raises(ValueError, match="pagination.*operator"):
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
                                name="limit",
                                type="int",
                                pagination=True,
                                operator="eq",
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
                        ],
                    ),
                ],
            )

    def test_pagination_valid(self):
        """pagination=True with type=int and no field/operator passes."""
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
                        InputQueryParam(name="limit", type="int", pagination=True),
                        InputQueryParam(name="offset", type="int", pagination=True),
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
