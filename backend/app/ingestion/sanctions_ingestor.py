from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import BaseIngestor, upsert_row
from app.ingestion.sample_data import sanctions_items
from app.models.sanctions_event import SanctionsEvent
from app.providers.registry import get_sanctions_provider


class SanctionsIngestor(BaseIngestor):
    """Normalize sanctions bulletins into sanctions event records."""

    source_name = "sanctions"

    def fetch(self) -> list[dict[str, Any]]:
        provider = get_sanctions_provider(demo_mode=self.demo_mode)
        try:
            records = provider.fetch()
            return records or sanctions_items()
        except Exception as exc:  # pragma: no cover - provider fallback
            self.logger.warning("sanctions_provider_failed", extra={"error": str(exc)})
            return sanctions_items()

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "jurisdiction": str(record["jurisdiction"]).strip(),
                    "target_country": str(record["target_country"]).strip(),
                    "target_entity": str(record["target_entity"]).strip(),
                    "sanction_type": str(record["sanction_type"]).strip(),
                    "effective_date": record["effective_date"],
                    "severity_score": float(record.get("severity_score", 0.0)),
                    "notes": str(record.get("notes", "")).strip() or None,
                }
            )
        return normalized

    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        for record in records:
            lookup = {
                "jurisdiction": record["jurisdiction"],
                "target_entity": record["target_entity"],
                "effective_date": record["effective_date"],
            }
            _, was_created = upsert_row(db, SanctionsEvent, lookup, record)
            if was_created:
                created += 1
            else:
                updated += 1
        self.logger.info(
            "sanctions_ingestion_complete",
            extra={"created": created, "updated": updated, "records": len(records)},
        )
        return {"upserted_count": len(records), "created_count": created, "updated_count": updated}
