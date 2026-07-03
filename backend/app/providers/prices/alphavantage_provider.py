from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.ingestion.sample_data import price_items
from app.providers.base import PriceProvider, ProviderError
from app.providers.http import get_json, build_query_url


class AlphaVantagePriceProvider(PriceProvider):
    """Fetch commodity price series with a safe demo fallback."""

    source_name = "alphavantage"

    def configured(self) -> bool:
        return bool(settings.alphavantage_api_key and settings.alphavantage_base_url)

    def fetch(self) -> list[dict[str, Any]]:
        if self.demo_mode or not self.configured():
            return price_items()
        try:
            url = build_query_url(
                settings.alphavantage_base_url,
                "",
                {
                    "function": "BRENT",
                    "apikey": settings.alphavantage_api_key,
                },
            )
            payload = get_json(url)
        except ProviderError:
            return price_items()

        series = payload.get("data") or payload.get("Time Series (Daily)") or []
        normalized: list[dict[str, Any]] = []
        if isinstance(series, list):
            for item in series:
                normalized.append(
                    {
                        "benchmark_name": item.get("benchmark_name") or "Brent",
                        "price_usd": float(item.get("price_usd", 0.0) or 0.0),
                        "timestamp": _parse_time(item.get("timestamp")) or datetime.now(timezone.utc),
                        "source": "alphavantage",
                    }
                )
        return normalized or price_items()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
