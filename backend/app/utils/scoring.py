from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


RISK_LEVELS = ("low", "moderate", "high", "critical")


def clamp_score(value: float) -> float:
    """Clamp a numeric score to the 0-100 range."""
    return round(max(0.0, min(100.0, float(value))), 2)


def risk_level_from_score(score: float) -> str:
    """Map a 0-100 score to the platform's descriptive risk levels."""
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "moderate"
    return "low"


def normalize_fraction(value: float, max_value: float = 1.0) -> float:
    """Normalize an input value to 0-1 against a practical maximum."""
    if max_value <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / float(max_value)))


def weighted_score(*components: tuple[float, float]) -> float:
    """Compute a weighted average where each component is already normalized 0-100."""
    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return 0.0
    total = sum(clamp_score(score) * weight for score, weight in components)
    return clamp_score(total / total_weight)


def level_bonus(level: str) -> float:
    """Return a numeric severity bonus for a textual risk level."""
    lookup = {"low": 0.0, "moderate": 15.0, "medium": 15.0, "high": 30.0, "critical": 45.0}
    return lookup.get(level.lower(), 0.0)


@dataclass
class RiskContribution:
    """Explainable component used in risk score payloads."""

    name: str
    value: float
    weight: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def contributions_payload(contributions: list[RiskContribution]) -> dict[str, Any]:
    """Serialize contribution details for storage in JSON columns."""
    return {
        "contributions": [item.to_dict() for item in contributions],
        "component_count": len(contributions),
    }

