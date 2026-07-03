from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query
from typing import Literal
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.scenario import (
    ScenarioCreateRequest,
    ScenarioListItemResponse,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioResultsEnvelopeResponse,
    ScenarioRunRequest,
    ScenarioSimulationResponse,
)
from app.services.audit_service import safe_record_audit_log
from app.services.scenario_service import (
    create_scenario,
    get_scenario,
    get_scenario_results,
    list_scenarios,
    run_scenario,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("", response_model=ScenarioResponse, summary="Create a disruption scenario")
def create(
    payload: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = create_scenario(db, payload, user_id=current_user.id)
    safe_record_audit_log(
        db,
        user_id=current_user.id,
        action="scenario_created",
        entity_type="scenario",
        entity_id=str(result["id"]),
        metadata={
            "scenario_name": result["name"],
            "scenario_type": result["scenario_type"],
            "status": result["status"],
        },
        commit=True,
    )
    return result


@router.get("", response_model=ScenarioListResponse, summary="List disruption scenarios")
def list_all(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    scenario_type: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioListResponse:
    return list_scenarios(
        db,
        limit=limit,
        offset=offset,
        status=status,
        scenario_type=scenario_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{scenario_id}", response_model=ScenarioListItemResponse, summary="Get a scenario")
def get_one(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return get_scenario(db, scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{scenario_id}/run", response_model=ScenarioSimulationResponse, summary="Run a scenario simulation")
def run(
    scenario_id: int,
    payload: ScenarioRunRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = run_scenario(db, scenario_id, payload)
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="scenario_executed",
            entity_type="scenario",
            entity_id=str(scenario_id),
            metadata={
                "scenario_name": result["scenario"]["name"],
                "mitigation_urgency_level": result.get("mitigation_urgency_level"),
                "supply_loss_pct": result["result"]["estimated_supply_loss_pct"],
            },
            commit=True,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{scenario_id}/results", response_model=ScenarioResultsEnvelopeResponse, summary="Get the latest scenario results")
def results(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return get_scenario_results(db, scenario_id)
