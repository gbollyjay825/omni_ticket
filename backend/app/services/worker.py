from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.store import InMemoryStore
from app.db.audit import audit_retention_policy, prune_audit_events
from app.db.alerts import operational_alert_repository
from app.db.mappers import audit_event_from_record, ticket_from_record
from app.db.models import (
    AuditEventRecord,
    MarketRecord,
    OutboundMessageRecord,
    SupportGroupRecord,
    TicketRecord,
)
from app.db.operations import OPEN_STATUSES, operations_repository
from app.db.outbound import outbound_repository
from app.db.ticketing import (
    _add_timeline_record,
    _queue_event_notification_email,
    ticket_repository,
)
from app.models.domain import (
    ChannelType,
    OperationalAlertSeverity,
    OutboundMessageStatus,
    TicketStatus,
    TimelineEventType,
    utc_now,
)
from app.services.alert_delivery import AlertWebhookTransport, alert_delivery_service
from app.services.attachments import attachment_storage
from app.services.campaigns import campaign_service
from app.services.escalation import escalation_service
from app.services.inbound_adapters import inbound_adapter_router
from app.services.report_delivery import report_delivery_service
from app.services.sla import sla_service


WORKER_ACTOR = "omni-worker"
OUTBOUND_DUE_STATUSES = {
    OutboundMessageStatus.queued.value,
    OutboundMessageStatus.failed.value,
    OutboundMessageStatus.retrying.value,
}


