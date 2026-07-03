from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


def record_audit_log(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    """Persist an audit entry for a sensitive or operational action."""
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=dict(metadata or {}),
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    return row


def safe_record_audit_log(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog | None:
    """Best-effort audit logging that must not block the primary workflow."""
    try:
        return record_audit_log(
            db,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            commit=commit,
        )
    except Exception:
        logger.exception(
            "audit_log_write_failed",
            extra={
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "user_id": user_id,
            },
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("audit_log_rollback_failed")
        return None


def list_audit_logs(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    """Return a filtered, paginated audit-log slice plus the total count."""
    query = select(AuditLog).options(joinedload(AuditLog.user)).order_by(AuditLog.created_at.desc())
    count_query = select(func.count(AuditLog.id))

    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if created_after is not None:
        filters.append(AuditLog.created_at >= created_after)
    if created_before is not None:
        filters.append(AuditLog.created_at <= created_before)

    if filters:
        for clause in filters:
            query = query.where(clause)
            count_query = count_query.where(clause)

    total = int(db.scalar(count_query) or 0)
    rows = list(db.scalars(query.limit(limit).offset(offset)).all())
    return rows, total


def user_login_audit_metadata(user: User) -> dict[str, Any]:
    """Small helper to keep login audit payload consistent."""
    return {
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }

