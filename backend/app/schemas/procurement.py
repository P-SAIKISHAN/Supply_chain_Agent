from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, conint

from app.schemas.common import APIBaseModel, ORMBaseSchema

ProcurementScope = Literal["national", "refinery", "scenario"]


class ProcurementRecommendRequest(APIBaseModel):
    """Input for generating procurement alternatives."""

    target_scope: ProcurementScope = "national"
    scenario_id: int | None = None
    refinery_id: int | None = None
    top_n: conint(ge=1, le=20) = 5
    candidate_suppliers_limit: conint(ge=1, le=20) = 5
    candidate_corridors_limit: conint(ge=1, le=20) = 5


class ProcurementRecommendationResponse(ORMBaseSchema):
    """Persisted recommendation row returned by the API."""

    id: int
    scenario_id: int | None = None
    refinery_id: int | None = None
    title: str
    recommended_supplier: str
    recommended_route: str
    expected_cost_delta: float
    risk_reduction_score: float
    compatibility_score: float
    action_priority: str
    generated_at: datetime
    recommendation_payload: dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    delivery_delay_days: float = 0.0
    sanctions_safety_score: float = 0.0
    rationale: str | None = None


class ProcurementOptionResponse(APIBaseModel):
    """One ranked recommendation option produced by the engine."""

    title: str
    scenario_id: int | None = None
    refinery_id: int | None = None
    supplier_country_id: int | None = None
    source_port_id: int | None = None
    destination_port_id: int | None = None
    corridor_id: int | None = None
    recommended_supplier: str
    recommended_route: str
    expected_cost_delta: float
    risk_reduction_score: float
    compatibility_score: float
    delivery_delay_days: float
    sanctions_safety_score: float
    overall_score: float
    action_priority: str
    rationale: str
    recommendation_payload: dict[str, Any] = Field(default_factory=dict)


class ProcurementRecommendResponse(APIBaseModel):
    """Batch response returned after generating recommendations."""

    target_scope: ProcurementScope
    scenario_id: int | None = None
    refinery_id: int | None = None
    generated_count: int
    recommendations: list[ProcurementOptionResponse] = Field(default_factory=list)


class ProcurementRecommendationListResponse(APIBaseModel):
    """Lightweight list response for persisted recommendations."""

    items: list[ProcurementRecommendationResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
    page: int
    pages: int
    sort_by: str | None = None
    sort_order: str | None = None
