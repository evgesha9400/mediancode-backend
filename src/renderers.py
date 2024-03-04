from typing import List, Set

from jinja2 import Template

from models.template import (
    TemplateRequest,
    TemplateResponse,
    TemplateView,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateAPI,
)


def render_query_params(
    query_params: List[TemplateQueryParam], query_template: Template
) -> str:
    rendered_query_params = query_template.render(params=query_params)
    return rendered_query_params


def render_path_params(
    path_params: List[TemplatePathParam], paths_template: Template
) -> str:
    rendered_paths = paths_template.render(params=path_params)
    return rendered_paths


def render_requests(
    requests: List[TemplateRequest],
    typing_imports: Set[str],
    requests_template: Template,
) -> str:
    rendered_requests = requests_template.render(requests=requests, typing_imports=typing_imports)
    return rendered_requests


def render_responses(
    responses: List[TemplateResponse],
    typing_imports: Set[str],
    responses_template: Template,
) -> str:
    rendered_responses = responses_template.render(responses=responses, typing_imports=typing_imports)
    return rendered_responses


def render_views(views: List[TemplateView], views_template: Template) -> str:
    rendered_views = views_template.render(views=views)
    return rendered_views


def render_main(api: TemplateAPI, main_template: Template) -> str:
    rendered_main = main_template.render(api=api)
    return rendered_main


def render_pyproject(api: TemplateAPI, pyproject_template: Template) -> str:
    rendered_pyproject = pyproject_template.render(api=api)
    return rendered_pyproject


def render_makefile(api: TemplateAPI, makefile_template: Template) -> str:
    rendered_makefile = makefile_template.render(api=api)
    return rendered_makefile


def render_dockerfile(api: TemplateAPI, dockerfile_template: Template) -> str:
    rendered_dockerfile = dockerfile_template.render(api=api)
    return rendered_dockerfile
