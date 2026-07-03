from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import (
    AlertResponse,
    CorridorRiskResponse,
    DashboardSummaryResponse,
    PriceTrendPointResponse,
    RefineryStressResponse,
    RecommendationResponse,
    SupplierRiskResponse,
)
from app.services.dashboard_service import (
    get_dashboard_kpis,
    get_latest_alerts,
    get_price_trends,
    get_refinery_stress,
    get_recommendations,
    get_corridor_risk,
    get_supplier_risk,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse, summary="Dashboard KPI summary")
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the top KPI block for the dashboard."""
    return {"kpis": get_dashboard_kpis(db)}


@router.get("/corridor-risk", response_model=list[CorridorRiskResponse], summary="Risk by corridor")
def corridor_risk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return corridor risk rows optimized for bar and heatmap charts."""
    return get_corridor_risk(db)


@router.get("/supplier-risk", response_model=list[SupplierRiskResponse], summary="Risk by supplier country")
def supplier_risk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return supplier country risk rows for ranking and drill-downs."""
    return get_supplier_risk(db)


@router.get("/alerts", response_model=list[AlertResponse], summary="Latest geopolitical alerts")
def alerts(
    limit: int = Query(default=5, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return the latest geopolitical and sanctions alerts."""
    return get_latest_alerts(db, limit=limit)


@router.get("/price-trends", response_model=list[PriceTrendPointResponse], summary="Recent price trend points")
def price_trends(
    limit: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return price trend data ordered for time-series charts."""
    return get_price_trends(db, limit=limit)


@router.get("/refinery-stress", response_model=list[RefineryStressResponse], summary="Refinery stress overview")
def refinery_stress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return refinery stress rows for operational dashboards."""
    return get_refinery_stress(db)


@router.get("/recommendations", response_model=list[RecommendationResponse], summary="Latest procurement recommendations")
def recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return the most recent procurement recommendations."""
    return get_recommendations(db, limit=limit)
