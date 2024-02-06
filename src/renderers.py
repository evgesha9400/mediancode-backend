from typing import List
from models.template import TemplateModel, TemplateView
from jinja2 import Template


def render_models(models: List[TemplateModel], models_template: Template) -> str:
    rendered_models = models_template.render(models=models)
    return rendered_models


def render_views(views: List[TemplateView], views_template: Template) -> str:
    rendered_views = views_template.render(views=views)
    return rendered_views
