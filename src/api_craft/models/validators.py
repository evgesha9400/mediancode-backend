"""Validation helpers for :mod:`api_craft.models.input`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - imports used for type checking only
    from api_craft.models.input import InputModel, InputView

TYPE_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

SUPPORTED_TYPE_IDENTIFIERS = {
    "Any",
    "AnyUrl",
    "Awaitable",
    "Callable",
    "ChainMap",
    "Coroutine",
    "Counter",
    "Decimal",
    "DefaultDict",
    "Deque",
    "Dict",
    "EmailStr",
    "Enum",
    "FrozenSet",
    "Generic",
    "HttpUrl",
    "IPvAnyAddress",
    "IPvAnyInterface",
    "IPvAnyNetwork",
    "Iterable",
    "Iterator",
    "Json",
    "List",
    "Literal",
    "Mapping",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "NegativeFloat",
    "NegativeInt",
    "NonNegativeFloat",
    "NonNegativeInt",
    "NonPositiveFloat",
    "NonPositiveInt",
    "Optional",
    "OrderedDict",
    "Path",
    "PositiveFloat",
    "PositiveInt",
    "PurePath",
    "SecretBytes",
    "SecretStr",
    "Sequence",
    "Set",
    "Tuple",
    "TypedDict",
    "Type",
    "Union",
    "UUID",
    "bool",
    "bytes",
    "bytearray",
    "complex",
    "date",
    "datetime",
    "dict",
    "float",
    "frozenset",
    "int",
    "list",
    "memoryview",
    "set",
    "str",
    "time",
    "timedelta",
    "timezone",
    "tuple",
    "type",
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


def validate_view_references(
    views: Iterable["InputView"],
    declared_object_names: set[str],
) -> None:
    """Validate request and response references declared on views.

    :param views: Collection of view definitions.
    :param declared_object_names: Object identifiers declared in the API specification.
    :raises ValueError: If a view references an unknown object.
    """

    for view in views:
        if view.response and view.response not in declared_object_names:
            raise ValueError(f"View '{view.name}' references unknown response '{view.response}'")

        if view.request and view.request not in declared_object_names:
            raise ValueError(f"View '{view.name}' references unknown request '{view.request}'")
