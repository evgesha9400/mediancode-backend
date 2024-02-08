"""Utility functions for the project."""
import subprocess
import os
import re


def create_dir(path):
    """Create the directory at the given path if it does not exist."""
    os.makedirs(path, exist_ok=True)


def write_file(path, content):
    """Write the given content to the file at the given path."""
    with open(path, 'w') as f:
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
    return ''.join(['_' + i.lower() if i.isupper() else i for i in name]).lstrip('_')


def snake_to_camel(name):
    """Convert the given name from snake case to camel case."""
    return ''.join([i.capitalize() for i in name.split('_')])


def remove_duplicates(s: str) -> str:
    """Remove adjacent duplicate words from the given string."""
    words = re.findall('[A-Z][^A-Z]*', s)
    seen = set()
    result = []
    for word in words:
        if word.lower() not in seen:
            result.append(word)
            seen.add(word.lower())
    return ''.join(result)


def remove_non_adjacent_duplicates(s: str) -> str:
    """Remove non-adjacent duplicate words from the given string."""
    words = re.findall('[A-Z][^A-Z]*', s)
    seen = set()
    result = []

    for word in words:
        word_lower = word.lower()
        if word_lower not in seen:
            result.append(word)
            seen.add(word_lower)
    return ''.join(result)