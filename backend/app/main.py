from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_422_UNPROCESSABLE_ENTITY

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import build_error_body
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.core.startup import verify_startup_dependencies
from app.jobs.scheduler import start_scheduler, stop_scheduler

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan hook for startup and shutdown logging."""
    logger.info(
        "application_starting",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )
    startup_status = verify_startup_dependencies()
    logger.info(
        "startup_checks_completed",
        extra={
            "database_ready": startup_status.database_ready,
            "redis_ready": startup_status.redis_ready,
            "initialized_tables": startup_status.initialized_tables,
            "strict": startup_status.strict,
            "warnings": startup_status.warnings,
        },
    )
    scheduler = start_scheduler()
    if scheduler is not None:
        logger.info("scheduler_initialized", extra={"enabled": settings.enable_scheduler})
    yield
    stop_scheduler()
    logger.info("application_stopping")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-driven energy supply chain resilience backend for India",
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url=settings.openapi_url,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, Any]:
    """Project metadata endpoint for quick health and environment inspection."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "docs_url": settings.docs_url,
        "redoc_url": settings.redoc_url,
        "api_v1_prefix": settings.api_v1_prefix,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return consistent JSON for expected HTTP errors."""
    logger.warning(
        "http_exception",
        extra={"path": request.url.path, "status_code": exc.status_code, "detail": exc.detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_body(
            error_type="http_error",
            message=str(exc.detail),
            status_code=exc.status_code,
            request=request,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return consistent JSON for request validation failures."""
    logger.warning(
        "validation_error",
        extra={"path": request.url.path, "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_body(
            error_type="validation_error",
            message="Request validation failed",
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            request=request,
            details=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler to prevent leaking stack traces to API clients."""
    logger.exception(
        "unhandled_exception",
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_body(
            error_type="internal_server_error",
            message="An unexpected error occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            request=request,
        ),
    )
