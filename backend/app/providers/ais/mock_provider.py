from __future__ import annotations

from typing import Any

from app.ingestion.sample_data import ais_items
from app.providers.base import AISProvider


class MockAISProvider(AISProvider):
    """Deterministic AIS mock provider."""

    source_name = "mock_ais"

    def fetch(self) -> list[dict[str, Any]]:
        return ais_items()
