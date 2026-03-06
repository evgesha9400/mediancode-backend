# src/api_craft/placeholders.py
"""Placeholder value generation for template models.

This module generates valid placeholder data from string-based type descriptions
and validator constraints. It handles:
- Primitive types (str, int, float, bool, datetime)
- Collections (List[T], Dict[K, V])
- Optional/Union types
- Nested model references
- Validator constraints (min_length, max_length, pattern, ge, le, gt, lt, multiple_of)
"""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_craft.models.template import TemplateField, TemplateValidator


def parse_type(type_str: str) -> tuple[str, list[str]]:
    """Parse a type string into base type and type arguments.

    Examples:
        "str"                -> ("str", [])
        "List[Item]"         -> ("List", ["Item"])
        "Dict[str, int]"     -> ("Dict", ["str", "int"])
        "List[List[str]]"    -> ("List", ["List[str]"])
        "Optional[Item]"     -> ("Optional", ["Item"])
        "str | None"         -> ("Optional", ["str"])

    :param type_str: Type annotation as a string.
    :returns: Tuple of (base_type, [type_args]).
    """
    type_str = type_str.strip()

    # Handle "X | None" union syntax -> Optional[X]
    if " | None" in type_str:
        inner = type_str.replace(" | None", "").strip()
        return ("Optional", [inner])
    if "None | " in type_str:
        inner = type_str.replace("None | ", "").strip()
        return ("Optional", [inner])

    # Find the base type and brackets
    bracket_start = type_str.find("[")
    if bracket_start == -1:
        return (type_str, [])

    base = type_str[:bracket_start]
    # Extract content between outermost brackets
    inner = type_str[bracket_start + 1 : -1]

    # Split args respecting nested brackets
    args = _split_type_args(inner)
    return (base, args)


def _split_type_args(inner: str) -> list[str]:
    """Split type arguments respecting nested brackets.

    "str, int"           -> ["str", "int"]
    "List[str], int"     -> ["List[str]", "int"]
    "Dict[str, int], X"  -> ["Dict[str, int]", "X"]
    """
    args = []
    current = []
    depth = 0

    for char in inner:
        if char == "[":
            depth += 1
            current.append(char)
        elif char == "]":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        args.append("".join(current).strip())

    return args


def extract_constraints(validators: list[TemplateValidator]) -> dict[str, Any]:
    """Extract constraint values from validators into a lookup dict.

    :param validators: List of validators to process.
    :returns: Dictionary mapping constraint names to their values.
    """
    constraints: dict[str, Any] = {}
    for v in validators:
        if v.params and "value" in v.params:
            constraints[v.name] = v.params["value"]
    return constraints


