from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "LineString", "Polygon"]
    coordinates: Any


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: dict[str, Any] = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature] = Field(default_factory=list)


class MapNetworkResponse(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    layers: dict[str, GeoJSONFeatureCollection] = Field(default_factory=dict)

