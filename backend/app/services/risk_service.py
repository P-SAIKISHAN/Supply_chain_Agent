from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingestion.base import utcnow
from app.models.commodity_price import CommodityPrice
from app.models.geopolitical_event import GeopoliticalEvent
from app.models.port import Port
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.sanctions_event import SanctionsEvent
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.utils.scoring import RiskContribution, clamp_score, contributions_payload, risk_level_from_score, weighted_score


RISK_SCOPE_CORRIDOR = "corridor"
RISK_SCOPE_SUPPLIER = "supplier"
RISK_SCOPE_SHIPMENT = "shipment"
RISK_SCOPE_REFINERY = "refinery"
RISK_SCOPE_NATIONAL = "national"


def _upsert_risk_score(db: Session, scope_type: str, scope_id: str, payload: dict[str, Any]) -> RiskScore:
    """Create or update a risk score row for a given scope."""
    row = (
        db.query(RiskScore)
        .filter(RiskScore.scope_type == scope_type, RiskScore.scope_id == scope_id)
        .one_or_none()
    )
    if row is None:
        row = RiskScore(scope_type=scope_type, scope_id=scope_id, **payload)
        db.add(row)
    else:
        for key, value in payload.items():
            setattr(row, key, value)
    db.flush()
    return row


def _latest_price_rows(db: Session) -> list[CommodityPrice]:
    """Return the latest available price observation for each benchmark."""
    subquery = (
        db.query(
            CommodityPrice.benchmark_name.label("benchmark_name"),
            func.max(CommodityPrice.timestamp).label("max_timestamp"),
        )
        .group_by(CommodityPrice.benchmark_name)
        .subquery()
    )
    rows = (
        db.query(CommodityPrice)
        .join(
            subquery,
            (CommodityPrice.benchmark_name == subquery.c.benchmark_name)
            & (CommodityPrice.timestamp == subquery.c.max_timestamp),
        )
        .all()
    )
    return rows


def _price_shock_index(db: Session) -> tuple[float, dict[str, Any]]:
    """Compute a simple price shock index from the latest benchmarks.

    Assumption: in demo mode we treat the mean of the latest benchmarks as
    the operating market price and compare it against the 30-day historical
    average. If insufficient history exists, the shock defaults to 0.
    """
    latest_rows = _latest_price_rows(db)
    if not latest_rows:
        return 0.0, {"basis": "no_price_data", "latest_points": 0}

    latest_avg = sum(float(row.price_usd) for row in latest_rows) / len(latest_rows)
    historical_avg = db.query(func.avg(CommodityPrice.price_usd)).scalar() or latest_avg
    if historical_avg <= 0:
        return 0.0, {"basis": "invalid_history", "latest_points": len(latest_rows)}

    delta_pct = ((latest_avg - float(historical_avg)) / float(historical_avg)) * 100.0
    shock_index = clamp_score(abs(delta_pct) * 2.0)
    return shock_index, {
        "latest_average_price": round(latest_avg, 2),
        "historical_average_price": round(float(historical_avg), 2),
        "delta_pct": round(delta_pct, 2),
        "basis": "latest_vs_history",
        "latest_points": len(latest_rows),
    }


def _event_pressure(db: Session) -> tuple[float, dict[str, Any]]:
    """Compute a geopolitical pressure index from current event tables."""
    geo_events = db.query(GeopoliticalEvent).all()
    sanctions_events = db.query(SanctionsEvent).all()

    geo_pressure = sum(float(item.severity_score or 0.0) for item in geo_events) * 12.0
    sanctions_pressure = sum(float(item.severity_score or 0.0) for item in sanctions_events) * 15.0
    total = clamp_score(geo_pressure + sanctions_pressure)
    return total, {
        "geopolitical_events": len(geo_events),
        "sanctions_events": len(sanctions_events),
        "geopolitical_pressure": round(geo_pressure, 2),
        "sanctions_pressure": round(sanctions_pressure, 2),
    }


