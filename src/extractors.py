import re
from typing import List, Union, Set
from models.template import (
    TemplateAPI,
    TemplateView,
    TemplateRequest,
    TemplateResponse,
    TemplatePathParam,
    TemplateQueryParam,
)


def extract_types_from_models(
    models: Union[List[TemplateRequest], List[TemplateResponse]]
) -> Set[str]:
    """Extracts and returns a list of unique types from the fields of the models."""
    typing_imports = set()
    for model in models:
        for field in model.fields:
            if "[" in field.type:
                found_type = field.type.split("[")[0]
                typing_imports.add(found_type)
    return typing_imports


def extract_views(template_api: TemplateAPI) -> List[TemplateView]:
    """Extracts and returns a list of views from the TemplateAPI instance."""
    return template_api.views


def extract_request_models(template_api: TemplateAPI) -> List[TemplateRequest]:
    """Extracts  a list of unique TemplateModels from the request of the views of the TemplateAPI instance."""
    model_names = set()
    models = []
    for view in template_api.views:
        if view.request and view.request.name not in model_names:
            models.append(view.request)
            model_names.add(view.request.name)
    return models


def extract_response_models(template_api: TemplateAPI) -> List[TemplateResponse]:
    """Extracts a list of unique TemplateModels from the response of the views of the TemplateAPI instance."""
    model_names = set()
    models = []
    for view in template_api.views:
        if view.response.name not in model_names:
            models.append(view.response)
            model_names.add(view.response.name)
    return models


def extract_path_parameters(template_api: TemplateAPI) -> List[TemplatePathParam]:
    """Extracts and returns a list of unique TemplatePathParams from the views of the TemplateAPI instance."""
    path_param_names = set()
    path_params = []
    for view in template_api.views:
        for param in view.path_params:
            if param.snake_name not in path_param_names:
                path_params.append(param)
                path_param_names.add(param.snake_name)
    return path_params


def extract_query_parameters(template_api: TemplateAPI) -> List[TemplateQueryParam]:
    """Extracts and returns a list of unique TemplateQueryParams from the views of the TemplateAPI instance."""
    query_param_names = set()
    query_params = []
    for view in template_api.views:
        for param in view.query_params:
            if param.snake_name not in query_param_names:
                query_params.append(param)
                query_param_names.add(param.snake_name)
    return query_params
