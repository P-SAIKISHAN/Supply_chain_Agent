from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, conint, confloat

from app.schemas.common import APIBaseModel, ORMBaseSchema


SPRScope = Literal["national", "scenario", "refinery"]


class SPROptimizeRequest(APIBaseModel):
    """Input for the strategic reserve optimizer."""

    target_scope: SPRScope = "national"
    scenario_id: int | None = None
    refinery_id: int | None = None
    current_reserve_days_cover: confloat(ge=0.0, le=365.0) = 30.0
    scenario_supply_loss_pct: confloat(ge=0.0, le=100.0) | None = None
    duration_days: conint(ge=1) | None = None
    import_recovery_days: conint(ge=1, le=365) = 21
    replenishment_window_days: conint(ge=1, le=365) = 45
    reserve_usage_allowed: bool = True


class SPRRefineryAllocationResponse(APIBaseModel):
    refinery_id: int
    name: str
    state: str
    strategic_priority_score: float
    stress_score: float
    allocated_bbl: float
    allocated_share_pct: float
    rationale: str

class SPRDailyReleaseResponse(APIBaseModel):
    day: int
    release_bbl: float
    cumulative_bbl: float
    allocation: list[SPRRefineryAllocationResponse] = Field(default_factory=list)

class SPRPlanResponse(ORMBaseSchema):
    id: int
    scenario_id: int | None = None
    total_drawdown_bbl: float
    drawdown_days: int
    daily_release_schedule: dict[str, Any] = Field(default_factory=dict)
    replenishment_strategy: dict[str, Any] = Field(default_factory=dict)
    policy_notes: str | None = None
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class SPROptimizeResponse(APIBaseModel):
    """Front-end friendly SPR optimization result."""

    plan: SPRPlanResponse
    refinery_allocation_suggestion: list[SPRRefineryAllocationResponse] = Field(default_factory=list)
    replenishment_strategy: dict[str, Any] = Field(default_factory=dict)
    risk_notes: list[str] = Field(default_factory=list)


class SPRPlanListResponse(APIBaseModel):
    items: list[SPRPlanResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
    page: int
    pages: int
    sort_by: str | None = None
    sort_order: str | None = None
