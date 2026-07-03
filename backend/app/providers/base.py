from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


class ProviderError(RuntimeError):
    """Raised when a provider cannot satisfy a request."""


class BaseProvider(ABC):
    """Common provider contract with safe demo-mode defaults."""

    source_name: str = "unknown"

    def __init__(self, demo_mode: bool | None = None) -> None:
        self.demo_mode = settings.demo_mode if demo_mode is None else demo_mode

    def configured(self) -> bool:
        """Return True when the provider has enough configuration to attempt a live call."""
        return True


class NewsProvider(BaseProvider, ABC):
    @abstractmethod
    def fetch(
        self,
        query: str | None = None,
        region: str | None = None,
        since: Any | None = None,
        until: Any | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class SanctionsProvider(BaseProvider, ABC):
    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class AISProvider(BaseProvider, ABC):
    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class PriceProvider(BaseProvider, ABC):
    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class LLMProvider(BaseProvider, ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str | None:
        raise NotImplementedError
