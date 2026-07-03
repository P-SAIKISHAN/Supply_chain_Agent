from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.config import settings
from app.jobs.cleanup_jobs import run_cleanup_job
from app.jobs.risk_jobs import run_recompute_risk_job
from app.jobs.scenario_jobs import run_scenario_audit_job
from app.services.ingestion_coordinator import run_ingestion
from app.core.database import SessionLocal


logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
except ImportError:  # pragma: no cover - APScheduler is optional
    BackgroundScheduler = None  # type: ignore[assignment]
    IntervalTrigger = None  # type: ignore[assignment]


_scheduler_instance: Any | None = None
_scheduler_started = False


@dataclass
class SchedulerStatus:
    enabled: bool
    running: bool
    jobs: list[dict[str, Any]] = field(default_factory=list)
    last_started_at: str | None = None
    reason: str | None = None


def _job_wrapper(job_name: str, func: Callable[[], Any]) -> Callable[[], Any]:
    def runner() -> Any:
        logger.info("scheduler_job_start", extra={"job": job_name})
        try:
            result = func()
            logger.info("scheduler_job_complete", extra={"job": job_name, "result": result})
            return result
        except Exception:
            logger.exception("scheduler_job_failed", extra={"job": job_name})
            raise

    return runner


def _add_job(scheduler: Any, func: Callable[[], Any], job_id: str, minutes: int, **kwargs: Any) -> None:
    if IntervalTrigger is None:
        return
    scheduler.add_job(
        _job_wrapper(job_id, func),
        trigger=IntervalTrigger(minutes=minutes),
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=minutes * 60,
        **kwargs,
    )


def get_scheduler_status() -> SchedulerStatus:
    running = bool(_scheduler_instance and getattr(_scheduler_instance, "running", False))
    jobs: list[dict[str, Any]] = []
    reason: str | None = None
    if _scheduler_instance is not None:
        for job in getattr(_scheduler_instance, "get_jobs", lambda: [])():
            next_run = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": getattr(job, "id", None),
                    "next_run_time": next_run.isoformat() if next_run else None,
                    "trigger": str(getattr(job, "trigger", "")),
                }
            )
    if not settings.enable_scheduler:
        reason = "scheduler_disabled_in_config"
    elif _scheduler_instance is None:
        reason = "scheduler_not_started"
    elif not running:
        reason = "scheduler_not_running"

    return SchedulerStatus(
        enabled=bool(settings.enable_scheduler),
        running=running,
        jobs=jobs,
        last_started_at=getattr(get_scheduler_status, "_last_started_at", None),
        reason=reason,
    )


def start_scheduler() -> Any | None:
    global _scheduler_instance, _scheduler_started

    if not settings.enable_scheduler:
        logger.info("scheduler_disabled", extra={"environment": settings.environment})
        return None

    if _scheduler_started and _scheduler_instance is not None:
        logger.info("scheduler_already_running")
        return _scheduler_instance

    if BackgroundScheduler is None:
        logger.warning("apscheduler_not_installed_scheduler_disabled")
        return None

    if os.getenv("UVICORN_RELOAD") == "true" and os.getenv("RUN_MAIN") not in {"true", "1"}:
        logger.info("scheduler_start_skipped_reload_parent")
        return None

    scheduler = BackgroundScheduler(timezone=timezone.utc)

    def ingest_news_job() -> Any:
        db = SessionLocal()
        try:
            return run_ingestion(db=db, sources=["news"], demo_mode=True, user_id=None)
        finally:
            db.close()

    def ingest_sanctions_job() -> Any:
        db = SessionLocal()
        try:
            return run_ingestion(db=db, sources=["sanctions"], demo_mode=True, user_id=None)
        finally:
            db.close()

    def ingest_prices_job() -> Any:
        db = SessionLocal()
        try:
            return run_ingestion(db=db, sources=["prices"], demo_mode=True, user_id=None)
        finally:
            db.close()

    interval_minutes = max(5, int(settings.scheduler_interval_minutes or 30))
    _add_job(scheduler, ingest_news_job, "ingest_news", interval_minutes)
    _add_job(scheduler, ingest_sanctions_job, "ingest_sanctions", interval_minutes)
    _add_job(scheduler, ingest_prices_job, "ingest_prices", interval_minutes)
    _add_job(scheduler, run_recompute_risk_job, "recompute_risk", interval_minutes)
    _add_job(scheduler, run_scenario_audit_job, "scenario_audit", max(15, interval_minutes * 2))
    _add_job(scheduler, lambda: run_cleanup_job(retention_days=30), "cleanup", max(60, interval_minutes * 4))

    scheduler.start()
    _scheduler_instance = scheduler
    _scheduler_started = True
    setattr(get_scheduler_status, "_last_started_at", datetime.now(timezone.utc).isoformat())
    logger.info(
        "scheduler_started",
        extra={"jobs": [job.id for job in scheduler.get_jobs()], "interval_minutes": interval_minutes},
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler_instance, _scheduler_started
    if _scheduler_instance is not None:
        try:
            _scheduler_instance.shutdown(wait=False)
        except Exception:
            logger.exception("scheduler_shutdown_failed")
    _scheduler_instance = None
    _scheduler_started = False
