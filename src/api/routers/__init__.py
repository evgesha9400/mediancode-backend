# src/api/routers/__init__.py
"""FastAPI routers for API endpoints."""

from api.routers.apis import router as apis_router
from api.routers.endpoints import router as endpoints_router
from api.routers.field_constraints import router as field_constraints_router
from api.routers.field_validator_templates import (
    router as field_validator_templates_router,
)
from api.routers.fields import router as fields_router
from api.routers.model_validator_templates import (
    router as model_validator_templates_router,
)
from api.routers.namespaces import router as namespaces_router
from api.routers.objects import router as objects_router
from api.routers.types import router as types_router

__all__ = [
    "apis_router",
    "endpoints_router",
    "field_constraints_router",
    "field_validator_templates_router",
    "fields_router",
    "model_validator_templates_router",
    "namespaces_router",
    "objects_router",
    "types_router",
]
