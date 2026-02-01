"""Transformers for input models to template models."""

from typing import Any, Dict, List

from api_craft.models.input import (
    InputAPI,
    InputEndpoint,
    InputField,
    InputModel,
    InputPathParam,
    InputQueryParam,
    InputTag,
    InputValidator,
)
from api_craft.models.template import (
    TemplateAPI,
    TemplateAPIConfig,
    TemplateField,
    TemplateModel,
    TemplatePathParam,
    TemplateQueryParam,
    TemplateTag,
    TemplateValidator,
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


def extract_validator_constraints(validators: List[TemplateValidator]) -> Dict[str, Any]:
    """Extract constraint values from validators into a lookup dict.

    :param validators: List of validators to process.
    :returns: Dictionary mapping constraint names to their values.
    """
    constraints = {}
    for v in validators:
        if v.params and "value" in v.params:
            constraints[v.name] = v.params["value"]
    return constraints


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
        if not field.required:
            # Skip optional fields in placeholders to avoid validation issues
            continue
        payload[field.name] = generate_placeholder_value(
            field.type,
            index + offset - 1,
            field_map,
            visited,
            extract_validator_constraints(field.validators),
        )
    visited.remove(model_name)
    return payload


def generate_placeholder_value(
    field_type: str,
    index: int,
    field_map: Dict[str, List[TemplateField]],
    visited: set[str],
    constraints: Dict[str, Any] | None = None,
) -> Any:
    """Generate a placeholder value based on the field type and constraints.

    :param field_type: Resolved Python type annotation.
    :param index: Seed index used for deterministic outputs.
    :param field_map: Registry of known models for nested references.
    :param visited: Tracking set to avoid circular references.
    :param constraints: Validator constraints (min_length, max_length, ge, le, etc.).
    :returns: Placeholder value compatible with the declared type and constraints.
    """
    if constraints is None:
        constraints = {}

    if field_type.startswith("List[") and field_type.endswith("]"):
        inner_type = field_type[5:-1]
        return [
            generate_placeholder_value(inner_type, item_index, field_map, visited)
            for item_index in range(index, index + 2)
        ]

    if field_type in field_map and field_type not in visited:
        return generate_model_placeholder(field_type, field_map[field_type], index, field_map, visited)

    # Generate constraint-aware values
    if field_type == "str":
        return generate_constrained_string(index, constraints)
    elif field_type == "int":
        return generate_constrained_int(index, constraints)
    elif field_type == "float":
        return generate_constrained_float(index, constraints)
    elif field_type == "bool":
        return generate_bool(index)
    elif field_type == "datetime.datetime":
        return generate_datetime(index)

    return generate_string(index, f"example_{field_type.lower()}")


def generate_constrained_string(index: int, constraints: Dict[str, Any]) -> str:
    """Generate a string that satisfies length and pattern constraints."""
    pattern = constraints.get("pattern")
    min_len = constraints.get("min_length", 1)
    max_len = constraints.get("max_length", 100)

    if pattern:
        # For common patterns, generate matching values
        if pattern in ("^[A-Z0-9-]+$", "^[A-Z0-9]+$"):
            base = f"SKU-{index:03d}"
            return base[:max_len]
        elif "email" in pattern.lower() or "@" in pattern:
            return f"user{index}@example.com"[:max_len]
        # Default: alphanumeric uppercase
        return f"VALUE{index:03d}"[:max_len]

    # No pattern, just respect length constraints
    base = f"example {index}"
    if len(base) < min_len:
        base = base + "x" * (min_len - len(base))
    return base[:max_len]


def generate_constrained_int(index: int, constraints: Dict[str, Any]) -> int:
    """Generate an integer that satisfies numeric constraints."""
    ge = constraints.get("ge")
    gt = constraints.get("gt")
    le = constraints.get("le")
    lt = constraints.get("lt")
    multiple_of = constraints.get("multiple_of")

    # Determine valid range
    min_val = 0
    if ge is not None:
        min_val = ge
    elif gt is not None:
        min_val = gt + 1

    max_val = 1000000
    if le is not None:
        max_val = le
    elif lt is not None:
        max_val = lt - 1

    # Start with a value in range
    value = min_val + index
    if value > max_val:
        value = min_val

    # Adjust for multiple_of constraint
    if multiple_of:
        # Round up to nearest multiple
        remainder = value % multiple_of
        if remainder != 0:
            value = value + (multiple_of - remainder)
        # If we exceeded max, go back to min multiple
        if value > max_val:
            value = min_val
            remainder = value % multiple_of
            if remainder != 0:
                value = value + (multiple_of - remainder)

    return value


def generate_constrained_float(index: int, constraints: Dict[str, Any]) -> float:
    """Generate a float that satisfies numeric constraints."""
    ge = constraints.get("ge")
    gt = constraints.get("gt")
    le = constraints.get("le")
    lt = constraints.get("lt")

    # Determine valid range
    min_val = 0.0
    if ge is not None:
        min_val = float(ge)
    elif gt is not None:
        min_val = float(gt) + 0.01

    max_val = 1000000.0
    if le is not None:
        max_val = float(le)
    elif lt is not None:
        max_val = float(lt) - 0.01

    # Generate value in range
    value = min_val + (index * 0.5)
    if value > max_val:
        value = (min_val + max_val) / 2

    return round(value, 2)


def transform_validator(input_validator: InputValidator) -> TemplateValidator:
    """Transform an :class:`InputValidator` into a :class:`TemplateValidator`.

    :param input_validator: Source validator definition.
    :returns: Template-ready validator definition.
    """
    return TemplateValidator(name=input_validator.name, params=input_validator.params)


def transform_field(input_field: InputField) -> TemplateField:
    """Transform an :class:`InputField` into a :class:`TemplateField`.

    :param input_field: Source field definition.
    :returns: Template-ready field definition with resolved types.
    """
    validators = [transform_validator(v) for v in input_field.validators]
    return TemplateField(
        type=input_field.type,
        name=input_field.name,
        required=input_field.required,
        description=input_field.description,
        default_value=input_field.default_value,
        validators=validators,
    )


def transform_model(input_model: InputModel) -> TemplateModel:
    """Convert an :class:`InputModel` to a :class:`TemplateModel`."""

    transformed_fields = [transform_field(field) for field in input_model.fields]
    return TemplateModel(
        name=input_model.name,
        fields=transformed_fields,
        description=input_model.description,
    )


def transform_tag(input_tag: InputTag) -> TemplateTag:
    """Convert an :class:`InputTag` to a :class:`TemplateTag`."""
    return TemplateTag(name=input_tag.name, description=input_tag.description)


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
                description=param.description,
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
                description=param.description,
            )
            for param in input_path_params
        ]
        if input_path_params
        else []
    )


