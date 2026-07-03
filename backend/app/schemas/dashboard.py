from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import APIBaseModel


class DashboardKpiResponse(APIBaseModel):
    """Top-level KPI block rendered on the dashboard hero section."""

    average_national_risk_score: float = Field(..., description="Average risk score across national signals")
    active_disruptions_count: int = Field(..., description="Count of active disruptions and high-risk events")
    shipments_at_risk_count: int = Field(..., description="Count of shipments with a risk flag")
    estimated_import_dependency_pct: float = Field(..., description="Estimated import dependency as a percentage")
    strategic_reserve_days_cover: float = Field(..., description="Estimated SPR days of cover")

class ChartPointResponse(APIBaseModel):
    """Generic chart point for frontend charting libraries."""

    label: str
    value: float
    meta: dict[str, Any] = Field(default_factory=dict)

class CorridorRiskResponse(APIBaseModel):
    corridor_id: int
    name: str
    risk_score: float
    risk_level: str
    status: str
    shipment_count: int
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

class SupplierRiskResponse(APIBaseModel):
    supplier_country_id: int
    name: str
    region: str
    risk_score: float
    risk_level: str
    shipment_count: int
    reliability_score: float
    sanctions_risk_base: float
    geopolitical_risk_base: float
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

class AlertResponse(APIBaseModel):
    id: int
    title: str
    event_type: str
    region: str
    severity_score: float
    event_time: datetime
    summary: str
    impact_tags: list[str] = Field(default_factory=list)

class PriceTrendPointResponse(APIBaseModel):
    benchmark_name: str
    timestamp: datetime
    price_usd: float
    source: str

class RefineryStressResponse(APIBaseModel):
    refinery_id: int
    name: str
    company: str
    state: str
    capacity_bpd: int
    complexity_index: float
    strategic_priority_score: float
    risk_score: float
    risk_level: str
    linked_port_name: str | None = None
    compatible_crude_grades: list[str] = Field(default_factory=list)
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

class RecommendationResponse(APIBaseModel):
    id: int
    title: str
    scenario_id: int | None = None
    refinery_id: int | None = None
    recommended_supplier: str
    recommended_route: str
    expected_cost_delta: float
    risk_reduction_score: float
    compatibility_score: float
    action_priority: str
    generated_at: datetime
    recommendation_payload: dict[str, Any] = Field(default_factory=dict)

class DashboardSummaryResponse(APIBaseModel):
    kpis: DashboardKpiResponse
