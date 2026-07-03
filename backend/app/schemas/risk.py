from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RiskRecomputeResponse(BaseModel):
    """Summary returned after recomputing risk scores."""

    recomputed_at: datetime
    total_scores: int
    corridor_count: int
    supplier_count: int
    shipment_count: int
    refinery_count: int
    national_score: float
    national_level: str
    average_confidence: float = 0.0
    price_shock_index: float = 0.0
    latest_signal_count: int = 0
    event_breakdown: dict[str, Any] = Field(default_factory=dict)
    price_breakdown: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class RiskContributionResponse(BaseModel):
    name: str
    value: float
    weight: float

    class Config:
        orm_mode = True


class RiskScoreResponse(BaseModel):
    id: int
    scope_type: str
    scope_id: str
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime

    class Config:
        orm_mode = True


class RiskOverviewResponse(BaseModel):
    national_score: float
    national_level: str
    average_confidence: float
    scope_counts: dict[str, int]
    highest_risk_scope: dict[str, Any] = Field(default_factory=dict)
    price_shock_index: float
    latest_signal_count: int

    class Config:
        orm_mode = True


class CorridorRiskResponse(BaseModel):
    scope_id: str
    corridor_id: int
    name: str
    status: str
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class SupplierRiskResponse(BaseModel):
    scope_id: str
    supplier_country_id: int
    name: str
    region: str
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class ShipmentRiskResponse(BaseModel):
    scope_id: str
    shipment_id: int
    tanker_name: str
    corridor_name: str
    supplier_name: str
    destination_port_name: str
    risk_score: float
    risk_level: str
    confidence_score: float
    risk_flag: bool
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class RefineryRiskResponse(BaseModel):
    scope_id: str
    refinery_id: int
    name: str
    company: str
    state: str
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True