def _corridor_risk_components(
    corridor: ShippingCorridor,
    shipment_count: int,
    event_pressure: float,
    price_shock: float,
) -> tuple[float, str, float, dict[str, Any]]:
    """Deterministic corridor score with explainable components."""
    status_bonus = {
        "open": 0.0,
        "degraded": 14.0,
        "restricted": 28.0,
        "closed": 45.0,
    }.get((corridor.status or "").lower(), 8.0)

    base_risk = {
        "low": 15.0,
        "medium": 35.0,
        "high": 60.0,
        "critical": 80.0,
    }.get((corridor.risk_level or "").lower(), 30.0)

    exposure = clamp_score(min(20.0, shipment_count * 4.0))
    score = clamp_score(
        weighted_score(
            (base_risk, 0.32),
            (status_bonus, 0.18),
            (event_pressure, 0.27),
            (price_shock, 0.12),
            (exposure, 0.11),
        )
    )
    confidence = clamp_score(82.0 + min(10.0, shipment_count * 1.5) - (price_shock * 0.05))
    return score, risk_level_from_score(score), confidence, {
        "base_risk": base_risk,
        "status_bonus": status_bonus,
        "event_pressure": event_pressure,
        "price_shock": price_shock,
        "shipment_exposure": exposure,
    }


def _supplier_risk_components(
    supplier: SupplierCountry,
    shipment_count: int,
    event_pressure: float,
    sanctions_pressure: float,
    price_shock: float,
) -> tuple[float, str, float, dict[str, Any]]:
    """Deterministic supplier score with explainable components."""
    base_risk = (float(supplier.geopolitical_risk_base or 0.0) * 45.0) + (
        float(supplier.sanctions_risk_base or 0.0) * 40.0
    )
    reliability_penalty = (100.0 - float(supplier.reliability_score or 0.0) * 100.0) * 0.25
    exposure = clamp_score(min(18.0, shipment_count * 3.0))
    score = clamp_score(
        weighted_score(
            (base_risk, 0.28),
            (reliability_penalty, 0.24),
            (event_pressure, 0.2),
            (sanctions_pressure, 0.18),
            (price_shock, 0.1),
        )
        + exposure * 0.05
    )
    confidence = clamp_score(78.0 + min(12.0, shipment_count * 2.0) - (event_pressure * 0.04))
    return score, risk_level_from_score(score), confidence, {
        "base_risk": round(base_risk, 2),
        "reliability_penalty": round(reliability_penalty, 2),
        "event_pressure": event_pressure,
        "sanctions_pressure": sanctions_pressure,
        "price_shock": price_shock,
        "shipment_exposure": exposure,
    }


def _shipment_risk_components(
    shipment: Shipment,
    corridor_risk: float,
    supplier_risk: float,
    event_pressure: float,
    price_shock: float,
) -> tuple[float, str, float, dict[str, Any]]:
    """Deterministic shipment score with explainable components."""
    volume_factor = clamp_score(min(20.0, float(shipment.cargo_volume_bbl or 0.0) / 150000.0))
    freight_factor = clamp_score(min(20.0, float(shipment.freight_cost or 0.0) / 600000.0))
    risk_flag_bonus = 14.0 if shipment.risk_flag else 0.0
    score = clamp_score(
        weighted_score(
            (corridor_risk, 0.35),
            (supplier_risk, 0.25),
            (event_pressure, 0.18),
            (price_shock, 0.1),
            (volume_factor + freight_factor + risk_flag_bonus, 0.12),
        )
    )
    confidence = clamp_score(76.0 + (0.08 * (100.0 - price_shock)) + (8.0 if shipment.risk_flag else 0.0))
    return score, risk_level_from_score(score), confidence, {
        "corridor_risk": round(corridor_risk, 2),
        "supplier_risk": round(supplier_risk, 2),
        "event_pressure": event_pressure,
        "price_shock": price_shock,
        "volume_factor": volume_factor,
        "freight_factor": freight_factor,
        "risk_flag": shipment.risk_flag,
    }


