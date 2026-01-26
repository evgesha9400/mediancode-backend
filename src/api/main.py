# src/api/main.py
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (
    apis_router,
    endpoints_router,
    fields_router,
    namespaces_router,
    objects_router,
    tags_router,
    types_router,
    validators_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    :param app: FastAPI application instance.
    :yields: Nothing, just manages startup/shutdown.
    """
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Median Code API",
    description=(
        "Production-ready FastAPI code generation and API entity management "
        "with Clerk JWT authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(validators_router, prefix=api_v1_prefix)
app.include_router(fields_router, prefix=api_v1_prefix)
app.include_router(objects_router, prefix=api_v1_prefix)
app.include_router(tags_router, prefix=api_v1_prefix)
app.include_router(endpoints_router, prefix=api_v1_prefix)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    :returns: Health status.
    """
    return {"status": "healthy"}
