from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.spr import (
    SPRPlanListResponse,
    SPRPlanResponse,
    SPROptimizeRequest,
    SPROptimizeResponse,
)
from app.services.spr_service import get_spr_plan, list_spr_plans, optimize_spr_plan

router = APIRouter(prefix="/spr", tags=["spr"])


@router.post("/optimize", response_model=SPROptimizeResponse, summary="Generate an SPR drawdown plan")
def optimize(
    payload: SPROptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return optimize_spr_plan(db, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/plans", response_model=SPRPlanListResponse, summary="List SPR plans")
def plans(
    limit: int = Query(50, ge=1, le=200),
    scenario_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SPRPlanListResponse:
    return list_spr_plans(db, limit=limit, scenario_id=scenario_id)


@router.get("/plans/{plan_id}", response_model=SPRPlanResponse, summary="Get an SPR plan")
def plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SPRPlanResponse:
    try:
        return get_spr_plan(db, plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

