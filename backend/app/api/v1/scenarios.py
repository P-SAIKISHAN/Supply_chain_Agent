from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.scenario import (
    ScenarioCreateRequest,
    ScenarioListItemResponse,
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
        entity_id=str(result["scenario"]["id"]),
        metadata={
            "scenario_name": result["scenario"]["name"],
            "scenario_type": result["scenario"]["scenario_type"],
            "status": result["scenario"]["status"],
        },
        commit=True,
    )
    return result


@router.get("", response_model=list[ScenarioListItemResponse], summary="List disruption scenarios")
def list_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return list_scenarios(db)


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
