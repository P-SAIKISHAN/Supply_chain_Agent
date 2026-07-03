from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.ingestion.sample_data import ais_items
from app.providers.base import AISProvider, ProviderError
from app.providers.http import get_json


class MarineTrafficAISProvider(AISProvider):
    """Scaffolded MarineTraffic provider with demo fallback."""

    source_name = "marinetraffic"

    def configured(self) -> bool:
        return bool(settings.marinetraffic_api_key and settings.marinetraffic_base_url)

    def fetch(self) -> list[dict[str, Any]]:
        if self.demo_mode or not self.configured():
            return ais_items()
        try:
            # Replace with the exact MarineTraffic endpoint when credentials are available.
            payload = get_json(
                settings.marinetraffic_base_url,
                headers={"Authorization": f"Bearer {settings.marinetraffic_api_key}"},
            )
        except ProviderError:
            return ais_items()

        items = payload.get("data") or payload.get("ships") or []
        normalized: list[dict[str, Any]] = []
        for item in items:
            normalized.append(
                {
                    "tanker_name": item.get("name") or item.get("vessel_name") or "AIS vessel",
                    "supplier_country": item.get("supplier_country") or item.get("flag") or "Unknown",
                    "source_port": item.get("source_port") or item.get("last_port") or "Unknown port",
                    "destination_port": item.get("destination_port") or item.get("next_port") or "Unknown port",
                    "corridor": item.get("corridor") or "Unknown corridor",
                    "cargo_volume_bbl": float(item.get("cargo_volume_bbl", 0.0) or 0.0),
                    "crude_grade": item.get("crude_grade") or "",
                    "eta": item.get("eta"),
                    "status": item.get("status") or "scheduled",
                    "freight_cost": float(item.get("freight_cost", 0.0) or 0.0),
                    "risk_flag": bool(item.get("risk_flag", False)),
                }
            )
        return normalized or ais_items()
