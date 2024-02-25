"""Transformers for input models to template models."""
from typing import List

from models.input import (
    InputAPI,
    InputView,
    InputModel,
    InputField,
    InputQueryParam,
    InputPathParam,
)
from models.template import (
    TemplateAPI,
    TemplateView,
    TemplateRequest,
    TemplateResponse,
    TemplateField,
    TemplateQueryParam,
    TemplatePathParam,
)
from utils import (
    snake_to_camel,
    camel_to_snake,
    remove_duplicates,
    add_spaces_to_camel_case,
)


def transform_field(input_field: InputField) -> TemplateField:
    """Transforms an InputField instance to a TemplateField instance."""
    return TemplateField(
        type=input_field.type, name=input_field.name, required=input_field.required
    )


def transform_request(input_request: InputModel, prefix: str = "") -> TemplateRequest:
    """Transforms an InputModel instance to a TemplateRequest instance."""
    transformed_fields = [transform_field(field) for field in input_request.fields]
    name = f"{prefix}{input_request.name}"
    transformed_name = remove_duplicates(name)
    return TemplateRequest(name=transformed_name, fields=transformed_fields)


def transform_response(
    input_response: InputModel, prefix: str = ""
) -> TemplateResponse:
    """Transforms an InputModel instance to a TemplateResponse instance."""
    transformed_fields = [transform_field(field) for field in input_response.fields]
    name = f"{prefix}{input_response.name}"
    transformed_name = remove_duplicates(name)
    return TemplateResponse(name=transformed_name, fields=transformed_fields)


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


def transform_view(input_view: InputView) -> TemplateView:
    """Transforms an InputView instance to a TemplateView instance."""
    prefix = f"{input_view.name}"

    transformed_request = None
    if input_view.request:
        transformed_request = transform_request(input_view.request, prefix)

    transformed_response = transform_response(input_view.response, prefix)
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
    transformed_views = [transform_view(view) for view in input_api.views]
    return TemplateAPI(
        snake_name=camel_to_snake(input_api.name),
        camel_name=input_api.name,
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        views=transformed_views,
        author=input_api.author,
        description=input_api.description,
        healthcheck_endpoint="/healthcheck",
    )
