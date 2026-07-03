from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Literal
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
from app.services.audit_service import safe_record_audit_log
from app.services.spr_service import get_spr_plan, list_spr_plans, optimize_spr_plan

router = APIRouter(prefix="/spr", tags=["spr"])


@router.post("/optimize", response_model=SPROptimizeResponse, summary="Generate an SPR drawdown plan")
def optimize(
    payload: SPROptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = optimize_spr_plan(db, payload)
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="spr_optimized",
            entity_type="spr_plan",
            entity_id=str(result["plan"].id),
            metadata={
                "scenario_id": payload.scenario_id,
                "target_scope": payload.target_scope,
                "total_drawdown_bbl": result["plan"].total_drawdown_bbl,
                "drawdown_days": result["plan"].drawdown_days,
            },
            commit=True,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/plans", response_model=SPRPlanListResponse, summary="List SPR plans")
def plans(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    scenario_id: int | None = None,
    sort_by: str = Query(default="generated_at"),
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SPRPlanListResponse:
    return list_spr_plans(
        db,
        limit=limit,
        offset=offset,
        scenario_id=scenario_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )


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