def _refinery_risk_components(
    refinery: Refinery,
    supplier_pressure: float,
    corridor_pressure: float,
    price_shock: float,
) -> tuple[float, str, float, dict[str, Any]]:
    """Deterministic refinery stress score with explainable components."""
    complexity_penalty = clamp_score(float(refinery.complexity_index or 0.0) * 4.0)
    priority_offset = clamp_score(float(refinery.strategic_priority_score or 0.0) * 8.0)
    compatibility_bonus = clamp_score(len(refinery.compatible_crude_grades or []) * 3.0)
    score = clamp_score(
        weighted_score(
            (complexity_penalty, 0.28),
            (supplier_pressure, 0.22),
            (corridor_pressure, 0.2),
            (price_shock, 0.15),
            (priority_offset, 0.15),
        )
        - compatibility_bonus * 0.1
    )
    confidence = clamp_score(79.0 + min(10.0, compatibility_bonus * 0.5) - (price_shock * 0.03))
    return score, risk_level_from_score(score), confidence, {
        "complexity_penalty": complexity_penalty,
        "supplier_pressure": supplier_pressure,
        "corridor_pressure": corridor_pressure,
        "price_shock": price_shock,
        "priority_offset": priority_offset,
        "compatibility_bonus": compatibility_bonus,
    }


