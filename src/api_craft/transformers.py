# src/api_craft/transformers.py
"""Transformers for input models to template models."""

import re

from api_craft.models.input import (
    InputAPI,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputResolvedFieldValidator,
    InputResolvedModelValidator,
    InputTag,
    InputValidator,
)
from api_craft.models.template import (
    TemplateAPI,
    TemplateAPIConfig,
    TemplateDatabaseConfig,
    TemplateField,
    TemplateModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateResolvedFieldValidator,
    TemplateResolvedModelValidator,
    TemplateTag,
    TemplateValidator,
    TemplateView,
)
from api_craft.orm_builder import transform_orm_models
from api_craft.placeholders import PlaceholderGenerator
from api_craft.schema_splitter import _has_appears_flags, split_model_schemas
from api_craft.utils import (
    add_spaces_to_camel_case,
    camel_to_kebab,
    camel_to_snake,
    remove_duplicates,
    snake_to_camel,
)


def transform_validator(input_validator: InputValidator) -> TemplateValidator:
    """Transform an :class:`InputValidator` into a :class:`TemplateValidator`.

    :param input_validator: Source validator definition.
    :returns: Template-ready validator definition.
    """
    return TemplateValidator(name=input_validator.name, params=input_validator.params)


def transform_resolved_field_validator(
    v: InputResolvedFieldValidator,
) -> TemplateResolvedFieldValidator:
    """Transform an :class:`InputResolvedFieldValidator` into a :class:`TemplateResolvedFieldValidator`.

    :param v: Source resolved field validator.
    :returns: Template-ready resolved field validator.
    """
    return TemplateResolvedFieldValidator(
        function_name=v.function_name,
        mode=v.mode,
        function_body=v.function_body,
    )


def transform_resolved_model_validator(
    v: InputResolvedModelValidator,
) -> TemplateResolvedModelValidator:
    """Transform an :class:`InputResolvedModelValidator` into a :class:`TemplateResolvedModelValidator`.

    :param v: Source resolved model validator.
    :returns: Template-ready resolved model validator.
    """
    return TemplateResolvedModelValidator(
        function_name=v.function_name,
        mode=v.mode,
        function_body=v.function_body,
    )


def transform_field(
    input_field: InputField, *, force_optional: bool = False
) -> TemplateField:
    """Transform an :class:`InputField` into a :class:`TemplateField`.

    :param input_field: Source field definition.
    :param force_optional: If True, mark the field as optional (for Update schemas).
    :returns: Template-ready field definition with resolved types.
    """
    validators = [transform_validator(v) for v in input_field.validators]
    field_validators = [
        transform_resolved_field_validator(v) for v in input_field.field_validators
    ]
    return TemplateField(
        type=input_field.type,
        name=input_field.name,
        optional=force_optional or input_field.optional,
        description=input_field.description,
        default_value=input_field.default_value,
        validators=validators,
        field_validators=field_validators,
        pk=input_field.pk,
    )


def transform_model(input_model: InputModel) -> TemplateModel:
    """Convert an :class:`InputModel` to a single :class:`TemplateModel` (legacy, all fields)."""
    transformed_fields = [transform_field(field) for field in input_model.fields]
    model_validators = [
        transform_resolved_model_validator(v) for v in input_model.model_validators
    ]
    return TemplateModel(
        name=input_model.name,
        fields=transformed_fields,
        description=input_model.description,
        model_validators=model_validators,
    )


def transform_tag(input_tag: InputTag) -> TemplateTag:
    """Convert an :class:`InputTag` to a :class:`TemplateTag`."""
    return TemplateTag(name=input_tag.name, description=input_tag.description)


def transform_query_params(
    input_query_params: list[InputQueryParam],
    target_fields: dict[str, InputField] | None = None,
) -> list[TemplateQueryParam]:
    if not input_query_params:
        return []
    result = []
    pagination_index = 0
    pagination_roles = ["limit", "offset"]
    for param in input_query_params:
        param_type = param.type
        optional = param.optional
        pagination_role = None

        # Derive type from target field when field is set
        if param.field and target_fields and param.field in target_fields:
            field_type = target_fields[param.field].type
            if param.operator == "in":
                param_type = f"List[{field_type}]"
            else:
                param_type = field_type
            # All field-based query params are optional
            optional = True
        elif param.pagination:
            # Pagination params keep declared type, forced optional
            optional = True
            # Assign role by position: first pagination param = limit, second = offset
            if pagination_index < len(pagination_roles):
                pagination_role = pagination_roles[pagination_index]
            pagination_index += 1

        result.append(
            TemplateQueryParam(
                type=param_type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=snake_to_camel(param.name),
                optional=optional,
                description=param.description,
                field=param.field,
                operator=param.operator,
                pagination=param.pagination,
                pagination_role=pagination_role,
            )
        )
    return result


def transform_path_params(
    input_path_params: list[InputPathParam],
    target_fields: dict[str, InputField] | None = None,
) -> list[TemplatePathParam]:
    if not input_path_params:
        return []
    result = []
    for param in input_path_params:
        param_type = param.type
        # Derive type from target field when field is set
        if param.field and target_fields and param.field in target_fields:
            param_type = target_fields[param.field].type

        result.append(
            TemplatePathParam(
                type=param_type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=add_spaces_to_camel_case(snake_to_camel(param.name)),
                description=param.description,
                field=param.field,
            )
        )
    return result


