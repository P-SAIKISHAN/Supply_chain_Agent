from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import IngestionRunRequest, IngestionRunResponse
from app.services.ingestion_coordinator import run_ingestion

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