def recompute_risk_scores(db: Session) -> dict[str, Any]:
    """Recompute every risk score in a deterministic, explainable way.

    Assumptions:
    - Demo mode prioritizes seeded signal tables over external feeds.
    - National risk is a weighted aggregate of corridor, supplier, shipment,
      and refinery risk.
    - Price shock is inferred from available benchmark points, comparing the
      latest benchmark average to the overall average.
    """
    event_pressure, event_breakdown = _event_pressure(db)
    price_shock, price_breakdown = _price_shock_index(db)

    corridor_by_id = {item.id: item for item in db.query(ShippingCorridor).all()}
    supplier_by_id = {item.id: item for item in db.query(SupplierCountry).all()}
    refinery_by_id = {item.id: item for item in db.query(Refinery).all()}
    shipment_by_id = {item.id: item for item in db.query(Shipment).all()}

    shipment_counts_by_corridor = dict(
        db.query(Shipment.corridor_id, func.count(Shipment.id)).group_by(Shipment.corridor_id).all()
    )
    shipment_counts_by_supplier = dict(
        db.query(Shipment.supplier_country_id, func.count(Shipment.id)).group_by(Shipment.supplier_country_id).all()
    )

    corridor_scores: list[float] = []
    supplier_scores: list[float] = []
    shipment_scores: list[float] = []
    refinery_scores: list[float] = []

    for corridor_id, corridor in corridor_by_id.items():
        score, level, confidence, factors = _corridor_risk_components(
            corridor,
            int(shipment_counts_by_corridor.get(corridor_id, 0)),
            event_pressure,
            price_shock,
        )
        corridor_scores.append(score)
        _upsert_risk_score(
            db,
            RISK_SCOPE_CORRIDOR,
            str(corridor_id),
            {
                "risk_score": score,
                "risk_level": level,
                "confidence_score": confidence,
                "contributing_factors": contributions_payload(
                    [
                        RiskContribution("base_risk", factors["base_risk"], 0.32),
                        RiskContribution("status_bonus", factors["status_bonus"], 0.18),
                        RiskContribution("event_pressure", factors["event_pressure"], 0.27),
                        RiskContribution("price_shock", factors["price_shock"], 0.12),
                        RiskContribution("shipment_exposure", factors["shipment_exposure"], 0.11),
                    ]
                ),
                "computed_at": utcnow(),
            },
        )

    sanctions_pressure = event_breakdown["sanctions_pressure"]

    for supplier_id, supplier in supplier_by_id.items():
        score, level, confidence, factors = _supplier_risk_components(
            supplier,
            int(shipment_counts_by_supplier.get(supplier_id, 0)),
            event_pressure,
            sanctions_pressure,
            price_shock,
        )
        supplier_scores.append(score)
        _upsert_risk_score(
            db,
            RISK_SCOPE_SUPPLIER,
            str(supplier_id),
            {
                "risk_score": score,
                "risk_level": level,
                "confidence_score": confidence,
                "contributing_factors": contributions_payload(
                    [
                        RiskContribution("base_risk", factors["base_risk"], 0.28),
                        RiskContribution("reliability_penalty", factors["reliability_penalty"], 0.24),
                        RiskContribution("event_pressure", factors["event_pressure"], 0.2),
                        RiskContribution("sanctions_pressure", factors["sanctions_pressure"], 0.18),
                        RiskContribution("price_shock", factors["price_shock"], 0.1),
                    ]
                ),
                "computed_at": utcnow(),
            },
        )

    corridor_risk_map = {
        str(item.id): score
        for item, score in zip(
            corridor_by_id.values(),
            corridor_scores,
        )
    }
    supplier_risk_map = {
        str(item.id): score
        for item, score in zip(
            supplier_by_id.values(),
            supplier_scores,
        )
    }

    for shipment_id, shipment in shipment_by_id.items():
        corridor_risk = corridor_risk_map.get(str(shipment.corridor_id), event_pressure)
        supplier_risk = supplier_risk_map.get(str(shipment.supplier_country_id), event_pressure)
        score, level, confidence, factors = _shipment_risk_components(
            shipment,
            corridor_risk,
            supplier_risk,
            event_pressure,
            price_shock,
        )
        shipment_scores.append(score)
        _upsert_risk_score(
            db,
            RISK_SCOPE_SHIPMENT,
            str(shipment_id),
            {
                "risk_score": score,
                "risk_level": level,
                "confidence_score": confidence,
                "contributing_factors": contributions_payload(
                    [
                        RiskContribution("corridor_risk", factors["corridor_risk"], 0.35),
                        RiskContribution("supplier_risk", factors["supplier_risk"], 0.25),
                        RiskContribution("event_pressure", factors["event_pressure"], 0.18),
                        RiskContribution("price_shock", factors["price_shock"], 0.1),
                        RiskContribution(
                            "exposure", factors["volume_factor"] + factors["freight_factor"] + (14.0 if factors["risk_flag"] else 0.0), 0.12
                        ),
                    ]
                ),
                "computed_at": utcnow(),
            },
        )

    for refinery_id, refinery in refinery_by_id.items():
        supplier_pressure = max(supplier_scores or [event_pressure])
        corridor_pressure = max(corridor_scores or [event_pressure])
        score, level, confidence, factors = _refinery_risk_components(
            refinery,
            supplier_pressure,
            corridor_pressure,
            price_shock,
        )
        refinery_scores.append(score)
        _upsert_risk_score(
            db,
            RISK_SCOPE_REFINERY,
            str(refinery_id),
            {
                "risk_score": score,
                "risk_level": level,
                "confidence_score": confidence,
                "contributing_factors": contributions_payload(
                    [
                        RiskContribution("complexity_penalty", factors["complexity_penalty"], 0.28),
                        RiskContribution("supplier_pressure", factors["supplier_pressure"], 0.22),
                        RiskContribution("corridor_pressure", factors["corridor_pressure"], 0.2),
                        RiskContribution("price_shock", factors["price_shock"], 0.15),
                        RiskContribution("priority_offset", factors["priority_offset"], 0.15),
                    ]
                ),
                "computed_at": utcnow(),
            },
        )

    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    national_components = [
        _average(corridor_scores),
        _average(supplier_scores),
        _average(shipment_scores),
        _average(refinery_scores),
        event_pressure,
    ]
    national_score = clamp_score(
        weighted_score(
            (national_components[0], 0.28),
            (national_components[1], 0.24),
            (national_components[2], 0.2),
            (national_components[3], 0.18),
            (national_components[4], 0.1),
        )
    )
    national_level = risk_level_from_score(national_score)
    national_confidence = clamp_score(
        75.0 + min(10.0, len(corridor_scores) * 1.5) + min(10.0, len(supplier_scores) * 1.0) - (price_shock * 0.04)
    )
    _upsert_risk_score(
        db,
        RISK_SCOPE_NATIONAL,
        "india",
        {
            "risk_score": national_score,
            "risk_level": national_level,
            "confidence_score": national_confidence,
            "contributing_factors": contributions_payload(
                [
                    RiskContribution("corridor_pressure", max(corridor_scores or [0.0]), 0.28),
                    RiskContribution("supplier_pressure", max(supplier_scores or [0.0]), 0.24),
                    RiskContribution("shipment_pressure", max(shipment_scores or [0.0]), 0.2),
                    RiskContribution("refinery_stress", max(refinery_scores or [0.0]), 0.18),
                    RiskContribution("event_pressure", event_pressure, 0.1),
                ]
            ),
            "computed_at": utcnow(),
        },
    )

    db.commit()

    all_scores = db.query(RiskScore).all()
    return {
        "recomputed_at": utcnow().isoformat(),
        "total_scores": len(all_scores),
        "corridor_count": len(corridor_by_id),
        "supplier_count": len(supplier_by_id),
        "shipment_count": len(shipment_by_id),
        "refinery_count": len(refinery_by_id),
        "national_score": national_score,
        "national_level": national_level,
        "average_confidence": round(
            sum(float(row.confidence_score or 0.0) for row in all_scores) / max(1, len(all_scores)),
            2,
        ),
        "price_shock_index": price_shock,
        "latest_signal_count": len(db.query(GeopoliticalEvent).all()) + len(db.query(SanctionsEvent).all()) + len(_latest_price_rows(db)),
        "event_breakdown": event_breakdown,
        "price_breakdown": price_breakdown,
    }


