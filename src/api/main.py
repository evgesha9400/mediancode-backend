# src/api/main.py
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.middleware import SecurityHeadersMiddleware
from api.rate_limit import limiter
from api.routers import (
    apis_router,
    endpoints_router,
    field_constraints_router,
    fields_router,
    namespaces_router,
    objects_router,
    types_router,
)
from api.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    :param app: FastAPI application instance.
    :yields: Nothing, just manages startup/shutdown.
    """
    # Startup
    yield
    # Shutdown


# Disable docs in production
settings = get_settings()
docs_url = None if settings.is_production else "/docs"
redoc_url = None if settings.is_production else "/redoc"
openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title="Median Code API",
    description=(
        "Production-ready FastAPI code generation and API entity management "
        "with Clerk JWT authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security headers middleware (must be added before CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS with allowed frontend origins
cors_origins = [
    "https://mediancode.com",  # Production frontend
    "https://dev.mediancode.com",  # Development frontend
]
# Add configurable frontend URL if different from defaults
if settings.frontend_url not in cors_origins:
    cors_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions globally.

    :param request: The incoming request.
    :param exc: The uncaught exception.
    :returns: JSON error response.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Register routers under /v1 prefix
api_v1_prefix = "/v1"

app.include_router(namespaces_router, prefix=api_v1_prefix)
app.include_router(apis_router, prefix=api_v1_prefix)
app.include_router(types_router, prefix=api_v1_prefix)
app.include_router(field_constraints_router, prefix=api_v1_prefix)
app.include_router(fields_router, prefix=api_v1_prefix)
app.include_router(objects_router, prefix=api_v1_prefix)
app.include_router(endpoints_router, prefix=api_v1_prefix)


@app.get("/health", tags=["Health"])
@limiter.limit("1000/minute")
async def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint.

    :param request: The incoming request (required for rate limiting).
    :returns: Health status.
    """
    return {"status": "healthy"}