@dataclass
class WorkerJobResult:
    name: str
    market_id: str | None = None
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_lettered: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerRunSummary:
    started_at: str
    finished_at: str
    jobs: list[WorkerJobResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit_worker(
    db: Session,
    state: InMemoryStore,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict[str, Any],
    actor: str = WORKER_ACTOR,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class BackgroundWorkerService:
    def market_ids(self, db: Session, requested_market_ids: list[str] | None = None) -> list[str]:
        if requested_market_ids:
            return requested_market_ids
        return list(
            db.scalars(
                select(MarketRecord.id)
                .where(MarketRecord.active.is_(True))
                .order_by(MarketRecord.code.asc())
            )
        )

    def sync_inbound_email(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        sync_result = inbound_adapter_router.sync_email(
            db,
            state,
            market_id,
            limit=limit,
        )
        details = sync_result.to_details()
        result = WorkerJobResult(
            name="email_inbound_sync",
            market_id=market_id,
            processed=sync_result.processed,
            succeeded=sync_result.succeeded + sync_result.deduplicated,
            failed=sync_result.failed,
            details=details,
        )
        if sync_result.failed:
            operational_alert_repository.upsert_alert(
                db,
                market_id=market_id,
                severity=OperationalAlertSeverity.warning,
                source="email_inbound_worker",
                entity_type="market",
                entity_id=market_id,
                dedupe_key=f"email-inbound:{market_id}:sync-failure",
                title="Email inbound sync failed",
                message="The email intake worker could not complete mailbox polling.",
                details=details,
                actor=actor,
            )
        if sync_result.processed or sync_result.failed:
            _audit_worker(
                db,
                state,
                action="worker.email_inbound_sync",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details=details,
                actor=actor,
            )
        db.commit()
        return result

    def process_due_outbound(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int = 50,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        now = utc_now()
        stale_sending_before = now - timedelta(minutes=10)
        message_ids = list(
            db.scalars(
                select(OutboundMessageRecord.id)
                .where(
                    OutboundMessageRecord.market_id == market_id,
                    or_(
                        and_(
                            OutboundMessageRecord.status.in_(OUTBOUND_DUE_STATUSES),
                            or_(
                                OutboundMessageRecord.next_attempt_at.is_(None),
                                OutboundMessageRecord.next_attempt_at <= now,
                            ),
                        ),
                        and_(
                            OutboundMessageRecord.status == OutboundMessageStatus.sending.value,
                            OutboundMessageRecord.updated_at <= stale_sending_before,
                        ),
                    ),
                )
                .order_by(OutboundMessageRecord.created_at.asc())
                .limit(limit)
            )
        )
        result = WorkerJobResult(
            name="outbound_retry",
            market_id=market_id,
            processed=len(message_ids),
            details={"message_ids": message_ids},
        )
        for message_id in message_ids:
            try:
                message = outbound_repository.process_message(
                    db,
                    state,
                    message_id,
                    market_id,
                    actor=actor,
                )
                if message.status == OutboundMessageStatus.sent:
                    result.succeeded += 1
                elif message.status == OutboundMessageStatus.dead_lettered:
                    result.dead_lettered += 1
                    operational_alert_repository.upsert_alert(
                        db,
                        market_id=market_id,
                        severity=OperationalAlertSeverity.critical,
                        source="outbound_worker",
                        entity_type="outbound_message",
                        entity_id=message.id,
                        dedupe_key=f"outbound:{message.id}:dead_lettered",
                        title=f"{message.provider.value.title()} reply is dead-lettered",
                        message=(
                            "A customer-facing outbound message exhausted retries and needs "
                            "connector or operator intervention."
                        ),
                        details={
                            "ticket_id": message.ticket_id,
                            "provider": message.provider.value,
                            "attempts": message.attempts,
                            "max_attempts": message.max_attempts,
                            "last_error": message.last_error,
                        },
                        actor=actor,
                    )
                else:
                    result.failed += 1
                    operational_alert_repository.upsert_alert(
                        db,
                        market_id=market_id,
                        severity=OperationalAlertSeverity.warning,
                        source="outbound_worker",
                        entity_type="outbound_message",
                        entity_id=message.id,
                        dedupe_key=f"outbound:{message.id}:delivery_failure",
                        title=f"{message.provider.value.title()} reply delivery failed",
                        message="An outbound message failed and is queued for retry.",
                        details={
                            "ticket_id": message.ticket_id,
                            "provider": message.provider.value,
                            "attempts": message.attempts,
                            "max_attempts": message.max_attempts,
                            "next_attempt_at": (
                                message.next_attempt_at.isoformat()
                                if message.next_attempt_at
                                else None
                            ),
                            "last_error": message.last_error,
                        },
                        actor=actor,
                    )
                db.commit()
            except Exception as exc:  # pragma: no cover - defensive isolation for production workers
                db.rollback()
                result.failed += 1
                _audit_worker(
                    db,
                    state,
                    action="worker.outbound_error",
                    entity_type="outbound_message",
                    entity_id=message_id,
                    market_id=market_id,
                    details={"error": str(exc)},
                    actor=actor,
                )
                operational_alert_repository.upsert_alert(
                    db,
                    market_id=market_id,
                    severity=OperationalAlertSeverity.critical,
                    source="outbound_worker",
                    entity_type="outbound_message",
                    entity_id=message_id,
                    dedupe_key=f"outbound:{message_id}:worker_exception",
                    title="Outbound worker exception",
                    message="The outbound worker hit an exception while processing a message.",
                    details={"error": str(exc)},
                    actor=actor,
                )
                db.commit()

        if result.processed:
            _audit_worker(
                db,
                state,
                action="worker.outbound_batch",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details={
                    "processed": result.processed,
                    "succeeded": result.succeeded,
                    "failed": result.failed,
                    "dead_lettered": result.dead_lettered,
                },
                actor=actor,
            )
            db.commit()
        return result

    def refresh_sla_states(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        records = list(
            db.scalars(
                select(TicketRecord)
                .where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.status.in_(OPEN_STATUSES),
                )
                .order_by(TicketRecord.created_at.asc())
            )
        )
        result = WorkerJobResult(
            name="sla_refresh",
            market_id=market_id,
            processed=len(records),
        )
        changed_ticket_ids: list[str] = []
        notified_ticket_ids: list[str] = []
        for record in records:
            previous_risk = record.sla.get("risk")
            previous_breached = bool(record.sla.get("breached"))
            ticket = ticket_from_record(record)
            ticket.sla = sla_service.refresh(ticket.sla)
            record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket
            if ticket.sla.risk != previous_risk or ticket.sla.breached != previous_breached:
                changed_ticket_ids.append(ticket.id)
                _audit_worker(
                    db,
                    state,
                    action="worker.sla_refresh",
                    entity_type="ticket",
                    entity_id=ticket.id,
                    market_id=market_id,
                    details={
                        "from": {"risk": previous_risk, "breached": previous_breached},
                        "to": {"risk": ticket.sla.risk, "breached": ticket.sla.breached},
                    },
                    actor=actor,
                )
                if ticket.sla.breached and not previous_breached:
                    # Newly breached: email the owning team's inbox (config-gated by the
                    # active "sla_breach" notification in Setup → Email notifications).
                    group = db.scalar(
                        select(SupportGroupRecord).where(
                            SupportGroupRecord.market_id == market_id,
                            SupportGroupRecord.name == record.team,
                        )
                    )
                    team_email = (group.team_email or "").strip() if group else ""
                    _queue_event_notification_email(
                        db,
                        state,
                        record,
                        event="sla_breach",
                        to_email=team_email,
                        idempotency_key=f"sla-breach-{ticket.id}",
                        default_subject=f"SLA breached on {ticket.public_id}",
                        extra_body=(
                            f"Ticket {ticket.public_id} — {record.subject}\n"
                            f"Priority {record.priority} · team {record.team}."
                        ),
                    )
            notification = escalation_service.notification_payload(db, ticket, state=state)
            if notification and not escalation_service.already_notified(
                db,
                ticket.id,
                market_id=market_id,
                risk=ticket.sla.risk,
            ):
                message = escalation_service.notification_message(ticket, notification)
                escalation_service.append_notification_timeline(
                    db,
                    state,
                    record,
                    actor=actor,
                    body=message,
                    metadata=notification,
                )
                ticket.updated_at = record.updated_at
                state.tickets[ticket.id] = ticket
                notified_ticket_ids.append(ticket.id)
                _audit_worker(
                    db,
                    state,
                    action="worker.supervisor_notification",
                    entity_type="ticket",
                    entity_id=ticket.id,
                    market_id=market_id,
                    details=notification | {"message": message},
                    actor=actor,
                )
                operational_alert_repository.upsert_alert(
                    db,
                    market_id=market_id,
                    severity=(
                        OperationalAlertSeverity.critical
                        if ticket.sla.breached
                        else OperationalAlertSeverity.warning
                    ),
                    source="sla_worker",
                    entity_type="ticket",
                    entity_id=ticket.id,
                    dedupe_key=f"sla:{ticket.id}:{ticket.sla.risk}",
                    title=f"Ticket {ticket.public_id} needs supervisor attention",
                    message=message,
                    details=notification
                    | {
                        "ticket_id": ticket.id,
                        "public_id": ticket.public_id,
                        "sla_risk": ticket.sla.risk,
                        "breached": ticket.sla.breached,
                    },
                    actor=actor,
                )
        result.succeeded = len(changed_ticket_ids) + len(notified_ticket_ids)
        result.details = {
            "changed_ticket_ids": changed_ticket_ids,
            "notified_ticket_ids": notified_ticket_ids,
        }
        db.commit()
        return result

    def auto_close_resolved(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        """Move resolved (solved) tickets to closed once they have sat untouched past the
        configured window — Freshdesk's "automatically close resolved tickets" behaviour."""
        after_hours = settings.auto_close_resolved_after_hours
        result = WorkerJobResult(name="auto_close_resolved", market_id=market_id, processed=0)
        if after_hours <= 0:
            return result
        cutoff = utc_now() - timedelta(hours=after_hours)
        records = list(
            db.scalars(
                select(TicketRecord).where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.status == TicketStatus.solved.value,
                    TicketRecord.resolved_at.is_not(None),
                    TicketRecord.resolved_at <= cutoff,
                )
            )
        )
        result.processed = len(records)
        closed_ids: list[str] = []
        now = utc_now()
        for record in records:
            record.status = TicketStatus.closed.value
            record.closed_at = now
            record.updated_at = now
            _add_timeline_record(
                db,
                state,
                record,
                event_type=TimelineEventType.status_change,
                channel=ChannelType.internal,
                actor=actor,
                body=f"Ticket auto-closed after {after_hours}h resolved with no further activity.",
                public=False,
                metadata={"previous_status": "solved", "new_status": "closed", "auto_close": True},
            )
            _audit_worker(
                db,
                state,
                action="worker.auto_close",
                entity_type="ticket",
                entity_id=record.id,
                market_id=market_id,
                details={"after_hours": after_hours},
                actor=actor,
            )
            state.tickets[record.id] = ticket_from_record(record)
            closed_ids.append(record.id)
        result.succeeded = len(closed_ids)
        result.details = {"closed_ticket_ids": closed_ids}
        db.commit()
        return result

    def recompute_work_queue(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        items = operations_repository.read_work_queue(db, state, market_id)
        top_item = items[0] if items else None
        result = WorkerJobResult(
            name="work_queue_recompute",
            market_id=market_id,
            processed=len(items),
            succeeded=len(items),
            details={
                "top_ticket_id": top_item.ticket.id if top_item else None,
                "top_score": top_item.score if top_item else None,
            },
        )
        _audit_worker(
            db,
            state,
            action="worker.work_queue_recompute",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details=result.details | {"items": len(items)},
            actor=actor,
        )
        db.commit()
        return result

    def rollup_analytics(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        snapshot = operations_repository.analytics_summary(db, state, market_id)
        rollup = operations_repository.record_analytics_rollup(
            db,
            market_id=market_id,
            snapshot=snapshot,
        )
        details = snapshot.model_dump(mode="json") | {
            "rollup_id": rollup.id,
            "period_start": rollup.period_start.isoformat(),
            "period_end": rollup.period_end.isoformat(),
        }
        result = WorkerJobResult(
            name="analytics_rollup",
            market_id=market_id,
            processed=1,
            succeeded=1,
            details=details,
        )
        _audit_worker(
            db,
            state,
            action="worker.analytics_rollup",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details=details,
            actor=actor,
        )
        db.commit()
        return result

    def deliver_scheduled_reports(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        scheduled = report_delivery_service.schedule_due(
            db,
            market_id=market_id,
            actor=actor,
        )
        dispatched = report_delivery_service.dispatch_due(
            db,
            market_id=market_id,
            actor=actor,
        )
        details = {
            "queued_ids": scheduled.queued_ids,
            "skipped": scheduled.skipped,
            "processed_ids": dispatched.processed_ids,
            "sent_ids": dispatched.sent_ids,
            "retrying_ids": dispatched.retrying_ids,
            "blocked_ids": dispatched.blocked_ids,
            "dead_lettered_ids": dispatched.dead_lettered_ids,
        }
        result = WorkerJobResult(
            name="scheduled_report_delivery",
            market_id=market_id,
            processed=len(dispatched.processed_ids),
            succeeded=len(dispatched.sent_ids),
            failed=len(dispatched.retrying_ids),
            dead_lettered=len(dispatched.dead_lettered_ids),
            details=details,
        )
        if scheduled.queued_ids or dispatched.processed_ids:
            _audit_worker(
                db,
                state,
                action="worker.scheduled_report_delivery",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details=details,
                actor=actor,
            )
        db.commit()
        return result

    def deliver_campaigns(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        dispatched = campaign_service.dispatch_due(
            db,
            market_id=market_id,
            actor=actor,
        )
        details = {
            "processed_ids": dispatched.processed_ids,
            "sent_ids": dispatched.sent_ids,
            "retrying_ids": dispatched.retrying_ids,
            "dead_lettered_ids": dispatched.dead_lettered_ids,
            "suppressed_ids": dispatched.suppressed_ids,
        }
        result = WorkerJobResult(
            name="campaign_delivery",
            market_id=market_id,
            processed=len(dispatched.processed_ids),
            succeeded=len(dispatched.sent_ids),
            failed=len(dispatched.retrying_ids),
            dead_lettered=len(dispatched.dead_lettered_ids),
            details=details,
        )
        if dispatched.processed_ids:
            _audit_worker(
                db,
                state,
                action="worker.campaign_delivery",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details=details,
                actor=actor,
            )
            db.commit()
        return result

    def dispatch_alert_deliveries(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
        sender: AlertWebhookTransport | None = None,
    ) -> WorkerJobResult:
        details = alert_delivery_service.dispatch_due_webhooks(
            db,
            market_id=market_id,
            actor=actor,
            sender=sender,
        )
        result = WorkerJobResult(
            name="alert_delivery",
            market_id=market_id,
            processed=len(details["delivery_ids"]),
            succeeded=details["sent"],
            failed=details["failed"],
            details=details,
        )
        if (
            details["webhook_configured"]
            or result.processed
            or result.succeeded
            or result.failed
        ):
            _audit_worker(
                db,
                state,
                action="worker.alert_delivery",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details=details,
                actor=actor,
            )
            db.commit()
        return result

    def prune_audit_retention(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        policy = audit_retention_policy(
            db,
            market_id=market_id,
            retention_days=settings.audit_retention_days,
            export_max_rows=settings.audit_export_max_rows,
        )
        deleted_events = prune_audit_events(
            db,
            market_id=market_id,
            retention_days=settings.audit_retention_days,
            state=state,
        )
        details = {
            "retention_days": policy["retention_days"],
            "cutoff_at": policy["cutoff_at"].isoformat(),
            "prunable_events": policy["prunable_events"],
            "deleted_events": deleted_events,
        }
        result = WorkerJobResult(
            name="audit_retention",
            market_id=market_id,
            processed=deleted_events,
            succeeded=deleted_events,
            details=details,
        )
        if deleted_events:
            _audit_worker(
                db,
                state,
                action="worker.audit_retention",
                entity_type="audit",
                entity_id=market_id,
                market_id=market_id,
                details=details,
                actor=actor,
            )
            db.commit()
        return result

    def prune_attachment_retention(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        policy = ticket_repository.attachment_retention_policy(
            db,
            market_id=market_id,
            active_retention_days=settings.attachment_retention_days,
            deleted_retention_days=settings.attachment_deleted_retention_days,
            prune_limit=settings.attachment_retention_prune_limit,
        )
        attachment_ids, audit_event_id = ticket_repository.prune_attachment_retention(
            db,
            state,
            market_id=market_id,
            active_retention_days=settings.attachment_retention_days,
            deleted_retention_days=settings.attachment_deleted_retention_days,
            limit=settings.attachment_retention_prune_limit,
            actor=actor,
            storage_delete=attachment_storage.delete,
        )
        details = {
            "purgeable_attachments": policy.purgeable_attachments,
            "purged_attachments": len(attachment_ids),
            "attachment_ids": attachment_ids,
            "active_retention_days": policy.active_retention_days,
            "deleted_retention_days": policy.deleted_retention_days,
            "audit_event_id": audit_event_id,
        }
        return WorkerJobResult(
            name="attachment_retention",
            market_id=market_id,
            processed=len(attachment_ids),
            succeeded=len(attachment_ids),
            details=details,
        )

    def run_once(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_ids: list[str] | None = None,
        outbound_limit: int = 50,
        actor: str = WORKER_ACTOR,
    ) -> WorkerRunSummary:
        started_at = utc_now()
        jobs: list[WorkerJobResult] = []
        for market_id in self.market_ids(db, market_ids):
            jobs.append(
                self.sync_inbound_email(
                    db,
                    state,
                    market_id,
                    limit=settings.email_imap_fetch_limit,
                    actor=actor,
                )
            )
            jobs.append(
                self.process_due_outbound(
                    db,
                    state,
                    market_id,
                    limit=outbound_limit,
                    actor=actor,
                )
            )
            jobs.append(self.refresh_sla_states(db, state, market_id, actor=actor))
            jobs.append(self.auto_close_resolved(db, state, market_id, actor=actor))
            jobs.append(self.recompute_work_queue(db, state, market_id, actor=actor))
            jobs.append(self.rollup_analytics(db, state, market_id, actor=actor))
            jobs.append(self.deliver_scheduled_reports(db, state, market_id, actor=actor))
            jobs.append(self.deliver_campaigns(db, state, market_id, actor=actor))
            jobs.append(self.dispatch_alert_deliveries(db, state, market_id, actor=actor))
            jobs.append(self.prune_audit_retention(db, state, market_id, actor=actor))
            jobs.append(self.prune_attachment_retention(db, state, market_id, actor=actor))
        return WorkerRunSummary(
            started_at=started_at.isoformat(),
            finished_at=utc_now().isoformat(),
            jobs=jobs,
        )


worker_service = BackgroundWorkerService()
