from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingestion.base import utcnow
from app.models.commodity_price import CommodityPrice
from app.models.port import Port
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.scenario import Scenario, ScenarioResult
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.schemas.scenario import (
    ScenarioAssumptions,
    ScenarioCreateRequest,
    ScenarioListItemResponse,
    ScenarioRefineryImpact,
    ScenarioResponse,
    ScenarioResultResponse,
    ScenarioRunRequest,
    ScenarioSimulationResponse,
)
from app.utils.scoring import clamp_score, risk_level_from_score


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _scenario_assumptions_payload(
    scenario: Scenario,
    overrides: ScenarioRunRequest | None = None,
) -> ScenarioAssumptions:
    """Merge stored assumptions with optional run-time overrides."""
    payload = {
        "impacted_corridors": list(_as_dict(scenario.assumptions).get("impacted_corridors", [])),
        "impacted_suppliers": list(_as_dict(scenario.assumptions).get("impacted_suppliers", [])),
        "duration_days": int(_as_dict(scenario.assumptions).get("duration_days", scenario.duration_days or 1)),
        "disruption_severity_pct": float(_as_dict(scenario.assumptions).get("disruption_severity_pct", 0.0)),
        "price_shock_pct": float(_as_dict(scenario.assumptions).get("price_shock_pct", 0.0)),
        "tanker_delay_days": int(_as_dict(scenario.assumptions).get("tanker_delay_days", 0)),
        "reserve_usage_allowed": bool(_as_dict(scenario.assumptions).get("reserve_usage_allowed", True)),
    }

    if overrides is not None:
        if overrides.impacted_corridors is not None:
            payload["impacted_corridors"] = list(overrides.impacted_corridors)
        if overrides.impacted_suppliers is not None:
            payload["impacted_suppliers"] = list(overrides.impacted_suppliers)
        if overrides.duration_days is not None:
            payload["duration_days"] = int(overrides.duration_days)
        if overrides.disruption_severity_pct is not None:
            payload["disruption_severity_pct"] = float(overrides.disruption_severity_pct)
        if overrides.price_shock_pct is not None:
            payload["price_shock_pct"] = float(overrides.price_shock_pct)
        if overrides.tanker_delay_days is not None:
            payload["tanker_delay_days"] = int(overrides.tanker_delay_days)
        if overrides.reserve_usage_allowed is not None:
            payload["reserve_usage_allowed"] = bool(overrides.reserve_usage_allowed)

    return ScenarioAssumptions(**payload)


def _scenario_response(scenario: Scenario, assumptions: ScenarioAssumptions) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "trigger_description": scenario.trigger_description,
        "assumptions": assumptions.dict(),
        "duration_days": scenario.duration_days,
        "status": scenario.status,
        "created_by": scenario.created_by,
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at,
    }


def _result_response(result: ScenarioResult, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result.id,
        "scenario_id": result.scenario_id,
        "estimated_supply_loss_pct": float(result.estimated_supply_loss_pct or 0.0),
        "refinery_utilization_impact": float(result.refinery_utilization_impact or 0.0),
        "fuel_price_impact_pct": float(result.fuel_price_impact_pct or 0.0),
        "logistics_cost_impact_pct": float(result.logistics_cost_impact_pct or 0.0),
        "gdp_impact_estimate": float(result.gdp_impact_estimate or 0.0),
        "output_json": payload,
        "generated_at": result.generated_at,
        "created_at": result.created_at,
        "updated_at": result.updated_at,
    }


def _risk_map(db: Session, scope_type: str) -> dict[str, float]:
    rows = db.query(RiskScore.scope_id, RiskScore.risk_score).filter(RiskScore.scope_type == scope_type).all()
    return {str(scope_id): float(score or 0.0) for scope_id, score in rows}