def transform_endpoint(
    input_endpoint: InputEndpoint,
    field_map: Dict[str, List[TemplateField]],
    generate_placeholders: bool = False,
) -> TemplateView:
    """Transform an :class:`InputEndpoint` into a :class:`TemplateView`."""

    response_name = input_endpoint.response
    if not response_name:
        raise ValueError(f"Endpoint at path '{input_endpoint.path}' must declare a response object")

    if response_name not in field_map:
        raise ValueError(f"Response object '{response_name}' is not declared")

    request_name = input_endpoint.request
    if request_name and request_name not in field_map:
        raise ValueError(f"Request object '{request_name}' is not declared")

    camel_name = remove_duplicates(input_endpoint.name)
    if not camel_name:
        raise ValueError(f"Endpoint name '{input_endpoint.name}' resolved to an empty identifier")
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


def transform_api(input_api: InputAPI) -> TemplateAPI:
    """Transform an :class:`InputAPI` instance to a :class:`TemplateAPI` instance."""

    template_models = [transform_model(model) for model in input_api.objects]
    field_map = {template_model.name: template_model.fields for template_model in template_models}

    transformed_views = [
        transform_endpoint(
            endpoint,
            field_map,
            generate_placeholders=input_api.config.response_placeholders,
        )
        for endpoint in input_api.endpoints
    ]

    template_tags = [transform_tag(tag) for tag in input_api.tags]

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
    )
