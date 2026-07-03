from __future__ import annotations

from typing import Any

from app.ingestion.sample_data import sanctions_items
from app.providers.base import SanctionsProvider


class MockSanctionsProvider(SanctionsProvider):
    """Deterministic mock sanctions provider for demo mode."""

    source_name = "mock_sanctions"

    def fetch(self) -> list[dict[str, Any]]:
        return sanctions_items()