def _fallback_corridor_score(corridor: ShippingCorridor) -> float:
    level_map = {"low": 18.0, "medium": 40.0, "high": 65.0, "critical": 85.0}
    status_bonus = {"open": 0.0, "degraded": 10.0, "restricted": 22.0, "closed": 38.0}.get(
        (corridor.status or "").lower(),
        6.0,
    )
    return clamp_score(level_map.get((corridor.risk_level or "").lower(), 28.0) + status_bonus)


def _fallback_supplier_score(supplier: SupplierCountry) -> float:
    return clamp_score(
        (float(supplier.geopolitical_risk_base or 0.0) * 48.0)
        + (float(supplier.sanctions_risk_base or 0.0) * 42.0)
        + ((100.0 - float(supplier.reliability_score or 0.0) * 100.0) * 0.22)
    )


def _fallback_refinery_score(refinery: Refinery) -> float:
    return clamp_score(
        (float(refinery.complexity_index or 0.0) * 3.2)
        + (float(refinery.strategic_priority_score or 0.0) * 18.0)
    )


def _average(values: Iterable[float]) -> float:
    values_list = list(values)
    return round(sum(values_list) / len(values_list), 2) if values_list else 0.0


def _urgency_from_metrics(supply_loss: float, fuel_price: float, gdp: float, reserve_usage_allowed: bool) -> str:
    """Translate scenario impacts into an operational urgency label.

    Assumption: urgency follows the worst-impact metric, then escalates one
    step if reserves are not allowed because response options are constrained.
    """
    base_score = max(supply_loss, fuel_price, gdp)
    urgency = risk_level_from_score(base_score)
    if not reserve_usage_allowed:
        if urgency == "low":
            return "moderate"
        if urgency == "moderate":
            return "high"
        if urgency == "high":
            return "critical"
    return urgency


def _compute_refinery_impacts(
    db: Session,
    scenario: Scenario,
    assumptions: ScenarioAssumptions,
    affected_shipment_ids: set[int],
    shipment_risk_map: dict[int, float],
) -> list[ScenarioRefineryImpact]:
    refineries = db.query(Refinery).all()
    port_lookup = {port.id: port.name for port in db.query(Port).all()}
    destination_shipment_map: dict[int, list[float]] = {}

    shipments = db.query(Shipment).all()
    for shipment in shipments:
        if shipment.id not in affected_shipment_ids:
            continue
        destination_shipment_map.setdefault(shipment.destination_port_id, []).append(
            shipment_risk_map.get(shipment.id, 0.0)
        )

    refinery_risk_map = _risk_map(db, "refinery")
    impacts: list[ScenarioRefineryImpact] = []
    for refinery in refineries:
        base_score = refinery_risk_map.get(str(refinery.id), _fallback_refinery_score(refinery))
        linked_exposure = _average(destination_shipment_map.get(refinery.linked_port_id or -1, []))
        stress_score = clamp_score(
            (base_score * 0.45)
            + (linked_exposure * 0.35)
            + (assumptions.disruption_severity_pct * 0.2)
            + (assumptions.price_shock_pct * 0.05)
        )
        impacts.append(
            ScenarioRefineryImpact(
                refinery_id=refinery.id,
                name=refinery.name,
                company=refinery.company,
                state=refinery.state,
                stress_score=stress_score,
                risk_level=risk_level_from_score(stress_score),
                linked_port_name=port_lookup.get(refinery.linked_port_id) if refinery.linked_port_id else None,
            )
        )

    impacts.sort(key=lambda item: item.stress_score, reverse=True)
    return impacts[:5]


