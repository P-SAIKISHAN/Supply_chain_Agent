from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.port import Port
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.utils.scoring import clamp_score, risk_level_from_score


COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "saudi arabia": (23.8859, 45.0792),
    "iraq": (33.2232, 43.6793),
    "uae": (23.4241, 53.8478),
    "russia": (61.5240, 105.3188),
    "usa": (37.0902, -95.7129),
    "nigeria": (9.0820, 8.6753),
    "india": (22.3511, 78.6677),
}

STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "gujarat": (22.2587, 71.1924),
    "odisha": (20.9517, 85.0985),
    "haryana": (29.0588, 76.0856),
    "kerala": (10.8505, 76.2711),
    "assam": (26.2006, 92.9376),
}


def _risk_map(db: Session, scope_type: str) -> dict[str, float]:
    rows = db.query(RiskScore.scope_id, RiskScore.risk_score).filter(RiskScore.scope_type == scope_type).all()
    return {str(scope_id): float(score or 0.0) for scope_id, score in rows}


def _risk_level(score: float) -> str:
    return risk_level_from_score(clamp_score(score))


def _feature(geometry_type: str, coordinates: Any, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": properties,
    }


def _collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _average_point(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    lat = sum(point[0] for point in points) / len(points)
    lng = sum(point[1] for point in points) / len(points)
    return round(lat, 6), round(lng, 6)


def _country_centroid(name: str) -> tuple[float, float]:
    fallback = COUNTRY_CENTROIDS.get(name.strip().lower())
    if fallback is not None:
        return fallback
    return (20.0, 0.0)


def _refinery_centroid(refinery: Refinery, ports_by_id: dict[int, Port]) -> tuple[float, float]:
    if refinery.linked_port_id is not None:
        port = ports_by_id.get(refinery.linked_port_id)
        if port is not None:
            return float(port.latitude), float(port.longitude)
    fallback = STATE_CENTROIDS.get((refinery.state or "").strip().lower())
    if fallback is not None:
        return fallback
    return (22.0, 78.0)


def _shipment_risk_value(
    shipment: Shipment,
    corridor_risk_map: dict[str, float],
    supplier_risk_map: dict[str, float],
) -> float:
    base = (
        corridor_risk_map.get(str(shipment.corridor_id), 45.0) * 0.4
        + supplier_risk_map.get(str(shipment.supplier_country_id), 35.0) * 0.35
        + (18.0 if shipment.risk_flag else 0.0)
    )
    return clamp_score(base)


def _port_risk_value(db: Session, port: Port, connected_shipments: list[Shipment], shipment_risk_map: dict[str, float]) -> float:
    congestion = float(port.congestion_score or 0.0) * 100.0
    shipment_risk = [
        shipment_risk_map.get(str(item.id), 0.0)
        for item in connected_shipments
    ]
    exposure = sum(shipment_risk) / len(shipment_risk) if shipment_risk else 0.0
    return clamp_score((congestion * 0.6) + (exposure * 0.4))


def _hotspot_feature(feature: dict[str, Any], risk_score: float) -> dict[str, Any]:
    properties = dict(feature["properties"])
    properties.update(
        {
            "risk_score": round(risk_score, 2),
            "risk_level": _risk_level(risk_score),
            "overlay_weight": round(min(1.0, risk_score / 100.0), 2),
        }
    )
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": properties,
    }


def get_network_map(db: Session) -> dict[str, Any]:
    """Return all geospatial layers needed by the map page."""
    return {
        "summary": {
            "supplier_count": db.query(func.count(SupplierCountry.id)).scalar() or 0,
            "corridor_count": db.query(func.count(ShippingCorridor.id)).scalar() or 0,
            "port_count": db.query(func.count(Port.id)).scalar() or 0,
            "refinery_count": db.query(func.count(Refinery.id)).scalar() or 0,
            "shipment_count": db.query(func.count(Shipment.id)).scalar() or 0,
        },
        "layers": {
            "suppliers": _collection(get_supplier_country_features(db)),
            "corridors": _collection(get_corridor_features(db)),
            "ports": _collection(get_port_features(db)),
            "refineries": _collection(get_refinery_features(db)),
            "shipments": _collection(get_shipment_features(db)),
            "risk_overlays": _collection(get_risk_overlay_features(db)),
            "risk_hotspots": _collection(get_risk_hotspot_features(db)),
        },
    }


