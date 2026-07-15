from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, event, inspect, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CaseRecord,
    ChatConversationRecord,
    ChatMessageRecord,
    ConversationAssignmentRecord,
    ConversationTicketLinkRecord,
    HandoffRecord,
    OutboundMessageRecord,
    PersonalTaskRecord,
    MessageReceiptRecord,
    RealtimeEventRecord,
    TicketRecord,
    TicketTimeEntryRecord,
    TicketWatcherRecord,
    TimelineEventRecord,
)
from app.models.domain import utc_now

logger = logging.getLogger(__name__)

_EVENT_QUEUE_KEY = "omni_realtime_envelopes"
_SUPPRESS_EVENTS_KEY = "omni_suppress_realtime_events"
_redis_client: Redis | None = None


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _record_payload(record: object) -> dict[str, Any]:
    if isinstance(record, ChatConversationRecord):
        return {
            "public_id": record.public_id,
            "customer_id": record.customer_id,
            "case_id": record.case_id,
            "channel": record.channel,
            "status": record.status,
            "priority": record.priority,
            "topic_id": record.topic_id,
            "assignee_id": record.assignee_id,
            "assigned_group_id": record.assigned_group_id,
            "last_message_at": record.last_message_at,
        }
    if isinstance(record, ChatMessageRecord):
        return {
            "conversation_id": record.conversation_id,
            "sender_type": record.sender_type,
            "sender_id": record.sender_id,
            "sender_name": record.sender_name,
            "visibility": record.visibility,
            "body": record.body,
            "content": record.content,
            "delivery_state": record.delivery_state,
            "sent_at": record.sent_at,
        }
    if isinstance(record, ConversationAssignmentRecord):
        return {
            "conversation_id": record.conversation_id,
            "from_user_id": record.from_user_id,
            "to_user_id": record.to_user_id,
            "from_group_id": record.from_group_id,
            "to_group_id": record.to_group_id,
            "reason": record.reason,
            "routed_by": record.routed_by,
        }
    if isinstance(record, MessageReceiptRecord):
        return {
            "conversation_id": record.conversation_id,
            "message_id": record.message_id,
            "user_id": record.user_id,
            "receipt_type": record.receipt_type,
            "recorded_at": record.recorded_at,
        }
    if isinstance(record, ConversationTicketLinkRecord):
        return {
            "conversation_id": record.conversation_id,
            "ticket_id": record.ticket_id,
            "relationship": record.relationship,
        }
    if isinstance(record, TicketRecord):
        return {
            "public_id": record.public_id,
            "customer_id": record.customer_id,
            "case_id": record.case_id,
            "channel": record.channel,
            "status": record.status,
            "priority": record.priority,
            "assignee_id": record.assignee_id,
            "team": record.team,
        }
    if isinstance(record, CaseRecord):
        return {
            "public_id": record.public_id,
            "customer_id": record.customer_id,
            "status": record.status,
            "priority": record.priority,
            "title": record.title,
        }
    if isinstance(record, TimelineEventRecord):
        return {
            "ticket_id": record.ticket_id,
            "event_type": record.type,
            "channel": record.channel,
            "actor": record.actor,
            "body": record.body,
            "public": record.public,
            "metadata": record.event_metadata,
        }
    if isinstance(record, HandoffRecord):
        return {
            "ticket_id": record.ticket_id,
            "linked_ticket_id": record.linked_ticket_id,
            "from_team": record.from_team,
            "to_team": record.to_team,
            "status": record.status,
            "due_at": record.due_at,
        }
    if isinstance(record, OutboundMessageRecord):
        return {
            "ticket_id": record.ticket_id,
            "timeline_event_id": record.timeline_event_id,
            "provider": record.provider,
            "status": record.status,
            "attempts": record.attempts,
            "sent_at": record.sent_at,
            "last_error": record.last_error,
        }
    if isinstance(record, PersonalTaskRecord):
        return {
            "user_id": record.user_id,
            "label": record.label,
            "completed": record.completed,
            "position": record.position,
        }
    if isinstance(record, TicketWatcherRecord):
        return {"ticket_id": record.ticket_id, "user_id": record.user_id}
    if isinstance(record, TicketTimeEntryRecord):
        return {
            "ticket_id": record.ticket_id,
            "user_id": record.user_id,
            "minutes": record.minutes,
            "note": record.note,
            "billable": record.billable,
        }
    return {}


def _aggregate_type(record: object) -> str | None:
    if isinstance(record, ChatConversationRecord):
        return "conversation"
    if isinstance(record, ChatMessageRecord):
        return "conversation_message"
    if isinstance(record, ConversationAssignmentRecord):
        return "conversation_assignment"
    if isinstance(record, MessageReceiptRecord):
        return "message_receipt"
    if isinstance(record, ConversationTicketLinkRecord):
        return "conversation_ticket_link"
    if isinstance(record, TicketRecord):
        return "ticket"
    if isinstance(record, CaseRecord):
        return "case"
    if isinstance(record, TimelineEventRecord):
        return "message"
    if isinstance(record, HandoffRecord):
        return "handoff"
    if isinstance(record, OutboundMessageRecord):
        return "outbound_message"
    if isinstance(record, PersonalTaskRecord):
        return "personal_task"
    if isinstance(record, TicketWatcherRecord):
        return "ticket_watcher"
    if isinstance(record, TicketTimeEntryRecord):
        return "ticket_time_entry"
    return None


