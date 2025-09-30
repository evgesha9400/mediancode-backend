"""Transformers for input models to template models."""

import re
from typing import Any, Dict, List

from api_craft.models.input import (
    InputAPI,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputView,
)
from api_craft.models.template import (
    TemplateAPI,
    TemplateAPIConfig,
    TemplateField,
    TemplateModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateView,
)
from api_craft.placeholders import (
    generate_bool,
    generate_datetime,
    generate_float,
    generate_int,
    generate_string,
)
from api_craft.utils import (
    add_spaces_to_camel_case,
    camel_to_kebab,
    camel_to_snake,
    remove_duplicates,
    snake_to_camel,
)

REFERENCE_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def normalize_reference_name(reference: str | None) -> str | None:
    """Strip the ``$`` prefix from an object reference.

    :param reference: Raw reference value from the input specification.
    :returns: Clean name without the prefix or ``None`` when the input is falsy.
    """

    if not reference:
        return None
    return reference[1:] if reference.startswith("$") else reference


def resolve_type_annotation(raw_type: str, object_map: Dict[str, InputModel]) -> str:
    """Resolve a type annotation, validating referenced objects.

    :param raw_type: Original type string, potentially containing ``$`` references.
    :param object_map: Mapping of object names declared in ``InputAPI``.
    :returns: Type annotation with resolved object names.
    :raises ValueError: If a referenced object is not declared.
    """

    def _replace(match: re.Match[str]) -> str:
        candidate = match.group(1)
        if candidate not in object_map:
            raise ValueError(f"Unknown object reference: {candidate}")
        return candidate

    return REFERENCE_PATTERN.sub(_replace, raw_type)


def generate_model_placeholder(
    model_name: str,
    fields: List[TemplateField],
    index: int,
    field_map: Dict[str, List[TemplateField]],
    visited: set[str] | None = None,
) -> Dict[str, Any]:
    """Generate placeholder values for a model instance.

    :param model_name: Name of the model being materialised.
    :param fields: Fields that compose the model.
    :param index: Starting index used to generate deterministic values.
    :param field_map: Registry of all known models and their fields.
    :param visited: Set used to break potential recursive references.
    :returns: Dictionary with placeholder values keyed by field name.
    """

    if visited is None:
        visited = set()
    if model_name in visited:
        return {}

    visited.add(model_name)
    payload: Dict[str, Any] = {}
    for offset, field in enumerate(fields, start=1):
        payload[field.name] = generate_placeholder_value(
            field.type,
            index + offset - 1,
            field_map,
            visited,
        )
    visited.remove(model_name)
    return payload


def generate_placeholder_value(
    field_type: str,
    index: int,
    field_map: Dict[str, List[TemplateField]],
    visited: set[str],
) -> Any:
    """Generate a placeholder value based on the field type.

    :param field_type: Resolved Python type annotation.
    :param index: Seed index used for deterministic outputs.
    :param field_map: Registry of known models for nested references.
    :param visited: Tracking set to avoid circular references.
    :returns: Placeholder value compatible with the declared type.
    """

    if field_type.startswith("List[") and field_type.endswith("]"):
        inner_type = field_type[5:-1]
        return [
            generate_placeholder_value(inner_type, item_index, field_map, visited)
            for item_index in range(index, index + 2)
        ]

    if field_type in field_map and field_type not in visited:
        return generate_model_placeholder(field_type, field_map[field_type], index, field_map, visited)

    type_mapping = {
        "str": lambda i: generate_string(i, "example"),
        "int": lambda i: generate_int(i, 1),
        "bool": generate_bool,
        "float": lambda i: generate_float(i, 1.5),
        "datetime.datetime": generate_datetime,
    }

    generator = type_mapping.get(field_type)
    if generator:
        return generator(index)

    return generate_string(index, f"example_{field_type.lower()}")


def transform_field(input_field: InputField, object_map: Dict[str, InputModel]) -> TemplateField:
    """Transform an :class:`InputField` into a :class:`TemplateField`.

    :param input_field: Source field definition.
    :param object_map: Registry of declared objects for resolving references.
    :returns: Template-ready field definition with resolved types.
    """

    resolved_type = resolve_type_annotation(input_field.type, object_map)
    return TemplateField(type=resolved_type, name=input_field.name, required=input_field.required)


def transform_model(input_model: InputModel, object_map: Dict[str, InputModel]) -> TemplateModel:
    """Convert an :class:`InputModel` to a :class:`TemplateModel`."""

    transformed_fields = [transform_field(field, object_map) for field in input_model.fields]
    return TemplateModel(name=input_model.name, fields=transformed_fields)


def transform_query_params(
    input_query_params: List[InputQueryParam],
) -> List[TemplateQueryParam]:
    return (
        [
            TemplateQueryParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=snake_to_camel(param.name),
                required=param.required,
            )
            for param in input_query_params
        ]
        if input_query_params
        else []
    )


def transform_path_params(
    input_path_params: List[InputPathParam],
) -> List[TemplatePathParam]:
    return (
        [
            TemplatePathParam(
                type=param.type,
                snake_name=param.name,
                camel_name=snake_to_camel(param.name),
                title=add_spaces_to_camel_case(snake_to_camel(param.name)),
            )
            for param in input_path_params
        ]
        if input_path_params
        else []
    )


def transform_view(
    input_view: InputView,
    field_map: Dict[str, List[TemplateField]],
    generate_placeholders: bool = False,
) -> TemplateView:
    """Transform an :class:`InputView` into a :class:`TemplateView`."""

    response_name = normalize_reference_name(input_view.response)
    if not response_name:
        raise ValueError(f"View at path '{input_view.path}' must declare a response object")

    if response_name not in field_map:
        raise ValueError(f"Response object '{response_name}' is not declared")

    request_name = normalize_reference_name(input_view.request)
    if request_name and request_name not in field_map:
        raise ValueError(f"Request object '{request_name}' is not declared")

    camel_name = remove_duplicates(input_view.name)
    if not camel_name:
        raise ValueError(f"View name '{input_view.name}' resolved to an empty identifier")
    snake_name = camel_to_snake(camel_name)

    response_placeholders = None
    if generate_placeholders:
        response_placeholders = generate_model_placeholder(
            response_name,
            field_map[response_name],
            index=1,
            field_map=field_map,
        )

    return TemplateView(
        snake_name=snake_name,
        camel_name=camel_name,
        path=input_view.path,
        method=input_view.method.lower(),
        response_model=response_name,
        request_model=request_name,
        response_placeholders=response_placeholders,
        query_params=transform_query_params(input_view.query_params),
        path_params=transform_path_params(input_view.path_params),
    )


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transform an :class:`InputAPI` instance to a :class:`TemplateAPI` instance."""

    object_map = {model.name: model for model in input_api.objects}
    template_models = [transform_model(model, object_map) for model in input_api.objects]
    field_map = {template_model.name: template_model.fields for template_model in template_models}

    transformed_views = [
        transform_view(
            view,
            field_map,
            generate_placeholders=input_api.config.response_placeholders,
        )
        for view in input_api.views
    ]

    return TemplateAPI(
        snake_name=camel_to_snake(input_api.name),
        camel_name=input_api.name,
        kebab_name=camel_to_kebab(input_api.name),
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        models=template_models,
        views=transformed_views,
        author=input_api.author,
        description=input_api.description,
        config=TemplateAPIConfig(
            healthcheck=input_api.config.healthcheck,
            response_placeholders=input_api.config.response_placeholders,
        ),
    )