def get_supplier_country_features(db: Session) -> list[dict[str, Any]]:
    suppliers = db.query(SupplierCountry).order_by(SupplierCountry.name.asc()).all()
    shipment_counts = dict(
        db.query(Shipment.supplier_country_id, func.count(Shipment.id)).group_by(Shipment.supplier_country_id).all()
    )
    risk_map = _risk_map(db, "supplier")
    corridor_risk_map = _risk_map(db, "corridor")
    shipments = db.query(Shipment).all()
    shipments_by_supplier: dict[int, list[Shipment]] = defaultdict(list)
    for shipment in shipments:
        shipments_by_supplier[shipment.supplier_country_id].append(shipment)

    features: list[dict[str, Any]] = []
    for supplier in suppliers:
        centroid = _country_centroid(supplier.name)
        risk_score = risk_map.get(str(supplier.id), float(supplier.geopolitical_risk_base or 0.0) * 45.0)
        connected_count = int(shipment_counts.get(supplier.id, 0))
        features.append(
            _feature(
                "Point",
                [centroid[1], centroid[0]],
                {
                    "layer": "suppliers",
                    "id": supplier.id,
                    "label": supplier.name,
                    "region": supplier.region,
                    "status": "active" if supplier.active else "inactive",
                    "risk_score": round(risk_score, 2),
                    "risk_level": _risk_level(risk_score),
                    "shipment_count": connected_count,
                    "crude_grade_types": list(supplier.crude_grade_types or []),
                    "connected_shipments": [
                        {
                            "shipment_id": shipment.id,
                            "tanker_name": shipment.tanker_name,
                            "risk_score": round(_shipment_risk_value(shipment, corridor_risk_map, risk_map), 2),
                        }
                        for shipment in shipments_by_supplier.get(supplier.id, [])
                    ],
                },
            )
        )
    return features


def get_corridor_features(db: Session) -> list[dict[str, Any]]:
    corridors = db.query(ShippingCorridor).order_by(ShippingCorridor.name.asc()).all()
    risk_map = _risk_map(db, "corridor")
    shipments = db.query(Shipment).all()
    ports_by_id = {port.id: port for port in db.query(Port).all()}

    features: list[dict[str, Any]] = []
    for corridor in corridors:
        corridor_shipments = [shipment for shipment in shipments if shipment.corridor_id == corridor.id]
        points: list[tuple[float, float]] = []
        for shipment in corridor_shipments:
            source = ports_by_id.get(shipment.source_port_id)
            destination = ports_by_id.get(shipment.destination_port_id)
            if source is not None and destination is not None:
                points.append((float(source.latitude), float(source.longitude)))
                points.append((float(destination.latitude), float(destination.longitude)))
        midpoint = _average_point(points)
        if midpoint is None:
            midpoint = (20.0, 50.0)

        route_coordinates = []
        if corridor_shipments:
            shipment = sorted(corridor_shipments, key=lambda item: float(item.cargo_volume_bbl or 0.0), reverse=True)[0]
            source = ports_by_id.get(shipment.source_port_id)
            destination = ports_by_id.get(shipment.destination_port_id)
            if source is not None and destination is not None:
                route_coordinates = [
                    [float(source.longitude), float(source.latitude)],
                    [float(destination.longitude), float(destination.latitude)],
                ]

        risk_score = risk_map.get(str(corridor.id), 35.0 if corridor.status == "open" else 55.0)
        features.append(
            _feature(
                "LineString" if route_coordinates else "Point",
                route_coordinates or [midpoint[1], midpoint[0]],
                {
                    "layer": "corridors",
                    "id": corridor.id,
                    "label": corridor.name,
                    "corridor_type": corridor.corridor_type,
                    "status": corridor.status,
                    "risk_score": round(risk_score, 2),
                    "risk_level": _risk_level(risk_score),
                    "typical_transit_days": corridor.typical_transit_days,
                    "shipment_count": len(corridor_shipments),
                    "notes": corridor.notes,
                },
            )
        )
    return features


def get_port_features(db: Session) -> list[dict[str, Any]]:
    ports = db.query(Port).order_by(Port.name.asc()).all()
    shipment_risk_map = _risk_map(db, "shipment")
    shipments = db.query(Shipment).all()
    shipments_by_port: dict[int, list[Shipment]] = defaultdict(list)
    for shipment in shipments:
        shipments_by_port[shipment.source_port_id].append(shipment)
        shipments_by_port[shipment.destination_port_id].append(shipment)

    features: list[dict[str, Any]] = []
    for port in ports:
        connected = shipments_by_port.get(port.id, [])
        risk_score = _port_risk_value(db, port, connected, shipment_risk_map)
        features.append(
            _feature(
                "Point",
                [float(port.longitude), float(port.latitude)],
                {
                    "layer": "ports",
                    "id": port.id,
                    "label": port.name,
                    "country": port.country,
                    "port_type": port.port_type,
                    "status": "active" if port.active else "inactive",
                    "risk_score": round(risk_score, 2),
                    "risk_level": _risk_level(risk_score),
                    "congestion_score": float(port.congestion_score or 0.0),
                    "shipment_count": len(connected),
                },
            )
        )
    return features


