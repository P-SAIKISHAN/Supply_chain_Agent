from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.ingestion.sample_data import news_items
from app.providers.base import NewsProvider, ProviderError
from app.providers.http import get_json, build_query_url


class GDELTNewsProvider(NewsProvider):
    """Fetch geopolitical events from GDELT with a safe demo fallback."""

    source_name = "gdelt"

    def configured(self) -> bool:
        return bool(settings.gdelt_enabled and settings.gdelt_base_url)

    def fetch(
        self,
        query: str | None = None,
        region: str | None = None,
        since: Any | None = None,
        until: Any | None = None,
    ) -> list[dict[str, Any]]:
        if self.demo_mode or not self.configured():
            return news_items()

        params = {
            "query": query or "crude oil OR shipping OR sanctions",
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 10,
            "sort": "datedesc",
        }
        if region:
            params["query"] = f"({params['query']}) {region}"
        if since:
            params["startdatetime"] = _gdelt_timestamp(since)
        if until:
            params["enddatetime"] = _gdelt_timestamp(until)

        url = build_query_url(settings.gdelt_base_url, "/doc/doc", params)
        try:
            payload = get_json(url)
        except ProviderError:
            return news_items()

        articles = payload.get("articles") or payload.get("articles", [])
        normalized: list[dict[str, Any]] = []
        for article in articles[:10]:
            normalized.append(
                {
                    "title": article.get("title") or article.get("seendate") or "GDELT event",
                    "event_type": article.get("sourceCountry") or "news",
                    "region": region or article.get("sourceCountry") or "Global",
                    "source": "gdelt",
                    "summary": article.get("summary") or article.get("snippet") or article.get("title") or "",
                    "severity_score": float(article.get("tone", 0.0) or 0.0),
                    "event_time": _parse_time(article.get("seendate")) or datetime.now(timezone.utc),
                    "extracted_entities": {
                        "source_country": article.get("sourceCountry"),
                        "domain": article.get("domain"),
                        "url": article.get("url"),
                    },
                    "impact_tags": [tag for tag in ["geopolitical", "shipping", "sanctions"] if tag],
                }
            )

        return normalized or news_items()


def _gdelt_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d%H%M%S")
    return str(value)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
