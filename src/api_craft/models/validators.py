"""Validation helpers for :mod:`api_craft.models.input`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - imports used for type checking only
    from api_craft.models.input import InputEndpoint, InputModel

TYPE_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Restrict to the actually supported identifiers in this project.
# Primitive types are defined by transformers.type_mapping (str, int, bool, float, datetime.datetime).
# Complex types are limited to List[primitive] or List[object], and object references themselves.
# For validation, identifiers are tokenized by TYPE_IDENTIFIER_PATTERN, so
#   - "datetime.datetime" becomes tokens {"datetime"}
#   - "List[T]" becomes tokens {"List", "T"}
# Therefore we only need to allow: primitives (str, int, bool, float), the token "datetime",
# and the generic container token "List". All other identifiers must be declared object names.
SUPPORTED_TYPE_IDENTIFIERS = {
    "str",
    "int",
    "bool",
    "float",
    "datetime",
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
