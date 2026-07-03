from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.providers.base import LLMProvider, ProviderError
from app.providers.http import post_json


class GeminiLLMProvider(LLMProvider):
    """Gemini provider for report generation and summarization."""

    source_name = "gemini"

    def configured(self) -> bool:
        return bool(settings.gemini_api_key)

    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
        if self.demo_mode or not self.configured():
            return None

        model = settings.gemini_model.strip() or "gemini-1.5-flash"
        url = (
            f"{settings.gemini_base_url.rstrip('/')}/models/"
            f"{model}:generateContent?key={settings.gemini_api_key}"
        )
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt or "You are an expert energy intelligence analyst."}]
            },
            "generationConfig": {
                "temperature": temperature,
            },
        }

        try:
            response = post_json(url, payload)
        except ProviderError:
            return None

        candidates = response.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        return None
