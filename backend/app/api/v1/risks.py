from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.risk import (
    CorridorRiskResponse,
    RefineryRiskResponse,
    RiskOverviewResponse,
    RiskRecomputeResponse,
    ShipmentRiskResponse,
    SupplierRiskResponse,
)
from app.services.risk_service import (
    get_corridor_risks,
    get_refinery_risks,
    get_risk_overview,
    get_shipment_risks,
    get_supplier_risks,
    recompute_risk_scores,
)

router = APIRouter(prefix="/risks", tags=["risks"])


@router.post("/recompute", response_model=RiskRecomputeResponse, summary="Recompute all risk scores")
def recompute(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Recompute the deterministic risk engine outputs."""
    try:
        return recompute_risk_scores(db)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/overview", response_model=RiskOverviewResponse, summary="Risk overview")
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a high-level risk summary for operations and dashboard views."""
    return get_risk_overview(db)


@router.get("/corridors", response_model=list[CorridorRiskResponse], summary="Corridor risk scores")
def corridors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return corridor-level disruption risk rows."""
    return get_corridor_risks(db)


@router.get("/suppliers", response_model=list[SupplierRiskResponse], summary="Supplier risk scores")
def suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return supplier-country disruption risk rows."""
    return get_supplier_risks(db)


@router.get("/shipments", response_model=list[ShipmentRiskResponse], summary="Shipment risk scores")
def shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return shipment-level exposure risk rows."""
    return get_shipment_risks(db)


@router.get("/refineries", response_model=list[RefineryRiskResponse], summary="Refinery risk scores")
def refineries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return refinery-level stress risk rows."""
    return get_refinery_risks(db)

