from typing import Set

from api_craft.models.template import (
    TemplateAPI,
    TemplateModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateView,
)


def collect_model_typing_imports(models: list[TemplateModel]) -> Set[str]:
    """Collect required typing imports for the generated models.

    :param models: Collection of template-ready models.
    :returns: Set with the unique generic type names referenced in model fields.
    """

    typing_imports = set()
    for model in models:
        for field in model.fields:
            if "[" in field.type:
                found_type = field.type.split("[")[0]
                typing_imports.add(found_type)
    return typing_imports


def extract_views(template_api: TemplateAPI) -> list[TemplateView]:
    """Extracts and returns a list of views from the TemplateAPI instance."""
    return template_api.views


def extract_models(template_api: TemplateAPI) -> list[TemplateModel]:
    """Return the list of shared template models defined in the API."""
    return template_api.models


def extract_path_parameters(template_api: TemplateAPI) -> list[TemplatePathParam]:
    """Extracts and returns a list of unique TemplatePathParams from the views of the TemplateAPI instance."""
    path_param_names = set()
    path_params = []
    for view in template_api.views:
        for param in view.path_params:
            if param.snake_name not in path_param_names:
                path_params.append(param)
                path_param_names.add(param.snake_name)
    return path_params


def extract_query_parameters(template_api: TemplateAPI) -> list[TemplateQueryParam]:
    """Extracts and returns a list of unique TemplateQueryParams from the views of the TemplateAPI instance."""
    query_param_names = set()
    query_params = []
    for view in template_api.views:
        for param in view.query_params:
            if param.snake_name not in query_param_names:
                query_params.append(param)
                query_param_names.add(param.snake_name)
    return query_params
