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
from api_craft.models.orm_types import (
    TemplateDatabaseConfig,
    TemplateORMModel,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.placeholders import PlaceholderGenerator
from api_craft.schema_splitter import (
    _has_appears_flags,
    _model_needs_split,
    split_model_schemas,
)
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
class PreparedFilter:
    """A pre-computed query filter expression for views.mako."""

    param_name: str
    filter_expr: str


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
    # Pre-computed fields for template rendering (Phase 2)
    signature_lines: list[str] = field(default_factory=list)
    has_signature: bool = False
    orm_class: str = ""
    has_orm: bool = False
    pk_param: str = "id"
    # Filter pre-computations for list endpoints
    list_path_where: str | None = None
    query_filters: list[PreparedFilter] = field(default_factory=list)
    pagination_params: list[PreparedQueryParam] = field(default_factory=list)
    # Detail endpoint pre-computations
    detail_where: str = ""


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
    # Pre-computed fields for views.mako imports (Phase 2)
    view_model_names: list[str] = field(default_factory=list)
    view_orm_names: list[str] = field(default_factory=list)
    has_path_params: bool = False
    has_query_params: bool = False
    has_no_response: bool = False
    # Pre-computed fields for models.mako imports
    pydantic_imports: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Template helper functions (passed to models.mako as context)
# ---------------------------------------------------------------------------


def indent_body(body: str, spaces: int = 4) -> str:
    """Add extra indentation to each line of a function body."""
    prefix = " " * spaces
    lines = body.split("\n")
    return "\n".join(prefix + line if line.strip() else line for line in lines)


def render_field_constraint(validator) -> str | None:
    """Render a validator as a Pydantic Field constraint string."""
    name = validator.name
    params = validator.params or {}
    value = params.get("value")

    constraint_map = {
        "min_length": "min_length",
        "max_length": "max_length",
        "pattern": "pattern",
        "gt": "gt",
        "ge": "ge",
        "lt": "lt",
        "le": "le",
        "multiple_of": "multiple_of",
    }

    pydantic_name = constraint_map.get(name)
    if not pydantic_name:
        return None

    if pydantic_name == "pattern":
        return f'{pydantic_name}=r"{value}"'
    elif isinstance(value, str):
        return f'{pydantic_name}="{value}"'
    else:
        return f"{pydantic_name}={value}"


def render_field(field, force_optional: bool = False) -> str:
    """Render a complete field definition with validators.

    :param field: InputField to render.
    :param force_optional: When True, render as ``Type | None = None``
        (used for Update schemas where every field is optional).
    :returns: Python field definition string.
    """
    constraints = []
    for v in field.validators:
        constraint = render_field_constraint(v)
        if constraint:
            constraints.append(constraint)

    type_annotation = field.type
    field_args = ", ".join(constraints)

    if force_optional:
        # Update schema: all fields become Type | None = None
        # Never apply literal defaults on Update (exclude_unset=True in PATCH)
        if field_args:
            return f"{field.name}: {type_annotation} | None = Field(default=None, {field_args})"
        return f"{field.name}: {type_annotation} | None = None"

    # Create/Response schema
    if field.default and field.default.kind == "literal":
        # Literal default: field is omittable, Pydantic schema default
        value = repr(field.default.value)
        if field_args:
            return f"{field.name}: {type_annotation} = Field(default={value}, {field_args})"
        return f"{field.name}: {type_annotation} = {value}"

    if field.nullable:
        if field_args:
            return f"{field.name}: {type_annotation} | None = Field(default=None, {field_args})"
        return f"{field.name}: {type_annotation} | None = None"

    # Required field
    if field_args:
        return f"{field.name}: {type_annotation} = Field({field_args})"
    return f"{field.name}: {type_annotation}"


def _compute_pydantic_imports(models: list[InputModel]) -> list[str]:
    """Compute the sorted list of pydantic imports needed by the models."""
    has_field_constraints = any(
        any(f.validators for f in model.fields) for model in models
    )
    has_field_validators = any(
        any(f.field_validators for f in model.fields) for model in models
    )
    has_model_validators = any(model.model_validators for model in models)
    has_response_model = any(
        str(model.name).endswith("Response") for model in models
    )

    imports = ["BaseModel"]
    if has_response_model:
        imports.append("ConfigDict")
    if has_field_constraints:
        imports.append("Field")
    if has_field_validators:
        imports.append("field_validator")
    if has_model_validators:
        imports.append("model_validator")
    return sorted(imports)


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
# View enrichment — pre-compute data used by views.mako
# ---------------------------------------------------------------------------


def _build_signature_lines(view: PreparedView, has_database: bool) -> list[str]:
    """Build the function signature lines for a view."""
    lines = []
    for p_param in view.path_params:
        lines.append(f"    {p_param.snake_name}: path.{p_param.camel_name},")
    if view.request_model:
        lines.append(f"    request: {view.request_model},")
    for q_param in view.query_params:
        suffix = " = None" if q_param.optional else ""
        lines.append(f"    {q_param.snake_name}: query.{q_param.camel_name}{suffix},")
    if has_database:
        lines.append("    session: AsyncSession = Depends(get_session),")
    return lines


def _resolve_orm_class(
    view: PreparedView,
    orm_model_map: dict[str, str] | None,
    orm_pk_map: dict[str, str] | None,
) -> tuple[str, bool]:
    """Resolve the ORM class name for a view. Returns (orm_class, has_orm)."""
    if not orm_model_map:
        return "", False

    # Try response model first
    if view.response_model and view.response_model in orm_model_map:
        return orm_model_map[view.response_model], True

    # Try target for list endpoints
    if view.target and view.target in orm_model_map:
        return orm_model_map[view.target], True

    # For delete without response model, resolve from path param PK
    if view.method == "delete" and orm_pk_map and view.path_params:
        for p in view.path_params:
            if p.snake_name in orm_pk_map:
                return orm_pk_map[p.snake_name], True

    return "", False


def _compute_view_imports(
    views: list[PreparedView],
    orm_model_map: dict[str, str] | None,
    orm_pk_map: dict[str, str] | None,
) -> tuple[list[str], list[str], bool, bool, bool]:
    """Compute import-related data from views for views.mako header."""
    model_names: list[str] = []
    for view in views:
        if view.response_model and view.response_model not in model_names:
            model_names.append(view.response_model)
        if view.request_model and view.request_model not in model_names:
            model_names.append(view.request_model)

    has_path_params = any(view.path_params for view in views)
    has_query_params = any(view.query_params for view in views)
    has_no_response = any(not view.response_model for view in views)

    orm_names_from_response = {
        orm_model_map[view.response_model]
        for view in views
        if view.response_model
        and orm_model_map
        and view.response_model in orm_model_map
    }
    orm_names_from_pk: set[str] = set()
    if orm_pk_map:
        for view in views:
            if view.method == "delete" and not view.response_model and view.path_params:
                for p in view.path_params:
                    if p.snake_name in orm_pk_map:
                        orm_names_from_pk.add(orm_pk_map[p.snake_name])
    orm_names_from_target: set[str] = set()
    if orm_model_map:
        for view in views:
            if view.target and view.target in orm_model_map:
                orm_names_from_target.add(orm_model_map[view.target])
    orm_names = sorted(
        orm_names_from_response | orm_names_from_pk | orm_names_from_target
    )

    return model_names, orm_names, has_path_params, has_query_params, has_no_response


def _build_filter_expr(
    orm_class: str, field: str, operator: str, param_name: str
) -> str:
    """Build a SQLAlchemy filter expression string."""
    match operator:
        case "eq":
            return f"{orm_class}.{field} == {param_name}"
        case "gte":
            return f"{orm_class}.{field} >= {param_name}"
        case "lte":
            return f"{orm_class}.{field} <= {param_name}"
        case "gt":
            return f"{orm_class}.{field} > {param_name}"
        case "lt":
            return f"{orm_class}.{field} < {param_name}"
        case "like":
            return f'{orm_class}.{field}.like(f"%{{{param_name}}}%")'
        case "ilike":
            return f'{orm_class}.{field}.ilike(f"%{{{param_name}}}%")'
        case "in":
            return f"{orm_class}.{field}.in_({param_name})"
        case _:
            return f"{orm_class}.{field} == {param_name}"


def _enrich_views(
    views: list[PreparedView],
    database_config: TemplateDatabaseConfig | None,
    orm_model_map: dict[str, str] | None,
    orm_pk_map: dict[str, str] | None,
) -> None:
    """Enrich views with pre-computed template data (mutates in place)."""
    has_database = database_config is not None
    for view in views:
        view.signature_lines = _build_signature_lines(view, has_database)
        view.has_signature = bool(view.signature_lines)
        view.orm_class, view.has_orm = _resolve_orm_class(
            view, orm_model_map, orm_pk_map
        )
        view.pk_param = view.path_params[0].snake_name if view.path_params else "id"

        # List endpoint filter pre-computation
        if (
            view.has_orm
            and view.method == "get"
            and view.response_shape == "list"
            and view.target
        ):
            path_where_clauses = []
            for pp in view.path_params:
                if pp.field:
                    path_where_clauses.append(
                        f"{view.orm_class}.{pp.field} == {pp.snake_name}"
                    )
            view.list_path_where = (
                ", ".join(path_where_clauses) if path_where_clauses else None
            )

            for qp in view.query_params:
                if qp.snake_name in ("limit", "offset") and view.pagination:
                    view.pagination_params.append(qp)
                elif qp.field and qp.operator:
                    view.query_filters.append(
                        PreparedFilter(
                            param_name=qp.snake_name,
                            filter_expr=_build_filter_expr(
                                view.orm_class, qp.field, qp.operator, qp.snake_name
                            ),
                        )
                    )

        # Detail endpoint where clause pre-computation
        if (
            view.has_orm
            and view.method == "get"
            and view.response_shape != "list"
            and view.target
        ):
            where_clauses = []
            for pp in view.path_params:
                if pp.field:
                    where_clauses.append(
                        f"{view.orm_class}.{pp.field} == {pp.snake_name}"
                    )
                else:
                    where_clauses.append(
                        f"{view.orm_class}.{pp.snake_name} == {pp.snake_name}"
                    )
            view.detail_where = ", ".join(where_clauses)


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
                prepared_models.extend(split_model_schemas(model, input_api.objects))
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
        optional_names = {str(f.name) for f in model.fields if f.nullable}
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

    # Build ORM maps for view enrichment
    orm_model_map = None
    orm_pk_map = None
    if database_config and orm_models:
        orm_model_map = {m.source_model: m.class_name for m in orm_models}
        orm_model_map.update(
            {f"{m.source_model}Response": m.class_name for m in orm_models}
        )
        orm_pk_map = {
            f.name: m.class_name for m in orm_models for f in m.fields if f.primary_key
        }

    # Enrich views with pre-computed template data
    _enrich_views(prepared_views, database_config, orm_model_map, orm_pk_map)

    # Compute view import data
    (
        view_model_names,
        view_orm_names,
        has_path_params,
        has_query_params,
        has_no_response,
    ) = _compute_view_imports(prepared_views, orm_model_map, orm_pk_map)

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
        view_model_names=view_model_names,
        view_orm_names=view_orm_names,
        has_path_params=has_path_params,
        has_query_params=has_query_params,
        has_no_response=has_no_response,
        pydantic_imports=_compute_pydantic_imports(prepared_models),
    )
