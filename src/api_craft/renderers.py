from mako.template import Template

from api_craft.models.template import (
    TemplateAPI,
    TemplateModel,
    TemplateORMModel,
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


def render_views(
    views: list[TemplateView],
    views_template: Template,
    database_config=None,
    orm_model_map: dict[str, str] | None = None,
    orm_pk_map: dict[str, str] | None = None,
) -> str:
    rendered_views = views_template.render(
        views=views,
        database_config=database_config,
        orm_model_map=orm_model_map or {},
        orm_pk_map=orm_pk_map or {},
    )
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


def render_orm_models(
    orm_models: list[TemplateORMModel],
    imports: list[str],
    template: Template,
    association_tables: list[dict] | None = None,
) -> str:
    return template.render(
        orm_models=orm_models,
        imports=imports,
        association_tables=association_tables or [],
    )


def render_database(api: TemplateAPI, template: Template) -> str:
    return template.render(api=api)


def render_docker_compose(api: TemplateAPI, template: Template) -> str:
    return template.render(api=api)


def render_alembic_ini(api: TemplateAPI, template: Template) -> str:
    return template.render(api=api)


def render_alembic_env(api: TemplateAPI, template: Template) -> str:
    return template.render(api=api)


def render_env(api: TemplateAPI, template: Template) -> str:
    return template.render(api=api)


def render_initial_migration(
    orm_models: list[TemplateORMModel],
    template: Template,
    association_tables: list[dict] | None = None,
) -> str:
    return template.render(
        orm_models=orm_models,
        association_tables=association_tables or [],
    )
