from __future__ import annotations

import logging
from typing import Any

from app.core.database import SessionLocal
from app.services.scenario_service import list_scenarios


logger = logging.getLogger(__name__)


def run_scenario_audit_job() -> dict[str, Any]:
    """Lightweight scheduled scenario maintenance hook.

    The job intentionally does not mutate data. It is a placeholder for future
    scenario refreshes, stale result marking, or scheduled reruns.
    """
    db = SessionLocal()
    try:
        scenarios = list_scenarios(db)
        result = {"scenario_count": len(scenarios)}
        logger.info("scenario_job_complete", extra=result)
        return result
    except Exception:
        logger.exception("scenario_job_failed")
        raise
    finally:
        db.close()

