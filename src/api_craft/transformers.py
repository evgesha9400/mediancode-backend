# src/api_craft/transformers.py
"""Transformers for input models to template models."""

import re

from api.schemas.literals import FieldAppearance
from api_craft.models.input import (
    InputAPI,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputRelationship,
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
    TemplateRelationship,
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


def _filter_fields_by_appears(
    fields: list[InputField], allowed: set[FieldAppearance]
) -> list[InputField]:
    """Filter fields by their `appears` value."""
    return [f for f in fields if f.appears in allowed]


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


def split_model_schemas(input_model: InputModel) -> list[TemplateModel]:
    """Split an InputModel into Create, Update, and Response TemplateModels.

    - Create: fields with appears in (both, request), PK excluded
    - Update: same as Create but all fields optional
    - Response: fields with appears in (both, response), PK included
    """
    model_validators = [
        transform_resolved_model_validator(v) for v in input_model.model_validators
    ]

    # Create fields: non-PK, appears in request
    create_input_fields = [
        f for f in input_model.fields if f.appears in ("both", "request") and not f.pk
    ]
    create_fields = [transform_field(f) for f in create_input_fields]

    # Update fields: same selection as Create but all optional
    update_fields = [
        transform_field(f, force_optional=True) for f in create_input_fields
    ]

    # Response fields: appears in response (PK included)
    response_input_fields = [
        f for f in input_model.fields if f.appears in ("both", "response")
    ]
    response_fields = [transform_field(f) for f in response_input_fields]

    # Add FK ID fields for `references` relationships
    for rel in input_model.relationships:
        if rel.cardinality == "references":
            fk_name = f"{rel.name}_id"
            # Avoid duplicating if the field already exists
            existing_names = {f.name for f in response_fields}
            if fk_name not in existing_names:
                response_fields.append(
                    TemplateField(
                        type="uuid",
                        name=fk_name,
                        optional=False,
                        description=f"FK reference to {rel.target_model}",
                    )
                )

    return [
        TemplateModel(
            name=f"{input_model.name}Create",
            fields=create_fields,
            description=input_model.description,
            model_validators=model_validators,
        ),
        TemplateModel(
            name=f"{input_model.name}Update",
            fields=update_fields,
            description=input_model.description,
            model_validators=[],
        ),
        TemplateModel(
            name=f"{input_model.name}Response",
            fields=response_fields,
            description=input_model.description,
            model_validators=[],
        ),
    ]


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


# Map input type names to Python type annotations for Mapped[].
# Keys match the canonical python_type values from the system types table.
# The fallback in transform_orm_models splits qualified names on "." and
# retries with the base module (e.g. "decimal.Decimal" → "decimal"), so
# entries like "datetime.date" are required to avoid resolving to the
# wrong base entry ("datetime" → "datetime.datetime").
ORM_PYTHON_TYPE_MAP = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "datetime": "datetime.datetime",
    "datetime.date": "datetime.date",
    "datetime.time": "datetime.time",
    "uuid": "uuid.UUID",
    "decimal": "decimal.Decimal",
    "EmailStr": "str",
    "HttpUrl": "str",
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

    type_map = {
        "str": lambda: (
            f"String({ml})" if (ml := _get_max_length(validators)) else "Text"
        ),
        "int": lambda: "Integer",
        "float": lambda: "Float",
        "bool": lambda: "Boolean",
        "datetime": lambda: "DateTime(timezone=True)",
        "datetime.date": lambda: "Date",
        "datetime.time": lambda: "Time",
        "uuid": lambda: "Uuid",
        "decimal": lambda: "Numeric",
        "EmailStr": lambda: "String(320)",
        "HttpUrl": lambda: "Text",
    }

    # Try full qualified name first (e.g. "datetime.date"), then base module name
    factory = type_map.get(type_str)
    if factory is None:
        base = type_str.split(".")[0] if "." in type_str else type_str
        factory = type_map.get(base)
    if factory is None:
        return None
    return factory()


def _make_association_table_name(table_a: str, table_b: str) -> str:
    """Build a deterministic association table name for many_to_many.

    Sorts the two table names alphabetically to ensure the same name
    regardless of which side declares the relationship.

    :param table_a: First table name.
    :param table_b: Second table name.
    :returns: Association table name.
    """
    return "_".join(sorted([table_a, table_b]))


def transform_orm_models(input_models: list[InputModel]) -> list[TemplateORMModel]:
    """Convert InputModels with pk fields into TemplateORMModels."""
    # Build entity lookup: name -> (table_name, pk_column_name, class_name)
    entity_lookup: dict[str, tuple[str, str, str]] = {}
    for model in input_models:
        pk_fields = [f for f in model.fields if f.pk]
        if pk_fields:
            table_name = snake_to_plural(camel_to_snake(model.name))
            class_name = f"{model.name}Record"
            entity_lookup[str(model.name)] = (
                table_name,
                str(pk_fields[0].name),
                class_name,
            )

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
            orm_type = ORM_PYTHON_TYPE_MAP.get(field.type) or ORM_PYTHON_TYPE_MAP.get(
                base_type, base_type
            )
            python_type = orm_type if not field.optional else f"{orm_type} | None"

            is_uuid_pk = field.pk and base_type in ("uuid", "UUID")
            orm_fields.append(
                TemplateORMField(
                    name=str(field.name),
                    python_type=python_type,
                    column_type=column_type,
                    primary_key=field.pk,
                    nullable=field.optional,
                    autoincrement=field.pk and base_type in ("int",),
                    uuid_default=is_uuid_pk,
                )
            )

        # Transform relationships
        template_rels = []
        for rel in model.relationships:
            target_info = entity_lookup.get(rel.target_model)
            if not target_info:
                continue
            target_table, target_pk, target_class = target_info

            fk_column = None
            association_table = None

            if rel.cardinality == "references":
                # Add FK column to this model's fields
                fk_col_name = f"{rel.name}_id"
                # Determine FK column type from target PK
                target_model = next(
                    (m for m in input_models if str(m.name) == rel.target_model),
                    None,
                )
                if target_model:
                    target_pk_field = next(
                        (f for f in target_model.fields if f.pk), None
                    )
                    if target_pk_field:
                        fk_col_type = map_column_type(
                            target_pk_field.type, target_pk_field.validators
                        )
                        fk_base = (
                            target_pk_field.type.split(".")[0]
                            if "." in target_pk_field.type
                            else target_pk_field.type
                        )
                        fk_orm_type = ORM_PYTHON_TYPE_MAP.get(
                            target_pk_field.type
                        ) or ORM_PYTHON_TYPE_MAP.get(fk_base, fk_base)
                        if fk_col_type:
                            orm_fields.append(
                                TemplateORMField(
                                    name=fk_col_name,
                                    python_type=fk_orm_type,
                                    column_type=fk_col_type,
                                    foreign_key=f"{target_table}.{target_pk}",
                                )
                            )
                fk_column = fk_col_name

            elif rel.cardinality == "many_to_many":
                association_table = _make_association_table_name(
                    table_name, target_table
                )

            template_rels.append(
                TemplateRelationship(
                    name=rel.name,
                    target_model=rel.target_model,
                    target_class_name=target_class,
                    cardinality=rel.cardinality,
                    is_inferred=rel.is_inferred,
                    fk_column=fk_column,
                    association_table=association_table,
                )
            )

        orm_models.append(
            TemplateORMModel(
                class_name=f"{model.name}Record",
                table_name=table_name,
                source_model=str(model.name),
                fields=orm_fields,
                relationships=template_rels,
            )
        )

    return orm_models


def _has_appears_flags(input_api: InputAPI) -> bool:
    """Check if any field in the API uses non-default appears flags or has pk=True."""
    for model in input_api.objects:
        for field in model.fields:
            if field.appears != "both" or field.pk:
                return True
    return False


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

    # Transform endpoints, remapping model names to derived schemas
    transformed_views = []
    for endpoint in input_api.endpoints:
        view = transform_endpoint(
            endpoint,
            placeholder_generator,
            generate_placeholders=input_api.config.response_placeholders,
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
