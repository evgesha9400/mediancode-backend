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
    TemplateORMField,
    TemplateORMModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateResolvedFieldValidator,
    TemplateResolvedModelValidator,
    TemplateTag,
    TemplateValidator,
    TemplateView,
)
from api_craft.placeholders import PlaceholderGenerator
from api_craft.utils import (
    add_spaces_to_camel_case,
    camel_to_kebab,
    camel_to_snake,
    remove_duplicates,
    snake_to_camel,
    snake_to_plural,
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


def transform_field(input_field: InputField) -> TemplateField:
    """Transform an :class:`InputField` into a :class:`TemplateField`.

    :param input_field: Source field definition.
    :returns: Template-ready field definition with resolved types.
    """
    validators = [transform_validator(v) for v in input_field.validators]
    field_validators = [
        transform_resolved_field_validator(v) for v in input_field.field_validators
    ]
    return TemplateField(
        type=input_field.type,
        name=input_field.name,
        optional=input_field.optional,
        description=input_field.description,
        default_value=input_field.default_value,
        validators=validators,
        field_validators=field_validators,
    )


def transform_model(input_model: InputModel) -> TemplateModel:
    """Convert an :class:`InputModel` to a :class:`TemplateModel`."""
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
) -> list[TemplateQueryParam]:
    return (
        [
            TemplateQueryParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=snake_to_camel(param.name),
                optional=param.optional,
                description=param.description,
            )
            for param in input_query_params
        ]
        if input_query_params
        else []
    )


def transform_path_params(
    input_path_params: list[InputPathParam],
) -> list[TemplatePathParam]:
    return (
        [
            TemplatePathParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=add_spaces_to_camel_case(snake_to_camel(param.name)),
                description=param.description,
            )
            for param in input_path_params
        ]
        if input_path_params
        else []
    )


def transform_endpoint(
    input_endpoint: InputEndpoint,
    placeholder_generator: PlaceholderGenerator,
    generate_placeholders: bool = False,
) -> TemplateView:
    """Transform an :class:`InputEndpoint` into a :class:`TemplateView`.

    :param input_endpoint: Source endpoint definition.
    :param placeholder_generator: Generator for creating placeholder response data.
    :param generate_placeholders: Whether to generate placeholder response values.
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

    return TemplateView(
        snake_name=snake_name,
        camel_name=camel_name,
        path=input_endpoint.path,
        method=input_endpoint.method.lower(),
        response_model=response_name,
        request_model=request_name,
        response_placeholders=response_placeholders,
        query_params=transform_query_params(input_endpoint.query_params),
        path_params=transform_path_params(input_endpoint.path_params),
        tag=input_endpoint.tag,
        description=input_endpoint.description,
        use_envelope=input_endpoint.use_envelope,
        response_shape=input_endpoint.response_shape,
    )


ON_DELETE_MAP = {
    "cascade": "CASCADE",
    "restrict": "RESTRICT",
    "set_null": "SET NULL",
}


def _get_max_length(validators):
    """Extract max_length value from validators list."""
    for v in validators:
        if v.name == "max_length" and v.params and "value" in v.params:
            return v.params["value"]
    return None


def map_column_type(type_str: str, validators: list) -> str | None:
    """Map a Python type string to a SQLAlchemy column type string.

    Returns None for types that cannot be mapped to columns (List, Dict, model refs).
    """
    # Skip collection types
    if type_str.startswith(("List[", "Dict[", "Set[", "Tuple[")):
        return None

    base = type_str.split(".")[0] if "." in type_str else type_str

    type_map = {
        "str": lambda: (
            f"String({ml})" if (ml := _get_max_length(validators)) else "Text"
        ),
        "int": lambda: "Integer",
        "float": lambda: "Float",
        "bool": lambda: "Boolean",
        "datetime": lambda: "DateTime",
        "date": lambda: "Date",
        "time": lambda: "Time",
        "uuid": lambda: "Uuid",
        "UUID": lambda: "Uuid",
        "Decimal": lambda: "Numeric",
        "decimal": lambda: "Numeric",
        "EmailStr": lambda: "String(320)",
        "HttpUrl": lambda: "Text",
    }

    factory = type_map.get(base)
    if factory is None:
        return None
    return factory()


def transform_orm_models(input_models: list[InputModel]) -> list[TemplateORMModel]:
    """Convert InputModels with pk fields into TemplateORMModels."""
    # Build entity lookup: name -> (table_name, pk_column_name)
    entity_lookup = {}
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if pk_fields:
            table_name = snake_to_plural(camel_to_snake(model.name))
            entity_lookup[str(model.name)] = (table_name, str(pk_fields[0].name))

    orm_models = []
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if not pk_fields:
            continue

        table_name = snake_to_plural(camel_to_snake(model.name))
        orm_fields = []

        for field in model.fields:
            column_type = map_column_type(field.type, field.validators)
            if column_type is None:
                continue

            base_type = field.type.split(".")[0] if "." in field.type else field.type
            python_type = base_type if not field.optional else f"{base_type} | None"

            foreign_key = None
            on_delete = None
            if field.fk and field.fk in entity_lookup:
                target_table, target_pk = entity_lookup[field.fk]
                foreign_key = f"{target_table}.{target_pk}"
                on_delete = ON_DELETE_MAP.get(field.on_delete, "RESTRICT")

            orm_fields.append(
                TemplateORMField(
                    name=str(field.name),
                    python_type=python_type,
                    column_type=column_type,
                    primary_key=field.pk,
                    nullable=field.optional,
                    autoincrement=field.pk and field.type in ("int",),
                    foreign_key=foreign_key,
                    on_delete=on_delete,
                )
            )

        orm_models.append(
            TemplateORMModel(
                class_name=f"{model.name}Record",
                table_name=table_name,
                source_model=str(model.name),
                fields=orm_fields,
            )
        )

    return orm_models


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transform an :class:`InputAPI` instance to a :class:`TemplateAPI` instance."""
    template_models = [transform_model(model) for model in input_api.objects]

    # Build field map and extract fields referenced by model validators
    field_map = {model.name: model.fields for model in template_models}
    field_names_per_model = {
        model.name: {f.name for f in model.fields} for model in template_models
    }
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
            validator_fields[model.name] = referenced
    placeholder_generator = PlaceholderGenerator(field_map, validator_fields)

    transformed_views = [
        transform_endpoint(
            endpoint,
            placeholder_generator,
            generate_placeholders=input_api.config.response_placeholders,
        )
        for endpoint in input_api.endpoints
    ]

    template_tags = [transform_tag(tag) for tag in input_api.tags]

    orm_models = []
    database_config = None
    if input_api.config.database.enabled:
        orm_models = transform_orm_models(input_api.objects)
        if not orm_models:
            raise ValueError(
                "Database generation requires at least one object with a primary key field. "
                "Mark a field as PK on your objects, or disable database generation."
            )
        snake_name = camel_to_snake(input_api.name)
        database_config = TemplateDatabaseConfig(
            enabled=True,
            seed_data=input_api.config.database.seed_data,
            default_url=f"postgresql+asyncpg://postgres:postgres@localhost:5432/{snake_name}",
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
            format_code=input_api.config.format_code,
            generate_swagger=input_api.config.generate_swagger,
        ),
        orm_models=orm_models,
        database_config=database_config,
    )
