from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    IngestionRunRequest,
    IngestionRunResponse,
    JobRunResponse,
    SchedulerStatusResponse,
)
from app.services.ingestion_coordinator import run_ingestion
from app.jobs.risk_jobs import run_recompute_risk_job
from app.jobs.scheduler import get_scheduler_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/run-ingestion", response_model=IngestionRunResponse, summary="Run ingestion pipeline")
def run_ingestion_endpoint(
    payload: IngestionRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    """Trigger the demo-mode ingestion pipeline for selected sources."""
    try:
        return run_ingestion(
            db=db,
            sources=payload.sources or None,
            demo_mode=payload.demo_mode,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/recompute-risk", response_model=JobRunResponse, summary="Manually recompute risk scores")
def recompute_risk_job(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = run_recompute_risk_job()
        return {
            "job_name": "recompute-risk",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "result": result,
            "error": None,
        }
    except Exception as exc:
        return {
            "job_name": "recompute-risk",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "result": {},
            "error": str(exc),
        }


@router.post("/jobs/run-ingestion", response_model=JobRunResponse, summary="Manually run ingestion jobs")
def run_ingestion_job(
    payload: IngestionRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = run_ingestion(
            db=db,
            sources=payload.sources or None,
            demo_mode=payload.demo_mode,
            user_id=current_user.id,
        )
        return {
            "job_name": "run-ingestion",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "result": result,
            "error": None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        return {
            "job_name": "run-ingestion",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "result": {},
            "error": str(exc),
        }


@router.get("/jobs/status", response_model=SchedulerStatusResponse, summary="Get scheduler status")
def jobs_status(
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    status_payload = get_scheduler_status()
    return {
        "enabled": status_payload.enabled,
        "running": status_payload.running,
        "jobs": status_payload.jobs,
        "last_started_at": status_payload.last_started_at,
        "reason": status_payload.reason,
    }