class PlaceholderGenerator:
    """Generates placeholder values for template models.

    This class maintains a registry of known models and handles recursive
    generation of nested structures while avoiding infinite loops from
    circular references.
    """

    def __init__(
        self,
        models: dict[str, list[TemplateField]],
        validator_fields: dict[str, set[str]] | None = None,
    ):
        """Initialize the generator with a model registry.

        :param models: Dict mapping model names to their field definitions.
        :param validator_fields: Optional dict mapping model names to sets of
            field names referenced by model validators. These fields will be
            included in placeholders even if optional.
        """
        self.models = models
        self.validator_fields = validator_fields or {}

    def generate_for_model(
        self,
        model_name: str,
        index: int = 1,
    ) -> dict[str, Any]:
        """Generate placeholder values for a model.

        :param model_name: Name of the model to generate.
        :param index: Starting index for deterministic values.
        :returns: Dictionary with placeholder values keyed by field name.
        """
        if model_name not in self.models:
            return {}

        return self._generate_model(
            model_name=model_name,
            index=index,
            visited=set(),
        )

    def _generate_model(
        self,
        model_name: str,
        index: int,
        visited: set[str],
    ) -> dict[str, Any]:
        """Internal model generation with cycle detection."""
        if model_name in visited:
            return {}

        fields = self.models.get(model_name, [])
        if not fields:
            return {}

        visited.add(model_name)
        result: dict[str, Any] = {}

        required_by_validators = self.validator_fields.get(model_name, set())

        for offset, field in enumerate(fields, start=1):
            if field.optional and field.name not in required_by_validators:
                continue

            constraints = extract_constraints(field.validators)
            result[field.name] = self._generate_value(
                type_str=field.type,
                constraints=constraints,
                index=index + offset - 1,
                visited=visited,
            )

        visited.discard(model_name)
        return result

    def _generate_value(
        self,
        type_str: str,
        constraints: dict[str, Any],
        index: int,
        visited: set[str],
    ) -> Any:
        """Generate a placeholder value for any type.

        :param type_str: Type annotation as string.
        :param constraints: Validator constraints dict.
        :param index: Seed index for deterministic output.
        :param visited: Set of model names currently being generated (cycle detection).
        :returns: Placeholder value matching the type and constraints.
        """
        base, args = parse_type(type_str)

        # Handle collection and wrapper types
        if base == "List":
            return self._generate_list(args, constraints, index, visited)
        if base == "Dict":
            return self._generate_dict(args, index, visited)
        if base == "Optional":
            # Generate the inner type (could also return None)
            inner_type = args[0] if args else "str"
            return self._generate_value(inner_type, constraints, index, visited)
        if base == "Union":
            # Use first non-None type
            for arg in args:
                if arg != "None":
                    return self._generate_value(arg, constraints, index, visited)
            return None

        # Handle model references
        if base in self.models:
            if base in visited:
                # Circular reference - return empty dict to break cycle
                return {}
            return self._generate_model(base, index, visited)

        # Handle primitives
        return self._generate_primitive(base, constraints, index)

    def _generate_list(
        self,
        args: list[str],
        constraints: dict[str, Any],
        index: int,
        visited: set[str],
    ) -> list[Any]:
        """Generate a list with 2 items of the inner type."""
        if not args:
            return []

        inner_type = args[0]
        min_items = constraints.get("min_items", 2)
        max_items = constraints.get("max_items", 2)
        count = max(min_items, min(2, max_items))

        return [
            self._generate_value(inner_type, {}, index + i, visited)
            for i in range(count)
        ]

    def _generate_dict(
        self,
        args: list[str],
        index: int,
        visited: set[str],
    ) -> dict[Any, Any]:
        """Generate a dict with one key-value pair."""
        if len(args) < 2:
            return {}

        key_type, value_type = args[0], args[1]
        key = self._generate_value(key_type, {}, index, visited)
        value = self._generate_value(value_type, {}, index, visited)
        return {key: value}

    def _generate_primitive(
        self,
        type_name: str,
        constraints: dict[str, Any],
        index: int,
    ) -> Any:
        """Generate a primitive value respecting constraints."""
        match type_name:
            case "str":
                return generate_string(index, constraints)
            case "int":
                return generate_int(index, constraints)
            case "float":
                return generate_float(index, constraints)
            case "bool":
                return generate_bool(index)
            case "datetime.datetime" | "datetime":
                return generate_datetime(index)
            case "date" | "datetime.date":
                return generate_date(index)
            case "UUID" | "uuid.UUID":
                return generate_uuid(index)
            case "decimal.Decimal" | "Decimal":
                return generate_decimal(index, constraints)
            case "datetime.time" | "time":
                return generate_time(index)
            case "EmailStr":
                return generate_email(index)
            case "HttpUrl":
                return generate_url(index)
            case _:
                # Unknown type, return a string placeholder
                return f"example_{type_name.lower()}_{index}"


# =============================================================================
# Primitive generators with constraint support
# =============================================================================


def generate_string(index: int, constraints: dict[str, Any]) -> str:
    """Generate a string satisfying length and pattern constraints."""
    pattern = constraints.get("pattern")
    min_len = constraints.get("min_length", 1)
    max_len = constraints.get("max_length", 100)

    if pattern:
        return _generate_pattern_string(pattern, index, max_len)

    # No pattern - generate a simple string respecting length
    base = f"example_{index}"
    if len(base) < min_len:
        base = base + "x" * (min_len - len(base))
    return base[:max_len]


