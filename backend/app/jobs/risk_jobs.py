from __future__ import annotations

import logging
from typing import Any

from app.core.database import SessionLocal
from app.services.risk_service import recompute_risk_scores


logger = logging.getLogger(__name__)


def run_recompute_risk_job() -> dict[str, Any]:
    """Run the risk recomputation job with isolated DB session handling."""
    db = SessionLocal()
    try:
        result = recompute_risk_scores(db)
        logger.info("risk_recompute_job_complete", extra={"summary": result})
        return result
    except Exception:
        logger.exception("risk_recompute_job_failed")
        raise
    finally:
        db.close()

