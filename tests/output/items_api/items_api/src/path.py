"""This module contains validators for path parameters."""
from typing import Annotated
from fastapi import Path


ItemId = Annotated[
    int,
    Path(
        title="Item Id",
    ),
]

