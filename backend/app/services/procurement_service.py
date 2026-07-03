from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingestion.base import utcnow
from app.models.commodity_price import CommodityPrice
from app.models.port import Port
from app.models.recommendation import ProcurementRecommendation as ProcurementRecommendationModel
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.sanctions_event import SanctionsEvent
from app.models.scenario import Scenario, ScenarioResult
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.schemas.procurement import (
    ProcurementOptionResponse,
    ProcurementRecommendRequest,
    ProcurementRecommendResponse,
    ProcurementRecommendationListResponse,
    ProcurementRecommendationResponse,
    ProcurementScope,
)
from app.utils.scoring import clamp_score, risk_level_from_score, weighted_score


@dataclass
class ProcurementCandidate:
    title: str
    scenario_id: int | None
    refinery_id: int | None
    supplier_country_id: int | None
    source_port_id: int | None
    destination_port_id: int | None
    corridor_id: int | None
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
    recommendation_payload: dict[str, Any]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_text_tokens(values: list[str] | None) -> set[str]:
    tokens: set[str] = set()
    for value in values or []:
        for token in str(value).lower().replace("/", " ").replace("-", " ").split():
            cleaned = token.strip(",.()")
            if cleaned:
                tokens.add(cleaned)
    return tokens


def _score_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _risk_map(db: Session, scope_type: str) -> dict[str, float]:
    rows = db.query(RiskScore.scope_id, RiskScore.risk_score).filter(RiskScore.scope_type == scope_type).all()
    return {str(scope_id): float(score or 0.0) for scope_id, score in rows}


def _latest_price_pressure(db: Session) -> tuple[float, dict[str, Any]]:
    latest_rows = (
        db.query(CommodityPrice)
        .order_by(CommodityPrice.timestamp.desc())
        .limit(10)
        .all()
    )
    if not latest_rows:
        return 0.0, {"basis": "no_price_data", "points": 0}

    latest_avg = sum(float(row.price_usd or 0.0) for row in latest_rows) / len(latest_rows)
    historical_avg = float(db.query(func.avg(CommodityPrice.price_usd)).scalar() or latest_avg)
    if historical_avg <= 0:
        return 0.0, {"basis": "invalid_history", "points": len(latest_rows)}

    delta_pct = ((latest_avg - historical_avg) / historical_avg) * 100.0
    pressure = clamp_score(abs(delta_pct) * 2.0)
    return pressure, {
        "latest_average_price": round(latest_avg, 2),
        "historical_average_price": round(historical_avg, 2),
        "delta_pct": round(delta_pct, 2),
        "points": len(latest_rows),
    }


def _active_sanctions_penalty(db: Session, supplier: SupplierCountry) -> tuple[float, dict[str, Any]]:
    sanctions = db.query(SanctionsEvent).all()
    matching = [
        event
        for event in sanctions
        if event.target_country.lower() == supplier.name.lower()
        or supplier.name.lower() in str(event.target_entity or "").lower()
    ]
    base = float(supplier.sanctions_risk_base or 0.0) * 65.0
    event_penalty = min(25.0, sum(float(item.severity_score or 0.0) * 25.0 for item in matching))
    total = clamp_score(base + event_penalty)
    return total, {
        "supplier_sanctions_base": round(base, 2),
        "matching_sanctions_events": len(matching),
        "event_penalty": round(event_penalty, 2),
    }


def _compatible_grade_score(refinery: Refinery, supplier: SupplierCountry) -> tuple[float, dict[str, Any]]:
    refinery_grades = _normalize_text_tokens(list(refinery.compatible_crude_grades or []))
    supplier_grades = _normalize_text_tokens(list(supplier.crude_grade_types or []))
    if not refinery_grades and not supplier_grades:
        return 60.0, {"basis": "missing_grade_lists", "overlap_ratio": 0.0}
    if not refinery_grades or not supplier_grades:
        return 45.0, {"basis": "one_sided_grade_list", "overlap_ratio": 0.0}

    overlap = refinery_grades.intersection(supplier_grades)
    ratio = len(overlap) / max(1, min(len(refinery_grades), len(supplier_grades)))
    score = clamp_score(30.0 + ratio * 70.0)
    return score, {"overlap_ratio": round(ratio, 2), "overlap_grades": sorted(overlap)}


