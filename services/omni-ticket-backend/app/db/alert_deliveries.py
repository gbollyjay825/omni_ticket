from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.mappers import operational_alert_delivery_from_record
from app.db.models import OperationalAlertDeliveryRecord, OperationalAlertRecord
from app.models.domain import (
    OperationalAlertDelivery,
    OperationalAlertDeliveryStatus,
    OperationalAlertSeverity,
    OperationalAlertStatus,
    utc_now,
)


SEVERITY_RANK = {
    OperationalAlertSeverity.info.value: 1,
    OperationalAlertSeverity.warning.value: 2,
    OperationalAlertSeverity.critical.value: 3,
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class OperationalAlertDeliveryRepository:
    def list_deliveries(
        self,
        db: Session,
        market_id: str,
        *,
        include_sent: bool = False,
        limit: int = 200,
    ) -> list[OperationalAlertDelivery]:
        query = select(OperationalAlertDeliveryRecord).where(
            OperationalAlertDeliveryRecord.market_id == market_id
        )
        if not include_sent:
            query = query.where(
                OperationalAlertDeliveryRecord.status
                != OperationalAlertDeliveryStatus.sent.value
            )
        records = db.scalars(
            query.order_by(
                OperationalAlertDeliveryRecord.status.asc(),
                OperationalAlertDeliveryRecord.updated_at.desc(),
            ).limit(limit)
        ).all()
        return [operational_alert_delivery_from_record(record) for record in records]

    def enqueue_missing_webhook_deliveries(
        self,
        db: Session,
        *,
        market_id: str,
        destination_name: str,
        max_attempts: int,
        min_severity: OperationalAlertSeverity,
    ) -> int:
        min_rank = SEVERITY_RANK[min_severity.value]
        active_alerts = db.scalars(
            select(OperationalAlertRecord)
            .where(
                OperationalAlertRecord.market_id == market_id,
                OperationalAlertRecord.status != OperationalAlertStatus.resolved.value,
            )
            .order_by(OperationalAlertRecord.last_seen_at.asc())
        ).all()
        created = 0
        now = utc_now()
        for alert in active_alerts:
            if SEVERITY_RANK.get(alert.severity, 0) < min_rank:
                continue
            existing = db.scalar(
                select(OperationalAlertDeliveryRecord).where(
                    OperationalAlertDeliveryRecord.alert_id == alert.id,
                    OperationalAlertDeliveryRecord.destination_type == "webhook",
                    OperationalAlertDeliveryRecord.destination_name == destination_name,
                )
            )
            if existing is None:
                db.add(
                    OperationalAlertDeliveryRecord(
                        id=_new_id("alert_delivery"),
                        market_id=market_id,
                        alert_id=alert.id,
                        destination_type="webhook",
                        destination_name=destination_name,
                        status=OperationalAlertDeliveryStatus.queued.value,
                        attempts=0,
                        max_attempts=max_attempts,
                        payload={},
                    )
                )
                created += 1
                continue
            if (
                existing.status == OperationalAlertDeliveryStatus.sent.value
                and existing.sent_at is not None
                and alert.last_seen_at > existing.sent_at
            ):
                existing.status = OperationalAlertDeliveryStatus.queued.value
                existing.attempts = 0
                existing.max_attempts = max_attempts
                existing.next_attempt_at = None
                existing.sent_at = None
                existing.last_error = None
                existing.updated_at = now
        if created:
            db.flush()
        return created

    def due_webhook_deliveries(
        self,
        db: Session,
        *,
        market_id: str,
        destination_name: str,
        limit: int = 50,
    ) -> list[OperationalAlertDeliveryRecord]:
        now = utc_now()
        return list(
            db.scalars(
                select(OperationalAlertDeliveryRecord)
                .where(
                    OperationalAlertDeliveryRecord.market_id == market_id,
                    OperationalAlertDeliveryRecord.destination_type == "webhook",
                    OperationalAlertDeliveryRecord.destination_name == destination_name,
                    OperationalAlertDeliveryRecord.status.in_(
                        [
                            OperationalAlertDeliveryStatus.queued.value,
                            OperationalAlertDeliveryStatus.failed.value,
                        ]
                    ),
                    OperationalAlertDeliveryRecord.attempts
                    < OperationalAlertDeliveryRecord.max_attempts,
                    or_(
                        OperationalAlertDeliveryRecord.next_attempt_at.is_(None),
                        OperationalAlertDeliveryRecord.next_attempt_at <= now,
                    ),
                )
                .order_by(OperationalAlertDeliveryRecord.created_at.asc())
                .limit(limit)
            )
        )

    def mark_sending(self, record: OperationalAlertDeliveryRecord) -> None:
        record.status = OperationalAlertDeliveryStatus.sending.value
        record.attempts += 1
        record.last_error = None
        record.updated_at = utc_now()

    def mark_sent(self, record: OperationalAlertDeliveryRecord, payload: dict) -> None:
        now = utc_now()
        record.status = OperationalAlertDeliveryStatus.sent.value
        record.sent_at = now
        record.next_attempt_at = None
        record.last_error = None
        record.payload = payload
        record.updated_at = now

    def mark_failed(
        self,
        record: OperationalAlertDeliveryRecord,
        *,
        error: str,
        payload: dict,
        retry_minutes: int,
    ) -> None:
        now = utc_now()
        record.status = OperationalAlertDeliveryStatus.failed.value
        record.last_error = error
        record.payload = payload
        record.next_attempt_at = (
            now + timedelta(minutes=retry_minutes)
            if record.attempts < record.max_attempts
            else None
        )
        record.updated_at = now


operational_alert_delivery_repository = OperationalAlertDeliveryRepository()
