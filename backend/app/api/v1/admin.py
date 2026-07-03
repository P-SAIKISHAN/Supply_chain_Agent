from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AuditLogListResponse,
    IngestionRunRequest,
    IngestionRunResponse,
    JobRunResponse,
    SeedDemoResponse,
    SchedulerStatusResponse,
    SystemSummaryResponse,
)
from app.services.admin_service import get_system_summary, list_audit_logs, seed_demo_data_from_api
from app.services.audit_service import safe_record_audit_log
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
        result = run_ingestion(
            db=db,
            sources=payload.sources or None,
            demo_mode=payload.demo_mode,
            user_id=current_user.id,
        )
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="manual_ingestion_run",
            entity_type="ingestion_run",
            entity_id=",".join(result.get("requested_sources", [])) or "all",
            metadata={
                "sources": result.get("requested_sources", []),
                "demo_mode": payload.demo_mode,
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0),
            },
            commit=True,
        )
        return result
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
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="risk_recomputed",
            entity_type="risk_job",
            entity_id="recompute-risk",
            metadata={
                "status": "success",
                "result": result,
            },
            commit=True,
        )
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
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="manual_ingestion_run",
            entity_type="ingestion_run",
            entity_id=",".join(result.get("requested_sources", [])) or "all",
            metadata={
                "sources": result.get("requested_sources", []),
                "demo_mode": payload.demo_mode,
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0),
            },
            commit=True,
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


@router.get("/audit-logs", response_model=AuditLogListResponse, summary="List audit logs")
def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> AuditLogListResponse:
    return list_audit_logs(
        db,
        limit=limit,
        offset=offset,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
    )


@router.get("/system-summary", response_model=SystemSummaryResponse, summary="Get system summary")
def system_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> SystemSummaryResponse:
    return get_system_summary(db)


@router.post("/seed-demo", response_model=SeedDemoResponse, summary="Seed demo data")
def seed_demo(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> SeedDemoResponse:
    return seed_demo_data_from_api(db, user_id=current_user.id)
