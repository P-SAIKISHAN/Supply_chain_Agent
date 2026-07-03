from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import BaseIngestor, upsert_row
from app.ingestion.sample_data import refinery_items
from app.models.port import Port
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore


class RefineryIngestor(BaseIngestor):
    """Normalize refinery operational snapshots into refinery records."""

    source_name = "refinery"

    def fetch(self) -> list[dict[str, Any]]:
        return refinery_items()

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "name": str(record["name"]).strip(),
                    "company": str(record.get("company", "")).strip(),
                    "state": str(record.get("state", "")).strip(),
                    "capacity_bpd": int(record.get("capacity_bpd", 0)),
                    "complexity_index": float(record.get("complexity_index", 0.0)),
                    "compatible_crude_grades": list(record.get("compatible_crude_grades", [])),
                    "linked_port_name": record.get("linked_port_name"),
                    "strategic_priority_score": float(record.get("strategic_priority_score", 0.0)),
                }
            )
        return normalized

    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        port_lookup = {row.name: row.id for row in db.query(Port).all()}
        for record in records:
            linked_port_id = port_lookup.get(record["linked_port_name"]) if record.get("linked_port_name") else None
            payload = {
                "company": record["company"],
                "state": record["state"],
                "capacity_bpd": record["capacity_bpd"],
                "complexity_index": record["complexity_index"],
                "compatible_crude_grades": record["compatible_crude_grades"],
                "linked_port_id": linked_port_id,
                "strategic_priority_score": record["strategic_priority_score"],
            }
            refinery, was_created = upsert_row(db, Refinery, {"name": record["name"]}, payload)
            if was_created:
                created += 1
            else:
                updated += 1

            risk_score = min(
                0.95,
                (record["complexity_index"] / 20.0) * 0.6 + (record["strategic_priority_score"] * 0.4),
            )
            upsert_row(
                db,
                RiskScore,
                {"scope_type": "refinery", "scope_id": str(refinery.id)},
                {
                    "risk_score": round(risk_score, 2),
                    "risk_level": "critical" if risk_score >= 0.8 else "high" if risk_score >= 0.65 else "medium",
                    "confidence_score": 0.8,
                    "contributing_factors": {
                        "capacity_bpd": record["capacity_bpd"],
                        "complexity_index": record["complexity_index"],
                        "strategic_priority_score": record["strategic_priority_score"],
                    },
                    "computed_at": refinery.updated_at,
                },
            )

        self.logger.info(
            "refinery_ingestion_complete",
            extra={"created": created, "updated": updated, "records": len(records)},
        )
        return {"upserted_count": len(records), "created_count": created, "updated_count": updated}

