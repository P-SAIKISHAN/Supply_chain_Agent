from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import BaseIngestor, upsert_row
from app.ingestion.sample_data import ais_items
from app.models.port import Port
from app.models.risk_score import RiskScore
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.providers.registry import get_ais_provider


class AISIngestor(BaseIngestor):
    """Normalize AIS vessel observations into shipment records."""

    source_name = "ais"

    def fetch(self) -> list[dict[str, Any]]:
        provider = get_ais_provider(demo_mode=self.demo_mode)
        try:
            records = provider.fetch()
            return records or ais_items()
        except Exception as exc:  # pragma: no cover - provider fallback
            self.logger.warning("ais_provider_failed", extra={"error": str(exc)})
            return ais_items()

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "tanker_name": str(record["tanker_name"]).strip(),
                    "supplier_country": str(record["supplier_country"]).strip(),
                    "source_port": str(record["source_port"]).strip(),
                    "destination_port": str(record["destination_port"]).strip(),
                    "corridor": str(record["corridor"]).strip(),
                    "cargo_volume_bbl": float(record.get("cargo_volume_bbl", 0.0)),
                    "crude_grade": str(record.get("crude_grade", "")).strip(),
                    "eta": record["eta"],
                    "status": str(record.get("status", "scheduled")).strip(),
                    "freight_cost": float(record.get("freight_cost", 0.0)),
                    "risk_flag": bool(record.get("risk_flag", False)),
                }
            )
        return normalized

    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        skipped = 0

        country_lookup = {row.name: row.id for row in db.query(SupplierCountry).all()}
        port_lookup = {row.name: row.id for row in db.query(Port).all()}
        corridor_lookup = {row.name: row.id for row in db.query(ShippingCorridor).all()}

        for record in records:
            supplier_country_id = country_lookup.get(record["supplier_country"])
            source_port_id = port_lookup.get(record["source_port"])
            destination_port_id = port_lookup.get(record["destination_port"])
            corridor_id = corridor_lookup.get(record["corridor"])

            if not all([supplier_country_id, source_port_id, destination_port_id, corridor_id]):
                skipped += 1
                self.logger.warning(
                    "ais_record_skipped_missing_lookup",
                    extra={"tanker_name": record["tanker_name"], "record": record},
                )
                continue

            payload = {
                "supplier_country_id": supplier_country_id,
                "source_port_id": source_port_id,
                "destination_port_id": destination_port_id,
                "corridor_id": corridor_id,
                "cargo_volume_bbl": record["cargo_volume_bbl"],
                "crude_grade": record["crude_grade"],
                "eta": record["eta"],
                "status": record["status"],
                "freight_cost": record["freight_cost"],
                "risk_flag": record["risk_flag"],
            }

            shipment, was_created = upsert_row(db, Shipment, {"tanker_name": record["tanker_name"]}, payload)
            if was_created:
                created += 1
            else:
                updated += 1

            risk_score = 0.2 + (0.5 if record["risk_flag"] else 0.0) + min(0.3, record["freight_cost"] / 20000000.0)
            risk_payload = {
                "risk_score": round(risk_score, 2),
                "risk_level": "high" if risk_score >= 0.65 else "medium" if risk_score >= 0.4 else "low",
                "confidence_score": 0.78,
                "contributing_factors": {
                    "risk_flag": record["risk_flag"],
                    "freight_cost": record["freight_cost"],
                    "cargo_volume_bbl": record["cargo_volume_bbl"],
                },
            }
            upsert_row(
                db,
                RiskScore,
                {"scope_type": "shipment", "scope_id": record["tanker_name"]},
                {**risk_payload, "computed_at": shipment.updated_at},
            )

        self.logger.info(
            "ais_ingestion_complete",
            extra={"created": created, "updated": updated, "skipped": skipped, "records": len(records)},
        )
        return {
            "upserted_count": created + updated,
            "created_count": created,
            "updated_count": updated,
            "skipped_count": skipped,
        }
