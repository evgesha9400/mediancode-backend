"""Validation helpers for :mod:`api_craft.models.input`."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING

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
    """Validate PK constraints: not optional, at most one per model.

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
            if field.optional:
                raise ValueError(
                    f"Field '{obj.name}.{field.name}' is a primary key and cannot be optional"
                )


def validate_database_config(
    config: "InputApiConfig",
    objects: Iterable["InputModel"],
) -> None:
    """Validate database generation configuration constraints.

    :param config: API configuration containing database and placeholder settings.
    :param objects: Collection of declared objects.
    :raises ValueError: If database is enabled with response placeholders,
        or if database is enabled but no object has a primary key.
    """
    if not config.database.enabled:
        return

    if config.response_placeholders:
        raise ValueError(
            "Response placeholders cannot be enabled when database generation is active. "
            "Disable response placeholders or disable database generation."
        )

    has_any_pk = any(any(field.pk for field in obj.fields) for obj in objects)
    if not has_any_pk:
        raise ValueError(
            "Database generation requires at least one object with a primary key field. "
            "Mark a field as PK on your objects, or disable database generation."
        )


SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


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

    if not value.replace("_", "").isalnum():
        raise ValueError(
            f"PascalCaseName must contain only letters and numbers, got: {value}"
        )

    # Disallow consecutive uppercase letters to enforce strict PascalCase
    for i in range(1, len(value)):
        if value[i].isupper() and value[i - 1].isupper():
            raise ValueError(
                f"PascalCaseName should not have consecutive uppercase letters, got: {value}"
            )
