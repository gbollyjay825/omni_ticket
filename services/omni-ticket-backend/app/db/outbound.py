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
    CustomerRecord,
    MarketRecord,
    OutboundMessageRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.email_settings import email_provider_settings_repository
from app.db.integration_credentials import integration_credential_settings_repository
from app.models.domain import (
    ChannelType,
    ConnectorDirection,
    OutboundMessage,
    OutboundMessageStatus,
    TimelineEventType,
    utc_now,
)
from app.services.outbound_adapters import OutboundSendContext, outbound_adapter_router


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


def _find_message_by_receipt(
    db: Session,
    *,
    market_id: str,
    provider: ChannelType,
    outbound_message_id: str | None = None,
    provider_message_id: str | None = None,
    idempotency_key: str | None = None,
) -> OutboundMessageRecord | None:
    if outbound_message_id:
        record = db.get(OutboundMessageRecord, outbound_message_id)
        if record is not None and record.market_id == market_id and record.provider == provider.value:
            return record
    if idempotency_key:
        record = db.scalar(
            select(OutboundMessageRecord).where(
                OutboundMessageRecord.market_id == market_id,
                OutboundMessageRecord.provider == provider.value,
                OutboundMessageRecord.idempotency_key == idempotency_key,
            )
        )
        if record is not None:
            return record
    if provider_message_id:
        records = db.scalars(
            select(OutboundMessageRecord).where(
                OutboundMessageRecord.market_id == market_id,
                OutboundMessageRecord.provider == provider.value,
            )
        ).all()
        for record in records:
            payload = record.payload or {}
            if str(payload.get("external_id") or "") == provider_message_id:
                return record
            provider_payload = payload.get("provider_payload") or {}
            if not isinstance(provider_payload, dict):
                continue
            if str(provider_payload.get("external_id") or "") == provider_message_id:
                return record
            provider_response = provider_payload.get("provider_response") or {}
            if not isinstance(provider_response, dict):
                continue
            for key in ("message_id", "messageId", "id", "sid", "reference", "provider_id"):
                if str(provider_response.get(key) or "") == provider_message_id:
                    return record
    return None


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

    def queue_handoff_forward(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        ticket: TicketRecord,
        timeline_event: TimelineEventRecord,
        handoff_id: str,
        to_team: str,
        to_email: str,
        actor: str,
        subject: str,
        body: str,
        linked_ticket_id: str | None = None,
        linked_ticket_public_id: str | None = None,
    ) -> OutboundMessage:
        resolved_key = f"{ticket.id}:{handoff_id}:handoff-forward:email"
        existing = db.scalar(
            select(OutboundMessageRecord).where(
                OutboundMessageRecord.market_id == ticket.market_id,
                OutboundMessageRecord.provider == ChannelType.email.value,
                OutboundMessageRecord.idempotency_key == resolved_key,
            )
        )
        if existing is not None:
            return outbound_message_from_record(existing)

        payload = {
            "source": "handoff_forward",
            "timeline_event_id": timeline_event.id,
            "handoff_id": handoff_id,
            "to_team": to_team,
            "to_email": to_email,
            "subject": subject,
            "source_ticket_id": ticket.id,
            "source_ticket_public_id": ticket.public_id,
            "linked_ticket_id": linked_ticket_id,
            "linked_ticket_public_id": linked_ticket_public_id,
            "reply_target": "linked_ticket" if linked_ticket_id else "source_ticket",
            "reply_target_ticket_id": linked_ticket_id or ticket.id,
        }
        connector_event = ConnectorEventRecord(
            id=_new_id("connector"),
            market_id=ticket.market_id,
            provider=ChannelType.email.value,
            direction=ConnectorDirection.outbound.value,
            external_id=resolved_key,
            ticket_id=ticket.id,
            status=OutboundMessageStatus.queued.value,
            payload={**payload, "body": body, "actor": actor},
        )
        db.add(connector_event)
        db.flush()

        message_record = OutboundMessageRecord(
            id=_new_id("outbound"),
            market_id=ticket.market_id,
            ticket_id=ticket.id,
            timeline_event_id=timeline_event.id,
            connector_event_id=connector_event.id,
            provider=ChannelType.email.value,
            status=OutboundMessageStatus.queued.value,
            actor=actor,
            body=body,
            idempotency_key=resolved_key,
            attempts=0,
            max_attempts=3,
            payload=payload,
        )
        db.add(message_record)
        db.flush()

        connector_event.payload = {
            **connector_event.payload,
            "outbound_message_id": message_record.id,
        }
        timeline_event.event_metadata = {
            **timeline_event.event_metadata,
            "handoff_forward_status": OutboundMessageStatus.queued.value,
            "handoff_forward_to": to_email,
            "handoff_forward_outbound_message_id": message_record.id,
            "handoff_forward_connector_event_id": connector_event.id,
            "handoff_forward_reply_target_ticket_id": linked_ticket_id or ticket.id,
            "handoff_forward_reply_target": payload["reply_target"],
        }
        _audit(
            db,
            state,
            actor=actor,
            action="handoff.forward.queue",
            entity_type="handoff",
            entity_id=handoff_id,
            market_id=ticket.market_id,
            details={"ticket_id": ticket.id, "to_team": to_team, "to_email": to_email},
        )
        message = outbound_message_from_record(message_record)
        state.outbound_messages[message.id] = message
        return message

    def queue_email(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        ticket: TicketRecord,
        timeline_event: TimelineEventRecord,
        actor: str,
        to_email: str,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
        payload_extra: dict | None = None,
        audit_action: str = "outbound.email.queue",
    ) -> OutboundMessage:
        existing = db.scalar(
            select(OutboundMessageRecord).where(
                OutboundMessageRecord.market_id == ticket.market_id,
                OutboundMessageRecord.provider == ChannelType.email.value,
                OutboundMessageRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return outbound_message_from_record(existing)

        payload = {
            "source": source,
            "timeline_event_id": timeline_event.id,
            "to_email": to_email,
            "subject": subject,
            **(payload_extra or {}),
        }
        connector_event = ConnectorEventRecord(
            id=_new_id("connector"),
            market_id=ticket.market_id,
            provider=ChannelType.email.value,
            direction=ConnectorDirection.outbound.value,
            external_id=idempotency_key,
            ticket_id=ticket.id,
            status=OutboundMessageStatus.queued.value,
            payload={**payload, "body": body, "actor": actor},
        )
        db.add(connector_event)
        db.flush()

        message_record = OutboundMessageRecord(
            id=_new_id("outbound"),
            market_id=ticket.market_id,
            ticket_id=ticket.id,
            timeline_event_id=timeline_event.id,
            connector_event_id=connector_event.id,
            provider=ChannelType.email.value,
            status=OutboundMessageStatus.queued.value,
            actor=actor,
            body=body,
            idempotency_key=idempotency_key,
            attempts=0,
            max_attempts=3,
            payload=payload,
        )
        db.add(message_record)
        db.flush()

        connector_event.payload = {
            **connector_event.payload,
            "outbound_message_id": message_record.id,
        }
        timeline_event.event_metadata = {
            **timeline_event.event_metadata,
            "delivery_status": OutboundMessageStatus.queued.value,
            "outbound_message_id": message_record.id,
            "connector_event_id": connector_event.id,
            "to_email": to_email,
            "source": source,
        }
        _audit(
            db,
            state,
            actor=actor,
            action=audit_action,
            entity_type="outbound_message",
            entity_id=message_record.id,
            market_id=ticket.market_id,
            details={
                "ticket_id": ticket.id,
                "provider": ChannelType.email.value,
                "to_email": to_email,
                "source": source,
            },
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
        send_result = None
        if ready and account is not None:
            send_result = outbound_adapter_router.send(
                OutboundSendContext(
                    account=account,
                    ticket=ticket,
                    message=message,
                    customer=db.get(CustomerRecord, ticket.customer_id),
                    market=db.get(MarketRecord, market_id),
                    email_settings=email_provider_settings_repository.runtime_settings(
                        db,
                        market_id=market_id,
                    ),
                    integration_credentials=integration_credential_settings_repository.runtime_credentials(
                        db,
                        market_id=market_id,
                    ),
                )
            )
            ready = send_result.succeeded
            error = send_result.error
        if ready:
            message.status = OutboundMessageStatus.sent.value
            message.sent_at = utc_now()
            message.next_attempt_at = None
            message.payload = {
                **message.payload,
                "adapter": send_result.adapter if send_result else "local-dev",
                "external_id": send_result.external_id if send_result else None,
                "provider_payload": send_result.payload if send_result else {},
            }
            if connector_event is not None:
                connector_event.status = OutboundMessageStatus.sent.value
                connector_event.payload = {
                    **connector_event.payload,
                    "sent_at": message.sent_at.isoformat(),
                    "adapter": send_result.adapter if send_result else "local-dev",
                    "external_id": send_result.external_id if send_result else None,
                    "provider_payload": send_result.payload if send_result else {},
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
                body=(
                    f"Outbound {message.provider} message sent by "
                    f"{send_result.adapter if send_result else 'local-dev'} adapter."
                ),
            )
            _audit(
                db,
                state,
                actor=actor,
                action="outbound.sent",
                entity_type="outbound_message",
                entity_id=message.id,
                market_id=market_id,
                details={
                    "provider": message.provider,
                    "attempts": message.attempts,
                    "adapter": send_result.adapter if send_result else "local-dev",
                    "external_id": send_result.external_id if send_result else None,
                },
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
                    "adapter": send_result.adapter if send_result else None,
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
                details={
                    "provider": message.provider,
                    "attempts": message.attempts,
                    "error": error,
                    "adapter": send_result.adapter if send_result else None,
                },
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

    def record_delivery_receipt(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        provider: ChannelType,
        status_label: str,
        provider_message_id: str | None = None,
        outbound_message_id: str | None = None,
        idempotency_key: str | None = None,
        delivery_id: str | None = None,
        raw_payload: dict | None = None,
        actor: str = "provider-webhook",
    ) -> OutboundMessage:
        message = _find_message_by_receipt(
            db,
            market_id=market_id,
            provider=provider,
            outbound_message_id=outbound_message_id,
            provider_message_id=provider_message_id,
            idempotency_key=idempotency_key,
        )
        if message is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Outbound message not found for delivery receipt",
            )
        ticket = db.get(TicketRecord, message.ticket_id)
        if ticket is None or ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")

        normalized_status = status_label.strip().lower() or "unknown"
        failure_statuses = {"failed", "undelivered", "rejected", "error", "blocked", "expired"}
        success_statuses = {"delivered", "sent", "accepted", "queued", "success", "ok"}
        receipt_received_at = utc_now()
        receipt_payload = {
            "status": status_label,
            "normalized_status": normalized_status,
            "provider_message_id": provider_message_id,
            "delivery_id": delivery_id,
            "received_at": receipt_received_at.isoformat(),
            "payload": raw_payload or {},
        }
        message.payload = {**(message.payload or {}), "delivery_receipt": receipt_payload}

        if normalized_status in failure_statuses:
            message.status = OutboundMessageStatus.dead_lettered.value
            message.last_error = f"Provider delivery receipt reported {status_label}."
            message.next_attempt_at = None
        elif normalized_status in success_statuses:
            message.status = OutboundMessageStatus.sent.value
            message.sent_at = message.sent_at or receipt_received_at
            message.last_error = None
            message.next_attempt_at = None

        connector_event = (
            db.get(ConnectorEventRecord, message.connector_event_id)
            if message.connector_event_id
            else None
        )
        if connector_event is not None:
            connector_event.status = normalized_status
            connector_event.payload = {
                **(connector_event.payload or {}),
                "delivery_receipt": receipt_payload,
            }

        receipt_external_id = (
            f"receipt:{delivery_id}"
            if delivery_id
            else f"receipt:{provider_message_id or message.id}:{normalized_status}"
        )
        receipt_event = ConnectorEventRecord(
            id=_new_id("connector"),
            market_id=market_id,
            provider=provider.value,
            direction=ConnectorDirection.inbound.value,
            external_id=receipt_external_id,
            ticket_id=message.ticket_id,
            status="delivery-receipt",
            payload={
                "outbound_message_id": message.id,
                "provider_message_id": provider_message_id,
                "receipt_status": status_label,
                "metadata": {
                    "webhook_delivery_id": delivery_id,
                    "source": "provider_delivery_receipt",
                },
                "payload": raw_payload or {},
            },
        )
        db.add(receipt_event)
        db.flush()

        if message.timeline_event_id:
            timeline = db.get(TimelineEventRecord, message.timeline_event_id)
            if timeline is not None:
                timeline.event_metadata = {
                    **(timeline.event_metadata or {}),
                    "delivery_status": message.status,
                    "delivery_receipt_status": normalized_status,
                }
        _mark_delivery_event(
            db,
            state,
            ticket=ticket,
            message=message,
            status_value=OutboundMessageStatus(message.status),
            body=f"{provider.value.upper()} delivery receipt reported {status_label}.",
            error=message.last_error,
        )
        _audit(
            db,
            state,
            actor=actor,
            action="outbound.delivery_receipt",
            entity_type="outbound_message",
            entity_id=message.id,
            market_id=market_id,
            details={
                "provider": provider.value,
                "status": status_label,
                "normalized_status": normalized_status,
                "provider_message_id": provider_message_id,
                "delivery_id": delivery_id,
                "connector_event_id": receipt_event.id,
            },
        )
        message.updated_at = utc_now()
        db.flush()
        domain_message = outbound_message_from_record(message)
        state.outbound_messages[domain_message.id] = domain_message
        return domain_message


outbound_repository = OutboundRepository()
