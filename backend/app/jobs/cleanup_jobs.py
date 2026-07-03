from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.intelligence_chunk import IntelligenceChunk
from app.models.intelligence_document import IntelligenceDocument


logger = logging.getLogger(__name__)


def run_cleanup_job(retention_days: int = 30) -> dict[str, Any]:
    """Remove stale non-critical artifacts while preserving operational data."""
    db = SessionLocal()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    try:
        chunk_delete = db.execute(
            delete(IntelligenceChunk).where(IntelligenceChunk.created_at < cutoff)
        )
        document_delete = db.execute(
            delete(IntelligenceDocument).where(
                IntelligenceDocument.created_at < cutoff,
                IntelligenceDocument.chunk_count == 0,
            )
        )
        audit_delete = db.execute(
            delete(AuditLog).where(
                AuditLog.created_at < cutoff,
                AuditLog.action.in_(["ingestion_run", "ingestion_error"]),
            )
        )
        db.commit()
        result = {
            "cutoff": cutoff.isoformat(),
            "deleted_chunks": getattr(chunk_delete, "rowcount", 0),
            "deleted_documents": getattr(document_delete, "rowcount", 0),
            "deleted_audit_logs": getattr(audit_delete, "rowcount", 0),
        }
        logger.info("cleanup_job_complete", extra=result)
        return result
    except Exception:
        db.rollback()
        logger.exception("cleanup_job_failed")
        raise
    finally:
        db.close()

