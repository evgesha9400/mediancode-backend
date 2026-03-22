"""Custom types for the Median Code Backend models."""

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from api_craft.models.validators import (
    validate_pascal_case_name,
    validate_snake_case_name,
)


class PascalCaseName(str):
    """A string that must be in PascalCase and provides derived naming variants.

    This type validates that the input is a valid PascalCase identifier and
    automatically provides snake_case, camelCase, and kebab-case variants.
    """

    def __new__(cls, value: str) -> "PascalCaseName":
        validate_pascal_case_name(value)
        return super().__new__(cls, value)

    @property
    def pascal_name(self) -> str:
        """Return self (already PascalCase), for symmetry with SnakeCaseName."""
        return str(self)

    @property
    def camel_name(self) -> str:
        """Return the camelCase version of the name."""
        return self[0].lower() + self[1:] if len(self) > 1 else self.lower()

    @property
    def snake_name(self) -> str:
        """Return the snake_case version of the name."""
        result = []
        for i, char in enumerate(self):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)

    @property
    def kebab_name(self) -> str:
        """Return the kebab-case version of the name."""
        result = []
        for i, char in enumerate(self):
            if char.isupper() and i > 0:
                result.append("-")
            result.append(char.lower())
        return "".join(result)

    @property
    def spaced_name(self) -> str:
        """Return the name with spaces before uppercase letters."""
        result = []
        for i, char in enumerate(self):
            if char.isupper() and i > 0:
                result.append(" ")
            result.append(char)
        return "".join(result)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


class SnakeCaseName(str):
    """A string that must be in snake_case and provides derived naming variants.

    This type validates that the input is a valid snake_case identifier and
    automatically provides camelCase, PascalCase, and kebab-case variants.
    """

    def __new__(cls, value: str) -> "SnakeCaseName":
        validate_snake_case_name(value)
        return super().__new__(cls, value)

    @property
    def camel_name(self) -> str:
        """Return the PascalCase version of the name.

        Note: For snake_case, camelCase capitalizes each segment, producing
        PascalCase. This matches the existing snake_to_camel utility behavior.
        """
        return "".join(segment.capitalize() for segment in self.split("_"))

    @property
    def pascal_name(self) -> str:
        """Return the PascalCase version of the name."""
        return "".join(segment.capitalize() for segment in self.split("_"))

    @property
    def kebab_name(self) -> str:
        """Return the kebab-case version of the name."""
        return self.replace("_", "-")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )
