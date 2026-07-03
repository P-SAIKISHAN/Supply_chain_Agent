from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingestion.base import utcnow
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.scenario import Scenario, ScenarioResult
from app.models.recommendation import SPRPlan
from app.schemas.spr import (
    SPRDailyReleaseResponse,
    SPRPlanListResponse,
    SPRPlanResponse,
    SPRRefineryAllocationResponse,
    SPROptimizeRequest,
    SPROptimizeResponse,
)
from app.utils.scoring import clamp_score, risk_level_from_score


@dataclass
class RefineryAllocation:
    refinery_id: int
    name: str
    state: str
    strategic_priority_score: float
    stress_score: float
    weight: float
    rationale: str


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _scenario_context(db: Session, scenario: Scenario | None) -> dict[str, Any]:
    if scenario is None:
        national_risk = (
            db.query(func.avg(RiskScore.risk_score))
            .filter(RiskScore.scope_type == "national")
            .scalar()
            or 0.0
        )
        return {
            "scenario_id": None,
            "scenario_name": None,
            "supply_loss_pct": float(national_risk or 0.0) * 0.35,
            "duration_days": 7,
            "recovery_days": 21,
        }

    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario.id).one_or_none()
    assumptions = _as_dict(scenario.assumptions)
    if result is not None:
        payload = _as_dict(result.output_json)
        breakdown = _as_dict(payload.get("impact_breakdown"))
        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "supply_loss_pct": float(result.estimated_supply_loss_pct or 0.0),
            "duration_days": int(breakdown.get("duration_days", scenario.duration_days or 7) or 7),
            "recovery_days": int(
                max(
                    1,
                    int(assumptions.get("import_recovery_days", 21) or 21),
                )
            ),
        }

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "supply_loss_pct": float(assumptions.get("disruption_severity_pct", 0.0) or 0.0),
        "duration_days": int(assumptions.get("duration_days", scenario.duration_days or 7) or 7),
        "recovery_days": int(assumptions.get("import_recovery_days", 21) or 21),
    }


def _refinery_risk_map(db: Session) -> dict[str, float]:
    rows = db.query(RiskScore.scope_id, RiskScore.risk_score).filter(RiskScore.scope_type == "refinery").all()
    return {str(scope_id): float(score or 0.0) for scope_id, score in rows}


def _reserve_baseline_cover(db: Session) -> float:
    total_drawdown_days = db.query(func.max(SPRPlan.drawdown_days)).scalar()
    return float(total_drawdown_days or 0.0)


def _estimate_daily_import_need_bbl(db: Session) -> tuple[float, dict[str, Any]]:
    refineries = db.query(Refinery).all()
    total_capacity = sum(float(refinery.capacity_bpd or 0.0) for refinery in refineries)
    if total_capacity <= 0:
        total_capacity = 5_000_000.0

    assumed_run_rate = total_capacity * 0.85
    assumed_import_dependency = 0.82
    daily_import_need = assumed_run_rate * assumed_import_dependency
    return daily_import_need, {
        "total_refinery_capacity_bpd": round(total_capacity, 2),
        "assumed_run_rate_bpd": round(assumed_run_rate, 2),
        "assumed_import_dependency_ratio": assumed_import_dependency,
    }


def _normalize_weights(weights: list[float]) -> list[float]:
    total = sum(weights)
    if total <= 0:
        return [0.0 for _ in weights]
    return [weight / total for weight in weights]


def _build_refinery_allocations(
    db: Session,
    target_bbl: float,
) -> list[RefineryAllocation]:
    refinery_risks = _refinery_risk_map(db)
    refineries = db.query(Refinery).all()

    weighted_refineries: list[tuple[float, RefineryAllocation]] = []
    for refinery in refineries:
        stress_score = refinery_risks.get(str(refinery.id), 0.0)
        priority = float(refinery.strategic_priority_score or 0.0)
        complexity = float(refinery.complexity_index or 0.0)
        capacity = float(refinery.capacity_bpd or 0.0)

        weight = max(
            0.1,
            (capacity / 1_000_000.0)
            * (0.8 + priority)
            * (1.0 + stress_score / 100.0)
            / (1.0 + complexity / 20.0),
        )
        rationale = (
            f"Priority={priority:.2f}, stress={stress_score:.1f}, capacity={int(capacity):,} bpd, complexity={complexity:.1f}"
        )
        weighted_refineries.append(
            (
                weight,
                RefineryAllocation(
                    refinery_id=refinery.id,
                    name=refinery.name,
                    state=refinery.state,
                    strategic_priority_score=priority,
                    stress_score=stress_score,
                    weight=weight,
                    rationale=rationale,
                ),
            )
        )

    weighted_refineries.sort(key=lambda item: item[0], reverse=True)
    top_refineries = [item[1] for item in weighted_refineries[:8]]
    normalized = _normalize_weights([item.weight for item in top_refineries])

    allocations: list[RefineryAllocation] = []
    for allocation, share in zip(top_refineries, normalized):
        allocations.append(
            RefineryAllocation(
                refinery_id=allocation.refinery_id,
                name=allocation.name,
                state=allocation.state,
                strategic_priority_score=allocation.strategic_priority_score,
                stress_score=allocation.stress_score,
                weight=allocation.weight,
                rationale=f"{allocation.rationale}; allocated share {share * 100:.1f}%",
            )
        )
    return allocations


def _allocation_response_items(allocations: list[RefineryAllocation], total_bbl: float) -> list[SPRRefineryAllocationResponse]:
    normalized = _normalize_weights([item.weight for item in allocations])
    return [
        SPRRefineryAllocationResponse(
            refinery_id=item.refinery_id,
            name=item.name,
            state=item.state,
            strategic_priority_score=item.strategic_priority_score,
            stress_score=item.stress_score,
            allocated_bbl=round(total_bbl * share, 2),
            allocated_share_pct=round(share * 100.0, 2),
            rationale=item.rationale,
        )
        for item, share in zip(allocations, normalized)
    ]


def _build_daily_schedule(
    drawdown_days: int,
    total_drawdown_bbl: float,
    allocations: list[SPRRefineryAllocation],
    duration_days: int,
    recovery_days: int,
) -> list[SPRDailyReleaseResponse]:
    if drawdown_days <= 0 or total_drawdown_bbl <= 0:
        return []

    weights: list[float] = []
    for day in range(1, drawdown_days + 1):
        if day <= duration_days:
            weights.append(1.2)
        elif day <= duration_days + max(1, recovery_days // 2):
            weights.append(1.0)
        else:
            weights.append(0.75)

    normalized_weights = _normalize_weights(weights)
    cumulative = 0.0
    schedule: list[SPRDailyReleaseResponse] = []
    for day_number, weight in enumerate(normalized_weights, start=1):
        release_bbl = round(total_drawdown_bbl * weight, 2)
        cumulative = round(cumulative + release_bbl, 2)
        schedule.append(
            SPRDailyReleaseResponse(
                day=day_number,
                release_bbl=release_bbl,
                cumulative_bbl=cumulative,
                allocation=_allocation_response_items(allocations, release_bbl),
            )
        )
    return schedule


def _build_replenishment_strategy(
    total_drawdown_bbl: float,
    drawdown_days: int,
    duration_days: int,
    recovery_days: int,
    replenishment_window_days: int,
    allocations: list[SPRRefineryAllocationResponse],
) -> dict[str, Any]:
    replenishment_start_day = drawdown_days + max(1, recovery_days // 2)
    staged_tranches = [
        {
            "stage": "stabilize",
            "share_pct": 40.0,
            "trigger": "When corridor and import recovery signals stabilize",
            "window_days": min(14, replenishment_window_days),
        },
        {
            "stage": "rebuild",
            "share_pct": 35.0,
            "trigger": "After steady supplier flow resumes",
            "window_days": min(21, replenishment_window_days),
        },
        {
            "stage": "normalize",
            "share_pct": 25.0,
            "trigger": "When market price volatility subsides",
            "window_days": max(1, replenishment_window_days - 35),
        },
    ]
    return {
        "replenishment_start_day": replenishment_start_day,
        "replenishment_window_days": replenishment_window_days,
        "import_recovery_days": recovery_days,
        "duration_days": duration_days,
        "staged_tranches": staged_tranches,
        "refinery_allocation": [item.dict() for item in allocations],
        "execution_rule": (
            "Replenish in phased tranches after the disruption window closes, "
            "prioritizing the same strategic refineries that received the drawdown."
        ),
        "total_drawdown_bbl": round(total_drawdown_bbl, 2),
    }


def _policy_notes(
    reserve_usage_allowed: bool,
    supply_loss_pct: float,
    daily_import_need_bbl: float,
    drawdown_days: int,
    reserve_cover_days: float,
) -> str:
    notes = [
        "Assumption: SPR is used to offset near-term crude shortfall against an estimated daily import requirement derived from refinery throughput.",
        f"Estimated daily import need: {daily_import_need_bbl:,.0f} bbl/day.",
        f"Scenario supply loss estimate: {supply_loss_pct:.1f}%.",
        f"Planned drawdown window: {drawdown_days} days against {reserve_cover_days:.1f} days of current cover.",
    ]
    if not reserve_usage_allowed:
        notes.append("Reserve drawdown is policy-restricted in this request; plan is advisory only and sets release volume to zero.")
    return " ".join(notes)


def _risk_notes(
    supply_loss_pct: float,
    drawdown_days: int,
    reserve_cover_days: float,
    recovery_days: int,
) -> list[str]:
    notes = [
        f"Supply loss above 20% is treated as a severe disruption and can quickly exhaust reserve cover.",
        f"Recovery window is assumed to be {recovery_days} days.",
        f"Selected drawdown days ({drawdown_days}) remain within current reserve cover ({reserve_cover_days:.1f} days) by design.",
    ]
    if supply_loss_pct >= 40.0:
        notes.append("Supply loss exceeds 40%, so release timing should be reviewed daily against new intelligence.")
    return notes


def _serialize_plan(plan: SPRPlan, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plan.id,
        "scenario_id": plan.scenario_id,
        "total_drawdown_bbl": float(plan.total_drawdown_bbl or 0.0),
        "drawdown_days": int(plan.drawdown_days or 0),
        "daily_release_schedule": payload.get("daily_release_schedule", _as_dict(plan.daily_release_schedule)),
        "replenishment_strategy": payload.get("replenishment_strategy", _as_dict(plan.replenishment_strategy)),
        "policy_notes": plan.policy_notes,
        "generated_at": plan.generated_at,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def optimize_spr_plan(db: Session, payload: SPROptimizeRequest) -> dict[str, Any]:
    scenario = None
    if payload.scenario_id is not None:
        scenario = db.query(Scenario).filter(Scenario.id == payload.scenario_id).one_or_none()
        if scenario is None:
            raise KeyError(f"Scenario {payload.scenario_id} not found")

    if payload.target_scope == "refinery" and payload.refinery_id is None:
        raise ValueError("refinery_id is required when target_scope is refinery")

    if payload.target_scope == "scenario" and scenario is None:
        raise ValueError("scenario_id is required when target_scope is scenario")

    scenario_ctx = _scenario_context(db, scenario)
    daily_import_need_bbl, demand_context = _estimate_daily_import_need_bbl(db)
    supply_loss_pct = (
        float(payload.scenario_supply_loss_pct)
        if payload.scenario_supply_loss_pct is not None
        else float(scenario_ctx["supply_loss_pct"])
    )
    supply_shortfall_bbl_per_day = daily_import_need_bbl * (supply_loss_pct / 100.0)

    reserve_cover_days = float(payload.current_reserve_days_cover)
    base_drawdown_days = int(payload.duration_days or scenario_ctx["duration_days"] or 1)
    recovery_days = int(payload.import_recovery_days)

    if payload.reserve_usage_allowed:
        drawdown_days = min(
            max(1, base_drawdown_days + ceil(recovery_days * 0.5)),
            max(1, int(reserve_cover_days)),
        )
    else:
        drawdown_days = 0

    buffer_factor = 1.0 + min(0.15, max(0.0, recovery_days - base_drawdown_days) / 100.0)
    total_drawdown_bbl = round(supply_shortfall_bbl_per_day * drawdown_days * buffer_factor, 2)
    if not payload.reserve_usage_allowed:
        total_drawdown_bbl = 0.0

    allocations = _build_refinery_allocations(db, total_drawdown_bbl)
    allocation_response = _allocation_response_items(allocations, total_drawdown_bbl)
    daily_release_schedule = _build_daily_schedule(
        drawdown_days,
        total_drawdown_bbl,
        allocations,
        base_drawdown_days,
        recovery_days,
    )
    replenishment_strategy = _build_replenishment_strategy(
        total_drawdown_bbl,
        drawdown_days,
        base_drawdown_days,
        recovery_days,
        int(payload.replenishment_window_days),
        allocation_response,
    )
    notes = _policy_notes(
        payload.reserve_usage_allowed,
        supply_loss_pct,
        daily_import_need_bbl,
        drawdown_days,
        reserve_cover_days,
    )
    risk_notes = _risk_notes(supply_loss_pct, drawdown_days, reserve_cover_days, recovery_days)

    plan = SPRPlan(
        scenario_id=scenario.id if scenario else None,
        total_drawdown_bbl=total_drawdown_bbl,
        drawdown_days=drawdown_days,
        daily_release_schedule={
            "daily_import_need_bbl": round(daily_import_need_bbl, 2),
            "demand_context": demand_context,
            "supply_loss_pct": round(supply_loss_pct, 2),
            "supply_shortfall_bbl_per_day": round(supply_shortfall_bbl_per_day, 2),
            "reserve_usage_allowed": payload.reserve_usage_allowed,
            "days": [item.dict() for item in daily_release_schedule],
        },
        replenishment_strategy=replenishment_strategy,
        policy_notes=notes,
        generated_at=utcnow(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    plan_payload = _serialize_plan(
        plan,
        {
            "daily_release_schedule": plan.daily_release_schedule,
            "replenishment_strategy": plan.replenishment_strategy,
        },
    )
    return {
        "plan": SPRPlanResponse(**plan_payload),
        "refinery_allocation_suggestion": allocation_response,
        "replenishment_strategy": replenishment_strategy,
        "risk_notes": risk_notes,
    }


def list_spr_plans(db: Session, limit: int = 50, scenario_id: int | None = None) -> SPRPlanListResponse:
    query = db.query(SPRPlan).order_by(SPRPlan.generated_at.desc())
    count_query = db.query(func.count(SPRPlan.id))
    if scenario_id is not None:
        query = query.filter(SPRPlan.scenario_id == scenario_id)
        count_query = count_query.filter(SPRPlan.scenario_id == scenario_id)

    rows = query.limit(limit).all()
    items = [
        SPRPlanResponse(**_serialize_plan(row, {"daily_release_schedule": row.daily_release_schedule, "replenishment_strategy": row.replenishment_strategy}))
        for row in rows
    ]
    return SPRPlanListResponse(items=items, total_count=int(count_query.scalar() or 0))


def get_spr_plan(db: Session, plan_id: int) -> SPRPlanResponse:
    row = db.query(SPRPlan).filter(SPRPlan.id == plan_id).one_or_none()
    if row is None:
        raise KeyError(f"SPR plan {plan_id} not found")
    return SPRPlanResponse(
        **_serialize_plan(row, {"daily_release_schedule": row.daily_release_schedule, "replenishment_strategy": row.replenishment_strategy})
    )

