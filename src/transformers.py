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
    TemplateModel,
    TemplateField,
    TemplateQueryParam,
    TemplatePathParam,
)
from utils import remove_duplicates


def transform_field(input_field: InputField) -> TemplateField:
    """Transforms an InputField instance to a TemplateField instance."""
    return TemplateField(
        type=input_field.type, name=input_field.name, required=input_field.required
    )


def transform_model(input_model: InputModel, prefix: str = "") -> TemplateModel:
    """Transforms an InputModel instance to a TemplateModel instance."""
    transformed_fields = [transform_field(field) for field in input_model.fields]
    name = f"{prefix}{input_model.name}"
    transformed_name = remove_duplicates(name)
    return TemplateModel(name=transformed_name, fields=transformed_fields)


def transform_query_params(
    input_query_params: List[InputQueryParam],
) -> List[TemplateQueryParam]:
    return (
        [
            TemplateQueryParam(
                name=param.name, type=param.type, required=param.required
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
            TemplatePathParam(name=param.name, type=param.type)
            for param in input_path_params
        ]
        if input_path_params
        else []
    )


def transform_view(input_view: InputView) -> TemplateView:
    """Transforms an InputView instance to a TemplateView instance."""
    prefix = f"{input_view.name}"
    transformed_request = (
        transform_model(input_view.request, prefix) if input_view.request else None
    )
    transformed_response = transform_model(input_view.response, prefix)
    transformed_query_params = transform_query_params(input_view.query_params)
    transformed_path_params = transform_path_params(input_view.path_params)

    return TemplateView(
        name=input_view.name,
        path=input_view.path,
        method=input_view.method.lower(),
        response=transformed_response,
        request=transformed_request,
        query_params=transformed_query_params,
        path_params=transformed_path_params,
        response_codes=input_view.response_codes,
    )


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transforms an InputAPI instance to a TemplateAPI instance."""
    transformed_views = [transform_view(view) for view in input_api.views]
    return TemplateAPI(
        name=input_api.name, version=input_api.version, views=transformed_views
    )
