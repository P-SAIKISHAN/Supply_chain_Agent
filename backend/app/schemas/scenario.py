from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, conint, confloat

from app.schemas.common import APIBaseModel, ORMBaseSchema


class ScenarioAssumptions(APIBaseModel):
    """Structured assumptions used by the scenario simulation engine."""

    impacted_corridors: list[int] = Field(default_factory=list)
    impacted_suppliers: list[int] = Field(default_factory=list)
    duration_days: int = Field(..., ge=1, description="Duration of the disruption in days")
    disruption_severity_pct: float = Field(..., ge=0.0, le=100.0)
    price_shock_pct: float = Field(0.0, ge=0.0, le=100.0)
    tanker_delay_days: int = Field(0, ge=0)
    reserve_usage_allowed: bool = True


class ScenarioCreateRequest(APIBaseModel):
    """Payload for creating a new disruption scenario."""

    name: str = Field(..., min_length=3, max_length=220)
    scenario_type: str = Field(..., min_length=3, max_length=120)
    trigger_description: str = Field(..., min_length=10)
    impacted_corridors: list[int] = Field(default_factory=list)
    impacted_suppliers: list[int] = Field(default_factory=list)
    duration_days: conint(ge=1) = 7
    disruption_severity_pct: confloat(ge=0.0, le=100.0) = 50.0
    price_shock_pct: confloat(ge=0.0, le=100.0) = 0.0
    tanker_delay_days: conint(ge=0) = 0
    reserve_usage_allowed: bool = True
    status: str = "draft"


class ScenarioRunRequest(APIBaseModel):
    """Optional override payload when running a scenario."""

    duration_days: conint(ge=1) | None = None
    disruption_severity_pct: confloat(ge=0.0, le=100.0) | None = None
    price_shock_pct: confloat(ge=0.0, le=100.0) | None = None
    tanker_delay_days: conint(ge=0) | None = None
    reserve_usage_allowed: bool | None = None
    impacted_corridors: list[int] | None = None
    impacted_suppliers: list[int] | None = None


class ScenarioRefineryImpact(APIBaseModel):
    refinery_id: int
    name: str
    company: str
    state: str
    stress_score: float
    risk_level: str
    linked_port_name: str | None = None

class ScenarioResponse(ORMBaseSchema):
    id: int
    name: str
    scenario_type: str
    trigger_description: str
    assumptions: ScenarioAssumptions
    duration_days: int
    status: str
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class ScenarioResultResponse(ORMBaseSchema):
    id: int
    scenario_id: int
    estimated_supply_loss_pct: float
    refinery_utilization_impact: float
    fuel_price_impact_pct: float
    logistics_cost_impact_pct: float
    gdp_impact_estimate: float
    output_json: dict[str, Any]
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class ScenarioSimulationResponse(APIBaseModel):
    """Frontend-friendly scenario simulation payload."""

    scenario: ScenarioResponse
    result: ScenarioResultResponse
    most_affected_refineries: list[ScenarioRefineryImpact] = Field(default_factory=list)
    mitigation_urgency_level: str


class ScenarioListItemResponse(APIBaseModel):
    """Scenario row with current result summary for list endpoints."""

    scenario: ScenarioResponse
    result: ScenarioResultResponse | None = None
    mitigation_urgency_level: str | None = None
    most_affected_refineries: list[ScenarioRefineryImpact] = Field(default_factory=list)


class ScenarioListResponse(APIBaseModel):
    """Paginated scenario list response."""

    items: list[ScenarioListItemResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
    page: int
    pages: int
    sort_by: str | None = None
    sort_order: str | None = None


class ScenarioResultsEnvelopeResponse(APIBaseModel):
    """Envelope returned by the scenario results endpoint."""

    scenario_id: int
    result: ScenarioResultResponse | None = None
    mitigation_urgency_level: str | None = None
    most_affected_refineries: list[ScenarioRefineryImpact] = Field(default_factory=list)
