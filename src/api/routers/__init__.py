# src/api/routers/__init__.py
"""FastAPI routers for API endpoints."""

from api.routers.apis import router as apis_router
from api.routers.endpoints import router as endpoints_router
from api.routers.fields import router as fields_router
from api.routers.namespaces import router as namespaces_router
from api.routers.objects import router as objects_router
from api.routers.types import router as types_router
from api.routers.constraints import router as constraints_router

__all__ = [
    "apis_router",
    "endpoints_router",
    "fields_router",
    "namespaces_router",
    "objects_router",
    "types_router",
    "constraints_router",
]
