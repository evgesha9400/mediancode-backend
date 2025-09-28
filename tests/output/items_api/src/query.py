"""This module contains query parameter type definitions and validators."""
from typing import Annotated
from fastapi import Query


Limit = Annotated[
    int,
    Query(
        title="Limit",
    ),
]


Offset = Annotated[
    int,
    Query(
        title="Offset",
    ),
]

