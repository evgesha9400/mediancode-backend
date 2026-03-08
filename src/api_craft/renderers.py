from mako.template import Template

from api_craft.models.template import (
    TemplateAPI,
    TemplateModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateView,
)


def render_query_params(
    query_params: list[TemplateQueryParam],
    imports: set[str],
    query_template: Template,
) -> str:
    rendered_query_params = query_template.render(params=query_params, imports=imports)
    return rendered_query_params


def render_path_params(
    path_params: list[TemplatePathParam],
    imports: set[str],
    paths_template: Template,
) -> str:
    rendered_paths = paths_template.render(params=path_params, imports=imports)
    return rendered_paths


def render_models(
    models: list[TemplateModel],
    imports: set[str],
    models_template: Template,
) -> str:
    rendered_models = models_template.render(
        models=models,
        imports=imports,
    )
    return rendered_models


def render_views(views: list[TemplateView], views_template: Template) -> str:
    rendered_views = views_template.render(views=views)
    return rendered_views


def render_main(api: TemplateAPI, main_template: Template) -> str:
    rendered_main = main_template.render(api=api)
    return rendered_main


def render_pyproject(
    api: TemplateAPI,
    pyproject_template: Template,
    extra_dependencies: list[str] | None = None,
) -> str:
    rendered_pyproject = pyproject_template.render(
        api=api, extra_dependencies=extra_dependencies or []
    )
    return rendered_pyproject


def render_makefile(api: TemplateAPI, makefile_template: Template) -> str:
    rendered_makefile = makefile_template.render(api=api)
    return rendered_makefile


def render_dockerfile(api: TemplateAPI, dockerfile_template: Template) -> str:
    rendered_dockerfile = dockerfile_template.render(api=api)
    return rendered_dockerfile


def render_readme(api: TemplateAPI, readme_template: Template) -> str:
    rendered_readme = readme_template.render(api=api)
    return rendered_readme
