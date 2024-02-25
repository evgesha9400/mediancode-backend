"""Utility functions for the project."""
import os
import re
import shutil
import subprocess


def copy_file(source_path: str, destination_path: str) -> None:
    """
    Copies a file from the source path to the destination path.

    :param source_path: The path of the source file to be copied.
    :param destination_path: The path where the source file will be copied to.
    """
    try:
        shutil.copy(source_path, destination_path)
        print(f"File copied successfully from {source_path} to {destination_path}.")
    except Exception as e:
        print(f"Error copying file: {e}")


def create_dir(path):
    """Create the directory at the given path if it does not exist."""
    os.makedirs(path, exist_ok=True)


def write_file(path, content):
    """Write the given content to the file at the given path."""
    with open(path, "w") as f:
        f.write(content)


def apply_black_formatting(path):
    """Apply black formatting to all python files in the given path and its subdirectories."""
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                print(f"Formatting {file_path}")
                subprocess.run(["black", file_path], check=True)


def camel_to_snake(name):
    """Convert the given name from camel case to snake case."""
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")


def snake_to_camel(name):
    """Convert the given name from snake case to camel case."""
    return "".join([i.capitalize() for i in name.split("_")])


def add_spaces_to_camel_case(name: str) -> str:
    # Insert a space before all caps (excluding the start of the string)
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


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


def create_project_structure(base_path, structure):
    """
    Creates a folder structure given a base path and a structure definition.

    :param base_path: The base directory for the project.
    :param structure: A nested dictionary where keys are directory names and values are
                      further dictionaries representing subdirectories or None for leaf directories.

        # Example usage
        project_structure = {
            'src': None,
            'tests': None,
            'deploy': None
        }

        base_project_path = '/path/to/your/project'
        create_project_structure(base_project_path, project_structure)
    """
    for dir_name, sub_structure in structure.items():
        # Construct the full path for the current directory
        dir_path = os.path.join(base_path, dir_name)

        # Create the directory if it doesn't already exist
        os.makedirs(dir_path, exist_ok=True)

        # If the current directory has a sub-structure, recursively create it
        if sub_structure is not None:
            create_project_structure(dir_path, sub_structure)
