from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import BaseIngestor, upsert_row
from app.ingestion.sample_data import news_items
from app.models.geopolitical_event import GeopoliticalEvent


class NewsIngestor(BaseIngestor):
    """Normalize geopolitical and security news into event records."""

    source_name = "news"

    def fetch(self) -> list[dict[str, Any]]:
        return news_items()

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "title": str(record["title"]).strip(),
                    "event_type": str(record.get("event_type", "news")).strip(),
                    "region": str(record.get("region", "Global")).strip(),
                    "source": str(record.get("source", "demo-newswire")).strip(),
                    "summary": str(record.get("summary", "")).strip(),
                    "severity_score": float(record.get("severity_score", 0.0)),
                    "event_time": record["event_time"],
                    "extracted_entities": record.get("extracted_entities", {}),
                    "impact_tags": list(record.get("impact_tags", [])),
                }
            )
        return normalized

    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        for record in records:
            _, was_created = upsert_row(db, GeopoliticalEvent, {"title": record["title"]}, record)
            if was_created:
                created += 1
            else:
                updated += 1
        self.logger.info(
            "news_ingestion_complete",
            extra={"created": created, "updated": updated, "records": len(records)},
        )
        return {"upserted_count": len(records), "created_count": created, "updated_count": updated}