def event_envelope(record: RealtimeEventRecord) -> dict[str, Any]:
    return {
        "event_id": record.id,
        "type": record.type,
        "organization_id": record.organization_id,
        "market_id": record.market_id,
        "aggregate_type": record.aggregate_type,
        "aggregate_id": record.aggregate_id,
        "version": record.version,
        "timestamp": record.created_at.isoformat(),
        "payload": _json_value(record.payload),
    }


def _queue_record(
    session: Session,
    *,
    market_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    version: int | None = None,
) -> RealtimeEventRecord:
    now = utc_now()
    record = RealtimeEventRecord(
        id=f"event_{uuid4().hex}",
        organization_id="wakanow",
        market_id=market_id,
        type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        version=version or int(now.timestamp() * 1_000_000),
        payload=_json_value(payload),
        created_at=now,
    )
    session.add(record)
    session.info.setdefault(_EVENT_QUEUE_KEY, []).append(event_envelope(record))
    return record


class RealtimeEventRepository:
    def latest_cursor(self, db: Session, *, market_id: str) -> str | None:
        return db.scalar(
            select(RealtimeEventRecord.id)
            .where(RealtimeEventRecord.market_id == market_id)
            .order_by(
                RealtimeEventRecord.created_at.desc(),
                RealtimeEventRecord.id.desc(),
            )
            .limit(1)
        )

    def list_after(
        self,
        db: Session,
        *,
        market_id: str,
        cursor: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, settings.realtime_backlog_limit))
        query = select(RealtimeEventRecord).where(RealtimeEventRecord.market_id == market_id)
        if cursor:
            cursor_record = db.get(RealtimeEventRecord, cursor)
            if cursor_record is None or cursor_record.market_id != market_id:
                raise ValueError("Realtime cursor was not found for this market")
            query = query.where(
                or_(
                    RealtimeEventRecord.created_at > cursor_record.created_at,
                    and_(
                        RealtimeEventRecord.created_at == cursor_record.created_at,
                        RealtimeEventRecord.id > cursor_record.id,
                    ),
                )
            ).order_by(RealtimeEventRecord.created_at.asc(), RealtimeEventRecord.id.asc())
            records = db.scalars(query.limit(bounded_limit)).all()
        else:
            records = list(
                db.scalars(
                    query.order_by(
                        RealtimeEventRecord.created_at.desc(),
                        RealtimeEventRecord.id.desc(),
                    ).limit(bounded_limit)
                ).all()
            )
            records.reverse()
        return [event_envelope(record) for record in records]

    def record(
        self,
        db: Session,
        *,
        market_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        record = _queue_record(
            db,
            market_id=market_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
        )
        db.commit()
        return event_envelope(record)


realtime_event_repository = RealtimeEventRepository()


def redis_channel(market_id: str) -> str:
    return f"{settings.realtime_channel_prefix}:{market_id}"


def _publish_after_commit(envelope: dict[str, Any]) -> None:
    global _redis_client
    if not settings.redis_url:
        return
    try:
        if _redis_client is None:
            _redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
            )
        _redis_client.publish(
            redis_channel(str(envelope["market_id"])),
            json.dumps(envelope, separators=(",", ":")),
        )
    except RedisError as exc:
        # The event is already durable. Reconnecting clients recover through the DB cursor.
        logger.warning("Redis realtime publish failed after commit: %s", exc)


@event.listens_for(Session, "before_flush")
def capture_realtime_changes(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    if session.info.get(_SUPPRESS_EVENTS_KEY):
        return
    candidates = list(session.new) + list(session.dirty) + list(session.deleted)
    seen: set[tuple[str, str, str]] = set()
    for record in candidates:
        aggregate_type = _aggregate_type(record)
        if aggregate_type is None:
            continue
        aggregate_id = str(getattr(record, "id", ""))
        market_id = str(getattr(record, "market_id", ""))
        if not aggregate_id or not market_id:
            continue
        if record in session.deleted:
            operation = "deleted"
        elif record in session.new:
            operation = "created"
        elif inspect(record).modified and session.is_modified(record, include_collections=True):
            operation = "updated"
        else:
            continue
        key = (aggregate_type, aggregate_id, operation)
        if key in seen:
            continue
        seen.add(key)
        _queue_record(
            session,
            market_id=market_id,
            event_type=f"{aggregate_type}.{operation}",
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=_record_payload(record),
            version=getattr(record, "version", None),
        )


@event.listens_for(Session, "after_commit")
def publish_realtime_changes(session: Session) -> None:
    envelopes = session.info.pop(_EVENT_QUEUE_KEY, [])
    for envelope in envelopes:
        _publish_after_commit(envelope)


@event.listens_for(Session, "after_rollback")
def discard_realtime_changes(session: Session) -> None:
    session.info.pop(_EVENT_QUEUE_KEY, None)