def _generate_pattern_string(pattern: str, index: int, max_len: int) -> str:
    """Generate a string matching common regex patterns."""
    # SKU-like patterns: uppercase alphanumeric with dashes
    if re.match(r"^\^?\[A-Z0-9\-?\]\+\$?$", pattern) or pattern in (
        "^[A-Z0-9-]+$",
        "^[A-Z0-9]+$",
        r"^[A-Z0-9-]+$",
    ):
        return f"SKU-{index:03d}"[:max_len]

    # Alpha-digit patterns: ^[A-Z]{N}-\d{M}$ or ^[A-Z]{N}\d{M}$
    alpha_digit = re.match(r"^\^?\[A-Z\]\{(\d+)\}(.?)\\d\{(\d+)\}\$?$", pattern)
    if alpha_digit:
        alpha_count = int(alpha_digit.group(1))
        separator = alpha_digit.group(2)
        digit_count = int(alpha_digit.group(3))
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        alpha = "".join(letters[(index + i) % 26] for i in range(alpha_count))
        digits = str(index % (10**digit_count)).zfill(digit_count)
        return f"{alpha}{separator}{digits}"[:max_len]

    # Email patterns
    if "email" in pattern.lower() or "@" in pattern:
        return f"user{index}@example.com"[:max_len]

    # URL patterns
    if "http" in pattern.lower() or "url" in pattern.lower():
        return f"https://example.com/{index}"[:max_len]

    # Phone patterns
    if "phone" in pattern.lower() or r"\d" in pattern:
        return f"+1555000{index:04d}"[:max_len]

    # Default: uppercase alphanumeric
    return f"VALUE{index:03d}"[:max_len]


def generate_int(index: int, constraints: dict[str, Any]) -> int:
    """Generate an integer satisfying numeric constraints."""
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

    max_val = 1_000_000
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
        remainder = value % multiple_of
        if remainder != 0:
            value = value + (multiple_of - remainder)
        if value > max_val:
            # Find smallest valid multiple
            value = ((min_val // multiple_of) + 1) * multiple_of
            if value < min_val:
                value = min_val
                remainder = value % multiple_of
                if remainder != 0:
                    value = value + (multiple_of - remainder)

    return value


def generate_float(index: int, constraints: dict[str, Any]) -> float:
    """Generate a float satisfying numeric constraints."""
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

    max_val = 1_000_000.0
    if le is not None:
        max_val = float(le)
    elif lt is not None:
        max_val = float(lt) - 0.01

    # Generate value in range
    value = min_val + (index * 0.5)
    if value > max_val:
        value = (min_val + max_val) / 2

    return round(value, 2)


def generate_bool(index: int) -> bool:
    """Generate a boolean (alternates based on index)."""
    return index % 2 == 1


def generate_datetime(index: int) -> str:
    """Generate an ISO format datetime string.

    Returns a string like "2026-01-27T00:00:06" that can be used directly
    in generated code without requiring datetime imports.
    """
    now = datetime.datetime.now(datetime.UTC)
    seconds = index % 86400
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}T{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_date(index: int) -> str:
    """Generate an ISO format date string."""
    now = datetime.datetime.now(datetime.UTC)
    day_offset = index % 28
    return f"{now.year:04d}-{now.month:02d}-{day_offset + 1:02d}"


def generate_uuid(index: int) -> str:
    """Generate a deterministic UUID-like string."""
    hex_index = f"{index:032x}"
    return f"{hex_index[:8]}-{hex_index[8:12]}-{hex_index[12:16]}-{hex_index[16:20]}-{hex_index[20:32]}"


def generate_decimal(index: int, constraints: dict[str, Any]) -> str:
    """Generate a decimal string value respecting constraints."""
    value = generate_float(index, constraints)
    return str(value)


def generate_time(index: int) -> str:
    """Generate an ISO format time string."""
    seconds = index % 86400
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_email(index: int) -> str:
    """Generate a placeholder email address."""
    return f"user{index}@example.com"


def generate_url(index: int) -> str:
    """Generate a placeholder HTTP URL."""
    return f"https://example.com/resource/{index}"
