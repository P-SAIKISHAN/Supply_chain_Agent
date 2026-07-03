from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.providers.registry import get_llm_provider


@dataclass
class LLMResult:
    """Lightweight wrapper for optional generated text."""

    text: str
    provider: str
    model: str


def llm_configured() -> bool:
    return bool(settings.gemini_api_key or settings.groq_api_key)


def _provider_name() -> str:
    return settings.llm_provider.strip() or "mock"


def _model_name() -> str:
    return settings.llm_model.strip() or "gpt-4o-mini"


def generate_text(prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
    """Generate text using the configured LLM provider or return ``None``.

    The provider registry automatically falls back to a template/mock provider
    when credentials are missing or the environment is in demo mode.
    """
    provider = get_llm_provider()
    if hasattr(provider, "generate"):
        return provider.generate(
            prompt=prompt,
            system_prompt=system_prompt or "You are an expert energy intelligence analyst.",
            temperature=temperature,
        )
    return None
