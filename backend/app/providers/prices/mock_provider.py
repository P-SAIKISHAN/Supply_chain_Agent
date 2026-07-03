from __future__ import annotations

from typing import Any

from app.ingestion.sample_data import price_items
from app.providers.base import PriceProvider


class MockPriceProvider(PriceProvider):
    """Deterministic market data fallback."""

    source_name = "mock_prices"

    def fetch(self) -> list[dict[str, Any]]:
        return price_items()
