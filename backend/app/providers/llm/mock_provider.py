from __future__ import annotations

from app.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Template-first fallback provider for demo mode."""

    source_name = "mock_llm"

    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
        return None
