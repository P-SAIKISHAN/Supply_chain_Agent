from datetime import date, datetime

from app.schemas.common import ORMBaseSchema


class SupplierCountryResponse(ORMBaseSchema):
    id: int
    name: str
    region: str
    crude_grade_types: list[str]
    geopolitical_risk_base: float
    sanctions_risk_base: float
    reliability_score: float
    active: bool
    created_at: datetime
    updated_at: datetime


class ShippingCorridorResponse(ORMBaseSchema):
    id: int
    name: str
    corridor_type: str
    risk_level: str
    status: str
    typical_transit_days: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PortResponse(ORMBaseSchema):
    id: int
    name: str
    country: str
    latitude: float
    longitude: float
    port_type: str
    congestion_score: float
    active: bool
    created_at: datetime
    updated_at: datetime


class RefineryResponse(ORMBaseSchema):
    id: int
    name: str
    company: str
    state: str
    capacity_bpd: int
    complexity_index: float
    compatible_crude_grades: list[str]
    linked_port_id: int | None
    strategic_priority_score: float
    created_at: datetime
    updated_at: datetime


class ShipmentResponse(ORMBaseSchema):
    id: int
    supplier_country_id: int
    source_port_id: int
    destination_port_id: int
    corridor_id: int
    tanker_name: str
    cargo_volume_bbl: float
    crude_grade: str
    eta: datetime
    status: str
    freight_cost: float
    risk_flag: bool
    created_at: datetime
    updated_at: datetime


class GeopoliticalEventResponse(ORMBaseSchema):
    id: int
    title: str
    event_type: str
    region: str
    source: str
    summary: str
    severity_score: float
    event_time: datetime
    extracted_entities: dict
    impact_tags: list[str]
    created_at: datetime
    updated_at: datetime


class SanctionsEventResponse(ORMBaseSchema):
    id: int
    jurisdiction: str
    target_country: str
    target_entity: str
    sanction_type: str
    effective_date: date
    severity_score: float
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CommodityPriceResponse(ORMBaseSchema):
    id: int
    benchmark_name: str
    price_usd: float
    timestamp: datetime
    source: str
    created_at: datetime
    updated_at: datetime


class RiskScoreResponse(ORMBaseSchema):
    id: int
    scope_type: str
    scope_id: str
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: dict
    computed_at: datetime
    created_at: datetime
    updated_at: datetime


class ScenarioResponse(ORMBaseSchema):
    id: int
    name: str
    scenario_type: str
    trigger_description: str
    assumptions: dict
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
    output_json: dict
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class ProcurementRecommendationResponse(ORMBaseSchema):
    id: int
    scenario_id: int | None
    refinery_id: int | None
    title: str
    recommended_supplier: str
    recommended_route: str
    expected_cost_delta: float
    risk_reduction_score: float
    compatibility_score: float
    action_priority: str
    recommendation_payload: dict
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class SPRPlanResponse(ORMBaseSchema):
    id: int
    scenario_id: int | None
    total_drawdown_bbl: float
    drawdown_days: int
    daily_release_schedule: dict
    replenishment_strategy: dict
    policy_notes: str | None
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(ORMBaseSchema):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
