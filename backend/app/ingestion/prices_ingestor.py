from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import BaseIngestor, upsert_row
from app.ingestion.sample_data import price_items
from app.models.commodity_price import CommodityPrice


class PricesIngestor(BaseIngestor):
    """Normalize benchmark price points into commodity price records."""

    source_name = "prices"

    def fetch(self) -> list[dict[str, Any]]:
        return price_items()

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "benchmark_name": str(record["benchmark_name"]).strip(),
                    "price_usd": float(record.get("price_usd", 0.0)),
                    "timestamp": record["timestamp"],
                    "source": str(record.get("source", "demo-market")).strip(),
                }
            )
        return normalized

    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        for record in records:
            _, was_created = upsert_row(
                db,
                CommodityPrice,
                {"benchmark_name": record["benchmark_name"], "timestamp": record["timestamp"]},
                record,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.logger.info(
            "prices_ingestion_complete",
            extra={"created": created, "updated": updated, "records": len(records)},
        )
        return {"upserted_count": len(records), "created_count": created, "updated_count": updated}

