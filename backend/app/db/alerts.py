from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.audit import write_audit_event
from app.db.mappers import operational_alert_from_record
from app.db.models import OperationalAlertRecord
from app.models.domain import (
    OperationalAlert,
    OperationalAlertSeverity,
    OperationalAlertStatus,
    utc_now,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class OperationalAlertRepository:
    def list_alerts(
        self,
        db: Session,
        market_id: str,
        *,
        status_filter: OperationalAlertStatus | None = None,
        include_resolved: bool = False,
        limit: int = 200,
    ) -> list[OperationalAlert]:
        query = select(OperationalAlertRecord).where(OperationalAlertRecord.market_id == market_id)
        if status_filter is not None:
            query = query.where(OperationalAlertRecord.status == status_filter.value)
        elif not include_resolved:
            query = query.where(OperationalAlertRecord.status != OperationalAlertStatus.resolved.value)
        records = db.scalars(
            query.order_by(
                OperationalAlertRecord.status.asc(),
                OperationalAlertRecord.severity.asc(),
                OperationalAlertRecord.last_seen_at.desc(),
            ).limit(limit)
        ).all()
        return [operational_alert_from_record(record) for record in records]

    def upsert_alert(
        self,
        db: Session,
        *,
        market_id: str,
        severity: OperationalAlertSeverity,
        source: str,
        entity_type: str,
        entity_id: str,
        dedupe_key: str,
        title: str,
        message: str,
        details: dict,
        actor: str,
    ) -> OperationalAlert:
        now = utc_now()
        record = db.scalar(
            select(OperationalAlertRecord).where(
                OperationalAlertRecord.market_id == market_id,
                OperationalAlertRecord.dedupe_key == dedupe_key,
            )
        )
        if record is None:
            record = OperationalAlertRecord(
                id=_new_id("alert"),
                market_id=market_id,
                severity=severity.value,
                status=OperationalAlertStatus.open.value,
                source=source,
                entity_type=entity_type,
                entity_id=entity_id,
                dedupe_key=dedupe_key,
                title=title,
                message=message,
                details=details,
                occurrence_count=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(record)
            action = "alert.open"
        else:
            record.severity = severity.value
            record.status = OperationalAlertStatus.open.value
            record.source = source
            record.entity_type = entity_type
            record.entity_id = entity_id
            record.title = title
            record.message = message
            record.details = details
            record.occurrence_count += 1
            record.last_seen_at = now
            record.resolved_at = None
            record.resolved_by = None
            action = "alert.update"
        db.flush()
        write_audit_event(
            db,
            actor=actor,
            action=action,
            entity_type="operational_alert",
            entity_id=record.id,
            market_id=market_id,
            details={
                "severity": record.severity,
                "source": source,
                "alert_entity_type": entity_type,
                "alert_entity_id": entity_id,
                "dedupe_key": dedupe_key,
                "occurrence_count": record.occurrence_count,
            },
        )
        return operational_alert_from_record(record)

    def update_alert_status(
        self,
        db: Session,
        *,
        alert_id: str,
        market_id: str,
        status_value: OperationalAlertStatus,
        actor: str,
        note: str | None = None,
    ) -> OperationalAlert:
        record = db.get(OperationalAlertRecord, alert_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Operational alert not found")
        now = utc_now()
        record.status = status_value.value
        details = {"status": status_value.value}
        if note:
            details["note"] = note
        if status_value == OperationalAlertStatus.acknowledged:
            record.acknowledged_at = record.acknowledged_at or now
            record.acknowledged_by = record.acknowledged_by or actor
        elif status_value == OperationalAlertStatus.resolved:
            record.resolved_at = now
            record.resolved_by = actor
            record.acknowledged_at = record.acknowledged_at or now
            record.acknowledged_by = record.acknowledged_by or actor
        elif status_value == OperationalAlertStatus.open:
            record.acknowledged_at = None
            record.acknowledged_by = None
            record.resolved_at = None
            record.resolved_by = None
        db.flush()
        write_audit_event(
            db,
            actor=actor,
            action="alert.status_update",
            entity_type="operational_alert",
            entity_id=record.id,
            market_id=market_id,
            details=details,
        )
        return operational_alert_from_record(record)


operational_alert_repository = OperationalAlertRepository()
