"""Validation helpers for :mod:`api_craft.models.input`."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import TYPE_CHECKING

from api_craft.models.validation_catalog import (
    ALLOWED_PK_TYPES,
    DATE_TIME_TYPES,
    NUMERIC_TYPES,
    OPERATOR_VALID_TYPES,
    ORDERED_TYPES,
    SERVER_DEFAULT_VALID_TYPES,
    SNAKE_CASE_PATTERN,
    STRING_TYPES,
)

if TYPE_CHECKING:  # pragma: no cover - imports used for type checking only
    from api_craft.models.input import InputApiConfig, InputEndpoint, InputModel

TYPE_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Supported type identifiers for validation. These are the tokens that appear
# when type annotation strings are tokenized by TYPE_IDENTIFIER_PATTERN:
#   - "datetime.datetime" becomes tokens {"datetime"}
#   - "datetime.date" becomes tokens {"datetime", "date"}
#   - "uuid.UUID" becomes tokens {"uuid", "UUID"}
#   - "List[T]" becomes tokens {"List", "T"}
# Includes all primitive types, module names, and pydantic special types.
SUPPORTED_TYPE_IDENTIFIERS = {
    "str",
    "int",
    "bool",
    "float",
    "datetime",
    "date",
    "time",
    "uuid",
    "UUID",
    "decimal",
    "Decimal",
    "EmailStr",
    "HttpUrl",
    "List",
}


def extract_type_identifiers(type_annotation: str) -> set[str]:
    """Return the identifier tokens present in a type annotation string.

    :param type_annotation: Annotation string declared on an input field.
    :returns: Set of tokens present in the annotation.
    """

    return set(TYPE_IDENTIFIER_PATTERN.findall(type_annotation))


def validate_type_annotation(
    type_annotation: str,
    declared_object_names: set[str],
    *,
    context: str,
) -> None:
    """Ensure all identifiers referenced in an annotation are known.

    :param type_annotation: Annotation string declared on an input field.
    :param declared_object_names: Object identifiers declared in the API specification.
    :param context: Human-readable context used for error reporting.
    :raises ValueError: If an unknown identifier is detected.
    """

    for identifier in extract_type_identifiers(type_annotation):
        if identifier in declared_object_names:
            continue

        if identifier in SUPPORTED_TYPE_IDENTIFIERS:
            continue

        raise ValueError(f"Unknown type reference '{identifier}' in {context}")


def validate_model_field_types(
    objects: Iterable["InputModel"],
    declared_object_names: set[str],
) -> None:
    """Validate the type annotations declared for shared objects.

    :param objects: Collection of shared object definitions.
    :param declared_object_names: Object identifiers declared in the API specification.
    :raises ValueError: If a field uses an unknown identifier.
    """

    for model in objects:
        for field in model.fields:
            validate_type_annotation(
                field.type,
                declared_object_names,
                context=f"field '{field.name}' of object '{model.name}'",
            )


def validate_endpoint_references(
    endpoints: Iterable["InputEndpoint"],
    declared_object_names: set[str],
) -> None:
    """Validate request and response references declared on endpoints.

    :param endpoints: Collection of endpoint definitions.
    :param declared_object_names: Object identifiers declared in the API specification.
    :raises ValueError: If an endpoint references an unknown object.
    """

    for endpoint in endpoints:
        if endpoint.response and endpoint.response not in declared_object_names:
            raise ValueError(
                f"Endpoint '{endpoint.name}' references unknown response '{endpoint.response}'"
            )

        if endpoint.request and endpoint.request not in declared_object_names:
            raise ValueError(
                f"Endpoint '{endpoint.name}' references unknown request '{endpoint.request}'"
            )


PATH_PARAM_PATTERN = re.compile(r"\{([^}]+)\}")


def validate_path_parameters(endpoint: "InputEndpoint") -> None:
    """Validate that path parameters are consistently declared between path and path_params.

    :param endpoint: The input endpoint to validate.
    :raises ValueError: If path parameters don't match bidirectionally.
    """
    # Extract parameters from path using curly braces
    path_params_from_url = set(PATH_PARAM_PATTERN.findall(endpoint.path))

    # Extract parameter names from declared path_params
    declared_path_param_names = set()
    if endpoint.path_params:
        declared_path_param_names = {param.name for param in endpoint.path_params}

    # Check for missing parameters in both directions
    missing_in_declaration = path_params_from_url - declared_path_param_names
    missing_in_path = declared_path_param_names - path_params_from_url

    if missing_in_declaration:
        params_list = ", ".join(sorted(missing_in_declaration))
        raise ValueError(
            f"Endpoint '{endpoint.name}' path '{endpoint.path}' declares parameters {{{params_list}}} but they are not defined in path_params"
        )

    if missing_in_path:
        params_list = ", ".join(sorted(missing_in_path))
        raise ValueError(
            f"Endpoint '{endpoint.name}' declares path_params {{{params_list}}} but they are not present in path '{endpoint.path}'"
        )


PATH_ENDS_WITH_PARAM_PATTERN = re.compile(r"/\{[^}]+\}$")


def validate_response_shape_for_path(endpoint: "InputEndpoint") -> None:
    """Validate that endpoints ending with a path parameter use response_shape 'object'.

    REST convention: a URI ending with ``/{param}`` identifies a single resource,
    so returning a list is semantically invalid.  List endpoints always end with
    the collection name (e.g., ``/products``, ``/stores/{store_id}/products``).

    :param endpoint: The input endpoint to validate.
    :raises ValueError: If the path ends with a path parameter and response_shape is 'list'.
    """
    if PATH_ENDS_WITH_PARAM_PATTERN.search(endpoint.path):
        if endpoint.response_shape == "list":
            raise ValueError(
                f"Endpoint '{endpoint.name}': endpoints ending with a path parameter "
                f"must have response_shape 'object' — list endpoints end with "
                f"the collection name (path: '{endpoint.path}')"
            )


def validate_response_shape_for_method(endpoint: "InputEndpoint") -> None:
    """Validate that only GET endpoints may use response_shape 'list'.

    POST, PUT, PATCH, and DELETE operate on a single resource and always return
    a single object.  Only GET endpoints can return a collection.

    :param endpoint: The input endpoint to validate.
    :raises ValueError: If a non-GET endpoint uses response_shape 'list'.
    """
    if endpoint.method != "GET" and endpoint.response_shape == "list":
        raise ValueError(
            f"Endpoint '{endpoint.name}': list response shape is only valid "
            f"for GET endpoints (method: '{endpoint.method}')"
        )


def validate_unique_object_names(objects: Iterable["InputModel"]) -> None:
    """Validate that all object names are unique within the API specification.

    :param objects: Collection of declared objects.
    :raises ValueError: If duplicate object names are detected.
    """
    seen_names = set()
    duplicates = set()

    for obj in objects:
        if obj.name in seen_names:
            duplicates.add(obj.name)
        else:
            seen_names.add(obj.name)

    if duplicates:
        duplicates_list = ", ".join(sorted(duplicates))
        raise ValueError(
            f"Duplicate object names found: {duplicates_list}. Each object name must be unique."
        )


def validate_primary_keys(objects: Iterable["InputModel"]) -> None:
    """Validate PK constraints: not nullable, at most one per model.

    :param objects: Collection of declared objects.
    :raises ValueError: If PK constraints are violated.
    """
    for obj in objects:
        pk_fields = [f for f in obj.fields if f.pk]
        if len(pk_fields) > 1:
            raise ValueError(
                f"Object '{obj.name}' has multiple primary key fields. "
                f"Composite keys are not supported."
            )
        for field in pk_fields:
            if field.nullable:
                raise ValueError(
                    f"Field '{obj.name}.{field.name}' is a primary key and cannot be nullable"
                )


def validate_pk_field_types(objects: Iterable["InputModel"]) -> None:
    """Validate that PK fields use only supported types (int or uuid).

    :param objects: Collection of declared objects.
    :raises ValueError: If a PK field uses an unsupported type.
    """
    for obj in objects:
        for field in obj.fields:
            if not field.pk:
                continue
            base_type = field.type.split(".")[0] if "." in field.type else field.type
            if base_type not in ALLOWED_PK_TYPES:
                raise ValueError(
                    f"Field '{obj.name}.{field.name}' is a primary key with unsupported type '{field.type}'. "
                    f"Only 'int' and 'uuid' types are allowed for primary keys."
                )


def validate_database_config(
    config: "InputApiConfig",
    objects: Iterable["InputModel"],
) -> None:
    """Validate database generation configuration constraints.

    :param config: API configuration containing database and placeholder settings.
    :param objects: Collection of declared objects.
    :raises ValueError: If database is enabled but no object has a primary key.
    """
    if not config.database.enabled:
        return

    has_any_pk = any(any(field.pk for field in obj.fields) for obj in objects)
    if not has_any_pk:
        raise ValueError(
            "Database generation requires at least one object with a primary key field. "
            "Mark a field as PK on your objects, or disable database generation."
        )


def validate_server_defaults(
    config: "InputApiConfig",
    objects: Iterable["InputModel"],
) -> None:
    """Validate default constraints on fields.

    Rules:

    1. read_only non-PK fields (with DB enabled) must have a default.
    2. Generated strategy must be compatible with the field's type.
    3. isPk=True forces exposure='read_only'.

    :param config: API configuration containing database settings.
    :param objects: Collection of declared objects.
    :raises ValueError: If any constraint is violated.
    """
    for obj in objects:
        for field in obj.fields:
            if field.pk:
                # PK fields must be read_only
                if field.exposure != "read_only":
                    raise ValueError(
                        f"Field '{obj.name}.{field.name}': "
                        f"primary key must be read_only"
                    )
                continue

            # Rule 1: read_only + non-PK + DB enabled → must have a default
            if (
                field.exposure == "read_only"
                and field.default is None
                and config.database.enabled
            ):
                raise ValueError(
                    f"Field '{obj.name}.{field.name}': read_only field "
                    f"has no default. Set a default strategy."
                )

            # Rule 2: generated strategy must match field type
            if field.default and field.default.kind == "generated":
                strategy = field.default.strategy
                base_type = (
                    field.type.split(".")[0] if "." in field.type else field.type
                )
                valid_types = SERVER_DEFAULT_VALID_TYPES.get(strategy, set())
                if base_type not in valid_types:
                    raise ValueError(
                        f"Field '{obj.name}.{field.name}': strategy '{strategy}' "
                        f"is not compatible with type '{field.type}'"
                    )


def _resolve_target(
    endpoint: "InputEndpoint",
    objects_by_name: dict[str, "InputModel"],
) -> "InputModel | None":
    """Resolve the target object for an endpoint.

    Returns None if the endpoint has no field-based params (legacy mode).

    :param endpoint: The endpoint to resolve target for.
    :param objects_by_name: Map of object names to InputModel.
    :returns: The resolved target InputModel, or None for legacy endpoints.
    :raises ValueError: If target cannot be determined or is invalid.
    """
    has_field_params = _has_field_params(endpoint)

    if endpoint.response_shape == "object":
        # Detail endpoint: target is the response model
        if endpoint.target and endpoint.target != endpoint.response:
            raise ValueError(
                f"Endpoint '{endpoint.name}': detail endpoint target '{endpoint.target}' "
                f"must match response '{endpoint.response}'"
            )
        target_name = endpoint.target or endpoint.response
    else:
        # List endpoint: target must be explicit when field params are used
        if has_field_params and not endpoint.target:
            raise ValueError(
                f"Endpoint '{endpoint.name}': list endpoint with field-based params "
                f"requires an explicit 'target' object"
            )
        target_name = endpoint.target

    if not target_name:
        return None

    target = objects_by_name.get(target_name)
    if not target:
        raise ValueError(
            f"Endpoint '{endpoint.name}': target '{target_name}' does not exist in objects"
        )
    return target


def _has_field_params(endpoint: "InputEndpoint") -> bool:
    """Check if an endpoint has any field-based (non-legacy) params."""
    if endpoint.path_params:
        for p in endpoint.path_params:
            if p.field is not None:
                return True
    if endpoint.query_params:
        for q in endpoint.query_params:
            if q.field is not None:
                return True
    return False


def validate_param_inference(
    endpoints: Iterable["InputEndpoint"],
    objects: Iterable["InputModel"],
) -> None:
    """Validate all seven param inference rules across endpoints.

    :param endpoints: Collection of endpoint definitions.
    :param objects: Collection of object definitions.
    :raises ValueError: If any rule is violated.
    """
    objects_by_name: dict[str, "InputModel"] = {str(obj.name): obj for obj in objects}

    for endpoint in endpoints:
        # Skip endpoints with no field-based params (legacy mode)
        if not _has_field_params(endpoint) and not endpoint.target:
            continue

        # Rule 1: Target is known
        target = _resolve_target(endpoint, objects_by_name)
        if target is None:
            continue

        target_fields = {str(f.name): f for f in target.fields}
        pk_field_names = {str(f.name) for f in target.fields if f.pk}

        # Validate endpoint-level pagination (only valid on list endpoints)
        if endpoint.pagination and endpoint.response_shape != "list":
            raise ValueError(
                f"Endpoint '{endpoint.name}': pagination is only valid on "
                f"list endpoints (response_shape='list')"
            )

        # Rule 2: Every param field exists on target
        if endpoint.path_params:
            for pp in endpoint.path_params:
                if pp.field and pp.field not in target_fields:
                    raise ValueError(
                        f"Endpoint '{endpoint.name}': field '{pp.field}' "
                        f"does not exist on '{target.name}'"
                    )

        if endpoint.query_params:
            for qp in endpoint.query_params:
                if qp.field and qp.field not in target_fields:
                    raise ValueError(
                        f"Endpoint '{endpoint.name}': field '{qp.field}' "
                        f"does not exist on '{target.name}'"
                    )

        # Rule 3 & 5 depend on response_shape
        if endpoint.response_shape == "object":
            # Rule 3: Detail -- last path param maps to PK
            if endpoint.path_params:
                last_param = endpoint.path_params[-1]
                if last_param.field and last_param.field not in pk_field_names:
                    raise ValueError(
                        f"Endpoint '{endpoint.name}': detail endpoint's last path "
                        f"param '{last_param.name}' must map to a primary key field, "
                        f"but '{last_param.field}' is not a PK on '{target.name}'"
                    )

            # Rule 4: Detail -- no query params
            if endpoint.query_params:
                has_field_query = any(
                    qp.field is not None for qp in endpoint.query_params
                )
                if has_field_query:
                    raise ValueError(
                        f"Endpoint '{endpoint.name}': query params with field "
                        f"references are not allowed on detail (object) endpoints"
                    )

        elif endpoint.response_shape == "list":
            # Rule 5: List -- no path param maps to PK
            if endpoint.path_params:
                for pp in endpoint.path_params:
                    if pp.field and pp.field in pk_field_names:
                        raise ValueError(
                            f"Endpoint '{endpoint.name}': path param '{pp.name}' "
                            f"maps to primary key field '{pp.field}' on a list endpoint. "
                            f"Use a detail endpoint for PK lookups"
                        )

        # Rule 6: Operator is compatible with field type
        if endpoint.query_params:
            for qp in endpoint.query_params:
                if qp.operator and qp.field:
                    target_field = target_fields[qp.field]
                    _validate_operator_type_compat(
                        endpoint_name=str(endpoint.name),
                        param_name=str(qp.name),
                        operator=qp.operator,
                        field_type=str(target_field.type),
                    )


def _validate_operator_type_compat(
    endpoint_name: str,
    param_name: str,
    operator: str,
    field_type: str,
) -> None:
    """Validate that an operator is compatible with the field's type.

    :param endpoint_name: Endpoint name for error messages.
    :param param_name: Param name for error messages.
    :param operator: The filter operator.
    :param field_type: The field's type string.
    :raises ValueError: If operator is incompatible with field type.
    """
    valid_types = OPERATOR_VALID_TYPES.get(operator)
    if valid_types is None:
        return  # Unknown operator -- handled by Pydantic Literal validation

    if not valid_types:
        return  # Empty set = all types valid (eq, in)

    # Normalize the field type for lookup
    base_type = field_type.split(".")[0] if "." in field_type else field_type
    if field_type not in valid_types and base_type not in valid_types:
        raise ValueError(
            f"Endpoint '{endpoint_name}': operator '{operator}' is not valid "
            f"for field type '{field_type}' on param '{param_name}'"
        )


def validate_snake_case_name(value: str) -> None:
    """Validate that ``value`` is a snake_case identifier.

    :param value: Candidate identifier to validate.
    :raises ValueError: If ``value`` is empty or not valid snake_case.
    """
    if not value:
        raise ValueError("SnakeCaseName cannot be empty")

    if not SNAKE_CASE_PATTERN.match(value):
        raise ValueError(
            f"SnakeCaseName must be lowercase letters, digits, and single underscores, got: {value}"
        )


def validate_pascal_case_name(value: str) -> None:
    """Validate that ``value`` is a PascalCase identifier.

    :param value: Candidate identifier to validate.
    :raises TypeError: If ``value`` is not a string.
    :raises ValueError: If ``value`` is empty, does not start with an uppercase
        letter, or contains characters other than letters and numbers.
    """

    if not value:
        raise ValueError("PascalCaseName cannot be empty")

    if not value[0].isupper():
        raise ValueError(
            f"PascalCaseName must start with uppercase letter, got: {value}"
        )

    if not value.isalnum():
        raise ValueError(
            f"PascalCaseName must contain only letters and numbers, got: {value}"
        )

    # Disallow consecutive uppercase letters to enforce strict PascalCase
    for i in range(1, len(value)):
        if value[i].isupper() and value[i - 1].isupper():
            raise ValueError(
                f"PascalCaseName should not have consecutive uppercase letters, got: {value}"
            )
