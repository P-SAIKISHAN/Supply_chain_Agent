from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.map import GeoJSONFeatureCollection, MapNetworkResponse
from app.services.map_service import (
    get_corridor_features,
    get_network_map,
    get_port_features,
    get_refinery_features,
    get_risk_hotspot_features,
    get_shipment_features,
)

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/network", response_model=MapNetworkResponse, summary="Return the complete digital twin network")
def network(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return get_network_map(db)


@router.get("/shipments", response_model=GeoJSONFeatureCollection, summary="Return shipment routes")
def shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"type": "FeatureCollection", "features": get_shipment_features(db)}


@router.get("/corridors", response_model=GeoJSONFeatureCollection, summary="Return shipping corridors")
def corridors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"type": "FeatureCollection", "features": get_corridor_features(db)}


@router.get("/refineries", response_model=GeoJSONFeatureCollection, summary="Return refinery locations")
def refineries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"type": "FeatureCollection", "features": get_refinery_features(db)}


@router.get("/ports", response_model=GeoJSONFeatureCollection, summary="Return port locations")
def ports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"type": "FeatureCollection", "features": get_port_features(db)}


@router.get("/risk-hotspots", response_model=GeoJSONFeatureCollection, summary="Return the highest risk map hotspots")
def risk_hotspots(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"type": "FeatureCollection", "features": get_risk_hotspot_features(db, limit=limit)}

