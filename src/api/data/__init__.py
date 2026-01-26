# src/api/data/__init__.py
"""Global configuration data loading for types and validators."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache
def load_global_config() -> dict[str, Any]:
    """Load the global configuration from YAML file.

    :returns: Dictionary containing types and validators definitions.
    """
    config_path = Path(__file__).parent / "global_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_global_types() -> list[dict[str, Any]]:
    """Get all global type definitions.

    :returns: List of type definition dictionaries.
    """
    config = load_global_config()
    return config.get("types", [])


def get_global_validators() -> list[dict[str, Any]]:
    """Get all global validator definitions.

    :returns: List of validator definition dictionaries.
    """
    config = load_global_config()
    return config.get("validators", [])