def get_risk_overview(db: Session) -> dict[str, Any]:
    """Return a high-level risk overview for the dashboard and operations views."""
    scores = db.query(RiskScore).all()
    national = (
        db.query(RiskScore)
        .filter(RiskScore.scope_type == RISK_SCOPE_NATIONAL, RiskScore.scope_id == "india")
        .one_or_none()
    )
    all_scores = [float(row.risk_score or 0.0) for row in scores]
    top_scope = max(scores, key=lambda row: float(row.risk_score or 0.0), default=None)
    price_shock, _ = _price_shock_index(db)

    scope_counts = {
        "corridor": db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_CORRIDOR).count(),
        "supplier": db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_SUPPLIER).count(),
        "shipment": db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_SHIPMENT).count(),
        "refinery": db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_REFINERY).count(),
        "national": db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_NATIONAL).count(),
    }

    return {
        "national_score": float(
            national.risk_score if national else (sum(all_scores) / len(all_scores) if all_scores else 0.0)
        ),
        "national_level": str(
            national.risk_level if national else risk_level_from_score(sum(all_scores) / len(all_scores) if all_scores else 0.0)
        ),
        "average_confidence": round(
            sum(float(row.confidence_score or 0.0) for row in scores) / max(1, len(scores)),
            2,
        ),
        "scope_counts": scope_counts,
        "highest_risk_scope": {
            "scope_type": top_scope.scope_type if top_scope else None,
            "scope_id": top_scope.scope_id if top_scope else None,
            "risk_score": float(top_scope.risk_score or 0.0) if top_scope else 0.0,
            "risk_level": top_scope.risk_level if top_scope else "low",
        },
        "price_shock_index": price_shock,
        "latest_signal_count": len(db.query(GeopoliticalEvent).all()) + len(db.query(SanctionsEvent).all()) + len(_latest_price_rows(db)),
    }


def _serialize_risk_rows(db: Session, scope_type: str, model_lookup: dict[str, Any]) -> list[dict[str, Any]]:
    rows = db.query(RiskScore).filter(RiskScore.scope_type == scope_type).all()
    payload: list[dict[str, Any]] = []
    for row in rows:
        model_id = row.scope_id
        base_object = model_lookup.get(model_id)
        if base_object is None:
            continue
        payload.append((row, base_object))
    return payload