def _build_result_payload(
    db: Session,
    scenario: Scenario,
    assumptions: ScenarioAssumptions,
) -> tuple[dict[str, Any], float, float, float, float, float, list[ScenarioRefineryImpact], set[int]]:
    """Build deterministic impact metrics for a scenario run.

    Assumptions:
    - All percentages are interpreted on a 0-100 scale.
    - Corridor/supplier impacts amplify the baseline scenario severity.
    - Reserve availability reduces direct supply loss and price pressure.
    - If no impacted corridors/suppliers are provided, the model falls back
      to all currently active shipments so the demo remains usable.
    """
    corridor_risk_map = _risk_map(db, "corridor")
    supplier_risk_map = _risk_map(db, "supplier")
    shipment_risk_map_existing = _risk_map(db, "shipment")

    corridors = {item.id: item for item in db.query(ShippingCorridor).all()}
    suppliers = {item.id: item for item in db.query(SupplierCountry).all()}
    shipments = db.query(Shipment).all()

    impacted_corridors = [item for item in assumptions.impacted_corridors if item in corridors]
    impacted_suppliers = [item for item in assumptions.impacted_suppliers if item in suppliers]

    affected_shipments = [
        shipment
        for shipment in shipments
        if (not impacted_corridors and not impacted_suppliers)
        or shipment.corridor_id in impacted_corridors
        or shipment.supplier_country_id in impacted_suppliers
    ]
    if not affected_shipments:
        affected_shipments = shipments

    def corridor_score(corridor_id: int) -> float:
        corridor = corridors.get(corridor_id)
        if corridor is None:
            return 0.0
        return corridor_risk_map.get(str(corridor_id), _fallback_corridor_score(corridor))

    def supplier_score(supplier_id: int) -> float:
        supplier = suppliers.get(supplier_id)
        if supplier is None:
            return 0.0
        return supplier_risk_map.get(str(supplier_id), _fallback_supplier_score(supplier))

    affected_corridor_scores = [corridor_score(item) for item in impacted_corridors] or [corridor_score(shipment.corridor_id) for shipment in affected_shipments]
    affected_supplier_scores = [supplier_score(item) for item in impacted_suppliers] or [supplier_score(shipment.supplier_country_id) for shipment in affected_shipments]
    affected_shipment_scores = [
        shipment_risk_map_existing.get(str(shipment.id), 0.0)
        or clamp_score((corridor_score(shipment.corridor_id) * 0.5) + (supplier_score(shipment.supplier_country_id) * 0.5))
        for shipment in affected_shipments
    ]

    duration_days = int(assumptions.duration_days or scenario.duration_days or 1)
    delay_days = int(assumptions.tanker_delay_days or 0)
    severity = float(assumptions.disruption_severity_pct or 0.0)
    price_shock = float(assumptions.price_shock_pct or 0.0)
    reserve_relief = 8.0 if assumptions.reserve_usage_allowed else 0.0
    corridor_scope_penalty = min(12.0, len(impacted_corridors) * 2.75)
    supplier_scope_penalty = min(10.0, len(impacted_suppliers) * 2.25)
    duration_penalty = min(12.0, duration_days * 0.75)
    delay_penalty = min(18.0, delay_days * 2.0)

    corridor_pressure = _average(affected_corridor_scores)
    supplier_pressure = _average(affected_supplier_scores)
    shipment_pressure = _average(affected_shipment_scores)

    supply_loss_pct = clamp_score(
        (severity * 0.42)
        + (corridor_pressure * 0.2)
        + (supplier_pressure * 0.15)
        + (shipment_pressure * 0.1)
        + (delay_penalty * 0.45)
        + corridor_scope_penalty
        + supplier_scope_penalty
        + (duration_penalty * 0.4)
        - reserve_relief
    )

    refinery_utilization_impact = clamp_score(
        (supply_loss_pct * 0.55)
        + (severity * 0.15)
        + (shipment_pressure * 0.18)
        + (duration_penalty * 0.25)
    )

    logistics_cost_impact = clamp_score(
        (severity * 0.18)
        + (price_shock * 0.22)
        + (delay_penalty * 1.15)
        + (corridor_pressure * 0.18)
        + (shipment_pressure * 0.08)
        - (reserve_relief * 0.35)
    )

    fuel_price_impact = clamp_score(
        (price_shock * 0.42)
        + (supply_loss_pct * 0.24)
        + (logistics_cost_impact * 0.18)
        + (severity * 0.1)
        + (delay_penalty * 0.12)
        - (reserve_relief * 0.2)
    )

    gdp_impact_estimate = clamp_score(
        (supply_loss_pct * 0.28)
        + (fuel_price_impact * 0.32)
        + (logistics_cost_impact * 0.18)
        + (refinery_utilization_impact * 0.14)
        + (duration_penalty * 0.35)
    )

    affected_shipment_ids = {shipment.id for shipment in affected_shipments}
    most_affected_refineries = _compute_refinery_impacts(
        db,
        scenario,
        assumptions,
        affected_shipment_ids,
        {shipment.id: score for shipment, score in zip(affected_shipments, affected_shipment_scores)},
    )
    urgency = _urgency_from_metrics(supply_loss_pct, fuel_price_impact, gdp_impact_estimate, assumptions.reserve_usage_allowed)

    payload = {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "assumptions": assumptions.dict(),
        "impact_breakdown": {
            "corridor_pressure": corridor_pressure,
            "supplier_pressure": supplier_pressure,
            "shipment_pressure": shipment_pressure,
            "severity_pct": severity,
            "price_shock_pct": price_shock,
            "delay_days": delay_days,
            "duration_days": duration_days,
            "reserve_relief": reserve_relief,
        },
        "affected_corridors": impacted_corridors,
        "affected_suppliers": impacted_suppliers,
        "affected_shipments_count": len(affected_shipments),
        "most_affected_refineries": [item.dict() for item in most_affected_refineries],
        "mitigation_urgency_level": urgency,
        "formula_notes": {
            "supply_loss": "linear weighted blend of severity, corridor exposure, supplier exposure, shipment exposure, delay, duration, and reserve relief",
            "refinery_utilization": "derived from supply loss and shipment pressure",
            "fuel_price": "derived from price shock, supply loss, logistics cost, and delay",
            "gdp": "derived from the interaction of supply loss, fuel prices, logistics cost, and duration",
        },
    }

    return (
        payload,
        supply_loss_pct,
        refinery_utilization_impact,
        fuel_price_impact,
        logistics_cost_impact,
        gdp_impact_estimate,
        most_affected_refineries,
        affected_shipment_ids,
    )


