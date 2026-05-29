from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record, outbound_message_from_record
from app.db.models import (
    AuditEventRecord,
    ConnectorAccountRecord,
    ConnectorEventRecord,
    OutboundMessageRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.models.domain import (
    ChannelType,
    ConnectorDirection,
    OutboundMessage,
    OutboundMessageStatus,
    TimelineEventType,
    utc_now,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str,
    details: dict,
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


def _message_or_404(db: Session, message_id: str, market_id: str) -> OutboundMessageRecord:
    record = db.get(OutboundMessageRecord, message_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Outbound message not found")
    return record


def _account_for(
    db: Session,
    *,
    market_id: str,
    provider: str,
) -> ConnectorAccountRecord | None:
    return db.scalar(
        select(ConnectorAccountRecord).where(
            ConnectorAccountRecord.market_id == market_id,
            ConnectorAccountRecord.provider == provider,
        )
    )


def _local_adapter_ready(account: ConnectorAccountRecord | None) -> tuple[bool, str | None]:
    if account is None:
        return False, "No connector account exists for this market and channel."
    if not account.outbound_enabled:
        return False, "Outbound replies are not enabled for this connector account."
    if account.status not in {"connected", "mocked"}:
        return False, f"Connector status is {account.status}."
    if not account.secret_configured:
        return False, "Connector credentials are not configured."
    return True, None


def _mark_delivery_event(
    db: Session,
    state: InMemoryStore,
    *,
    ticket: TicketRecord,
    message: OutboundMessageRecord,
    status_value: OutboundMessageStatus,
    body: str,
    error: str | None = None,
) -> None:
    metadata = {
        "outbound_message_id": message.id,
        "connector_event_id": message.connector_event_id,
        "delivery_status": status_value.value,
    }
    if error:
        metadata["error"] = error
    event = TimelineEventRecord(
        id=_new_id("event"),
        market_id=ticket.market_id,
        ticket_id=ticket.id,
        type=TimelineEventType.connector_receipt.value,
        channel=message.provider,
        actor="Outbound queue",
        body=body,
        public=False,
        event_metadata=metadata,
    )
    db.add(event)
    db.flush()
    state.timeline.setdefault(ticket.id, [])


class OutboundRepository:
    def list_messages(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        ticket_id: str | None = None,
        status_filter: OutboundMessageStatus | None = None,
    ) -> list[OutboundMessage]:
        query = select(OutboundMessageRecord).where(OutboundMessageRecord.market_id == market_id)
        if ticket_id:
            query = query.where(OutboundMessageRecord.ticket_id == ticket_id)
        if status_filter:
            query = query.where(OutboundMessageRecord.status == status_filter.value)
        records = db.scalars(query.order_by(OutboundMessageRecord.created_at.desc())).all()
        messages = [outbound_message_from_record(record) for record in records]
        state.outbound_messages = {
            **{
                key: value
                for key, value in state.outbound_messages.items()
                if value.market_id != market_id
            },
            **{message.id: message for message in messages},
        }
        return messages

    def queue_reply(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        ticket: TicketRecord,
        timeline_event: TimelineEventRecord,
        provider: ChannelType,
        actor: str,
        body: str,
        idempotency_key: str | None = None,
    ) -> OutboundMessage:
        resolved_key = idempotency_key or f"{ticket.id}:{timeline_event.id}:{provider.value}"
        existing = db.scalar(
            select(OutboundMessageRecord).where(
                OutboundMessageRecord.market_id == ticket.market_id,
                OutboundMessageRecord.provider == provider.value,
                OutboundMessageRecord.idempotency_key == resolved_key,
            )
        )
        if existing is not None:
            return outbound_message_from_record(existing)

        connector_event = ConnectorEventRecord(
            id=_new_id("connector"),
            market_id=ticket.market_id,
            provider=provider.value,
            direction=ConnectorDirection.outbound.value,
            external_id=resolved_key,
            ticket_id=ticket.id,
            status=OutboundMessageStatus.queued.value,
            payload={"body": body, "actor": actor, "timeline_event_id": timeline_event.id},
        )
        db.add(connector_event)
        db.flush()

        message_record = OutboundMessageRecord(
            id=_new_id("outbound"),
            market_id=ticket.market_id,
            ticket_id=ticket.id,
            timeline_event_id=timeline_event.id,
            connector_event_id=connector_event.id,
            provider=provider.value,
            status=OutboundMessageStatus.queued.value,
            actor=actor,
            body=body,
            idempotency_key=resolved_key,
            attempts=0,
            max_attempts=3,
            payload={"source": "ticket_reply", "timeline_event_id": timeline_event.id},
        )
        db.add(message_record)
        db.flush()

        connector_event.payload = {
            **connector_event.payload,
            "outbound_message_id": message_record.id,
        }
        timeline_event.event_metadata = {
            **timeline_event.event_metadata,
            "outbound_message_id": message_record.id,
            "connector_event_id": connector_event.id,
            "delivery_status": OutboundMessageStatus.queued.value,
        }
        _audit(
            db,
            state,
            actor=actor,
            action="outbound.queue",
            entity_type="outbound_message",
            entity_id=message_record.id,
            market_id=ticket.market_id,
            details={"provider": provider.value, "ticket_id": ticket.id},
        )
        message = outbound_message_from_record(message_record)
        state.outbound_messages[message.id] = message
        return message

    def process_message(
        self,
        db: Session,
        state: InMemoryStore,
        message_id: str,
        market_id: str,
        *,
        actor: str = "outbound-queue",
    ) -> OutboundMessage:
        message = _message_or_404(db, message_id, market_id)
        if message.status == OutboundMessageStatus.sent.value:
            return outbound_message_from_record(message)

        ticket = db.get(TicketRecord, message.ticket_id)
        if ticket is None or ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")

        message.status = OutboundMessageStatus.sending.value
        message.attempts += 1
        message.last_error = None
        message.updated_at = utc_now()
        connector_event = (
            db.get(ConnectorEventRecord, message.connector_event_id)
            if message.connector_event_id
            else None
        )
        if connector_event is not None:
            connector_event.status = OutboundMessageStatus.sending.value

        account = _account_for(db, market_id=market_id, provider=message.provider)
        ready, error = _local_adapter_ready(account)
        if ready:
            message.status = OutboundMessageStatus.sent.value
            message.sent_at = utc_now()
            message.next_attempt_at = None
            if connector_event is not None:
                connector_event.status = OutboundMessageStatus.sent.value
                connector_event.payload = {
                    **connector_event.payload,
                    "sent_at": message.sent_at.isoformat(),
                    "adapter": "local-dev",
                }
            if message.timeline_event_id:
                timeline = db.get(TimelineEventRecord, message.timeline_event_id)
                if timeline is not None:
                    timeline.event_metadata = {
                        **timeline.event_metadata,
                        "delivery_status": OutboundMessageStatus.sent.value,
                    }
            _mark_delivery_event(
                db,
                state,
                ticket=ticket,
                message=message,
                status_value=OutboundMessageStatus.sent,
                body=f"Outbound {message.provider} message sent by local-dev adapter.",
            )
            _audit(
                db,
                state,
                actor=actor,
                action="outbound.sent",
                entity_type="outbound_message",
                entity_id=message.id,
                market_id=market_id,
                details={"provider": message.provider, "attempts": message.attempts},
            )
        else:
            message.last_error = error
            if message.attempts >= message.max_attempts:
                message.status = OutboundMessageStatus.dead_lettered.value
                message.next_attempt_at = None
            else:
                message.status = OutboundMessageStatus.failed.value
                message.next_attempt_at = utc_now() + timedelta(minutes=5 * message.attempts)
            if connector_event is not None:
                connector_event.status = message.status
                connector_event.payload = {
                    **connector_event.payload,
                    "last_error": error,
                    "attempts": message.attempts,
                }
            if account is not None:
                account.failure_count += 1
                account.last_error = error
            if message.timeline_event_id:
                timeline = db.get(TimelineEventRecord, message.timeline_event_id)
                if timeline is not None:
                    timeline.event_metadata = {
                        **timeline.event_metadata,
                        "delivery_status": message.status,
                        "delivery_error": error,
                    }
            _mark_delivery_event(
                db,
                state,
                ticket=ticket,
                message=message,
                status_value=OutboundMessageStatus(message.status),
                body=f"Outbound {message.provider} delivery failed: {error}",
                error=error,
            )
            _audit(
                db,
                state,
                actor=actor,
                action=(
                    "outbound.dead_lettered"
                    if message.status == OutboundMessageStatus.dead_lettered.value
                    else "outbound.failed"
                ),
                entity_type="outbound_message",
                entity_id=message.id,
                market_id=market_id,
                details={"provider": message.provider, "attempts": message.attempts, "error": error},
            )

        message.updated_at = utc_now()
        db.flush()
        domain_message = outbound_message_from_record(message)
        state.outbound_messages[domain_message.id] = domain_message
        return domain_message

    def retry_message(
        self,
        db: Session,
        state: InMemoryStore,
        message_id: str,
        market_id: str,
        *,
        actor: str,
        reason: str,
    ) -> OutboundMessage:
        message = _message_or_404(db, message_id, market_id)
        if message.status != OutboundMessageStatus.sent.value:
            message.status = OutboundMessageStatus.retrying.value
            message.next_attempt_at = utc_now()
            message.payload = {**message.payload, "retry_reason": reason}
            _audit(
                db,
                state,
                actor=actor,
                action="outbound.retry",
                entity_type="outbound_message",
                entity_id=message.id,
                market_id=market_id,
                details={"reason": reason, "attempts": message.attempts},
            )
            db.flush()
        return self.process_message(db, state, message.id, market_id, actor=actor)


outbound_repository = OutboundRepository()
