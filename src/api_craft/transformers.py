"""Transformers for input models to template models."""

import re
from typing import Any, Dict, List

from src.api_craft.models.input import (
    InputAPI,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputView,
)
from src.api_craft.models.template import (
    TemplateAPI,
    TemplateAPIConfig,
    TemplateField,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateRequest,
    TemplateResponse,
    TemplateView,
)
from src.api_craft.placeholders import (
    generate_bool,
    generate_datetime,
    generate_float,
    generate_int,
    generate_string,
)
from src.api_craft.utils import (
    add_spaces_to_camel_case,
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


def derive_view_camel_name(
    input_view: InputView,
    response_name: str | None,
    request_name: str | None,
) -> str:
    """Derive a CamelCase view name using referenced objects and route metadata.

    :param input_view: Original view definition from the input spec.
    :param response_name: Response object name, if any.
    :param request_name: Request object name, if any.
    :returns: CamelCase operation name used for templates.
    """

    def _strip_suffix(name: str, suffix: str) -> str:
        return name[: -len(suffix)] if name.endswith(suffix) else name

    for candidate in (response_name, request_name):
        if candidate:
            base = _strip_suffix(candidate, "Response")
            base = _strip_suffix(base, "Request")
            if base:
                return remove_duplicates(base)

    method = input_view.method.lower()
    parts = [segment for segment in input_view.path.split("/") if segment and not segment.startswith("{")]
    resource = "_".join(parts) or "root"
    return remove_duplicates(snake_to_camel(f"{method}_{resource}"))


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


def clone_fields(fields: List[TemplateField]) -> List[TemplateField]:
    """Deep copy template fields to avoid shared state.

    :param fields: Collection of template fields to clone.
    :returns: New list with cloned :class:`TemplateField` instances.
    """

    return [TemplateField(type=field.type, name=field.name, required=field.required) for field in fields]


def build_request_model(
    request_name: str | None,
    field_map: Dict[str, List[TemplateField]],
) -> TemplateRequest | None:
    """Create a :class:`TemplateRequest` from a shared object name.

    :param request_name: Name of the request object reference.
    :param field_map: Registry of transformed object fields.
    :returns: Instance of :class:`TemplateRequest` or ``None`` when no request is declared.
    :raises ValueError: If the requested object is not defined.
    """

    if not request_name:
        return None

    if request_name not in field_map:
        raise ValueError(f"Request object '{request_name}' is not declared")

    return TemplateRequest(name=request_name, fields=clone_fields(field_map[request_name]))


def build_response_model(
    response_name: str,
    field_map: Dict[str, List[TemplateField]],
    generate_placeholders: bool,
) -> TemplateResponse:
    """Create a :class:`TemplateResponse` from a shared object name.

    :param response_name: Name of the response object reference.
    :param field_map: Registry of transformed object fields.
    :param generate_placeholders: Flag controlling placeholder generation.
    :returns: Instance of :class:`TemplateResponse` with optional placeholders.
    :raises ValueError: If the response object is not declared.
    """

    if response_name not in field_map:
        raise ValueError(f"Response object '{response_name}' is not declared")

    fields = clone_fields(field_map[response_name])
    placeholder_values = None
    if generate_placeholders:
        placeholder_values = generate_model_placeholder(
            response_name,
            fields,
            index=1,
            field_map=field_map,
        )

    return TemplateResponse(name=response_name, fields=fields, placeholder_values=placeholder_values)


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

    request_name = normalize_reference_name(input_view.request)

    if input_view.name:
        camel_name = remove_duplicates(input_view.name)
    else:
        camel_name = derive_view_camel_name(input_view, response_name, request_name)
    snake_name = camel_to_snake(camel_name)

    return TemplateView(
        snake_name=snake_name,
        camel_name=camel_name,
        path=input_view.path,
        method=input_view.method.lower(),
        response=build_response_model(response_name, field_map, generate_placeholders),
        request=build_request_model(request_name, field_map),
        query_params=transform_query_params(input_view.query_params),
        path_params=transform_path_params(input_view.path_params),
    )


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transform an :class:`InputAPI` instance to a :class:`TemplateAPI` instance."""

    object_map = {model.name: model for model in input_api.objects}
    field_map = {
        name: [transform_field(field, object_map) for field in model.fields] for name, model in object_map.items()
    }

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
        spaced_name=add_spaces_to_camel_case(input_api.name),
        version=input_api.version,
        views=transformed_views,
        author=input_api.author,
        description=input_api.description,
        config=TemplateAPIConfig(
            healthcheck=input_api.config.healthcheck,
            response_placeholders=input_api.config.response_placeholders,
        ),
    )