def create_scenario(db: Session, payload: ScenarioCreateRequest, user_id: int | None = None) -> dict[str, Any]:
    assumptions = ScenarioAssumptions(
        impacted_corridors=list(payload.impacted_corridors),
        impacted_suppliers=list(payload.impacted_suppliers),
        duration_days=int(payload.duration_days),
        disruption_severity_pct=float(payload.disruption_severity_pct),
        price_shock_pct=float(payload.price_shock_pct),
        tanker_delay_days=int(payload.tanker_delay_days),
        reserve_usage_allowed=bool(payload.reserve_usage_allowed),
    )

    scenario = Scenario(
        name=payload.name,
        scenario_type=payload.scenario_type,
        trigger_description=payload.trigger_description,
        assumptions=assumptions.dict(),
        duration_days=payload.duration_days,
        status=payload.status,
        created_by=user_id,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return _scenario_response(scenario, assumptions)


def list_scenarios(db: Session) -> list[dict[str, Any]]:
    scenarios = db.query(Scenario).order_by(Scenario.created_at.desc()).all()
    results = {
        row.scenario_id: row
        for row in db.query(ScenarioResult).filter(ScenarioResult.scenario_id.in_([item.id for item in scenarios])).all()
    }

    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        assumptions = _scenario_assumptions_payload(scenario)
        result = results.get(scenario.id)
        result_payload = None
        mitigation_level = None
        refinery_impacts: list[ScenarioRefineryImpact] = []
        if result is not None:
            result_payload = _result_response(result, _as_dict(result.output_json))
            mitigation_level = _as_dict(result.output_json).get("mitigation_urgency_level")
            refinery_impacts = [
                ScenarioRefineryImpact(**item)
                for item in _as_dict(result.output_json).get("most_affected_refineries", [])
                if isinstance(item, dict)
            ]

        rows.append(
            {
                "scenario": _scenario_response(scenario, assumptions),
                "result": result_payload,
                "mitigation_urgency_level": mitigation_level,
                "most_affected_refineries": refinery_impacts,
            }
        )
    return rows


def get_scenario(db: Session, scenario_id: int) -> dict[str, Any]:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if scenario is None:
        raise KeyError(f"Scenario {scenario_id} not found")

    assumptions = _scenario_assumptions_payload(scenario)
    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario_id).one_or_none()
    result_payload = None
    mitigation_level = None
    refinery_impacts: list[ScenarioRefineryImpact] = []
    if result is not None:
        result_payload = _result_response(result, _as_dict(result.output_json))
        mitigation_level = _as_dict(result.output_json).get("mitigation_urgency_level")
        refinery_impacts = [
            ScenarioRefineryImpact(**item)
            for item in _as_dict(result.output_json).get("most_affected_refineries", [])
            if isinstance(item, dict)
        ]

    return {
        "scenario": _scenario_response(scenario, assumptions),
        "result": result_payload,
        "mitigation_urgency_level": mitigation_level,
        "most_affected_refineries": refinery_impacts,
    }


