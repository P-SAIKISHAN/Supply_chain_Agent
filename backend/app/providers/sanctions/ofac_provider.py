from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.ingestion.sample_data import sanctions_items
from app.providers.base import ProviderError, SanctionsProvider
from app.providers.http import get_json


class OFACSanctionsProvider(SanctionsProvider):
    """Fetch sanctions data with a safe demo fallback.

    Note: OFAC data is often distributed through downloadable lists rather than a
    single simple JSON API, so this provider is intentionally scaffolded. The
    platform can use mock/demo data until a live feed or parsed file source is wired.
    """

    source_name = "ofac"

    def configured(self) -> bool:
        return bool(settings.ofac_enabled and settings.ofac_base_url)

    def fetch(self) -> list[dict[str, Any]]:
        if self.demo_mode or not self.configured():
            return sanctions_items()
        try:
            # This is a scaffolded request path. If a real sanctions feed is wired,
            # replace the URL/path with the exact source export endpoint.
            payload = get_json(settings.ofac_base_url)
        except ProviderError:
            return sanctions_items()

        items = payload.get("items") or payload.get("results") or []
        normalized: list[dict[str, Any]] = []
        for item in items:
            normalized.append(
                {
                    "jurisdiction": item.get("jurisdiction") or "United States",
                    "target_country": item.get("target_country") or item.get("country") or "Unknown",
                    "target_entity": item.get("target_entity") or item.get("name") or "Unknown entity",
                    "sanction_type": item.get("sanction_type") or item.get("type") or "designation",
                    "effective_date": item.get("effective_date"),
                    "severity_score": float(item.get("severity_score", 0.0) or 0.0),
                    "notes": item.get("notes") or item.get("description") or "",
                }
            )
        return normalized or sanctions_items()
