from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.ingestion.ais_ingestor import AISIngestor
from app.ingestion.base import utcnow
from app.ingestion.news_ingestor import NewsIngestor
from app.ingestion.prices_ingestor import PricesIngestor
from app.ingestion.refinery_ingestor import RefineryIngestor
from app.ingestion.sanctions_ingestor import SanctionsIngestor
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

INGESTOR_REGISTRY = {
    "news": NewsIngestor,
    "sanctions": SanctionsIngestor,
    "ais": AISIngestor,
    "prices": PricesIngestor,
    "refinery": RefineryIngestor,
}


def _record_audit(db: Session, user_id: int | None, action: str, entity_type: str, entity_id: str, metadata: dict) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
    )


def run_ingestion(
    db: Session,
    sources: Iterable[str] | None = None,
    demo_mode: bool = True,
    user_id: int | None = None,
) -> dict:
    """Run one or more ingestion sources and return a detailed summary."""
    requested_sources = [source.lower().strip() for source in (sources or INGESTOR_REGISTRY.keys())]
    unknown_sources = [source for source in requested_sources if source not in INGESTOR_REGISTRY]
    if unknown_sources:
        raise ValueError(f"Unsupported ingestion source(s): {', '.join(unknown_sources)}")

    started_at = utcnow()
    results: list[dict] = []
    success_count = 0
    failure_count = 0

    for source_name in requested_sources:
        ingestor = INGESTOR_REGISTRY[source_name](demo_mode=demo_mode)
        source_started_at = utcnow()
        try:
            outcome = ingestor.run(db)
            outcome["status"] = "success"
            outcome["error"] = None
            results.append(
                {
                    **outcome,
                    "started_at": source_started_at.isoformat(),
                    "finished_at": outcome["finished_at"].isoformat(),
                }
            )
            _record_audit(
                db,
                user_id,
                "ingestion_run",
                "ingestion_source",
                source_name,
                {
                    "status": "success",
                    "demo_mode": demo_mode,
                    "fetched_count": outcome["fetched_count"],
                    "normalized_count": outcome["normalized_count"],
                    "upserted_count": outcome["upserted_count"],
                },
            )
            db.commit()
            success_count += 1
            logger.info(
                "ingestion_source_complete",
                extra={"source": source_name, "demo_mode": demo_mode, "summary": outcome},
            )
        except Exception as exc:
            db.rollback()
            failure_count += 1
            error_payload = {
                "source": source_name,
                "demo_mode": demo_mode,
                "started_at": source_started_at.isoformat(),
                "finished_at": utcnow().isoformat(),
                "fetched_count": 0,
                "normalized_count": 0,
                "upserted_count": 0,
                "created_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "status": "failed",
                "error": str(exc),
            }
            results.append(error_payload)
            try:
                _record_audit(
                    db,
                    user_id,
                    "ingestion_error",
                    "ingestion_source",
                    source_name,
                    {"status": "failed", "error": str(exc), "demo_mode": demo_mode},
                )
                db.commit()
            except Exception:
                db.rollback()
            logger.exception(
                "ingestion_source_failed",
                extra={"source": source_name, "demo_mode": demo_mode},
            )

    finished_at = utcnow()
    return {
        "run_started_at": started_at.isoformat(),
        "run_finished_at": finished_at.isoformat(),
        "requested_sources": requested_sources,
        "results": results,
        "success_count": success_count,
        "failure_count": failure_count,
    }

