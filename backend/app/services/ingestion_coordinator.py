from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.ingestion.ais_ingestor import AISIngestor
from app.ingestion.base import utcnow
from app.ingestion.news_ingestor import NewsIngestor
from app.ingestion.prices_ingestor import PricesIngestor
from app.ingestion.refinery_ingestor import RefineryIngestor
from app.ingestion.sanctions_ingestor import SanctionsIngestor
from app.services.audit_service import safe_record_audit_log

logger = logging.getLogger(__name__)

INGESTOR_REGISTRY = {
    "news": NewsIngestor,
    "sanctions": SanctionsIngestor,
    "ais": AISIngestor,
    "prices": PricesIngestor,
    "refinery": RefineryIngestor,
}


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
            safe_record_audit_log(
                db,
                user_id=user_id,
                action="ingestion_run",
                entity_type="ingestion_source",
                entity_id=source_name,
                metadata={
                    "status": "success",
                    "demo_mode": demo_mode,
                    "fetched_count": outcome["fetched_count"],
                    "normalized_count": outcome["normalized_count"],
                    "upserted_count": outcome["upserted_count"],
                },
                commit=True,
            )
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
                safe_record_audit_log(
                    db,
                    user_id=user_id,
                    action="ingestion_error",
                    entity_type="ingestion_source",
                    entity_id=source_name,
                    metadata={"status": "failed", "error": str(exc), "demo_mode": demo_mode},
                    commit=True,
                )
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
