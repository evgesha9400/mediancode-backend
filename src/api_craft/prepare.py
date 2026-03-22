# src/api_craft/prepare.py
"""Prepare InputAPI for template rendering.

Replaces the transform layer (transformers.py) by passing Input models
directly to templates and only creating new types where the template
interface genuinely diverges from the input interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from api_craft.models.enums import ResponseShape
from api_craft.models.input import (
    InputAPI,
    InputEndpoint,
    InputField,
    InputModel,
    InputTag,
)
from api_craft.models.template import (
    TemplateDatabaseConfig,
    TemplateORMModel,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.placeholders import PlaceholderGenerator
from api_craft.schema_splitter import _has_appears_flags, _model_needs_split
from api_craft.utils import (
    add_spaces_to_camel_case,
    camel_to_kebab,
    camel_to_snake,
    remove_duplicates,
    snake_to_camel,
)


# ---------------------------------------------------------------------------
# Prepared dataclasses — only for types where Template diverges from Input
# ---------------------------------------------------------------------------


@dataclass
class PreparedQueryParam:
    """Query parameter ready for template rendering."""

    camel_name: str
    snake_name: str
    type: str
    title: str
    optional: bool
    description: str | None = None
    field: str | None = None
    operator: str | None = None
    constraints: dict[str, int | float] | None = None


@dataclass
class PreparedPathParam:
    """Path parameter ready for template rendering."""

    snake_name: str
    camel_name: str
    type: str
    title: str
    description: str | None = None
    field: str | None = None


@dataclass
class PreparedView:
    """Endpoint/view ready for template rendering."""

    snake_name: str
    camel_name: str
    path: str
    method: str
    response_model: str | None
    request_model: str | None
    response_placeholders: dict[str, Any] | None
    query_params: list[PreparedQueryParam]
    path_params: list[PreparedPathParam]
    tag: str | None = None
    description: str | None = None
    use_envelope: bool = True
    response_shape: ResponseShape = "object"
    target: str | None = None
    pagination: bool = False


@dataclass
class PreparedAPIConfig:
    """Configuration subset needed by templates."""

    healthcheck: str | None
    response_placeholders: bool


@dataclass
class PreparedAPI:
    """Root API object passed to Mako templates.

    Field names match the former TemplateAPI so templates need zero changes.
    """

    snake_name: str
    camel_name: str
    kebab_name: str
    spaced_name: str
    version: str
    author: str
    description: str
    app_port: int
    models: list[InputModel]
    views: list[PreparedView]
    tags: list[InputTag]
    config: PreparedAPIConfig
    orm_models: list[TemplateORMModel] = field(default_factory=list)
    database_config: TemplateDatabaseConfig | None = None


# ---------------------------------------------------------------------------
# Preparation helpers
# ---------------------------------------------------------------------------


def _prepare_query_params(
    input_query_params: list | None,
    target_fields: dict[str, InputField] | None = None,
) -> list[PreparedQueryParam]:
    if not input_query_params:
        return []
    result = []
    for param in input_query_params:
        param_type = param.type
        optional = param.optional

        if param.field and target_fields and param.field in target_fields:
            field_type = target_fields[param.field].type
            if param.operator == "in":
                param_type = f"List[{field_type}]"
            else:
                param_type = field_type
            optional = True

        result.append(
            PreparedQueryParam(
                type=param_type,
                snake_name=str(param.name),
                camel_name=snake_to_camel(param.name),
                title=snake_to_camel(param.name),
                optional=optional,
                description=param.description,
                field=param.field,
                operator=param.operator,
            )
        )
    return result


def _pagination_params() -> list[PreparedQueryParam]:
    return [
        PreparedQueryParam(
            type="int",
            snake_name="limit",
            camel_name="Limit",
            title="Limit",
            optional=True,
            description="Maximum number of results to return (1-100).",
            constraints={"ge": 1, "le": 100},
        ),
        PreparedQueryParam(
            type="int",
            snake_name="offset",
            camel_name="Offset",
            title="Offset",
            optional=True,
            description="Number of results to skip.",
            constraints={"ge": 0},
        ),
    ]


def _prepare_path_params(
    input_path_params: list | None,
    target_fields: dict[str, InputField] | None = None,
) -> list[PreparedPathParam]:
    if not input_path_params:
        return []
    result = []
    for param in input_path_params:
        param_type = param.type
        if param.field and target_fields and param.field in target_fields:
            param_type = target_fields[param.field].type

        result.append(
            PreparedPathParam(
                type=param_type,
                snake_name=str(param.name),
                camel_name=snake_to_camel(param.name),
                title=add_spaces_to_camel_case(snake_to_camel(param.name)),
                description=param.description,
                field=param.field,
            )
        )
    return result


def _prepare_view(
    endpoint: InputEndpoint,
    placeholder_generator: PlaceholderGenerator,
    generate_placeholders: bool = False,
    objects_by_name: dict[str, InputModel] | None = None,
) -> PreparedView:
    response_name = endpoint.response
    if response_name and response_name not in placeholder_generator.models:
        raise ValueError(f"Response object '{response_name}' is not declared")

    request_name = endpoint.request
    if request_name and request_name not in placeholder_generator.models:
        raise ValueError(f"Request object '{request_name}' is not declared")

    camel_name = remove_duplicates(endpoint.name)
    if not camel_name:
        raise ValueError(
            f"Endpoint name '{endpoint.name}' resolved to an empty identifier"
        )
    snake_name = camel_to_snake(camel_name)

    response_placeholders = None
    if generate_placeholders and response_name:
        response_placeholders = placeholder_generator.generate_for_model(response_name)

    # Resolve target object fields for type derivation
    target_fields: dict[str, InputField] | None = None
    target_name: str | None = endpoint.target
    if objects_by_name:
        if endpoint.response_shape == "object" and not target_name:
            target_name = endpoint.response
        if target_name and target_name in objects_by_name:
            target_obj = objects_by_name[target_name]
            target_fields = {str(f.name): f for f in target_obj.fields}

    # Auto-infer PK field for the last path param on detail endpoints
    path_params_input = endpoint.path_params
    if (
        endpoint.response_shape == "object"
        and path_params_input
        and not path_params_input[-1].field
        and objects_by_name
        and target_name
        and target_name in objects_by_name
    ):
        target_obj_for_pk = objects_by_name[target_name]
        pk_fields = [f for f in target_obj_for_pk.fields if f.pk]
        last_param = path_params_input[-1]
        non_pk_field_names = {str(f.name) for f in target_obj_for_pk.fields if not f.pk}
        if pk_fields and str(last_param.name) not in non_pk_field_names:
            inferred = last_param.model_copy(update={"field": str(pk_fields[0].name)})
            path_params_input = list(path_params_input[:-1]) + [inferred]
            if target_fields is None:
                target_fields = {str(f.name): f for f in target_obj_for_pk.fields}

    query_params = _prepare_query_params(endpoint.query_params, target_fields)
    if endpoint.pagination:
        query_params.extend(_pagination_params())

    return PreparedView(
        snake_name=snake_name,
        camel_name=camel_name,
        path=endpoint.path,
        method=endpoint.method.lower(),
        response_model=response_name,
        request_model=request_name,
        response_placeholders=response_placeholders,
        query_params=query_params,
        path_params=_prepare_path_params(path_params_input, target_fields),
        tag=endpoint.tag,
        description=endpoint.description,
        use_envelope=endpoint.use_envelope,
        response_shape=endpoint.response_shape,
        target=target_name,
        pagination=endpoint.pagination,
    )


# ---------------------------------------------------------------------------
# Schema splitting (returns InputModel instead of TemplateModel)
# ---------------------------------------------------------------------------


def _split_model_schemas(input_model: InputModel) -> list[InputModel]:
    """Split an InputModel into Create, Update, and Response InputModels."""
    from api_craft.models.types import PascalCaseName

    model_validators = list(input_model.model_validators)

    # Create fields: non-PK, appears in request
    create_fields = [
        f for f in input_model.fields if f.appears in ("both", "request") and not f.pk
    ]

    # Update fields: same selection as Create but all optional
    update_fields = [f.model_copy(update={"optional": True}) for f in create_fields]

    # Response fields: appears in response (PK included)
    response_fields = list(
        f for f in input_model.fields if f.appears in ("both", "response")
    )

    # Add FK ID fields for `references` relationships
    for rel in input_model.relationships:
        if rel.cardinality == "references":
            fk_name = f"{rel.name}_id"
            existing_names = {str(f.name) for f in response_fields}
            if fk_name not in existing_names:
                response_fields.append(
                    InputField(
                        type="uuid",
                        name=fk_name,
                        optional=False,
                        description=f"FK reference to {rel.target_model}",
                    )
                )

    return [
        InputModel(
            name=PascalCaseName(f"{input_model.name}Create"),
            fields=create_fields,
            description=input_model.description,
            model_validators=model_validators,
        ),
        InputModel(
            name=PascalCaseName(f"{input_model.name}Update"),
            fields=update_fields,
            description=input_model.description,
            model_validators=[],
        ),
        InputModel(
            name=PascalCaseName(f"{input_model.name}Response"),
            fields=response_fields,
            description=input_model.description,
            model_validators=[],
        ),
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def prepare_api(input_api: InputAPI) -> PreparedAPI:
    """Prepare an InputAPI for template rendering.

    This replaces transform_api() from transformers.py. Input models pass
    through directly — no identity-copy transforms.
    """
    use_split = _has_appears_flags(input_api)

    if use_split:
        prepared_models: list[InputModel] = []
        split_model_names: set[str] = set()
        for model in input_api.objects:
            if _model_needs_split(model):
                prepared_models.extend(_split_model_schemas(model))
                split_model_names.add(str(model.name))
            else:
                prepared_models.append(model)

        # Rewrite field types in unsplit models that reference split model names
        if split_model_names:
            for i, model in enumerate(prepared_models):
                if str(model.name) in split_model_names or any(
                    str(model.name).endswith(s)
                    for s in ("Create", "Update", "Response")
                ):
                    continue
                updated_fields = []
                changed = False
                for f in model.fields:
                    new_type = str(f.type)
                    for name in split_model_names:
                        new_type = re.sub(
                            rf"\b{re.escape(name)}\b",
                            f"{name}Response",
                            new_type,
                        )
                    if new_type != str(f.type):
                        updated_fields.append(f.model_copy(update={"type": new_type}))
                        changed = True
                    else:
                        updated_fields.append(f)
                if changed:
                    prepared_models[i] = model.model_copy(
                        update={"fields": updated_fields}
                    )
    else:
        prepared_models = list(input_api.objects)
        split_model_names = set()

    # Build field map for placeholder generation
    if use_split:
        field_map: dict[str, list] = {}
        for model in prepared_models:
            if (
                str(model.name).endswith("Response")
                and str(model.name).removesuffix("Response") in split_model_names
            ):
                base_name = str(model.name).removesuffix("Response")
                field_map[base_name] = model.fields
            elif str(model.name) not in split_model_names and not any(
                str(model.name).endswith(suffix) for suffix in ("Create", "Update")
            ):
                field_map[str(model.name)] = model.fields
    else:
        field_map = {str(model.name): model.fields for model in prepared_models}

    # Include validator-referenced fields in placeholders
    validator_fields: dict[str, set[str]] = {}
    for model in prepared_models:
        referenced: set[str] = set()
        optional_names = {str(f.name) for f in model.fields if f.optional}
        for mv in model.model_validators:
            if mv.mode != "before":
                continue
            for match in re.finditer(r'data\.get\(["\'](\w+)["\']\)', mv.function_body):
                name = match.group(1)
                if name in optional_names:
                    referenced.add(name)
                    break
        if referenced:
            key = str(model.name)
            if use_split and key.endswith("Create"):
                key = key.removesuffix("Create")
            validator_fields[key] = referenced
    placeholder_generator = PlaceholderGenerator(field_map, validator_fields)

    # Build objects lookup for type derivation
    objects_by_name = {str(obj.name): obj for obj in input_api.objects}

    # Prepare views, remapping model names to derived schemas
    prepared_views = []
    for endpoint in input_api.endpoints:
        view = _prepare_view(
            endpoint,
            placeholder_generator,
            generate_placeholders=input_api.config.response_placeholders,
            objects_by_name=objects_by_name,
        )
        if use_split:
            if view.request_model and view.request_model in split_model_names:
                base_name = view.request_model
                if endpoint.method in ("PUT", "PATCH"):
                    view.request_model = f"{base_name}Update"
                else:
                    view.request_model = f"{base_name}Create"
            if view.response_model and view.response_model in split_model_names:
                base_name = view.response_model
                view.response_model = f"{base_name}Response"
        prepared_views.append(view)

    orm_models: list[TemplateORMModel] = []
    database_config = None
    if input_api.config.database.enabled:
        orm_models = transform_orm_models(input_api.objects)
        snake_name = camel_to_snake(input_api.name)
        db_port = 5433
        database_config = TemplateDatabaseConfig(
            enabled=True,
            default_url=f"postgresql+asyncpg://postgres:postgres@localhost:{db_port}/{snake_name}",
            db_port=db_port,
        )

    return PreparedAPI(
        snake_name=camel_to_snake(input_api.name),
        camel_name=str(input_api.name),
        kebab_name=camel_to_kebab(input_api.name),
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        models=prepared_models,
        views=prepared_views,
        tags=list(input_api.tags),
        author=input_api.author,
        description=input_api.description,
        config=PreparedAPIConfig(
            healthcheck=input_api.config.healthcheck,
            response_placeholders=input_api.config.response_placeholders,
        ),
        orm_models=orm_models,
        database_config=database_config,
        app_port=8001,
    )
