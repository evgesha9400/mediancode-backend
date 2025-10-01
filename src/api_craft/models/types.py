"""Custom types for the API Craft models."""

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PascalCaseName(str):
    """A string that must be in PascalCase and provides derived naming variants.

    This type validates that the input is a valid PascalCase identifier and
    automatically provides snake_case, camelCase, and kebab-case variants.
    """

    def __new__(cls, value: str) -> "PascalCaseName":
        if not isinstance(value, str):
            raise TypeError("PascalCaseName must be a string")

        # Validate PascalCase format
        if not value:
            raise ValueError("PascalCaseName cannot be empty")

        if not value[0].isupper():
            raise ValueError(f"PascalCaseName must start with uppercase letter, got: {value}")

        if not value.replace("_", "").isalnum():
            raise ValueError(f"PascalCaseName must contain only letters and numbers, got: {value}")

        # Check for consecutive uppercase letters (should be avoided in PascalCase)
        for i in range(1, len(value)):
            if value[i].isupper() and value[i - 1].isupper():
                raise ValueError(f"PascalCaseName should not have consecutive uppercase letters, got: {value}")

        instance = super().__new__(cls, value)
        return instance

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

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )
