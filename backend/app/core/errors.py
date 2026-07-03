from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request


def build_error_body(
    *,
    error_type: str,
    message: str,
    status_code: int,
    request: Request | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build a consistent API error envelope used across exception handlers."""
    body: dict[str, Any] = {
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            body["error"]["request_id"] = request_id
        body["error"]["path"] = request.url.path
        body["error"]["method"] = request.method
    return body
