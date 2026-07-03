from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from app.providers.base import ProviderError


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    req = request.Request(url, headers=headers or {}, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProviderError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ProviderError("Expected JSON object response")
    return payload


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = request.Request(url, data=data, headers=req_headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            payload_json = json.loads(body) if body else {}
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProviderError(str(exc)) from exc
    if not isinstance(payload_json, dict):
        raise ProviderError("Expected JSON object response")
    return payload_json


def build_query_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    query = parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}{f'?{query}' if query else ''}"