def get_refinery_features(db: Session) -> list[dict[str, Any]]:
    refineries = db.query(Refinery).order_by(Refinery.name.asc()).all()
    risk_map = _risk_map(db, "refinery")
    ports_by_id = {port.id: port for port in db.query(Port).all()}

    features: list[dict[str, Any]] = []
    for refinery in refineries:
        centroid = _refinery_centroid(refinery, ports_by_id)
        risk_score = risk_map.get(str(refinery.id), float(refinery.complexity_index or 0.0) * 4.0)
        linked_port = ports_by_id.get(refinery.linked_port_id) if refinery.linked_port_id else None
        features.append(
            _feature(
                "Point",
                [centroid[1], centroid[0]],
                {
                    "layer": "refineries",
                    "id": refinery.id,
                    "label": refinery.name,
                    "company": refinery.company,
                    "state": refinery.state,
                    "status": "active",
                    "risk_score": round(risk_score, 2),
                    "risk_level": _risk_level(risk_score),
                    "capacity_bpd": int(refinery.capacity_bpd or 0),
                    "strategic_priority_score": float(refinery.strategic_priority_score or 0.0),
                    "linked_port_name": linked_port.name if linked_port else None,
                    "compatible_crude_grades": list(refinery.compatible_crude_grades or []),
                },
            )
        )
    return features


def get_shipment_features(db: Session) -> list[dict[str, Any]]:
    shipments = db.query(Shipment).order_by(Shipment.eta.asc()).all()
    ports_by_id = {port.id: port for port in db.query(Port).all()}
    risk_map = _risk_map(db, "shipment")
    corridor_risk_map = _risk_map(db, "corridor")
    supplier_risk_map = _risk_map(db, "supplier")

    features: list[dict[str, Any]] = []
    for shipment in shipments:
        source = ports_by_id.get(shipment.source_port_id)
        destination = ports_by_id.get(shipment.destination_port_id)
        if source is None or destination is None:
            continue
        risk_score = risk_map.get(
            str(shipment.id),
            _shipment_risk_value(shipment, corridor_risk_map, supplier_risk_map),
        )
        features.append(
            _feature(
                "LineString",
                [
                    [float(source.longitude), float(source.latitude)],
                    [float(destination.longitude), float(destination.latitude)],
                ],
                {
                    "layer": "shipments",
                    "id": shipment.id,
                    "label": shipment.tanker_name,
                    "status": shipment.status,
                    "risk_flag": shipment.risk_flag,
                    "risk_score": round(risk_score, 2),
                    "risk_level": _risk_level(risk_score),
                    "cargo_volume_bbl": float(shipment.cargo_volume_bbl or 0.0),
                    "crude_grade": shipment.crude_grade,
                    "eta": shipment.eta,
                    "freight_cost": float(shipment.freight_cost or 0.0),
                    "supplier_country_id": shipment.supplier_country_id,
                    "corridor_id": shipment.corridor_id,
                },
            )
        )
    return features


def get_risk_overlay_features(db: Session) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for feature in get_supplier_country_features(db):
        risk_score = float(feature["properties"]["risk_score"])
        if risk_score >= 50:
            properties = {
                "overlay_type": "supplier_risk",
                "label": feature["properties"]["label"],
                "risk_score": risk_score,
                "risk_level": feature["properties"]["risk_level"],
                "radius_km": round(150 + risk_score * 6, 2),
            }
            features.append(_hotspot_feature({"type": "Feature", "geometry": feature["geometry"], "properties": properties}, risk_score))

    for feature in get_corridor_features(db):
        risk_score = float(feature["properties"]["risk_score"])
        if risk_score >= 55:
            properties = {
                "overlay_type": "corridor_risk",
                "label": feature["properties"]["label"],
                "risk_score": risk_score,
                "risk_level": feature["properties"]["risk_level"],
                "radius_km": round(100 + risk_score * 4, 2),
            }
            features.append(_hotspot_feature({"type": "Feature", "geometry": feature["geometry"], "properties": properties}, risk_score))

    for feature in get_refinery_features(db):
        risk_score = float(feature["properties"]["risk_score"])
        if risk_score >= 50:
            properties = {
                "overlay_type": "refinery_risk",
                "label": feature["properties"]["label"],
                "risk_score": risk_score,
                "risk_level": feature["properties"]["risk_level"],
                "radius_km": round(80 + risk_score * 3, 2),
            }
            features.append(_hotspot_feature({"type": "Feature", "geometry": feature["geometry"], "properties": properties}, risk_score))

    for feature in get_shipment_features(db):
        risk_score = float(feature["properties"]["risk_score"])
        if risk_score >= 60:
            properties = {
                "overlay_type": "shipment_risk",
                "label": feature["properties"]["label"],
                "risk_score": risk_score,
                "risk_level": feature["properties"]["risk_level"],
                "radius_km": round(60 + risk_score * 2, 2),
            }
            features.append(_hotspot_feature({"type": "Feature", "geometry": feature["geometry"], "properties": properties}, risk_score))

    features.sort(key=lambda item: float(item["properties"]["risk_score"]), reverse=True)
    return features


def get_risk_hotspot_features(db: Session, limit: int = 25) -> list[dict[str, Any]]:
    hotspots = get_risk_overlay_features(db)
    return hotspots[:limit]
