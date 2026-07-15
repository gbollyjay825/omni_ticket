from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.observability import current_request_id
from app.core.store import InMemoryStore
from app.db.models import AuditEventRecord
from app.models.domain import utc_now


def write_audit_event(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict,
    commit: bool = False,
) -> AuditEventRecord:
    enriched_details = dict(details)
    request_id = current_request_id()
    if request_id and "request_id" not in enriched_details:
        enriched_details["request_id"] = request_id
    record = AuditEventRecord(
        id=f"audit_{uuid4().hex}",
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=enriched_details,
    )
    db.add(record)
    if commit:
        db.commit()
    else:
        db.flush()
    return record


def _market_scope(market_id: str):
    return or_(AuditEventRecord.market_id.is_(None), AuditEventRecord.market_id == market_id)


def _filtered_audit_statement(
    *,
    market_id: str,
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    statement = select(AuditEventRecord).where(_market_scope(market_id))
    if actor:
        statement = statement.where(AuditEventRecord.actor == actor)
    if action:
        statement = statement.where(AuditEventRecord.action == action)
    if entity_type:
        statement = statement.where(AuditEventRecord.entity_type == entity_type)
    if entity_id:
        statement = statement.where(AuditEventRecord.entity_id == entity_id)
    if since:
        statement = statement.where(AuditEventRecord.created_at >= since)
    if until:
        statement = statement.where(AuditEventRecord.created_at <= until)
    return statement


def list_audit_events(
    db: Session,
    *,
    market_id: str,
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 500,
) -> list[AuditEventRecord]:
    bounded_limit = max(1, limit)
    statement = (
        _filtered_audit_statement(
            market_id=market_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            since=since,
            until=until,
        )
        .order_by(AuditEventRecord.created_at.desc())
        .limit(bounded_limit)
    )
    return list(db.scalars(statement).all())


def count_audit_events(
    db: Session,
    *,
    market_id: str,
) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AuditEventRecord).where(_market_scope(market_id)))
        or 0
    )


def audit_retention_cutoff(retention_days: int) -> datetime:
    return utc_now() - timedelta(days=retention_days)


def count_prunable_audit_events(
    db: Session,
    *,
    market_id: str,
    retention_days: int,
) -> int:
    cutoff = audit_retention_cutoff(retention_days)
    return int(
        db.scalar(
            select(func.count())
            .select_from(AuditEventRecord)
            .where(_market_scope(market_id), AuditEventRecord.created_at < cutoff)
        )
        or 0
    )


def audit_retention_policy(
    db: Session,
    *,
    market_id: str,
    retention_days: int,
    export_max_rows: int,
) -> dict[str, Any]:
    cutoff = audit_retention_cutoff(retention_days)
    return {
        "market_id": market_id,
        "retention_days": retention_days,
        "cutoff_at": cutoff,
        "retained_events": count_audit_events(db, market_id=market_id),
        "prunable_events": count_prunable_audit_events(
            db,
            market_id=market_id,
            retention_days=retention_days,
        ),
        "export_max_rows": export_max_rows,
    }


def prune_audit_events(
    db: Session,
    *,
    market_id: str,
    retention_days: int,
    state: InMemoryStore | None = None,
) -> int:
    cutoff = audit_retention_cutoff(retention_days)
    prunable_ids = list(
        db.scalars(
            select(AuditEventRecord.id).where(
                _market_scope(market_id),
                AuditEventRecord.created_at < cutoff,
            )
        ).all()
    )
    if not prunable_ids:
        return 0

    db.execute(delete(AuditEventRecord).where(AuditEventRecord.id.in_(prunable_ids)))
    if state is not None:
        prunable_set = set(prunable_ids)
        state.audit = [event for event in state.audit if event.id not in prunable_set]
    return len(prunable_ids)
