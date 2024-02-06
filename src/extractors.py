from typing import List
from models.template import TemplateAPI, TemplateView, TemplateModel


def extract_views(template_api: TemplateAPI) -> List[TemplateView]:
    """Extracts and returns a list of views from the TemplateAPI instance."""
    return template_api.views


def extract_models(template_api: TemplateAPI) -> List[TemplateModel]:
    """Extracts and returns a list of unique TemplateModels from the views of the TemplateAPI instance."""
    model_names = set()
    models = []
    for view in template_api.views:
        if view.response.name not in model_names:
            models.append(view.response)
            model_names.add(view.response.name)
        if view.request and view.request.name not in model_names:
            models.append(view.request)
            model_names.add(view.request.name)
    return models
