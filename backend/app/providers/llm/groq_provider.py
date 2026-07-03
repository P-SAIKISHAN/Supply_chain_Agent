from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.providers.base import LLMProvider, ProviderError
from app.providers.http import post_json


class GroqLLMProvider(LLMProvider):
    source_name = "groq"

    def configured(self) -> bool:
        return bool(settings.groq_api_key)

    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
        if self.demo_mode or not self.configured():
            return None
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are an expert energy intelligence analyst."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        try:
            response = post_json(
                f"{settings.groq_base_url.rstrip('/')}/chat/completions",
                payload,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
        except ProviderError:
            return None

        choices = response.get("choices") or []
        for choice in choices:
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None
