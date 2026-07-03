from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.jobs.scheduler import get_scheduler_status
from app.models.audit_log import AuditLog
from app.models.commodity_price import CommodityPrice
from app.models.geopolitical_event import GeopoliticalEvent
from app.models.port import Port
from app.models.refinery import Refinery
from app.models.risk_score import RiskScore
from app.models.sanctions_event import SanctionsEvent
from app.models.scenario import Scenario, ScenarioResult
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.recommendation import ProcurementRecommendation, SPRPlan
from app.models.supplier_country import SupplierCountry
from app.models.user import User
from app.schemas.admin import AuditLogItemResponse, AuditLogListResponse, SeedDemoResponse, SystemSummaryResponse
from app.scripts.seed_demo_data import seed_demo_data

from app.services.audit_service import safe_record_audit_log


def _count(db: Session, model: Any, clause: Any | None = None) -> int:
    query = select(func.count()).select_from(model)
    if clause is not None:
        query = query.where(clause)
    return int(db.scalar(query) or 0)


def _latest_timestamp(db: Session, model: Any, column: Any) -> str | None:
    value = db.scalar(select(func.max(column)).select_from(model))
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _serialize_audit_row(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_email": getattr(row.user, "email", None),
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "metadata_json": row.metadata_json or {},
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_audit_logs(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> AuditLogListResponse:
    from app.services.audit_service import list_audit_logs as fetch_audit_logs

    rows, total = fetch_audit_logs(
        db,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
    )
    return AuditLogListResponse(
        items=[AuditLogItemResponse(**_serialize_audit_row(row)) for row in rows],
        total_count=total,
        limit=limit,
        offset=offset,
        page=(offset // limit) + 1 if limit > 0 else 1,
        pages=(total + limit - 1) // limit if limit > 0 and total > 0 else 0,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def get_system_summary(db: Session) -> SystemSummaryResponse:
    scheduler_status = get_scheduler_status()
    counts = {
        "users": _count(db, User),
        "active_users": _count(db, User, User.is_active.is_(True)),
        "supplier_countries": _count(db, SupplierCountry),
        "corridors": _count(db, ShippingCorridor),
        "ports": _count(db, Port),
        "refineries": _count(db, Refinery),
        "shipments": _count(db, Shipment),
        "geopolitical_events": _count(db, GeopoliticalEvent),
        "sanctions_events": _count(db, SanctionsEvent),
        "commodity_prices": _count(db, CommodityPrice),
        "risk_scores": _count(db, RiskScore),
        "scenarios": _count(db, Scenario),
        "scenario_results": _count(db, ScenarioResult),
        "procurement_recommendations": _count(db, ProcurementRecommendation),
        "spr_plans": _count(db, SPRPlan),
        "audit_logs": _count(db, AuditLog),
    }
    latest_activity = {
        "latest_audit_log_at": _latest_timestamp(db, AuditLog, AuditLog.created_at),
        "latest_price_at": _latest_timestamp(db, CommodityPrice, CommodityPrice.timestamp),
        "latest_event_at": _latest_timestamp(db, GeopoliticalEvent, GeopoliticalEvent.event_time),
        "latest_scenario_at": _latest_timestamp(db, Scenario, Scenario.created_at),
    }
    return SystemSummaryResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        counts=counts,
        latest_activity=latest_activity,
        scheduler={
            "enabled": scheduler_status.enabled,
            "running": scheduler_status.running,
            "last_started_at": scheduler_status.last_started_at,
            "reason": scheduler_status.reason,
            "job_count": len(scheduler_status.jobs),
        },
    )


def seed_demo_data_from_api(db: Session, user_id: int | None = None) -> SeedDemoResponse:
    """Seed demo data and return a summary suitable for the admin API."""
    seed_demo_data(create_tables=True)
    with SessionLocal() as summary_db:
        summary = get_system_summary(summary_db)
        safe_record_audit_log(
            summary_db,
            user_id=user_id,
            action="seed_demo_data",
            entity_type="system",
            entity_id="demo_seed",
            metadata={
                "seeded_at": datetime.now(timezone.utc).isoformat(),
                "counts": summary.counts,
            },
            commit=True,
        )
    return SeedDemoResponse(
        message="Demo data seeded successfully.",
        seeded_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
    )
