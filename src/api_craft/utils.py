"""Utility functions for the project."""

import logging
import os
import re
import shutil

logger = logging.getLogger(__name__)


def copy_file(source_path: str, destination_path: str) -> None:
    """
    Copies a file from the source path to the destination path.

    :param source_path: The path of the source file to be copied.
    :param destination_path: The path where the source file will be copied to.
    """
    try:
        shutil.copy(source_path, destination_path)
        logger.debug(
            f"File copied successfully from {source_path} to {destination_path}."
        )
    except Exception as e:
        logger.error(f"Error copying file: {e}")


def create_dir(path: str) -> None:
    """Create the directory at the given path if it does not exist."""
    os.makedirs(path, exist_ok=True)


def write_file(path: str, content: str) -> None:
    """Write the given content to the file at the given path."""
    with open(path, "w") as f:
        f.write(content)


def camel_to_snake(name: str) -> str:
    """Convert the given name from camel case to snake case."""
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")


def camel_to_kebab(name: str) -> str:
    """Convert the given name from camel case to kebab case."""
    return "".join(["-" + i.lower() if i.isupper() else i for i in name]).lstrip("-")


def snake_to_camel(name: str) -> str:
    """Convert the given name from snake case to camel case."""
    return "".join([i.capitalize() for i in name.split("_")])


def add_spaces_to_camel_case(name: str) -> str:
    # Insert a space before all caps (excluding the start of the string)
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


def snake_to_plural(name: str) -> str:
    """Pluralize a snake_case name using basic English rules."""
    if name.endswith("y") and not name.endswith(("ay", "ey", "iy", "oy", "uy")):
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"


def remove_duplicates(s: str) -> str:
    """Remove duplicate words from the given string."""
    words = re.findall("[A-Z][^A-Z]*", s)
    seen = set()
    result = []
    for word in words:
        if word.lower() not in seen:
            result.append(word)
            seen.add(word.lower())
    return "".join(result)
