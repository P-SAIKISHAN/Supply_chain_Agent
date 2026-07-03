from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass
class LLMResult:
    """Lightweight wrapper for optional generated text."""

    text: str
    provider: str
    model: str


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"))


def _provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip() or "openai"


def _model_name() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def generate_text(prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
    """Try to generate text with a real provider, but fail closed if unavailable.

    This scaffolding intentionally returns ``None`` instead of raising when no
    provider key exists so the platform can always fall back to templates.
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None

    provider = _provider_name().lower()
    model = _model_name()
    if provider != "openai":
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/responses"
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": system_prompt or "You are an expert energy intelligence analyst.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None

    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = body.get("output") or []
    collected: list[str] = []
    for item in output:
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                collected.append(text)
    text = "\n".join(part for part in collected if part).strip()
    return text or None

