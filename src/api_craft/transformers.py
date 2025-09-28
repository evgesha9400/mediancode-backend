"""Transformers for input models to template models."""

from typing import Any, Dict, List

from src.api_craft.models.input import (
    InputAPI,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputView,
)
from src.api_craft.models.template import (
    TemplateAPI,
    TemplateAPIConfig,
    TemplateField,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateRequest,
    TemplateResponse,
    TemplateView,
)
from src.api_craft.placeholders import (
    generate_bool,
    generate_datetime,
    generate_float,
    generate_int,
    generate_string,
)
from src.api_craft.utils import (
    add_spaces_to_camel_case,
    camel_to_snake,
    remove_duplicates,
    snake_to_camel,
)


def generate_model_placeholder(model_name: str, fields: List[TemplateField], index: int) -> Dict[str, Any]:
    """Generate placeholder values for a model instance."""
    return {field.name: generate_placeholder_value(field.type, index) for field in fields}


def generate_placeholder_value(field_type: str, index: int) -> Any:
    """Generate a placeholder value based on the field type."""
    # Handle List type
    if field_type.startswith("List["):
        inner_type = field_type[5:-1]  # Extract type between List[ and ]
        # Generate 2 examples for lists
        return [generate_placeholder_value(inner_type, i) for i in range(index, index + 2)]

    # Handle reference to another model
    if field_type.startswith(("Get", "Create", "Update", "Delete", "List")):
        # This is a reference to another model, we'll create it with index-based values
        return {
            "id": generate_int(index, 1),
            "name": generate_string(index, "example"),
        }

    # Handle primitive types
    type_mapping = {
        "str": lambda i: generate_string(i, "example"),
        "int": lambda i: generate_int(i, 1),
        "bool": generate_bool,
        "float": lambda i: generate_float(i, 1.5),
        "datetime.datetime": generate_datetime,
    }

    generator = type_mapping.get(field_type)
    if not generator:
        return generate_string(index, f"example_{field_type.lower()}")

    return generator(index)


def transform_field(input_field: InputField) -> TemplateField:
    """Transforms an InputField instance to a TemplateField instance."""
    return TemplateField(type=input_field.type, name=input_field.name, required=input_field.required)


def transform_request(input_request: InputModel, prefix: str = "") -> TemplateRequest:
    """Transforms an InputModel instance to a TemplateRequest instance."""
    transformed_fields = [transform_field(field) for field in input_request.fields]
    name = f"{prefix}{input_request.name}"
    transformed_name = remove_duplicates(name)
    return TemplateRequest(name=transformed_name, fields=transformed_fields)


def transform_response(
    input_response: InputModel, prefix: str = "", generate_placeholders: bool = False
) -> TemplateResponse:
    """Transforms an InputModel instance to a TemplateResponse instance."""
    transformed_fields = [transform_field(field) for field in input_response.fields]
    name = f"{prefix}{input_response.name}"
    transformed_name = remove_duplicates(name)

    placeholder_values = None
    if generate_placeholders:
        placeholder_values = {
            field.name: generate_placeholder_value(field.type, idx) for idx, field in enumerate(transformed_fields, 1)
        }

    return TemplateResponse(
        name=transformed_name,
        fields=transformed_fields,
        placeholder_values=placeholder_values,
    )


def transform_query_params(
    input_query_params: List[InputQueryParam],
) -> List[TemplateQueryParam]:
    return (
        [
            TemplateQueryParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=snake_to_camel(param.name),
                required=param.required,
            )
            for param in input_query_params
        ]
        if input_query_params
        else []
    )


def transform_path_params(
    input_path_params: List[InputPathParam],
) -> List[TemplatePathParam]:
    return (
        [
            TemplatePathParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=add_spaces_to_camel_case(snake_to_camel(param.name)),
            )
            for param in input_path_params
        ]
        if input_path_params
        else []
    )


def transform_view(input_view: InputView, generate_placeholders: bool = False) -> TemplateView:
    """Transforms an InputView instance to a TemplateView instance."""
    prefix = f"{input_view.name}"

    transformed_request = None
    if input_view.request:
        transformed_request = transform_request(input_view.request, prefix)

    transformed_response = transform_response(input_view.response, prefix, generate_placeholders=generate_placeholders)
    transformed_query_params = transform_query_params(input_view.query_params)
    transformed_path_params = transform_path_params(input_view.path_params)

    return TemplateView(
        snake_name=camel_to_snake(input_view.name),
        camel_name=input_view.name,
        path=input_view.path,
        method=input_view.method.lower(),
        response=transformed_response,
        request=transformed_request,
        query_params=transformed_query_params,
        path_params=transformed_path_params,
    )


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transforms an InputAPI instance to a TemplateAPI instance."""
    transformed_views = [
        transform_view(view, generate_placeholders=input_api.config.response_placeholders) for view in input_api.views
    ]

    return TemplateAPI(
        snake_name=camel_to_snake(input_api.name),
        camel_name=input_api.name,
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        views=transformed_views,
        author=input_api.author,
        description=input_api.description,
        config=TemplateAPIConfig(
            healthcheck=input_api.config.healthcheck,
            response_placeholders=input_api.config.response_placeholders,
        ),
    )