def run_scenario(
    db: Session,
    scenario_id: int,
    payload: ScenarioRunRequest | None = None,
) -> dict[str, Any]:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if scenario is None:
        raise KeyError(f"Scenario {scenario_id} not found")

    assumptions = _scenario_assumptions_payload(scenario, payload)
    scenario.duration_days = assumptions.duration_days
    scenario.assumptions = assumptions.dict()
    scenario.status = "simulated"

    output_json, supply_loss_pct, refinery_utilization_impact, fuel_price_impact, logistics_cost_impact, gdp_impact_estimate, most_affected_refineries, _affected_shipments = _build_result_payload(
        db,
        scenario,
        assumptions,
    )

    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario_id).one_or_none()
    if result is None:
        result = ScenarioResult(
            scenario_id=scenario_id,
            estimated_supply_loss_pct=supply_loss_pct,
            refinery_utilization_impact=refinery_utilization_impact,
            fuel_price_impact_pct=fuel_price_impact,
            logistics_cost_impact_pct=logistics_cost_impact,
            gdp_impact_estimate=gdp_impact_estimate,
            output_json=output_json,
            generated_at=utcnow(),
        )
        db.add(result)
    else:
        result.estimated_supply_loss_pct = supply_loss_pct
        result.refinery_utilization_impact = refinery_utilization_impact
        result.fuel_price_impact_pct = fuel_price_impact
        result.logistics_cost_impact_pct = logistics_cost_impact
        result.gdp_impact_estimate = gdp_impact_estimate
        result.output_json = output_json
        result.generated_at = utcnow()

    db.commit()
    db.refresh(scenario)
    db.refresh(result)

    return {
        "scenario": _scenario_response(scenario, assumptions),
        "result": _result_response(result, output_json),
        "most_affected_refineries": most_affected_refineries,
        "mitigation_urgency_level": output_json["mitigation_urgency_level"],
    }


def get_scenario_results(db: Session, scenario_id: int) -> dict[str, Any]:
    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario_id).one_or_none()
    if result is None:
        return {
            "scenario_id": scenario_id,
            "result": None,
            "mitigation_urgency_level": None,
            "most_affected_refineries": [],
        }

    payload = _as_dict(result.output_json)
    refinery_impacts = [
        ScenarioRefineryImpact(**item)
        for item in payload.get("most_affected_refineries", [])
        if isinstance(item, dict)
    ]
    return {
        "scenario_id": scenario_id,
        "result": _result_response(result, payload),
        "mitigation_urgency_level": payload.get("mitigation_urgency_level"),
        "most_affected_refineries": refinery_impacts,
    }

