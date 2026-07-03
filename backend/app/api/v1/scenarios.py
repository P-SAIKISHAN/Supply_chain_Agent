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
    return create_scenario(db, payload, user_id=current_user.id)


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
        return run_scenario(db, scenario_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{scenario_id}/results", response_model=ScenarioResultsEnvelopeResponse, summary="Get the latest scenario results")
def results(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return get_scenario_results(db, scenario_id)