def transform_endpoint(
    input_endpoint: InputEndpoint,
    placeholder_generator: PlaceholderGenerator,
    generate_placeholders: bool = False,
    objects_by_name: dict[str, InputModel] | None = None,
) -> TemplateView:
    """Transform an :class:`InputEndpoint` into a :class:`TemplateView`.

    :param input_endpoint: Source endpoint definition.
    :param placeholder_generator: Generator for creating placeholder response data.
    :param generate_placeholders: Whether to generate placeholder response values.
    :param objects_by_name: Map of object names to InputModel for type derivation.
    :returns: Template-ready view definition.
    """
    response_name = input_endpoint.response
    if response_name and response_name not in placeholder_generator.models:
        raise ValueError(f"Response object '{response_name}' is not declared")

    request_name = input_endpoint.request
    if request_name and request_name not in placeholder_generator.models:
        raise ValueError(f"Request object '{request_name}' is not declared")

    camel_name = remove_duplicates(input_endpoint.name)
    if not camel_name:
        raise ValueError(
            f"Endpoint name '{input_endpoint.name}' resolved to an empty identifier"
        )
    snake_name = camel_to_snake(camel_name)

    response_placeholders = None
    if generate_placeholders and response_name:
        response_placeholders = placeholder_generator.generate_for_model(response_name)

    # Resolve target object fields for type derivation
    target_fields: dict[str, InputField] | None = None
    target_name: str | None = input_endpoint.target
    if objects_by_name:
        if input_endpoint.response_shape == "object" and not target_name:
            target_name = input_endpoint.response
        if target_name and target_name in objects_by_name:
            target_obj = objects_by_name[target_name]
            target_fields = {str(f.name): f for f in target_obj.fields}

    return TemplateView(
        snake_name=snake_name,
        camel_name=camel_name,
        path=input_endpoint.path,
        method=input_endpoint.method.lower(),
        response_model=response_name,
        request_model=request_name,
        response_placeholders=response_placeholders,
        query_params=transform_query_params(input_endpoint.query_params, target_fields),
        path_params=transform_path_params(input_endpoint.path_params, target_fields),
        tag=input_endpoint.tag,
        description=input_endpoint.description,
        use_envelope=input_endpoint.use_envelope,
        response_shape=input_endpoint.response_shape,
        target=target_name,
    )


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transform an :class:`InputAPI` instance to a :class:`TemplateAPI` instance."""
    use_split = _has_appears_flags(input_api)

    if use_split:
        # Derive Create/Update/Response schemas per object
        template_models = []
        for model in input_api.objects:
            template_models.extend(split_model_schemas(model))
    else:
        template_models = [transform_model(model) for model in input_api.objects]

    # Build field map for placeholder generation.
    # Placeholders are keyed by the base object name (used in InputEndpoint.response).
    if use_split:
        field_map = {}
        for model in template_models:
            # Use Response schema fields for placeholder generation, keyed by base name
            if model.name.endswith("Response"):
                base_name = model.name.removesuffix("Response")
                field_map[base_name] = model.fields
    else:
        field_map = {model.name: model.fields for model in template_models}

    # For before-mode model validators (e.g. At Least One Required),
    # include the first referenced optional field so placeholders are valid.
    validator_fields: dict[str, set[str]] = {}
    for model in template_models:
        referenced: set[str] = set()
        optional_names = {f.name for f in model.fields if f.optional}
        for mv in model.model_validators:
            if mv.mode != "before":
                continue
            for match in re.finditer(r'data\.get\(["\'](\w+)["\']\)', mv.function_body):
                name = match.group(1)
                if name in optional_names:
                    referenced.add(name)
                    break  # one field per validator suffices
        if referenced:
            # Use base name for split mode so it matches field_map keys
            key = model.name
            if use_split and key.endswith("Create"):
                key = key.removesuffix("Create")
            validator_fields[key] = referenced
    placeholder_generator = PlaceholderGenerator(field_map, validator_fields)

    # Build objects lookup for type derivation
    objects_by_name = {str(obj.name): obj for obj in input_api.objects}

    # Transform endpoints, remapping model names to derived schemas
    transformed_views = []
    for endpoint in input_api.endpoints:
        view = transform_endpoint(
            endpoint,
            placeholder_generator,
            generate_placeholders=input_api.config.response_placeholders,
            objects_by_name=objects_by_name,
        )
        if use_split:
            # Remap request_model → Create/Update, response_model → Response
            if view.request_model:
                base_name = view.request_model
                if endpoint.method in ("PUT", "PATCH"):
                    view = view.model_copy(
                        update={"request_model": f"{base_name}Update"}
                    )
                else:
                    view = view.model_copy(
                        update={"request_model": f"{base_name}Create"}
                    )
            if view.response_model:
                base_name = view.response_model
                view = view.model_copy(
                    update={"response_model": f"{base_name}Response"}
                )
        transformed_views.append(view)

    template_tags = [transform_tag(tag) for tag in input_api.tags]

    orm_models = []
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

    return TemplateAPI(
        snake_name=camel_to_snake(input_api.name),
        camel_name=input_api.name,
        kebab_name=camel_to_kebab(input_api.name),
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        models=template_models,
        views=transformed_views,
        tags=template_tags,
        author=input_api.author,
        description=input_api.description,
        config=TemplateAPIConfig(
            healthcheck=input_api.config.healthcheck,
            response_placeholders=input_api.config.response_placeholders,
        ),
        orm_models=orm_models,
        database_config=database_config,
    )