def get_corridor_risks(db: Session) -> list[dict[str, Any]]:
    risk_rows = db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_CORRIDOR).all()
    corridors = {str(item.id): item for item in db.query(ShippingCorridor).all()}
    rows: list[dict[str, Any]] = []
    for row in risk_rows:
        corridor = corridors.get(row.scope_id)
        if corridor is None:
            continue
        rows.append(
            {
                "scope_id": row.scope_id,
                "corridor_id": corridor.id,
                "name": corridor.name,
                "status": corridor.status,
                "risk_score": float(row.risk_score or 0.0),
                "risk_level": row.risk_level,
                "confidence_score": float(row.confidence_score or 0.0),
                "contributing_factors": row.contributing_factors or {},
            }
        )
    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_supplier_risks(db: Session) -> list[dict[str, Any]]:
    risk_rows = db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_SUPPLIER).all()
    suppliers = {str(item.id): item for item in db.query(SupplierCountry).all()}
    rows: list[dict[str, Any]] = []
    for row in risk_rows:
        supplier = suppliers.get(row.scope_id)
        if supplier is None:
            continue
        rows.append(
            {
                "scope_id": row.scope_id,
                "supplier_country_id": supplier.id,
                "name": supplier.name,
                "region": supplier.region,
                "risk_score": float(row.risk_score or 0.0),
                "risk_level": row.risk_level,
                "confidence_score": float(row.confidence_score or 0.0),
                "contributing_factors": row.contributing_factors or {},
            }
        )
    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_shipment_risks(db: Session) -> list[dict[str, Any]]:
    risk_rows = db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_SHIPMENT).all()
    shipments = {str(item.id): item for item in db.query(Shipment).all()}
    corridors = {item.id: item for item in db.query(ShippingCorridor).all()}
    suppliers = {item.id: item for item in db.query(SupplierCountry).all()}
    ports = {item.id: item for item in db.query(Port).all()}
    rows: list[dict[str, Any]] = []
    for row in risk_rows:
        shipment = shipments.get(row.scope_id)
        if shipment is None:
            continue
        rows.append(
            {
                "scope_id": row.scope_id,
                "shipment_id": shipment.id,
                "tanker_name": shipment.tanker_name,
                "corridor_name": corridors.get(shipment.corridor_id).name if corridors.get(shipment.corridor_id) else None,
                "supplier_name": suppliers.get(shipment.supplier_country_id).name if suppliers.get(shipment.supplier_country_id) else None,
                "destination_port_name": ports.get(shipment.destination_port_id).name if ports.get(shipment.destination_port_id) else None,
                "risk_score": float(row.risk_score or 0.0),
                "risk_level": row.risk_level,
                "confidence_score": float(row.confidence_score or 0.0),
                "risk_flag": shipment.risk_flag,
                "contributing_factors": row.contributing_factors or {},
            }
        )
    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows


def get_refinery_risks(db: Session) -> list[dict[str, Any]]:
    risk_rows = db.query(RiskScore).filter(RiskScore.scope_type == RISK_SCOPE_REFINERY).all()
    refineries = {str(item.id): item for item in db.query(Refinery).all()}
    rows: list[dict[str, Any]] = []
    for row in risk_rows:
        refinery = refineries.get(row.scope_id)
        if refinery is None:
            continue
        rows.append(
            {
                "scope_id": row.scope_id,
                "refinery_id": refinery.id,
                "name": refinery.name,
                "company": refinery.company,
                "state": refinery.state,
                "risk_score": float(row.risk_score or 0.0),
                "risk_level": row.risk_level,
                "confidence_score": float(row.confidence_score or 0.0),
                "contributing_factors": row.contributing_factors or {},
            }
        )
    rows.sort(key=lambda item: item["risk_score"], reverse=True)
    return rows