def _active_corridors(db: Session) -> list[ShippingCorridor]:
    corridors = db.query(ShippingCorridor).all()
    active = [corridor for corridor in corridors if (corridor.status or "").lower() != "closed"]
    return active or corridors


def _best_destination_port(db: Session, refinery: Refinery) -> Port | None:
    if refinery.linked_port_id is not None:
        port = db.query(Port).filter(Port.id == refinery.linked_port_id).one_or_none()
        if port is not None:
            return port
    return (
        db.query(Port)
        .filter(Port.country == "India", Port.active.is_(True))
        .order_by(Port.congestion_score.asc(), Port.name.asc())
        .first()
    )


def _best_source_port(db: Session, supplier: SupplierCountry) -> Port | None:
    ports = (
        db.query(Port)
        .filter(Port.country == supplier.name, Port.active.is_(True))
        .order_by(Port.congestion_score.asc(), Port.name.asc())
        .all()
    )
    if ports:
        return ports[0]

    shipment_sources = (
        db.query(Shipment.source_port_id, func.count(Shipment.id))
        .filter(Shipment.supplier_country_id == supplier.id)
        .group_by(Shipment.source_port_id)
        .order_by(func.count(Shipment.id).desc())
        .all()
    )
    if shipment_sources:
        port = db.query(Port).filter(Port.id == shipment_sources[0][0]).one_or_none()
        if port is not None:
            return port
    return (
        db.query(Port)
        .filter(Port.active.is_(True))
        .order_by(Port.congestion_score.asc(), Port.name.asc())
        .first()
    )


def _scenario_context(db: Session, scenario: Scenario | None) -> dict[str, Any]:
    if scenario is None:
        return {
            "impact_breakdown": {},
            "affected_corridors": [],
            "affected_suppliers": [],
            "scenario_delay_days": 0,
            "scenario_supply_loss_pct": 0.0,
            "scenario_price_shock_pct": 0.0,
            "scenario_urgency": None,
        }

    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario.id).one_or_none()
    assumptions = _as_dict(scenario.assumptions)
    if result is not None:
        payload = _as_dict(result.output_json)
        breakdown = _as_dict(payload.get("impact_breakdown"))
        return {
            "impact_breakdown": breakdown,
            "affected_corridors": list(payload.get("affected_corridors") or assumptions.get("impacted_corridors") or []),
            "affected_suppliers": list(payload.get("affected_suppliers") or assumptions.get("impacted_suppliers") or []),
            "scenario_delay_days": int(breakdown.get("delay_days", assumptions.get("tanker_delay_days", 0)) or 0),
            "scenario_supply_loss_pct": float(result.estimated_supply_loss_pct or 0.0),
            "scenario_price_shock_pct": float(breakdown.get("price_shock_pct", assumptions.get("price_shock_pct", 0.0)) or 0.0),
            "scenario_urgency": payload.get("mitigation_urgency_level"),
        }

    return {
        "impact_breakdown": {},
        "affected_corridors": list(assumptions.get("impacted_corridors") or []),
        "affected_suppliers": list(assumptions.get("impacted_suppliers") or []),
        "scenario_delay_days": int(assumptions.get("tanker_delay_days", 0) or 0),
        "scenario_supply_loss_pct": float(assumptions.get("disruption_severity_pct", 0.0) or 0.0),
        "scenario_price_shock_pct": float(assumptions.get("price_shock_pct", 0.0) or 0.0),
        "scenario_urgency": None,
    }


def _current_route_risk(db: Session, refinery: Refinery | None) -> float:
    shipment_risk_map = _risk_map(db, "shipment")
    if refinery is not None and refinery.linked_port_id is not None:
        shipments = db.query(Shipment).filter(Shipment.destination_port_id == refinery.linked_port_id).all()
        values = [float(shipment_risk_map.get(str(item.id), 0.0)) for item in shipments if shipment_risk_map.get(str(item.id)) is not None]
        if values:
            return round(sum(values) / len(values), 2)

    values = [float(value) for value in shipment_risk_map.values()]
    if values:
        return round(sum(values) / len(values), 2)
    return 50.0


