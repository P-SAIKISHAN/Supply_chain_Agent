from __future__ import annotations

from typing import Any

from app.ingestion.sample_data import news_items
from app.providers.base import NewsProvider


class MockNewsProvider(NewsProvider):
    """Deterministic mock provider for demo mode."""

    source_name = "mock_news"

    def fetch(
        self,
        query: str | None = None,
        region: str | None = None,
        since: Any | None = None,
        until: Any | None = None,
    ) -> list[dict[str, Any]]:
        return news_items()
