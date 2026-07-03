from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.commodity_price import CommodityPrice
from app.models.geopolitical_event import GeopoliticalEvent
from app.models.port import Port
from app.models.recommendation import ProcurementRecommendation, SPRPlan
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.sanctions_event import SanctionsEvent
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry


def _risk_level_from_score(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _risk_score_map(db: Session, scope_type: str) -> dict[str, float]:
    scores = (
        db.query(RiskScore.scope_id, func.max(RiskScore.risk_score))
        .filter(RiskScore.scope_type == scope_type)
        .group_by(RiskScore.scope_id)
        .all()
    )
    return {str(scope_id): float(score or 0.0) for scope_id, score in scores}


def get_dashboard_kpis(db: Session) -> dict[str, Any]:
    national_score = db.query(func.avg(RiskScore.risk_score)).filter(RiskScore.scope_type == "national").scalar()
    if national_score is None:
        national_score = db.query(func.avg(RiskScore.risk_score)).scalar()
    national_score = float(national_score or 0.0)

    active_disruptions = (
        db.query(func.count(GeopoliticalEvent.id))
        .filter(GeopoliticalEvent.severity_score >= 0.7)
        .scalar()
        or 0
    )
    active_disruptions += (
        db.query(func.count(SanctionsEvent.id))
        .filter(SanctionsEvent.severity_score >= 0.8)
        .scalar()
        or 0
    )

    shipments_at_risk = (
        db.query(func.count(Shipment.id))
        .filter(Shipment.risk_flag.is_(True))
        .scalar()
        or 0
    )

    import_dependency = 82.0 + (national_score * 3.0) + min(10.0, float(shipments_at_risk) * 1.5)

    latest_spr_days = db.query(func.max(SPRPlan.drawdown_days)).scalar() or 0

    return {
        "average_national_risk_score": round(national_score, 2),
        "active_disruptions_count": int(active_disruptions),
        "shipments_at_risk_count": int(shipments_at_risk),
        "estimated_import_dependency_pct": _clamp(import_dependency),
        "strategic_reserve_days_cover": float(latest_spr_days),
    }


def get_corridor_risk(db: Session) -> list[dict[str, Any]]:
    risk_map = _risk_score_map(db, "corridor")
    shipment_counts = dict(
        db.query(Shipment.corridor_id, func.count(Shipment.id)).group_by(Shipment.corridor_id).all()
    )

    corridors = db.query(ShippingCorridor).order_by(ShippingCorridor.name.asc()).all()
    rows: list[dict[str, Any]] = []
    for corridor in corridors:
        score = risk_map.get(str(corridor.id))
        if score is None:
            score = {"critical": 0.9, "high": 0.75, "medium": 0.5, "low": 0.25}.get(corridor.risk_level, 0.4)

        shipment_count = int(shipment_counts.get(corridor.id, 0))
        rows.append(
            {
                "corridor_id": corridor.id,
                "name": corridor.name,
                "risk_score": round(score, 2),
                "risk_level": corridor.risk_level,
                "status": corridor.status,
                "shipment_count": shipment_count,
                "contributing_factors": {
                    "shipment_concentration": round(min(1.0, shipment_count / 5.0), 2),
                    "baseline_risk": round(score, 2),
                    "typical_transit_days": corridor.typical_transit_days,
                },
            }
        )

    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_supplier_risk(db: Session) -> list[dict[str, Any]]:
    risk_map = _risk_score_map(db, "supplier")
    shipment_counts = dict(
        db.query(Shipment.supplier_country_id, func.count(Shipment.id)).group_by(Shipment.supplier_country_id).all()
    )

    countries = db.query(SupplierCountry).order_by(SupplierCountry.name.asc()).all()
    rows: list[dict[str, Any]] = []
    for country in countries:
        score = risk_map.get(str(country.id))
        if score is None:
            score = (float(country.geopolitical_risk_base or 0.0) * 0.6) + (
                float(country.sanctions_risk_base or 0.0) * 0.4
            )

        shipment_count = int(shipment_counts.get(country.id, 0))
        rows.append(
            {
                "supplier_country_id": country.id,
                "name": country.name,
                "region": country.region,
                "risk_score": round(score, 2),
                "risk_level": _risk_level_from_score(score),
                "shipment_count": shipment_count,
                "reliability_score": float(country.reliability_score or 0.0),
                "sanctions_risk_base": float(country.sanctions_risk_base or 0.0),
                "geopolitical_risk_base": float(country.geopolitical_risk_base or 0.0),
                "contributing_factors": {
                    "reliability": round(float(country.reliability_score or 0.0), 2),
                    "sanctions_base": round(float(country.sanctions_risk_base or 0.0), 2),
                    "geopolitical_base": round(float(country.geopolitical_risk_base or 0.0), 2),
                },
            }
        )

    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_latest_alerts(db: Session, limit: int = 5) -> list[dict[str, Any]]:
    geopolitical_events = (
        db.query(GeopoliticalEvent).order_by(GeopoliticalEvent.event_time.desc()).limit(limit).all()
    )
    sanctions_events = db.query(SanctionsEvent).order_by(SanctionsEvent.effective_date.desc()).limit(limit).all()

    combined: list[dict[str, Any]] = []
    for event in geopolitical_events:
        combined.append(
            {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "region": event.region,
                "severity_score": float(event.severity_score or 0.0),
                "event_time": event.event_time,
                "summary": event.summary,
                "impact_tags": list(event.impact_tags or []),
            }
        )

    for event in sanctions_events:
        combined.append(
            {
                "id": event.id,
                "title": f"Sanctions: {event.target_country} - {event.target_entity}",
                "event_type": f"sanctions:{event.sanction_type}",
                "region": event.jurisdiction,
                "severity_score": float(event.severity_score or 0.0),
                "event_time": datetime.combine(event.effective_date, time.min, tzinfo=timezone.utc),
                "summary": event.notes or "Sanctions event in force",
                "impact_tags": ["sanctions", event.sanction_type],
            }
        )

    combined.sort(key=lambda item: (item["severity_score"], item["event_time"]), reverse=True)
    return combined[:limit]


def get_price_trends(db: Session, limit: int = 30) -> list[dict[str, Any]]:
    rows = (
        db.query(CommodityPrice)
        .order_by(CommodityPrice.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "benchmark_name": row.benchmark_name,
            "timestamp": row.timestamp,
            "price_usd": float(row.price_usd),
            "source": row.source,
        }
        for row in rows
    ]


def get_refinery_stress(db: Session) -> list[dict[str, Any]]:
    risk_map = _risk_score_map(db, "refinery")
    refineries = db.query(Refinery).all()
    port_lookup = {port.id: port.name for port in db.query(Port).all()}

    rows: list[dict[str, Any]] = []
    for refinery in refineries:
        score = risk_map.get(str(refinery.id))
        if score is None:
            score = (
                float(refinery.complexity_index or 0.0) / 20.0
                + float(refinery.strategic_priority_score or 0.0) / 3.0
            )

        rows.append(
            {
                "refinery_id": refinery.id,
                "name": refinery.name,
                "company": refinery.company,
                "state": refinery.state,
                "capacity_bpd": int(refinery.capacity_bpd or 0),
                "complexity_index": float(refinery.complexity_index or 0.0),
                "strategic_priority_score": float(refinery.strategic_priority_score or 0.0),
                "risk_score": round(score, 2),
                "risk_level": _risk_level_from_score(score),
                "linked_port_name": port_lookup.get(refinery.linked_port_id) if refinery.linked_port_id else None,
                "compatible_crude_grades": list(refinery.compatible_crude_grades or []),
                "contributing_factors": {
                    "capacity": int(refinery.capacity_bpd or 0),
                    "complexity_index": float(refinery.complexity_index or 0.0),
                    "strategic_priority": float(refinery.strategic_priority_score or 0.0),
                },
            }
        )

    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_recommendations(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        db.query(ProcurementRecommendation)
        .order_by(ProcurementRecommendation.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "scenario_id": row.scenario_id,
            "refinery_id": row.refinery_id,
            "recommended_supplier": row.recommended_supplier,
            "recommended_route": row.recommended_route,
            "expected_cost_delta": float(row.expected_cost_delta or 0.0),
            "risk_reduction_score": float(row.risk_reduction_score or 0.0),
            "compatibility_score": float(row.compatibility_score or 0.0),
            "action_priority": row.action_priority,
            "generated_at": row.generated_at,
            "recommendation_payload": row.recommendation_payload or {},
        }
        for row in rows
    ]