def _route_risk_components(
    db: Session,
    supplier: SupplierCountry,
    corridor: ShippingCorridor,
    source_port: Port | None,
    destination_port: Port | None,
    scenario_ctx: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    supplier_risk_map = _risk_map(db, "supplier")
    corridor_risk_map = _risk_map(db, "corridor")

    supplier_risk = supplier_risk_map.get(str(supplier.id), float(supplier.geopolitical_risk_base or 0.0) * 45.0)
    corridor_risk = corridor_risk_map.get(str(corridor.id), 40.0)
    source_congestion = float(source_port.congestion_score if source_port else 20.0)
    dest_congestion = float(destination_port.congestion_score if destination_port else 20.0)

    scenario_penalty = 0.0
    if corridor.id in scenario_ctx["affected_corridors"]:
        scenario_penalty += 18.0
    if supplier.id in scenario_ctx["affected_suppliers"]:
        scenario_penalty += 14.0
    scenario_penalty += min(18.0, float(scenario_ctx["scenario_supply_loss_pct"] or 0.0) * 0.18)

    route_risk = weighted_score(
        (clamp_score(supplier_risk), 0.28),
        (clamp_score(corridor_risk), 0.34),
        (clamp_score(source_congestion), 0.12),
        (clamp_score(dest_congestion), 0.12),
        (clamp_score(scenario_penalty), 0.14),
    )
    return route_risk, {
        "supplier_risk": round(clamp_score(supplier_risk), 2),
        "corridor_risk": round(clamp_score(corridor_risk), 2),
        "source_congestion": round(source_congestion, 2),
        "destination_congestion": round(dest_congestion, 2),
        "scenario_penalty": round(scenario_penalty, 2),
    }


def _candidate_priority(overall_score: float) -> str:
    if overall_score >= 80:
        return "critical"
    if overall_score >= 65:
        return "high"
    if overall_score >= 40:
        return "medium"
    return "low"


def _recommendation_payload(
    scenario: Scenario | None,
    refinery: Refinery | None,
    supplier: SupplierCountry,
    corridor: ShippingCorridor,
    source_port: Port | None,
    destination_port: Port | None,
    route_risk: float,
    compatibility_score: float,
    cost_efficiency: float,
    delivery_feasibility: float,
    sanctions_safety: float,
    overall_score: float,
    risk_reduction_score: float,
    expected_cost_delta: float,
    delivery_delay_days: float,
    rationale: str,
    score_components: dict[str, Any],
    scenario_ctx: dict[str, Any],
    price_pressure: float,
    sanctions_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario.id if scenario else None,
        "scenario_name": scenario.name if scenario else None,
        "refinery_id": refinery.id if refinery else None,
        "refinery_name": refinery.name if refinery else None,
        "supplier_country_id": supplier.id,
        "supplier_name": supplier.name,
        "corridor_id": corridor.id,
        "corridor_name": corridor.name,
        "source_port_id": source_port.id if source_port else None,
        "source_port_name": source_port.name if source_port else None,
        "destination_port_id": destination_port.id if destination_port else None,
        "destination_port_name": destination_port.name if destination_port else None,
        "overall_score": round(overall_score, 2),
        "risk_reduction_score": round(risk_reduction_score, 2),
        "expected_cost_delta": round(expected_cost_delta, 2),
        "delivery_delay_days": round(delivery_delay_days, 2),
        "score_breakdown": {
            "route_risk_inverse": round(clamp_score(100.0 - route_risk), 2),
            "crude_compatibility": round(compatibility_score, 2),
            "cost_efficiency": round(cost_efficiency, 2),
            "delivery_feasibility": round(delivery_feasibility, 2),
            "sanctions_safety": round(sanctions_safety, 2),
            "route_risk": round(route_risk, 2),
        },
        "route_rationale": rationale,
        "scoring_components": score_components,
        "scenario_context": scenario_ctx,
        "price_pressure": round(price_pressure, 2),
        "sanctions_context": sanctions_context,
        "assumptions": {
            "weighted_formula": "0.30*route_risk_inverse + 0.25*crude_compatibility + 0.20*cost_efficiency + 0.15*delivery_feasibility + 0.10*sanctions_safety",
            "cost_delta_is_percentage": True,
            "delivery_delay_is_days": True,
        },
        "generated_at": utcnow().isoformat(),
    }


def _persist_candidate(db: Session, candidate: ProcurementCandidate) -> ProcurementRecommendationModel:
    row = ProcurementRecommendationModel(
        scenario_id=candidate.scenario_id,
        refinery_id=candidate.refinery_id,
        title=candidate.title,
        recommended_supplier=candidate.recommended_supplier,
        recommended_route=candidate.recommended_route,
        expected_cost_delta=candidate.expected_cost_delta,
        risk_reduction_score=candidate.risk_reduction_score,
        compatibility_score=candidate.compatibility_score,
        action_priority=candidate.action_priority,
        recommendation_payload=candidate.recommendation_payload,
        generated_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _serialize_row(row: ProcurementRecommendationModel) -> dict[str, Any]:
    payload = _as_dict(row.recommendation_payload)
    return {
        "id": row.id,
        "scenario_id": row.scenario_id,
        "refinery_id": row.refinery_id,
        "title": row.title,
        "recommended_supplier": row.recommended_supplier,
        "recommended_route": row.recommended_route,
        "expected_cost_delta": float(row.expected_cost_delta or 0.0),
        "risk_reduction_score": float(row.risk_reduction_score or 0.0),
        "compatibility_score": float(row.compatibility_score or 0.0),
        "action_priority": row.action_priority,
        "generated_at": row.generated_at,
        "recommendation_payload": payload,
        "overall_score": float(payload.get("overall_score", 0.0)),
        "delivery_delay_days": float(payload.get("delivery_delay_days", 0.0)),
        "sanctions_safety_score": float(
            payload.get("score_breakdown", {}).get("sanctions_safety", 0.0)
        ),
        "rationale": payload.get("route_rationale"),
    }


def _build_candidates(
    db: Session,
    target_scope: ProcurementScope,
    scenario: Scenario | None,
    refinery: Refinery | None,
    top_n: int,
    candidate_suppliers_limit: int,
    candidate_corridors_limit: int,
) -> list[ProcurementCandidate]:
    scenario_ctx = _scenario_context(db, scenario)
    price_pressure, price_context = _latest_price_pressure(db)
    refinery_risk_map = _risk_map(db, "refinery")
    corridor_risk_map = _risk_map(db, "corridor")
    supplier_risk_map = _risk_map(db, "supplier")
    baseline_route_risk = _current_route_risk(db, refinery)

    target_refineries = [refinery] if refinery is not None else db.query(Refinery).all()
    active_suppliers = db.query(SupplierCountry).filter(SupplierCountry.active.is_(True)).all()
    corridors = sorted(
        _active_corridors(db),
        key=lambda item: (
            1 if item.id in scenario_ctx["affected_corridors"] else 0,
            corridor_risk_map.get(str(item.id), float(item.risk_level == "critical") * 90.0),
            item.typical_transit_days,
        ),
    )

    candidate_rows: list[ProcurementCandidate] = []
    for target_refinery in target_refineries:
        destination_port = _best_destination_port(db, target_refinery)
        refinery_risk = refinery_risk_map.get(str(target_refinery.id), float(target_refinery.complexity_index or 0.0) * 4.0)
        compatible_refinery_grades = _normalize_text_tokens(list(target_refinery.compatible_crude_grades or []))

        supplier_rankings: list[tuple[float, SupplierCountry, dict[str, Any], Port | None, float]] = []
        for supplier in active_suppliers:
            source_port = _best_source_port(db, supplier)
            compatibility_score, compatibility_context = _compatible_grade_score(target_refinery, supplier)
            supplier_risk = supplier_risk_map.get(str(supplier.id), float(supplier.geopolitical_risk_base or 0.0) * 45.0)
            supplier_rankings.append((compatibility_score + (100.0 - clamp_score(supplier_risk)) * 0.15, supplier, compatibility_context, source_port, supplier_risk))

        supplier_rankings.sort(key=lambda item: item[0], reverse=True)
        supplier_rankings = supplier_rankings[:candidate_suppliers_limit]

        for _, supplier, compatibility_context, source_port, supplier_risk in supplier_rankings:
            sanctions_safety, sanctions_context = _active_sanctions_penalty(db, supplier)
            compatibility_score, _ = _compatible_grade_score(target_refinery, supplier)
            for corridor in corridors[:candidate_corridors_limit]:
                route_risk, route_context = _route_risk_components(
                    db,
                    supplier,
                    corridor,
                    source_port,
                    destination_port,
                    scenario_ctx,
                )
                route_risk_inverse = clamp_score(100.0 - route_risk)

                scenario_delay = float(scenario_ctx["scenario_delay_days"] or 0.0)
                source_congestion = float(source_port.congestion_score if source_port else 20.0)
                destination_congestion = float(destination_port.congestion_score if destination_port else 20.0)
                delivery_delay_days = clamp_score(
                    (corridor.typical_transit_days or 0)
                    + scenario_delay
                    + (route_risk * 0.045)
                    + (source_congestion * 0.04)
                    + (destination_congestion * 0.04)
                )

                expected_cost_delta = clamp_score(
                    (price_pressure * 0.18)
                    + (route_risk * 0.16)
                    + (delivery_delay_days * 1.05)
                    + (float(supplier.geopolitical_risk_base or 0.0) * 9.0)
                    + (float(supplier.sanctions_risk_base or 0.0) * 12.0)
                    + (scenario_ctx["scenario_supply_loss_pct"] * 0.1)
                    - (compatibility_score * 0.08)
                )
                cost_efficiency = clamp_score(100.0 - (expected_cost_delta * 2.4))
                delivery_feasibility = clamp_score(
                    100.0
                    - (delivery_delay_days * 5.0)
                    - (route_risk * 0.12)
                    - max(0.0, source_congestion - 25.0) * 0.35
                    - max(0.0, destination_congestion - 25.0) * 0.35
                )

                baseline_risk_for_scope = baseline_route_risk
                risk_reduction_score = clamp_score(max(0.0, baseline_risk_for_scope - route_risk))

                overall_score = clamp_score(
                    (
                        route_risk_inverse * 0.30
                        + compatibility_score * 0.25
                        + cost_efficiency * 0.20
                        + delivery_feasibility * 0.15
                        + sanctions_safety * 0.10
                    )
                )

                urgency = _candidate_priority(overall_score)
                rationale = (
                    f"Route via {corridor.name} keeps the route risk at {route_risk:.1f}/100 "
                    f"with compatibility {compatibility_score:.1f}/100 and sanctions safety {sanctions_safety:.1f}/100."
                )
                title_scope = f"{target_refinery.name}" if target_refinery else "National import basket"
                title = f"{urgency.title()} procurement option for {title_scope}"
                recommended_route = (
                    f"{source_port.name if source_port else supplier.name} -> {corridor.name} -> "
                    f"{destination_port.name if destination_port else target_refinery.name}"
                )

                recommendation_payload = _recommendation_payload(
                    scenario,
                    target_refinery,
                    supplier,
                    corridor,
                    source_port,
                    destination_port,
                    route_risk,
                    compatibility_score,
                    cost_efficiency,
                    delivery_feasibility,
                    sanctions_safety,
                    overall_score,
                    risk_reduction_score,
                    expected_cost_delta,
                    delivery_delay_days,
                    rationale,
                    {
                        "route_context": route_context,
                        "compatibility_context": compatibility_context,
                        "supplier_risk": round(supplier_risk, 2),
                        "refinery_risk": round(refinery_risk, 2),
                        "baseline_route_risk": round(baseline_risk_for_scope, 2),
                    },
                    scenario_ctx,
                    price_pressure,
                    sanctions_context,
                )

                candidate_rows.append(
                    ProcurementCandidate(
                        title=title,
                        scenario_id=scenario.id if scenario else None,
                        refinery_id=target_refinery.id if target_refinery else None,
                        supplier_country_id=supplier.id,
                        source_port_id=source_port.id if source_port else None,
                        destination_port_id=destination_port.id if destination_port else None,
                        corridor_id=corridor.id,
                        recommended_supplier=supplier.name,
                        recommended_route=recommended_route,
                        expected_cost_delta=expected_cost_delta,
                        risk_reduction_score=risk_reduction_score,
                        compatibility_score=compatibility_score,
                        delivery_delay_days=delivery_delay_days,
                        sanctions_safety_score=sanctions_safety,
                        overall_score=overall_score,
                        action_priority=urgency,
                        rationale=rationale,
                        recommendation_payload=recommendation_payload,
                    )
                )

    candidate_rows.sort(key=lambda item: item.overall_score, reverse=True)
    return candidate_rows[:top_n]


def generate_procurement_recommendations(
    db: Session,
    payload: ProcurementRecommendRequest,
) -> dict[str, Any]:
    scenario = None
    refinery = None
    if payload.target_scope == "scenario":
        if payload.scenario_id is None:
            raise ValueError("scenario_id is required when target_scope is scenario")
        scenario = db.query(Scenario).filter(Scenario.id == payload.scenario_id).one_or_none()
        if scenario is None:
            raise KeyError(f"Scenario {payload.scenario_id} not found")
    elif payload.scenario_id is not None:
        scenario = db.query(Scenario).filter(Scenario.id == payload.scenario_id).one_or_none()
        if scenario is None:
            raise KeyError(f"Scenario {payload.scenario_id} not found")

    if payload.target_scope == "refinery":
        if payload.refinery_id is None:
            raise ValueError("refinery_id is required when target_scope is refinery")
        refinery = db.query(Refinery).filter(Refinery.id == payload.refinery_id).one_or_none()
        if refinery is None:
            raise KeyError(f"Refinery {payload.refinery_id} not found")
    elif payload.refinery_id is not None:
        refinery = db.query(Refinery).filter(Refinery.id == payload.refinery_id).one_or_none()
        if refinery is None:
            raise KeyError(f"Refinery {payload.refinery_id} not found")

    candidates = _build_candidates(
        db,
        payload.target_scope,
        scenario,
        refinery,
        payload.top_n,
        payload.candidate_suppliers_limit,
        payload.candidate_corridors_limit,
    )
    persisted_rows = [_persist_candidate(db, candidate) for candidate in candidates]
    db.commit()
    for row in persisted_rows:
        db.refresh(row)

    return {
        "target_scope": payload.target_scope,
        "scenario_id": scenario.id if scenario else None,
        "refinery_id": refinery.id if refinery else None,
        "generated_count": len(persisted_rows),
        "recommendations": [
            ProcurementOptionResponse(**candidate.__dict__) for candidate in candidates
        ],
    }


def list_procurement_recommendations(
    db: Session,
    limit: int = 50,
    scenario_id: int | None = None,
    refinery_id: int | None = None,
) -> ProcurementRecommendationListResponse:
    query = db.query(ProcurementRecommendationModel).order_by(ProcurementRecommendationModel.generated_at.desc())
    count_query = db.query(func.count(ProcurementRecommendationModel.id))
    if scenario_id is not None:
        query = query.filter(ProcurementRecommendationModel.scenario_id == scenario_id)
        count_query = count_query.filter(ProcurementRecommendationModel.scenario_id == scenario_id)
    if refinery_id is not None:
        query = query.filter(ProcurementRecommendationModel.refinery_id == refinery_id)
        count_query = count_query.filter(ProcurementRecommendationModel.refinery_id == refinery_id)

    rows = query.limit(limit).all()
    return ProcurementRecommendationListResponse(
        items=[ProcurementRecommendationResponse(**_serialize_row(row)) for row in rows],
        total_count=int(count_query.scalar() or 0),
    )


def get_procurement_recommendation(db: Session, recommendation_id: int) -> ProcurementRecommendationResponse:
    row = (
        db.query(ProcurementRecommendationModel)
        .filter(ProcurementRecommendationModel.id == recommendation_id)
        .one_or_none()
    )
    if row is None:
        raise KeyError(f"Recommendation {recommendation_id} not found")
    return ProcurementRecommendationResponse(**_serialize_row(row))
