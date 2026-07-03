from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.errors import build_error_body
from app.core.logging import get_logger


logger = get_logger(__name__)
_request_buckets: dict[str, Deque[float]] = defaultdict(deque)
_rate_limit_window_seconds = 60.0


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response metadata with a stable request id."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        request.state.request_id = request_id
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            logger.exception(
                "http_request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            if response is not None:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time-MS"] = str(duration_ms)
            if request.url.path not in {"/api/v1/health", "/api/v1/ready"}:
                logger.info(
                    "http_request",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code if response is not None else None,
                        "duration_ms": duration_ms,
                        "client_ip": request.client.host if request.client else None,
                    },
                )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting placeholder.

    The implementation is intentionally small and single-process friendly so it
    can be replaced later with a Redis-backed limiter without changing callers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path in {"/api/v1/health", "/api/v1/ready", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "anonymous"
        bucket = _request_buckets[client_ip]
        now = time.monotonic()
        while bucket and now - bucket[0] > _rate_limit_window_seconds:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=build_error_body(
                    error_type="rate_limited",
                    message="Too many requests",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    request=request,
                    details={
                        "limit_per_minute": settings.rate_limit_requests_per_minute,
                        "window_seconds": _rate_limit_window_seconds,
                    },
                ),
            )

        bucket.append(now)
        return await call_next(request)
