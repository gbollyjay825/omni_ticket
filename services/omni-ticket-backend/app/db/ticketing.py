from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.attachment_tokens import (
    create_attachment_download_token,
    parse_attachment_download_token,
)
from app.core.config import settings
from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    attachment_from_record,
    ai_decision_from_record,
    automation_rule_from_record,
    audit_event_from_record,
    case_from_record,
    company_from_record,
    connector_event_from_record,
    csat_feedback_from_record,
    customer_from_record,
    handoff_from_record,
    outbound_message_from_record,
    ticket_from_record,
    timeline_event_from_record,
)
from app.db.models import (
    AgentRecord,
    AttachmentRecord,
    AiDecisionRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    CaseRecord,
    CompanyRecord,
    ConnectorEventRecord,
    CsatFeedbackRecord,
    CustomerRecord,
    HandoffRecord,
    OutboundMessageRecord,
    SlaPolicyRecord,
    SupportGroupRecord,
    TicketFieldRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.outbound import outbound_repository
from app.models.domain import (
    AppendEventRequest,
    Attachment,
    AttachmentLifecycleStatus,
    AttachmentRetentionPolicy,
    AttachmentScanStatus,
    Case,
    CaseStatus,
    ChannelType,
    ConnectorEvent,
    ConnectorDirection,
    ConnectorInboundRequest,
    CreateCaseRequest,
    CreateCsatFeedbackRequest,
    CreateHandoffRequest,
    CreateAttachmentRequest,
    CreateTicketRequest,
    CsatFeedback,
    DuplicateTicketSuggestion,
    Handoff,
    HandoffStatus,
    MergeTicketsRequest,
    MergeTicketsResponse,
    Priority,
    ReplyRequest,
    SlaState,
    Ticket,
    TicketStatus,
    TicketTask,
    TimelineEvent,
    TimelineEventType,
    TicketFieldType,
    UpdateCaseRequest,
    UpdateHandoffRequest,
    UpdateTicketRequest,
    WorkQueueOverrideRequest,
    default_sla,
    utc_now,
)
from app.services.attachments import scan_attachment_metadata
from app.services.ai import automation_service
from app.services.sla import sla_service


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _next_public_ticket_id(db: Session) -> str:
    public_ids = db.scalars(select(TicketRecord.public_id)).all()
    numbers = [
        int(public_id.split("-")[-1])
        for public_id in public_ids
        if public_id.startswith("OMNI-") and public_id.split("-")[-1].isdigit()
    ]
    return f"OMNI-{max(numbers, default=1000) + 1}"


def _ticket_record_or_404(db: Session, ticket_id: str, market_id: str) -> TicketRecord:
    record = db.get(TicketRecord, ticket_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return record


def _customer_record_or_404(db: Session, customer_id: str, market_id: str) -> CustomerRecord:
    record = db.get(CustomerRecord, customer_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return record


def _ticket_payload(ticket: Ticket) -> dict:
    payload = ticket.model_dump(mode="json")
    payload["created_at"] = ticket.created_at
    payload["updated_at"] = ticket.updated_at
    return payload


def _task(label: str) -> TicketTask:
    return TicketTask(id=_new_id("task"), label=label, complete=False)


def _search_text(*parts: object) -> str:
    return " ".join(str(part).lower() for part in parts if part)


def _ticket_search_text(ticket: TicketRecord) -> str:
    return _search_text(
        ticket.subject,
        ticket.description,
        ticket.channel,
        ticket.priority,
        ticket.sentiment,
        " ".join(ticket.tags or []),
    )


_TOKEN_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "from",
    "have",
    "into",
    "need",
    "needs",
    "only",
    "that",
    "this",
    "ticket",
    "with",
    "your",
}

_REFERENCE_KEY_PARTS = (
    "booking",
    "confirmation",
    "invoice",
    "order",
    "payment",
    "pnr",
    "reference",
    "reservation",
    "ticket",
    "transaction",
)


def _word_tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", str(value).lower())
        if token not in _TOKEN_STOP_WORDS
    }


def _flatten_custom_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_custom_values(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for item in value:
            flattened.extend(_flatten_custom_values(item))
        return flattened
    text = str(value).strip()
    return [text] if text else []


def _reference_values(ticket: TicketRecord) -> set[str]:
    references: set[str] = set()
    for key, value in (ticket.custom_fields or {}).items():
        key_text = str(key).lower()
        if not any(part in key_text for part in _REFERENCE_KEY_PARTS):
            continue
        for item in _flatten_custom_values(value):
            normalized = re.sub(r"\s+", "", item).lower()
            if len(normalized) >= 4:
                references.add(normalized)
    return references


def _ticket_duplicate_tokens(ticket: TicketRecord) -> set[str]:
    custom_text = " ".join(_flatten_custom_values(ticket.custom_fields or {}))
    return _word_tokens(
        " ".join(
            [
                ticket.subject,
                ticket.description,
                " ".join(ticket.tags or []),
                custom_text,
            ]
        )
    )


def _customer_contact_values(customer: CustomerRecord | None) -> set[str]:
    if customer is None:
        return set()
    values = {customer.email.lower()}
    for point in customer.contact_points or []:
        value = str(point.get("value", "")).strip().lower()
        if value:
            values.add(value)
    return values


def _is_linked_handoff_child(ticket: TicketRecord) -> bool:
    custom_fields = ticket.custom_fields or {}
    return custom_fields.get("linked_ticket_type") == "handoff_child"


def _is_merged_source(ticket: TicketRecord) -> bool:
    return bool((ticket.custom_fields or {}).get("merged_into_ticket_id"))


def _short_public_id_tag(public_id: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", public_id.lower()).strip("-")


def _ticket_merge_context(db: Session, source_ticket: TicketRecord) -> str:
    source_customer = db.get(CustomerRecord, source_ticket.customer_id)
    timeline = db.scalars(
        select(TimelineEventRecord)
        .where(
            TimelineEventRecord.market_id == source_ticket.market_id,
            TimelineEventRecord.ticket_id == source_ticket.id,
        )
        .order_by(TimelineEventRecord.created_at.asc())
    ).all()
    timeline_lines = [
        (
            f"- [{event.created_at.isoformat()}] {event.actor} "
            f"({event.type}/{event.channel}, {'public' if event.public else 'internal'}): "
            f"{event.body}"
        )
        for event in timeline[-10:]
    ]
    attachments = db.scalars(
        select(AttachmentRecord).where(
            AttachmentRecord.market_id == source_ticket.market_id,
            AttachmentRecord.ticket_id == source_ticket.id,
        )
    ).all()
    attachment_lines = [
        f"- {attachment.filename} ({attachment.content_type}, {attachment.scan_status}, {attachment.lifecycle_status})"
        for attachment in attachments
    ]
    return "\n".join(
        [
            f"Merged duplicate ticket {source_ticket.public_id}.",
            "",
            "Source ticket",
            f"- Subject: {source_ticket.subject}",
            f"- Status: {source_ticket.status}",
            f"- Priority: {source_ticket.priority}",
            f"- Channel: {source_ticket.channel}",
            f"- Customer: {source_customer.name if source_customer else 'Unknown'}",
            f"- Customer email: {source_customer.email if source_customer else 'Unknown'}",
            "",
            "Recent source comments and notes",
            *(timeline_lines or ["- No timeline entries."]),
            "",
            "Source attachments",
            *(attachment_lines or ["- None"]),
        ]
    )


_MESSAGE_ID_RE = re.compile(r"<[^>]+>")
_PUBLIC_ID_RE = re.compile(r"\bOMNI-\d+\b", re.IGNORECASE)


def _metadata_values(metadata: dict, *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = metadata.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
            continue
        value = str(raw).strip()
        if value:
            values.append(value)
    return values


def _email_message_ids(metadata: dict) -> list[str]:
    values = _metadata_values(metadata, "in_reply_to", "references")
    message_ids: list[str] = []
    for value in values:
        matches = _MESSAGE_ID_RE.findall(value)
        if matches:
            message_ids.extend(matches)
        elif value.startswith("<") and value.endswith(">"):
            message_ids.append(value)
    return list(dict.fromkeys(message_ids))


def _ticket_by_id(db: Session, market_id: str, ticket_id: str | None) -> TicketRecord | None:
    if not ticket_id:
        return None
    ticket = db.get(TicketRecord, ticket_id)
    if ticket is None or ticket.market_id != market_id:
        return None
    return ticket


def _ticket_by_public_id(db: Session, market_id: str, public_id: str) -> TicketRecord | None:
    return db.scalar(
        select(TicketRecord).where(
            TicketRecord.market_id == market_id,
            func.upper(TicketRecord.public_id) == public_id.upper(),
        )
    )


def _outbound_thread_candidates(payload: dict) -> set[str]:
    candidates = {
        str(payload.get("external_id") or ""),
        str(payload.get("message_id") or ""),
    }
    provider_payload = payload.get("provider_payload") or {}
    if isinstance(provider_payload, dict):
        candidates.update({
            str(provider_payload.get("external_id") or ""),
            str(provider_payload.get("message_id") or ""),
        })
    return {candidate for candidate in candidates if candidate}


def _thread_target_from_outbound_reference(
    db: Session,
    *,
    market_id: str,
    message_ids: list[str],
) -> tuple[TicketRecord | None, dict]:
    if not message_ids:
        return None, {}
    records = db.scalars(
        select(OutboundMessageRecord).where(
            OutboundMessageRecord.market_id == market_id,
            OutboundMessageRecord.provider == ChannelType.email.value,
        )
    ).all()
    for message in records:
        payload = message.payload or {}
        if not (_outbound_thread_candidates(payload) & set(message_ids)):
            continue
        target_id = (
            str(payload.get("reply_target_ticket_id") or "")
            or str(payload.get("linked_ticket_id") or "")
            or message.ticket_id
        )
        target = _ticket_by_id(db, market_id, target_id)
        if target is None:
            continue
        return target, {
            "thread_match": "outbound_email_reference",
            "outbound_message_id": message.id,
            "outbound_message_external_id": payload.get("external_id"),
            "source": payload.get("source"),
            "handoff_id": payload.get("handoff_id"),
            "source_ticket_id": payload.get("source_ticket_id") or message.ticket_id,
            "linked_ticket_id": payload.get("linked_ticket_id"),
            "reply_target": payload.get("reply_target"),
        }
    return None, {}


def _thread_target_from_request(
    db: Session,
    *,
    market_id: str,
    request: ConnectorInboundRequest,
) -> tuple[TicketRecord | None, dict]:
    metadata = request.metadata or {}
    for key in (
        "omni_linked_ticket_id",
        "omni_reply_target_ticket_id",
        "omni_ticket_id",
        "omni_source_ticket_id",
    ):
        target = _ticket_by_id(db, market_id, str(metadata.get(key) or ""))
        if target is not None:
            return target, {
                "thread_match": key,
                "source_ticket_id": metadata.get("omni_source_ticket_id"),
            }
    target, match = _thread_target_from_outbound_reference(
        db,
        market_id=market_id,
        message_ids=_email_message_ids(metadata),
    )
    if target is not None:
        return target, match
    for public_id in _PUBLIC_ID_RE.findall(request.subject):
        target = _ticket_by_public_id(db, market_id, public_id)
        if target is not None:
            return target, {"thread_match": "subject_public_id", "public_id": target.public_id}
    return None, {}


_TICKET_SORT_COLUMNS = {
    "updated_at": TicketRecord.updated_at,
    "created_at": TicketRecord.created_at,
    "public_id": TicketRecord.public_id,
    "subject": TicketRecord.subject,
    "status": TicketRecord.status,
    "priority": TicketRecord.priority,
    "channel": TicketRecord.channel,
}


def _ticket_list_query(
    *,
    market_id: str,
    status_filter: str | None = None,
    channel: ChannelType | None = None,
    priority: Priority | None = None,
    customer_id: str | None = None,
    assignee_id: str | None = None,
    team: str | None = None,
    q: str | None = None,
):
    query = select(TicketRecord).where(TicketRecord.market_id == market_id)
    if status_filter:
        query = query.where(TicketRecord.status == status_filter)
    if channel:
        query = query.where(TicketRecord.channel == channel.value)
    if priority:
        query = query.where(TicketRecord.priority == priority.value)
    if customer_id:
        query = query.where(TicketRecord.customer_id == customer_id)
    if assignee_id:
        query = query.where(TicketRecord.assignee_id == assignee_id)
    if team:
        query = query.where(func.lower(TicketRecord.team) == team.strip().lower())
    search = q.strip().lower() if q else ""
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                func.lower(TicketRecord.public_id).like(term),
                func.lower(TicketRecord.subject).like(term),
                func.lower(TicketRecord.description).like(term),
                func.lower(TicketRecord.channel).like(term),
                func.lower(TicketRecord.status).like(term),
                func.lower(TicketRecord.priority).like(term),
                func.lower(TicketRecord.sentiment).like(term),
                func.lower(TicketRecord.team).like(term),
                func.lower(TicketRecord.ai_summary).like(term),
                func.lower(TicketRecord.recommended_action).like(term),
            )
        )
    return query


def _trigger_channels(trigger: str) -> set[str]:
    return {channel.value for channel in ChannelType if channel.value in trigger}


def _trigger_sentiments(trigger: str) -> set[str]:
    return {"positive", "neutral", "frustrated", "angry"} & set(trigger.replace(",", " ").split())


def _retention_cutoff(days: int):
    return utc_now() - timedelta(days=days)


def _ticket_field_applies(record: TicketFieldRecord, channel: str) -> bool:
    return record.active and (not record.channels or channel in record.channels)


def _sla_state_from_policy(policy: SlaPolicyRecord, base: datetime) -> SlaState:
    return SlaState(
        first_response_due_at=base + timedelta(minutes=policy.first_response_minutes),
        resolution_due_at=base + timedelta(minutes=policy.resolution_minutes),
    )


def _active_sla_policy(
    db: Session,
    market_id: str,
    priority: Priority,
    channel: ChannelType,
) -> SlaPolicyRecord | None:
    records = db.scalars(
        select(SlaPolicyRecord).where(
            SlaPolicyRecord.market_id == market_id,
            SlaPolicyRecord.active.is_(True),
            SlaPolicyRecord.priority == priority.value,
        )
    ).all()
    candidates = [
        record
        for record in records
        if not record.channels or channel.value in record.channels
    ]
    candidates.sort(
        key=lambda record: (
            channel.value not in (record.channels or []),
            record.position,
            record.name.lower(),
        )
    )
    return candidates[0] if candidates else None


def _append_threaded_connector_reply(
    db: Session,
    state: InMemoryStore,
    *,
    target_ticket: TicketRecord,
    request: ConnectorInboundRequest,
    match: dict,
    market_id: str,
) -> dict:
    connector_record = ConnectorEventRecord(
        id=_new_id("connector"),
        market_id=market_id,
        provider=request.provider.value,
        direction=ConnectorDirection.inbound.value,
        external_id=request.external_id,
        ticket_id=target_ticket.id,
        status="thread-appended",
        payload={
            **request.model_dump(mode="json"),
            "threaded": True,
            "thread_match": match,
        },
    )
    db.add(connector_record)
    db.flush()
    connector_event = connector_event_from_record(connector_record)
    state.connector_events[connector_event.id] = connector_event

    is_internal_thread = (
        target_ticket.channel == ChannelType.internal.value
        or bool(match.get("handoff_id"))
        or match.get("source") == "handoff_forward"
    )
    previous_status = target_ticket.status
    event = _add_timeline_record(
        db,
        state,
        target_ticket,
        event_type=TimelineEventType.inbound,
        channel=request.provider,
        actor=request.customer_name or str(request.customer_email),
        body=request.body,
        public=not is_internal_thread,
        metadata={
            "connector_event_id": connector_event.id,
            "external_id": request.external_id,
            "threaded": True,
            "thread_match": match,
            "from": str(request.customer_email),
        },
    )
    target_ticket.updated_at = utc_now()
    target_tags = set(target_ticket.tags or [])
    target_tags.add("thread-reply")
    if is_internal_thread:
        target_tags.add("team-replied")
    else:
        target_tags.add("customer-replied")
    target_ticket.tags = sorted(target_tags)
    if previous_status != TicketStatus.open.value:
        target_ticket.status = TicketStatus.open.value
        _add_timeline_record(
            db,
            state,
            target_ticket,
            event_type=TimelineEventType.status_change,
            channel=ChannelType.internal,
            actor="email-threading",
            body=(
                f"Threaded {request.provider.value} reply moved ticket "
                f"from {previous_status} to open."
            ),
            public=False,
            metadata={
                "previous_status": previous_status,
                "new_status": TicketStatus.open.value,
                "connector_event_id": connector_event.id,
                "external_id": request.external_id,
                "provider": request.provider.value,
                "threaded": True,
                "thread_match": match,
            },
        )

    source_ticket_id = str(match.get("source_ticket_id") or "")
    if source_ticket_id and source_ticket_id != target_ticket.id:
        source_ticket = _ticket_by_id(db, market_id, source_ticket_id)
        if source_ticket is not None:
            _add_timeline_record(
                db,
                state,
                source_ticket,
                event_type=TimelineEventType.internal_note,
                channel=ChannelType.internal,
                actor="email-threading",
                body=(
                    f"Team reply received on linked ticket {target_ticket.public_id} "
                    f"from {request.customer_email}."
                ),
                public=False,
                metadata={
                    "connector_event_id": connector_event.id,
                    "linked_ticket_id": target_ticket.id,
                    "linked_ticket_public_id": target_ticket.public_id,
                    "source": "handoff_forward_reply",
                    "external_id": request.external_id,
                },
            )
            source_ticket.updated_at = utc_now()

    _audit(
        db,
        state,
        actor="connector-service",
        action="connector.thread_append",
        entity_type="connector_event",
        entity_id=connector_event.id,
        market_id=market_id,
        details={
            "provider": request.provider.value,
            "ticket_id": target_ticket.id,
            "external_id": request.external_id,
            "thread_match": match.get("thread_match"),
            "public": event.public,
            "previous_status": previous_status,
            "new_status": target_ticket.status,
        },
    )
    db.commit()
    db.refresh(target_ticket)
    return {
        "deduplicated": False,
        "threaded": True,
        "ticket": _sync_ticket(db, state, target_ticket),
        "connector_event": connector_event,
    }


def _sla_for_ticket(
    db: Session,
    market_id: str,
    priority: Priority,
    channel: ChannelType,
    base: datetime,
) -> SlaState:
    policy = _active_sla_policy(db, market_id, priority, channel)
    if policy is None:
        return default_sla(priority, base)
    return _sla_state_from_policy(policy, base)


def _is_blank_custom_field(value: object) -> bool:
    return value is None or value == "" or value == []


def _field_error(record: TicketFieldRecord, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"{record.label}: {message}",
    )


def _match_option(record: TicketFieldRecord, value: str) -> str:
    options = {option.lower(): option for option in record.options or []}
    matched = options.get(value.strip().lower())
    if matched is None:
        raise _field_error(record, "value must match a configured option")
    return matched


def _normalize_custom_field_value(record: TicketFieldRecord, value: object) -> object:
    field_type = record.field_type
    if field_type in {TicketFieldType.text.value, TicketFieldType.textarea.value}:
        if not isinstance(value, str):
            raise _field_error(record, "value must be text")
        text_value = value.strip()
        max_length = 4000 if field_type == TicketFieldType.textarea.value else 500
        if len(text_value) > max_length:
            raise _field_error(record, f"value must be {max_length} characters or fewer")
        return text_value
    if field_type == TicketFieldType.select.value:
        if not isinstance(value, str):
            raise _field_error(record, "value must be one option")
        return _match_option(record, value)
    if field_type == TicketFieldType.multiselect.value:
        if not isinstance(value, list):
            raise _field_error(record, "value must be a list of options")
        selected_options: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise _field_error(record, "each selected option must be text")
            option = _match_option(record, item)
            key = option.lower()
            if key not in seen:
                selected_options.append(option)
                seen.add(key)
        return selected_options
    if field_type == TicketFieldType.checkbox.value:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise _field_error(record, "value must be true or false")
    if field_type == TicketFieldType.number.value:
        if isinstance(value, bool):
            raise _field_error(record, "value must be a number")
        if isinstance(value, int | float):
            return value
        if isinstance(value, str):
            try:
                number = float(value.strip())
            except ValueError as exc:
                raise _field_error(record, "value must be a number") from exc
            return int(number) if number.is_integer() else number
        raise _field_error(record, "value must be a number")
    if field_type == TicketFieldType.date.value:
        if not isinstance(value, str):
            raise _field_error(record, "value must be an ISO date")
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError as exc:
            raise _field_error(record, "value must be an ISO date") from exc
    return value


def _normalized_ticket_custom_fields(
    db: Session,
    *,
    market_id: str,
    channel: str,
    submitted: dict | None,
    existing: dict | None = None,
    require_required: bool = True,
) -> dict:
    records = db.scalars(
        select(TicketFieldRecord).where(TicketFieldRecord.market_id == market_id)
    ).all()
    fields_by_key = {record.key: record for record in records}
    next_fields = dict(existing or {})
    submitted_fields = submitted or {}
    if not isinstance(submitted_fields, dict):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ticket custom_fields must be an object",
        )

    for key, value in submitted_fields.items():
        record = fields_by_key.get(key)
        if record is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown ticket custom field: {key}",
            )
        if not _ticket_field_applies(record, channel):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Ticket custom field does not apply to this channel: {key}",
            )
        if _is_blank_custom_field(value):
            next_fields.pop(key, None)
            continue
        next_fields[key] = _normalize_custom_field_value(record, value)

    if require_required:
        for record in records:
            if not record.required or not _ticket_field_applies(record, channel):
                continue
            if _is_blank_custom_field(next_fields.get(record.key)):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"{record.label} is required",
                )

    return next_fields


def _automation_rule_matches(rule: AutomationRuleRecord, ticket: TicketRecord) -> bool:
    trigger_text = _search_text(rule.trigger)
    rule_text = _search_text(rule.name, rule.trigger, rule.action)
    ticket_text = _ticket_search_text(ticket)

    channel_constraints = _trigger_channels(trigger_text)
    if channel_constraints and ticket.channel not in channel_constraints:
        return False

    sentiment_constraints = _trigger_sentiments(trigger_text)
    if sentiment_constraints and ticket.sentiment not in sentiment_constraints:
        return False

    topic_keywords: dict[str, tuple[str, ...]] = {
        "payment": ("payment", "paid", "charge", "refund", "invoice", "billing", "duplicate"),
        "duplicate": ("duplicate", "double", "payment", "charge"),
        "social": ("facebook", "instagram", "messenger", "dm", "public", "post", "complaint"),
        "vip": ("vip", "priority customer", "premium"),
        "sla": ("sla", "breach", "breached", "overdue", "due soon", "risk"),
        "handoff": ("handoff", "transfer", "fulfillment", "operations"),
    }
    keywords = {
        keyword
        for topic, candidates in topic_keywords.items()
        if topic in rule_text
        for keyword in candidates
    }
    if keywords:
        return any(keyword in ticket_text for keyword in keywords)

    return bool(channel_constraints or sentiment_constraints)


def _best_agent_for_team(db: Session, market_id: str, team: str) -> AgentRecord | None:
    records = db.scalars(select(AgentRecord).where(AgentRecord.role == team)).all()
    candidates = [record for record in records if market_id in record.market_ids]
    if not candidates:
        return None
    status_rank = {"available": 0, "away": 1, "busy": 2, "offline": 3}
    return min(
        candidates,
        key=lambda record: (
            status_rank.get(record.status, 4),
            record.occupancy / max(record.capacity, 1),
            record.occupancy,
        ),
    )


def _recommended_team(rule: AutomationRuleRecord, ticket: TicketRecord) -> str | None:
    rule_text = _search_text(rule.name, rule.trigger, rule.action)
    if any(token in rule_text for token in ("billing support", "billing", "payment", "duplicate")):
        return "Billing Support"
    if any(token in rule_text for token in ("social care", "social", "facebook", "instagram")):
        return "Social Care"
    if any(token in rule_text for token in ("escalation", "escalations")):
        return "Escalations"
    if "chat care" in rule_text or ticket.channel in {"whatsapp", "sms"}:
        return "Chat Care"
    return None


def _append_task_labels(ticket: TicketRecord, labels: list[str]) -> list[str]:
    existing = {str(item.get("label", "")).lower() for item in ticket.tasks or []}
    tasks = list(ticket.tasks or [])
    added: list[str] = []
    for label in labels:
        if label.lower() in existing:
            continue
        tasks.append(_task(label).model_dump(mode="json"))
        existing.add(label.lower())
        added.append(label)
    if added:
        ticket.tasks = tasks
    return added


def _apply_rule_action(
    db: Session,
    rule: AutomationRuleRecord,
    ticket: TicketRecord,
) -> list[str]:
    rule_text = _search_text(rule.name, rule.trigger, rule.action)
    changes: list[str] = []

    if any(token in rule_text for token in ("raise priority", "urgent", "escalate")):
        if ticket.priority != Priority.urgent.value:
            ticket.priority = Priority.urgent.value
            ticket.sla = _sla_for_ticket(
                db,
                ticket.market_id,
                Priority.urgent,
                ChannelType(ticket.channel),
                ticket.created_at,
            ).model_dump(mode="json")
            changes.append("priority:urgent")

    team = _recommended_team(rule, ticket)
    if team:
        agent = _best_agent_for_team(db, ticket.market_id, team)
        if agent and ticket.assignee_id != agent.id:
            ticket.assignee_id = agent.id
            ticket.team = team
            changes.append(f"assignee:{agent.id}")
        elif ticket.team != team:
            ticket.team = team
            changes.append(f"team:{team}")

    tags = set(ticket.tags or [])
    next_tags = tags | {"automation-rule", f"rule:{rule.id}"}
    if next_tags != tags:
        ticket.tags = sorted(next_tags)
        changes.append("tags:automation-rule")

    task_labels: list[str] = []
    if any(token in rule_text for token in ("payment", "duplicate", "billing")):
        task_labels.extend(
            [
                "Confirm duplicate transaction reference",
                "Validate payment gateway status",
                "Send customer reversal timeline",
            ]
        )
    if any(token in rule_text for token in ("social", "facebook", "instagram", "public")):
        task_labels.extend(
            [
                "Reply in the private social thread",
                "Keep public acknowledgement neutral",
            ]
        )
    if "notify supervisor" in rule_text:
        task_labels.append("Notify supervisor if the blocker remains open")

    added_tasks = _append_task_labels(ticket, task_labels)
    if added_tasks:
        changes.append("tasks:" + ",".join(added_tasks))

    ticket.updated_at = utc_now()
    return changes


def _apply_enabled_automation_rules(
    db: Session,
    state: InMemoryStore,
    ticket: TicketRecord,
) -> list[str]:
    rules = db.scalars(
        select(AutomationRuleRecord)
        .where(AutomationRuleRecord.market_id == ticket.market_id)
        .where(AutomationRuleRecord.enabled.is_(True))
    ).all()
    applied: list[str] = []
    for rule in rules:
        if not _automation_rule_matches(rule, ticket):
            continue
        try:
            changes = _apply_rule_action(db, rule, ticket)
            rule.last_fired_at = utc_now()
            rule.failure_count = 0
            state.rules[rule.id] = automation_rule_from_record(rule)
            if not changes:
                continue
            applied.append(rule.id)
            _add_timeline_record(
                db,
                state,
                ticket,
                event_type=TimelineEventType.status_change,
                channel=ChannelType.internal,
                actor="Automation Rules",
                body=f"Automation rule applied: {rule.name}.",
                public=False,
                metadata={"rule_id": rule.id, "changes": changes},
            )
            _audit(
                db,
                state,
                actor="automation-rules",
                action="automation_rule.fire",
                entity_type="automation_rule",
                entity_id=rule.id,
                market_id=ticket.market_id,
                details={"ticket_id": ticket.id, "changes": changes},
            )
        except Exception as exc:
            rule.failure_count = (rule.failure_count or 0) + 1
            state.rules[rule.id] = automation_rule_from_record(rule)
            _audit(
                db,
                state,
                actor="automation-rules",
                action="automation_rule.failure",
                entity_type="automation_rule",
                entity_id=rule.id,
                market_id=ticket.market_id,
                details={"ticket_id": ticket.id, "error": str(exc)},
            )
    return applied


_RESOLVED_STATUSES = {TicketStatus.solved.value, TicketStatus.closed.value}


def _coerce_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _sla_met_at(record: TicketRecord, when: datetime) -> bool | None:
    """Frozen SLA outcome: did the ticket meet its resolution target at moment `when`?
    Returns None when no resolution target is known."""
    sla = record.sla if isinstance(record.sla, dict) else {}
    due = _coerce_dt(sla.get("resolution_due_at"))
    if due is None:
        return None
    return when <= due


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict,
) -> AuditEventRecord:
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
    return record


def _add_timeline_record(
    db: Session,
    state: InMemoryStore,
    ticket: TicketRecord,
    *,
    event_type: TimelineEventType,
    channel: ChannelType,
    actor: str,
    body: str,
    public: bool,
    metadata: dict | None = None,
) -> TimelineEvent:
    ticket.updated_at = utc_now()
    record = TimelineEventRecord(
        id=_new_id("event"),
        market_id=ticket.market_id,
        ticket_id=ticket.id,
        type=event_type.value,
        channel=channel.value,
        actor=actor,
        body=body,
        public=public,
        event_metadata=metadata or {},
    )
    db.add(record)
    db.flush()
    event = timeline_event_from_record(record)
    state.timeline.setdefault(ticket.id, []).append(event)
    if ticket.id in state.tickets:
        state.tickets[ticket.id].updated_at = ticket.updated_at
    _audit(
        db,
        state,
        actor=actor,
        action=f"timeline.{event_type.value}",
        entity_type="ticket",
        entity_id=ticket.id,
        market_id=ticket.market_id,
        details={"channel": channel.value, "public": public},
    )
    return event


def _sla_is_frozen(ticket: TicketRecord) -> bool:
    """Resolved/closed tickets keep the SLA state they had at close-out — wall-clock
    drift must not flip a met ticket to breached after the fact."""
    return ticket.status in _RESOLVED_STATUSES


def _sync_ticket(db: Session, state: InMemoryStore, ticket: TicketRecord) -> Ticket:
    domain_ticket = ticket_from_record(ticket)
    if not _sla_is_frozen(ticket):
        domain_ticket.sla = sla_service.refresh(domain_ticket.sla)
        ticket.sla = domain_ticket.sla.model_dump(mode="json")
    state.tickets[domain_ticket.id] = domain_ticket
    return domain_ticket


def _handoff_forward_subject(
    ticket: TicketRecord,
    to_team: str,
    linked_public_id: str | None = None,
) -> str:
    subject = ticket.subject.strip() or "Customer case"
    public_id = ticket.public_id or ticket.id
    if linked_public_id:
        return f"Team handoff: {linked_public_id} from {public_id} to {to_team} - {subject}"
    return f"Team handoff: {public_id} to {to_team} - {subject}"


def _public_api_url(path: str) -> str:
    base_url = settings.public_app_url.rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{clean_path}"


def _handoff_attachment_lines(
    db: Session,
    state: InMemoryStore,
    *,
    ticket: TicketRecord,
    handoff: HandoffRecord,
    attachments: Sequence[AttachmentRecord],
) -> list[str]:
    lines: list[str] = []
    for attachment in attachments:
        label = (
            f"- {attachment.filename} ({attachment.content_type}, "
            f"{attachment.scan_status}, {attachment.lifecycle_status})"
        )
        if (
            attachment.scan_status == AttachmentScanStatus.clean.value
            and attachment.lifecycle_status == AttachmentLifecycleStatus.active.value
        ):
            token, expires_at = create_attachment_download_token(
                market_id=ticket.market_id,
                ticket_id=ticket.id,
                attachment_id=attachment.id,
                created_by=f"handoff:{handoff.id}",
                ttl_minutes=settings.handoff_attachment_download_ttl_minutes,
            )
            path = (
                f"{settings.api_prefix}/tickets/{ticket.id}/attachments/"
                f"{attachment.id}/download/signed?token={token}"
            )
            parsed_token = parse_attachment_download_token(token)
            label = f"{label} - Download: {_public_api_url(path)}"
            _audit(
                db,
                state,
                actor=handoff.requested_by,
                action="attachment.handoff_link.create",
                entity_type="attachment",
                entity_id=attachment.id,
                market_id=ticket.market_id,
                details={
                    "ticket_id": ticket.id,
                    "handoff_id": handoff.id,
                    "filename": attachment.filename,
                    "expires_at": expires_at.isoformat(),
                    "token_id": parsed_token.token_id if parsed_token else "unknown",
                    "ttl_minutes": settings.handoff_attachment_download_ttl_minutes,
                },
            )
        lines.append(label)
    return lines


def _handoff_forward_body(
    db: Session,
    state: InMemoryStore,
    *,
    ticket: TicketRecord,
    handoff: HandoffRecord,
    to_email: str,
) -> str:
    customer = db.get(CustomerRecord, ticket.customer_id)
    company = db.get(CompanyRecord, customer.company_id) if customer and customer.company_id else None
    timeline = db.scalars(
        select(TimelineEventRecord)
        .where(
            TimelineEventRecord.market_id == ticket.market_id,
            TimelineEventRecord.ticket_id == ticket.id,
        )
        .order_by(TimelineEventRecord.created_at.asc())
    ).all()
    attachments = db.scalars(
        select(AttachmentRecord).where(
            AttachmentRecord.market_id == ticket.market_id,
            AttachmentRecord.ticket_id == ticket.id,
        )
    ).all()
    contact_lines = [
        f"- {point.get('channel')}: {point.get('value')}"
        for point in (customer.contact_points if customer else [])
        if point.get("value")
    ]
    custom_field_lines = [
        f"- {key}: {value}" for key, value in sorted((ticket.custom_fields or {}).items())
    ]
    timeline_lines = [
        (
            f"- [{event.created_at.isoformat()}] {event.actor} "
            f"({event.type}/{event.channel}, {'public' if event.public else 'internal'}): "
            f"{event.body}"
        )
        for event in timeline[-12:]
    ]
    attachment_lines = _handoff_attachment_lines(
        db,
        state,
        ticket=ticket,
        handoff=handoff,
        attachments=attachments,
    )
    sla = ticket.sla or {}
    return "\n".join(
        [
            "A team handoff was requested in Omni Ticket.",
            "",
            "Handoff",
            f"- To team: {handoff.to_team}",
            f"- To inbox: {to_email}",
            f"- From team: {handoff.from_team}",
            f"- Requested by: {handoff.requested_by}",
            f"- Reason: {handoff.reason}",
            f"- Due at: {handoff.due_at.isoformat()}",
            "",
            "Ticket",
            f"- Public ID: {ticket.public_id}",
            f"- Subject: {ticket.subject}",
            f"- Status: {ticket.status}",
            f"- Priority: {ticket.priority}",
            f"- Channel: {ticket.channel}",
            f"- Current team: {ticket.team}",
            f"- Tags: {', '.join(ticket.tags or []) or 'None'}",
            f"- AI summary: {ticket.ai_summary or 'None'}",
            f"- Recommended action: {ticket.recommended_action or 'None'}",
            f"- SLA risk: {sla.get('risk', 'unknown')}",
            "",
            "Customer",
            f"- Name: {customer.name if customer else 'Unknown'}",
            f"- Email: {customer.email if customer else 'Unknown'}",
            f"- Company: {company.name if company else 'None'}",
            f"- Sentiment: {customer.sentiment if customer else 'Unknown'}",
            f"- Notes: {customer.notes if customer and customer.notes else 'None'}",
            "",
            "Contact points",
            *(contact_lines or ["- None"]),
            "",
            "Custom fields",
            *(custom_field_lines or ["- None"]),
            "",
            "Recent comments and notes",
            *(timeline_lines or ["- No timeline entries yet."]),
            "",
            "Attachments",
            *(attachment_lines or ["- None"]),
        ]
    )


def _handoff_linked_ticket_subject(ticket: TicketRecord, to_team: str) -> str:
    subject = ticket.subject.strip() or "Customer case"
    return f"[{to_team}] Handoff from {ticket.public_id}: {subject}"[:255]


def _safe_priority(value: str) -> Priority:
    try:
        return Priority(value)
    except ValueError:
        return Priority.normal


def _handoff_child_tasks(handoff: HandoffRecord) -> list[dict]:
    checklist_labels = [
        str(item.get("label", "")).strip()
        for item in (handoff.checklist or [])
        if str(item.get("label", "")).strip()
    ]
    labels = checklist_labels or [
        "Accept team ownership",
        "Review source ticket thread",
        "Return a customer-ready update",
    ]
    return [_task(label).model_dump(mode="json") for label in labels]


def _handoff_child_tags(ticket: TicketRecord, to_team: str) -> list[str]:
    team_tag = to_team.lower().replace(" ", "-")
    return sorted(set(ticket.tags or []) | {"handoff", "internal", team_tag})


def _create_linked_handoff_ticket(
    db: Session,
    state: InMemoryStore,
    *,
    source_ticket: TicketRecord,
    handoff: HandoffRecord,
    case_context: str,
) -> TicketRecord:
    now = utc_now()
    priority = _safe_priority(source_ticket.priority)
    sla = sla_service.refresh(
        _sla_for_ticket(db, source_ticket.market_id, priority, ChannelType.internal, now)
    )
    linked_ticket = TicketRecord(
        id=_new_id("ticket"),
        market_id=source_ticket.market_id,
        public_id=_next_public_ticket_id(db),
        subject=_handoff_linked_ticket_subject(source_ticket, handoff.to_team),
        description=case_context,
        customer_id=source_ticket.customer_id,
        channel=ChannelType.internal.value,
        status=TicketStatus.open.value,
        priority=priority.value,
        sentiment=source_ticket.sentiment,
        assignee_id=None,
        team=handoff.to_team,
        tags=_handoff_child_tags(source_ticket, handoff.to_team),
        custom_fields={
            **(source_ticket.custom_fields or {}),
            "linked_ticket_type": "handoff_child",
            "source_ticket_id": source_ticket.id,
            "source_public_id": source_ticket.public_id,
            "handoff_id": handoff.id,
            "handoff_from_team": handoff.from_team,
            "handoff_to_team": handoff.to_team,
            "handoff_requested_by": handoff.requested_by,
        },
        tasks=_handoff_child_tasks(handoff),
        sla=sla.model_dump(mode="json"),
        ai_summary=f"Linked handoff ticket for {source_ticket.public_id}.",
        recommended_action=(
            f"Accept ownership for {handoff.to_team}, review the source thread, "
            "and return a customer-ready update."
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(linked_ticket)
    db.flush()
    _sync_ticket(db, state, linked_ticket)
    _add_timeline_record(
        db,
        state,
        linked_ticket,
        event_type=TimelineEventType.internal_note,
        channel=ChannelType.internal,
        actor="handoff-service",
        body=case_context,
        public=False,
        metadata={
            "handoff_id": handoff.id,
            "source_ticket_id": source_ticket.id,
            "source_public_id": source_ticket.public_id,
            "linked_ticket_role": "handoff_child",
        },
    )
    _audit(
        db,
        state,
        actor=handoff.requested_by,
        action="handoff.linked_ticket.create",
        entity_type="ticket",
        entity_id=linked_ticket.id,
        market_id=source_ticket.market_id,
        details={
            "handoff_id": handoff.id,
            "source_ticket_id": source_ticket.id,
            "source_public_id": source_ticket.public_id,
            "linked_public_id": linked_ticket.public_id,
            "to_team": handoff.to_team,
        },
    )
    return linked_ticket


class TicketRepository:
    def count_tickets(
        self,
        db: Session,
        *,
        market_id: str,
        status_filter: str | None = None,
        channel: ChannelType | None = None,
        priority: Priority | None = None,
        customer_id: str | None = None,
        assignee_id: str | None = None,
        team: str | None = None,
        q: str | None = None,
    ) -> int:
        query = _ticket_list_query(
            market_id=market_id,
            status_filter=status_filter,
            channel=channel,
            priority=priority,
            customer_id=customer_id,
            assignee_id=assignee_id,
            team=team,
            q=q,
        )
        return db.scalar(select(func.count()).select_from(query.subquery())) or 0

    def list_tickets(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        status_filter: str | None = None,
        channel: ChannelType | None = None,
        priority: Priority | None = None,
        customer_id: str | None = None,
        assignee_id: str | None = None,
        team: str | None = None,
        q: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Ticket]:
        sort_column = _TICKET_SORT_COLUMNS.get(sort_by, TicketRecord.updated_at)
        order_expr = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        query = _ticket_list_query(
            market_id=market_id,
            status_filter=status_filter,
            channel=channel,
            priority=priority,
            customer_id=customer_id,
            assignee_id=assignee_id,
            team=team,
            q=q,
        ).order_by(order_expr, TicketRecord.id.asc())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        records = db.scalars(query).all()
        tickets = [_sync_ticket(db, state, record) for record in records]
        db.commit()
        return tickets

    def get_ticket(self, db: Session, state: InMemoryStore, ticket_id: str, market_id: str) -> Ticket:
        record = _ticket_record_or_404(db, ticket_id, market_id)
        ticket = _sync_ticket(db, state, record)
        db.commit()
        return ticket

    def get_ticket_context(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
    ) -> dict:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        ticket = _sync_ticket(db, state, ticket_record)
        customer_record = _customer_record_or_404(db, ticket.customer_id, market_id)
        customer = customer_from_record(customer_record)
        company = None
        if customer.company_id:
            company_record = db.get(CompanyRecord, customer.company_id)
            if company_record and company_record.market_id == market_id:
                company = company_from_record(company_record)
                state.companies[company.id] = company
        assignee = None
        if ticket.assignee_id:
            agent_record = db.get(AgentRecord, ticket.assignee_id)
            if agent_record and market_id in agent_record.market_ids:
                assignee = agent_from_record(agent_record)
                state.agents[assignee.id] = assignee
        timeline = [
            timeline_event_from_record(record)
            for record in db.scalars(
                select(TimelineEventRecord)
                .where(
                    TimelineEventRecord.market_id == market_id,
                    TimelineEventRecord.ticket_id == ticket_id,
                )
                .order_by(TimelineEventRecord.created_at.asc())
            ).all()
        ]
        handoffs = [
            handoff_from_record(record)
            for record in db.scalars(
                select(HandoffRecord)
                .where(HandoffRecord.market_id == market_id, HandoffRecord.ticket_id == ticket_id)
                .order_by(HandoffRecord.created_at.asc())
            ).all()
        ]
        ai_decisions = [
            ai_decision_from_record(record)
            for record in db.scalars(
                select(AiDecisionRecord)
                .where(AiDecisionRecord.market_id == market_id, AiDecisionRecord.ticket_id == ticket_id)
                .order_by(AiDecisionRecord.created_at.asc())
            ).all()
        ]
        outbound_messages = [
            outbound_message_from_record(record)
            for record in db.scalars(
                select(OutboundMessageRecord)
                .where(
                    OutboundMessageRecord.market_id == market_id,
                    OutboundMessageRecord.ticket_id == ticket_id,
                )
                .order_by(OutboundMessageRecord.created_at.asc())
            ).all()
        ]
        attachments = [
            attachment_from_record(record)
            for record in db.scalars(
                select(AttachmentRecord)
                .where(
                    AttachmentRecord.market_id == market_id,
                    AttachmentRecord.ticket_id == ticket_id,
                )
                .order_by(AttachmentRecord.created_at.asc())
            ).all()
        ]
        csat_feedback = [
            csat_feedback_from_record(record)
            for record in db.scalars(
                select(CsatFeedbackRecord)
                .where(
                    CsatFeedbackRecord.market_id == market_id,
                    CsatFeedbackRecord.ticket_id == ticket_id,
                )
                .order_by(CsatFeedbackRecord.updated_at.desc())
            ).all()
        ]
        state.customers[customer.id] = customer
        state.timeline[ticket_id] = timeline
        state.handoffs.update({handoff.id: handoff for handoff in handoffs})
        state.outbound_messages.update({message.id: message for message in outbound_messages})
        state.ai_decisions = [
            decision for decision in state.ai_decisions if decision.ticket_id != ticket_id
        ] + ai_decisions
        db.commit()
        return {
            "ticket": ticket,
            "customer": customer,
            "company": company,
            "assignee": assignee,
            "timeline": timeline,
            "handoffs": handoffs,
            "ai_decisions": ai_decisions,
            "outbound_messages": outbound_messages,
            "attachments": attachments,
            "csat_feedback": csat_feedback,
        }

    def suggest_duplicate_tickets(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
        *,
        limit: int = 5,
    ) -> list[DuplicateTicketSuggestion]:
        target = _ticket_record_or_404(db, ticket_id, market_id)
        if _is_linked_handoff_child(target) or _is_merged_source(target):
            return []

        target_customer = _customer_record_or_404(db, target.customer_id, market_id)
        target_company_id = target_customer.company_id
        target_contacts = _customer_contact_values(target_customer)
        target_references = _reference_values(target)
        target_tokens = _ticket_duplicate_tokens(target)
        target_subject_tokens = _word_tokens(target.subject)
        target_tags = set(target.tags or [])

        records = db.scalars(
            select(TicketRecord)
            .where(
                TicketRecord.market_id == market_id,
                TicketRecord.id != ticket_id,
                TicketRecord.status != TicketStatus.closed.value,
            )
            .order_by(TicketRecord.updated_at.desc())
            .limit(250)
        ).all()
        suggestions: list[DuplicateTicketSuggestion] = []
        for candidate in records:
            if _is_linked_handoff_child(candidate) or _is_merged_source(candidate):
                continue
            candidate_customer = db.get(CustomerRecord, candidate.customer_id)
            if candidate_customer is None or candidate_customer.market_id != market_id:
                continue

            score = 0
            reasons: list[str] = []
            matched_terms: list[str] = []

            def add_matched_terms(terms: Sequence[str]) -> None:
                for term in terms:
                    if term not in matched_terms:
                        matched_terms.append(term)

            if candidate.customer_id == target.customer_id:
                score += 30
                reasons.append("Same customer")
            elif target_contacts & _customer_contact_values(candidate_customer):
                score += 25
                reasons.append("Matching customer contact")

            if target_company_id and candidate_customer.company_id == target_company_id:
                score += 10
                reasons.append("Same company")

            shared_references = sorted(target_references & _reference_values(candidate))
            if shared_references:
                score += 42
                add_matched_terms(shared_references[:3])
                reasons.append("Matching booking or transaction reference")

            shared_subject_terms = sorted(target_subject_tokens & _word_tokens(candidate.subject))
            if shared_subject_terms:
                score += min(24, len(shared_subject_terms) * 6)
                add_matched_terms(shared_subject_terms[:5])
                reasons.append("Similar subject")

            shared_terms = sorted(target_tokens & _ticket_duplicate_tokens(candidate))
            meaningful_shared_terms = [term for term in shared_terms if term not in set(matched_terms)]
            if meaningful_shared_terms:
                score += min(16, len(meaningful_shared_terms) * 3)
                add_matched_terms(meaningful_shared_terms[:5])
                reasons.append("Shared case language")

            shared_tags = sorted(target_tags & set(candidate.tags or []))
            if shared_tags:
                score += min(12, len(shared_tags) * 4)
                add_matched_terms(shared_tags[:4])
                reasons.append("Shared labels")

            if candidate.channel == target.channel:
                score += 5
                reasons.append("Same channel")

            if target.created_at and candidate.created_at:
                age_delta_days = abs((target.created_at - candidate.created_at).days)
                if age_delta_days <= 7:
                    score += 8
                    reasons.append("Created within 7 days")

            if score < 45:
                continue

            ticket = _sync_ticket(db, state, candidate)
            customer = customer_from_record(candidate_customer)
            state.customers[customer.id] = customer
            suggestions.append(
                DuplicateTicketSuggestion(
                    ticket=ticket,
                    customer=customer,
                    score=min(score, 100),
                    reasons=list(dict.fromkeys(reasons)),
                    matched_terms=matched_terms[:8],
                )
            )

        suggestions.sort(
            key=lambda suggestion: (
                -suggestion.score,
                suggestion.ticket.status == TicketStatus.closed,
                suggestion.ticket.updated_at,
            )
        )
        db.commit()
        return suggestions[:limit]

    def merge_tickets(
        self,
        db: Session,
        state: InMemoryStore,
        target_ticket_id: str,
        request: MergeTicketsRequest,
        market_id: str,
        *,
        actor: str,
    ) -> MergeTicketsResponse:
        target = _ticket_record_or_404(db, target_ticket_id, market_id)
        source = _ticket_record_or_404(db, request.source_ticket_id, market_id)
        if target.id == source.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A ticket cannot be merged into itself",
            )
        if _is_linked_handoff_child(target) or _is_linked_handoff_child(source):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Linked handoff tickets cannot be merged",
            )
        if _is_merged_source(target):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Target ticket has already been merged into another ticket",
            )
        if _is_merged_source(source):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Source ticket has already been merged",
            )

        operator = (request.actor or actor).strip() or actor
        reason = request.reason.strip()
        now = utc_now()
        source_summary = _ticket_merge_context(db, source)
        target_custom_fields = dict(target.custom_fields or {})
        source_custom_fields = dict(source.custom_fields or {})
        merged_source_ids = list(target_custom_fields.get("merged_source_ticket_ids") or [])
        merged_source_public_ids = list(target_custom_fields.get("merged_source_public_ids") or [])
        if source.id not in merged_source_ids:
            merged_source_ids.append(source.id)
        if source.public_id not in merged_source_public_ids:
            merged_source_public_ids.append(source.public_id)
        target.custom_fields = {
            **target_custom_fields,
            "merged_source_ticket_ids": merged_source_ids,
            "merged_source_public_ids": merged_source_public_ids,
            "last_merge_reason": reason,
            "last_merged_at": now.isoformat(),
        }
        source.custom_fields = {
            **source_custom_fields,
            "merged_into_ticket_id": target.id,
            "merged_into_public_id": target.public_id,
            "merge_reason": reason,
            "merged_at": now.isoformat(),
        }
        target.tags = sorted(set(target.tags or []) | set(source.tags or []) | {"merged-source"})
        source.tags = sorted(
            set(source.tags or [])
            | {"merged", f"merged-into-{_short_public_id_tag(target.public_id)}"}
        )
        if request.close_source:
            source.status = TicketStatus.closed.value
        target.updated_at = now
        source.updated_at = now

        target_event = _add_timeline_record(
            db,
            state,
            target,
            event_type=TimelineEventType.internal_note,
            channel=ChannelType.internal,
            actor=operator,
            body=(
                f"Merged duplicate ticket {source.public_id} into this ticket: {reason}\n\n"
                f"{source_summary}"
            ),
            public=False,
            metadata={
                "merge_role": "target",
                "source_ticket_id": source.id,
                "source_public_id": source.public_id,
                "reason": reason,
                "close_source": request.close_source,
            },
        )
        source_event = _add_timeline_record(
            db,
            state,
            source,
            event_type=TimelineEventType.status_change,
            channel=ChannelType.internal,
            actor=operator,
            body=f"Merged into {target.public_id}: {reason}",
            public=False,
            metadata={
                "merge_role": "source",
                "target_ticket_id": target.id,
                "target_public_id": target.public_id,
                "reason": reason,
                "closed": request.close_source,
            },
        )
        audit_record = _audit(
            db,
            state,
            actor=operator,
            action="ticket.merge",
            entity_type="ticket",
            entity_id=target.id,
            market_id=market_id,
            details={
                "source_ticket_id": source.id,
                "source_public_id": source.public_id,
                "target_ticket_id": target.id,
                "target_public_id": target.public_id,
                "reason": reason,
                "close_source": request.close_source,
            },
        )
        db.commit()
        db.refresh(target)
        db.refresh(source)
        return MergeTicketsResponse(
            target_ticket=_sync_ticket(db, state, target),
            source_ticket=_sync_ticket(db, state, source),
            target_timeline_event=target_event,
            source_timeline_event=source_event,
            audit_event_id=audit_record.id,
        )

    def list_csat_feedback(
        self,
        db: Session,
        *,
        market_id: str,
        ticket_id: str | None = None,
        limit: int = 100,
    ) -> list[CsatFeedback]:
        query = select(CsatFeedbackRecord).where(CsatFeedbackRecord.market_id == market_id)
        if ticket_id:
            query = query.where(CsatFeedbackRecord.ticket_id == ticket_id)
        records = db.scalars(
            query.order_by(CsatFeedbackRecord.updated_at.desc()).limit(limit)
        ).all()
        return [csat_feedback_from_record(record) for record in records]

    def submit_csat_feedback(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: CreateCsatFeedbackRequest,
        market_id: str,
        *,
        actor: str,
    ) -> CsatFeedback:
        ticket = _ticket_record_or_404(db, ticket_id, market_id)
        customer = _customer_record_or_404(db, ticket.customer_id, market_id)
        record = db.scalar(
            select(CsatFeedbackRecord).where(
                CsatFeedbackRecord.market_id == market_id,
                CsatFeedbackRecord.ticket_id == ticket_id,
            )
        )
        submitted_by = request.submitted_by or customer.email
        action = "csat.update"
        if record is None:
            record = CsatFeedbackRecord(
                id=_new_id("csat"),
                market_id=market_id,
                ticket_id=ticket_id,
                customer_id=customer.id,
                rating=request.rating,
                comment=request.comment,
                source=request.source.value,
                submitted_by=submitted_by,
            )
            db.add(record)
            action = "csat.create"
        else:
            record.rating = request.rating
            record.comment = request.comment
            record.source = request.source.value
            record.submitted_by = submitted_by
            record.updated_at = utc_now()
        db.flush()
        _add_timeline_record(
            db,
            state,
            ticket,
            event_type=TimelineEventType.internal_note,
            channel=ChannelType.internal,
            actor="CSAT survey",
            body=f"Customer satisfaction rating recorded: {record.rating}/5.",
            public=False,
            metadata={
                "csat_feedback_id": record.id,
                "rating": record.rating,
                "source": record.source,
                "submitted_by": record.submitted_by,
            },
        )
        _audit(
            db,
            state,
            actor=actor,
            action=action,
            entity_type="csat_feedback",
            entity_id=record.id,
            market_id=market_id,
            details={
                "ticket_id": ticket_id,
                "customer_id": customer.id,
                "rating": record.rating,
                "source": record.source,
            },
        )
        db.commit()
        db.refresh(record)
        return csat_feedback_from_record(record)

    def create_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateTicketRequest,
        market_id: str,
        *,
        ai_enabled: bool,
        actor: str = "api",
        source: str = "api",
    ) -> Ticket:
        customer_record = _customer_record_or_404(db, request.customer_id, market_id)
        customer = customer_from_record(customer_record)
        state.customers[customer.id] = customer

        text = f"{request.subject} {request.description}"
        priority = automation_service.classify_priority(text, request.priority)
        sentiment = automation_service.classify_sentiment(text)
        tags = automation_service.classify_tags(text, request.channel, request.tags)
        assignee = automation_service.choose_agent(state, request.channel, market_id) if ai_enabled else None
        team = assignee.team if assignee else "Unassigned"
        if ai_enabled:
            tags = sorted(set(tags) | {"ai-routed"})
        custom_fields = _normalized_ticket_custom_fields(
            db,
            market_id=market_id,
            channel=request.channel.value,
            submitted=request.custom_fields,
        )
        now = utc_now()
        ticket = Ticket(
            id=_new_id("ticket"),
            market_id=market_id,
            public_id=_next_public_ticket_id(db),
            subject=request.subject,
            description=request.description,
            customer_id=request.customer_id,
            channel=request.channel,
            priority=priority,
            sentiment=sentiment,
            assignee_id=assignee.id if assignee else None,
            team=team,
            tags=tags,
            custom_fields=custom_fields,
            tasks=[
                _task("Acknowledge customer"),
                _task("Clear blocker"),
                _task("Close promise"),
            ],
            sla=sla_service.refresh(_sla_for_ticket(db, market_id, priority, request.channel, now)),
            created_at=now,
            updated_at=now,
        )
        guidance = automation_service.generate_guidance(ticket, customer)
        ticket.ai_summary = guidance.summary
        ticket.recommended_action = guidance.recommended_action
        ticket_record = TicketRecord(**_ticket_payload(ticket))
        db.add(ticket_record)
        db.flush()
        state.tickets[ticket.id] = ticket
        state.timeline[ticket.id] = []

        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.inbound,
            channel=request.channel,
            actor=customer.name,
            body=request.description,
            public=True,
            metadata={"external_id": request.external_id},
        )
        applied_rules = _apply_enabled_automation_rules(db, state, ticket_record)
        if applied_rules:
            ticket = _sync_ticket(db, state, ticket_record)
            guidance = automation_service.generate_guidance(ticket, customer)
            ticket.ai_summary = guidance.summary
            ticket.recommended_action = guidance.recommended_action
            ticket_record.ai_summary = ticket.ai_summary
            ticket_record.recommended_action = ticket.recommended_action
        if ai_enabled:
            decision = automation_service.make_decision(ticket, guidance)
            decision_record = AiDecisionRecord(
                id=decision.id,
                market_id=market_id,
                ticket_id=ticket.id,
                decision_type=decision.decision_type,
                confidence=int(round(decision.confidence * 100)),
                summary=decision.summary,
                model_version=decision.model_version,
                input_reference=decision.input_reference,
                override_allowed=decision.override_allowed,
                created_at=decision.created_at,
            )
            db.add(decision_record)
            db.flush()
            state.ai_decisions.append(ai_decision_from_record(decision_record))
            _add_timeline_record(
                db,
                state,
                ticket_record,
                event_type=TimelineEventType.ai_decision,
                channel=ChannelType.internal,
                actor="AI Work Queue",
                body=decision.summary,
                public=False,
                metadata={"confidence": decision.confidence},
            )
        _audit(
            db,
            state,
            actor=actor,
            action="ticket.create",
            entity_type="ticket",
            entity_id=ticket.id,
            market_id=market_id,
            details={"ai_enabled": ai_enabled, "channel": request.channel.value, "source": source},
        )
        ticket_record.updated_at = utc_now()
        db.commit()
        db.refresh(ticket_record)
        return _sync_ticket(db, state, ticket_record)

    def update_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: UpdateTicketRequest,
        market_id: str,
    ) -> Ticket:
        record = _ticket_record_or_404(db, ticket_id, market_id)
        previous_status = record.status
        patch = request.model_dump(exclude_unset=True, mode="json")
        task_item_id = patch.pop("task_item_id", None)
        task_item_complete = patch.pop("task_item_complete", None)
        custom_fields_patch = patch.pop("custom_fields", None)
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        if custom_fields_patch is not None:
            record.custom_fields = _normalized_ticket_custom_fields(
                db,
                market_id=market_id,
                channel=record.channel,
                submitted=custom_fields_patch,
                existing=record.custom_fields,
            )
            patch["custom_fields"] = record.custom_fields
        if task_item_id and task_item_complete is not None:
            updated = False
            tasks: list[dict] = []
            for item in record.tasks:
                next_item = dict(item)
                if next_item["id"] == task_item_id:
                    next_item["complete"] = task_item_complete
                    updated = True
                tasks.append(next_item)
            if updated:
                record.tasks = tasks
        now = utc_now()
        record.updated_at = now

        status_changed = previous_status != record.status
        timeline_body = "Ticket fields updated."
        if status_changed:
            new_status = record.status
            if new_status == TicketStatus.solved.value:
                if record.resolved_at is None:
                    record.resolved_at = now
                    record.sla_resolution_met = _sla_met_at(record, now)
                record.closed_at = None
                timeline_body = "Ticket resolved."
            elif new_status == TicketStatus.closed.value:
                if record.resolved_at is None:
                    record.resolved_at = now
                    record.sla_resolution_met = _sla_met_at(record, now)
                record.closed_at = now
                timeline_body = "Ticket closed."
            elif previous_status in _RESOLVED_STATUSES:
                record.resolved_at = None
                record.closed_at = None
                record.sla_resolution_met = None
                timeline_body = "Ticket reopened."
            else:
                timeline_body = f"Status changed to {new_status}."

        event_metadata = dict(patch)
        if status_changed:
            event_metadata["previous_status"] = previous_status
            event_metadata["new_status"] = record.status
        _add_timeline_record(
            db,
            state,
            record,
            event_type=TimelineEventType.status_change,
            channel=ChannelType.internal,
            actor="api",
            body=timeline_body,
            public=False,
            metadata=event_metadata,
        )
        if status_changed:
            _audit(
                db,
                state,
                actor="api",
                action="ticket.status_change",
                entity_type="ticket",
                entity_id=record.id,
                market_id=market_id,
                details={
                    "previous_status": previous_status,
                    "new_status": record.status,
                    "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
                    "sla_resolution_met": record.sla_resolution_met,
                },
            )
        db.commit()
        db.refresh(record)
        return _sync_ticket(db, state, record)

    def override_work_queue(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: WorkQueueOverrideRequest,
        market_id: str,
        actor: str,
    ) -> Ticket:
        record = _ticket_record_or_404(db, ticket_id, market_id)
        patch = request.model_dump(exclude_unset=True, mode="json")
        reason = patch.pop("reason").strip()
        if not patch:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="At least one override field is required",
            )
        if "assignee_id" in patch:
            assignee_id = patch["assignee_id"]
            if assignee_id is None:
                record.assignee_id = None
                record.team = "Unassigned"
            else:
                agent_record = db.get(AgentRecord, assignee_id)
                if agent_record is None or market_id not in agent_record.market_ids:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
                record.assignee_id = assignee_id
                record.team = agent_from_record(agent_record).team
        for key, value in patch.items():
            if key == "assignee_id":
                continue
            if value is not None:
                setattr(record, key, value)
        record.updated_at = utc_now()
        _add_timeline_record(
            db,
            state,
            record,
            event_type=TimelineEventType.status_change,
            channel=ChannelType.internal,
            actor=actor,
            body=f"Manual work queue override applied: {reason}",
            public=False,
            metadata={"reason": reason, "override": patch},
        )
        _audit(
            db,
            state,
            actor=actor,
            action="work_queue.override",
            entity_type="ticket",
            entity_id=ticket_id,
            market_id=market_id,
            details={"reason": reason, "override": patch},
        )
        db.commit()
        db.refresh(record)
        return _sync_ticket(db, state, record)

    def list_timeline(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
    ) -> list[TimelineEvent]:
        _ticket_record_or_404(db, ticket_id, market_id)
        events = [
            timeline_event_from_record(record)
            for record in db.scalars(
                select(TimelineEventRecord)
                .where(
                    TimelineEventRecord.market_id == market_id,
                    TimelineEventRecord.ticket_id == ticket_id,
                )
                .order_by(TimelineEventRecord.created_at.asc())
            ).all()
        ]
        state.timeline[ticket_id] = events
        return events

    def append_event(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: AppendEventRequest,
        market_id: str,
    ) -> TimelineEvent:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        event = _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=request.type,
            channel=request.channel,
            actor=request.actor,
            body=request.body,
            public=request.public,
            metadata=request.metadata,
        )
        db.commit()
        return event

    def list_attachments(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
    ) -> list[Attachment]:
        _ticket_record_or_404(db, ticket_id, market_id)
        records = db.scalars(
            select(AttachmentRecord)
            .where(
                AttachmentRecord.market_id == market_id,
                AttachmentRecord.ticket_id == ticket_id,
            )
            .order_by(AttachmentRecord.created_at.asc())
        ).all()
        return [attachment_from_record(record) for record in records]

    def get_attachment(
        self,
        db: Session,
        ticket_id: str,
        attachment_id: str,
        market_id: str,
    ) -> Attachment:
        _ticket_record_or_404(db, ticket_id, market_id)
        record = db.get(AttachmentRecord, attachment_id)
        if record is None or record.market_id != market_id or record.ticket_id != ticket_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        return attachment_from_record(record)

    def create_attachment(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: CreateAttachmentRequest,
        market_id: str,
        *,
        actor: str,
        attachment_id: str | None = None,
        scan_status_override: AttachmentScanStatus | None = None,
        scan_result_override: str | None = None,
    ) -> Attachment:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        filename = request.filename.strip()
        if not filename:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Attachment filename is required",
            )

        attachment_id = attachment_id or _new_id("attachment")
        scan_status, scan_result = (
            (scan_status_override, scan_result_override or "Attachment scan status supplied by upload boundary.")
            if scan_status_override is not None
            else scan_attachment_metadata(filename, request.content_type)
        )
        storage_key = (
            request.storage_key
            or f"attachment://{market_id}/{ticket_id}/{attachment_id}/{filename}"
        )
        scan_label = "blocked" if scan_status == AttachmentScanStatus.blocked else "ready"
        event = _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.attachment_added,
            channel=ChannelType.internal,
            actor=actor,
            body=f"Attachment {scan_label}: {filename}. {scan_result}",
            public=False,
            metadata={
                "attachment_id": attachment_id,
                "filename": filename,
                "content_type": request.content_type,
                "size_bytes": request.size_bytes,
                "scan_status": scan_status.value,
            },
        )
        record = AttachmentRecord(
            id=attachment_id,
            market_id=market_id,
            ticket_id=ticket_id,
            timeline_event_id=event.id,
            filename=filename,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
            storage_key=storage_key,
            uploaded_by=actor,
            scan_status=scan_status.value,
            scan_result=scan_result,
            lifecycle_status=AttachmentLifecycleStatus.active.value,
            retained_until=utc_now() + timedelta(days=settings.attachment_retention_days),
        )
        db.add(record)
        db.flush()
        attachment = attachment_from_record(record)
        _audit(
            db,
            state,
            actor=actor,
            action="attachment.create",
            entity_type="attachment",
            entity_id=attachment.id,
            market_id=market_id,
            details={
                "ticket_id": ticket_id,
                "filename": filename,
                "content_type": request.content_type,
                "size_bytes": request.size_bytes,
                "scan_status": scan_status.value,
            },
        )
        db.commit()
        db.refresh(record)
        return attachment_from_record(record)

    def attachment_retention_policy(
        self,
        db: Session,
        *,
        market_id: str,
        active_retention_days: int,
        deleted_retention_days: int,
        prune_limit: int,
    ) -> AttachmentRetentionPolicy:
        active_cutoff = _retention_cutoff(active_retention_days)
        deleted_cutoff = _retention_cutoff(deleted_retention_days)
        purgeable_predicate = self._attachment_purgeable_predicate(
            market_id=market_id,
            active_cutoff=active_cutoff,
            deleted_cutoff=deleted_cutoff,
        )
        return AttachmentRetentionPolicy(
            market_id=market_id,
            active_retention_days=active_retention_days,
            deleted_retention_days=deleted_retention_days,
            active_cutoff_at=active_cutoff,
            deleted_cutoff_at=deleted_cutoff,
            prune_limit=prune_limit,
            active_attachments=self._count_attachments(
                db,
                market_id,
                AttachmentLifecycleStatus.active,
            ),
            deleted_attachments=self._count_attachments(
                db,
                market_id,
                AttachmentLifecycleStatus.deleted,
            ),
            purged_attachments=self._count_attachments(
                db,
                market_id,
                AttachmentLifecycleStatus.purged,
            ),
            purgeable_attachments=int(
                db.scalar(
                    select(func.count()).select_from(AttachmentRecord).where(purgeable_predicate)
                )
                or 0
            ),
        )

    def delete_attachment(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        ticket_id: str,
        attachment_id: str,
        market_id: str,
        actor: str,
        reason: str,
        purge_storage: bool,
        storage_delete: Callable[[str], bool],
    ) -> Attachment:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        record = db.get(AttachmentRecord, attachment_id)
        if record is None or record.market_id != market_id or record.ticket_id != ticket_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        if record.lifecycle_status == AttachmentLifecycleStatus.purged.value:
            return attachment_from_record(record)

        now = utc_now()
        record.lifecycle_status = AttachmentLifecycleStatus.deleted.value
        record.deleted_at = record.deleted_at or now
        record.deleted_by = actor
        record.deletion_reason = reason
        record.retained_until = now + timedelta(days=settings.attachment_deleted_retention_days)
        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.attachment_added,
            channel=ChannelType.internal,
            actor=actor,
            body=f"Attachment deleted: {record.filename}. {reason}",
            public=False,
            metadata={
                "attachment_id": record.id,
                "filename": record.filename,
                "lifecycle_status": AttachmentLifecycleStatus.deleted.value,
                "purge_storage": purge_storage,
            },
        )
        action = "attachment.delete"
        if purge_storage:
            self._purge_attachment_record(
                db,
                state,
                record,
                ticket_record=ticket_record,
                actor=actor,
                reason=reason,
                storage_delete=storage_delete,
            )
            action = "attachment.purge"
        _audit(
            db,
            state,
            actor=actor,
            action=action,
            entity_type="attachment",
            entity_id=record.id,
            market_id=market_id,
            details={
                "ticket_id": ticket_id,
                "filename": record.filename,
                "reason": reason,
                "purge_storage": purge_storage,
                "lifecycle_status": record.lifecycle_status,
            },
        )
        db.commit()
        db.refresh(record)
        return attachment_from_record(record)

    def prune_attachment_retention(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        active_retention_days: int,
        deleted_retention_days: int,
        limit: int,
        actor: str,
        storage_delete: Callable[[str], bool],
    ) -> tuple[list[str], str | None]:
        active_cutoff = _retention_cutoff(active_retention_days)
        deleted_cutoff = _retention_cutoff(deleted_retention_days)
        records = list(
            db.scalars(
                select(AttachmentRecord)
                .where(
                    self._attachment_purgeable_predicate(
                        market_id=market_id,
                        active_cutoff=active_cutoff,
                        deleted_cutoff=deleted_cutoff,
                    )
                )
                .order_by(AttachmentRecord.created_at.asc())
                .limit(limit)
            ).all()
        )
        purged_ids: list[str] = []
        for record in records:
            ticket_record = db.get(TicketRecord, record.ticket_id)
            if ticket_record is None or ticket_record.market_id != market_id:
                continue
            self._purge_attachment_record(
                db,
                state,
                record,
                ticket_record=ticket_record,
                actor=actor,
                reason="Attachment retention policy",
                storage_delete=storage_delete,
            )
            purged_ids.append(record.id)
        audit_id: str | None = None
        if purged_ids:
            audit_record = _audit(
                db,
                state,
                actor=actor,
                action="attachment.retention_prune",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details={
                    "attachment_ids": purged_ids,
                    "active_retention_days": active_retention_days,
                    "deleted_retention_days": deleted_retention_days,
                    "limit": limit,
                },
            )
            audit_id = audit_record.id
        db.commit()
        return purged_ids, audit_id

    def _attachment_purgeable_predicate(
        self,
        *,
        market_id: str,
        active_cutoff,
        deleted_cutoff,
    ):
        return and_(
            AttachmentRecord.market_id == market_id,
            AttachmentRecord.lifecycle_status != AttachmentLifecycleStatus.purged.value,
            or_(
                and_(
                    AttachmentRecord.lifecycle_status == AttachmentLifecycleStatus.active.value,
                    or_(
                        AttachmentRecord.retained_until <= utc_now(),
                        AttachmentRecord.created_at < active_cutoff,
                    ),
                ),
                and_(
                    AttachmentRecord.lifecycle_status == AttachmentLifecycleStatus.deleted.value,
                    or_(
                        AttachmentRecord.deleted_at <= deleted_cutoff,
                        AttachmentRecord.retained_until <= utc_now(),
                    ),
                ),
            ),
        )

    def _count_attachments(
        self,
        db: Session,
        market_id: str,
        lifecycle_status: AttachmentLifecycleStatus,
    ) -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(AttachmentRecord)
                .where(
                    AttachmentRecord.market_id == market_id,
                    AttachmentRecord.lifecycle_status == lifecycle_status.value,
                )
            )
            or 0
        )

    def _purge_attachment_record(
        self,
        db: Session,
        state: InMemoryStore,
        record: AttachmentRecord,
        *,
        ticket_record: TicketRecord,
        actor: str,
        reason: str,
        storage_delete: Callable[[str], bool],
    ) -> None:
        now = utc_now()
        try:
            storage_deleted = storage_delete(record.storage_key)
        except (OSError, ValueError):
            storage_deleted = False
        record.lifecycle_status = AttachmentLifecycleStatus.purged.value
        record.deleted_at = record.deleted_at or now
        record.deleted_by = record.deleted_by or actor
        record.deletion_reason = record.deletion_reason or reason
        record.purged_at = now
        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.attachment_added,
            channel=ChannelType.internal,
            actor=actor,
            body=f"Attachment purged: {record.filename}. {reason}",
            public=False,
            metadata={
                "attachment_id": record.id,
                "filename": record.filename,
                "lifecycle_status": AttachmentLifecycleStatus.purged.value,
                "storage_deleted": storage_deleted,
            },
        )

    def reply(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: ReplyRequest,
        market_id: str,
    ) -> TimelineEvent:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        event_type = (
            TimelineEventType.public_reply if request.public else TimelineEventType.internal_note
        )
        event = _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=event_type,
            channel=request.channel,
            actor=request.actor,
            body=request.body,
            public=request.public,
        )
        if request.public:
            timeline_record = db.get(TimelineEventRecord, event.id)
            if timeline_record is None:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Timeline event missing")
            outbound_message = outbound_repository.queue_reply(
                db,
                state,
                ticket=ticket_record,
                timeline_event=timeline_record,
                provider=request.channel,
                actor=request.actor,
                body=request.body,
                idempotency_key=request.idempotency_key,
            )
            outbound_repository.process_message(
                db,
                state,
                outbound_message.id,
                market_id,
                actor="outbound-queue",
            )
            db.flush()
            event = timeline_event_from_record(timeline_record)
        db.commit()
        return event

    def portal_customer_reply(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
        *,
        actor: str,
        body: str,
        submitted_by: str,
    ) -> TimelineEvent:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        previous_status = ticket_record.status
        event = _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.inbound,
            channel=ChannelType.portal,
            actor=actor,
            body=body,
            public=True,
            metadata={"source": "portal", "submitted_by": submitted_by},
        )
        if previous_status != TicketStatus.open.value:
            ticket_record.status = TicketStatus.open.value
            _add_timeline_record(
                db,
                state,
                ticket_record,
                event_type=TimelineEventType.status_change,
                channel=ChannelType.internal,
                actor="customer-portal",
                body=f"Customer replied in the portal; ticket moved from {previous_status} to open.",
                public=False,
                metadata={"previous_status": previous_status, "new_status": TicketStatus.open.value},
            )
        ticket_record.tags = sorted(set(ticket_record.tags or []) | {"portal", "customer-replied"})
        ticket_record.updated_at = utc_now()
        _audit(
            db,
            state,
            actor="customer-portal",
            action="ticket.portal_reply",
            entity_type="ticket",
            entity_id=ticket_id,
            market_id=market_id,
            details={
                "previous_status": previous_status,
                "new_status": ticket_record.status,
                "submitted_by": submitted_by,
            },
        )
        db.commit()
        db.refresh(ticket_record)
        _sync_ticket(db, state, ticket_record)
        return event

    def create_handoff(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        request: CreateHandoffRequest,
        market_id: str,
    ) -> Handoff:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        handoff_record = HandoffRecord(
            id=_new_id("handoff"),
            market_id=market_id,
            ticket_id=ticket_id,
            from_team=ticket_record.team,
            to_team=request.to_team,
            requested_by=request.requested_by,
            reason=request.reason,
            due_at=utc_now() + timedelta(minutes=request.due_minutes),
            checklist=[_task(item).model_dump(mode="json") for item in request.checklist],
        )
        db.add(handoff_record)
        db.flush()
        receiving_group = db.scalar(
            select(SupportGroupRecord).where(
                SupportGroupRecord.market_id == market_id,
                SupportGroupRecord.name == request.to_team,
                SupportGroupRecord.active.is_(True),
            )
        )
        team_email = (receiving_group.team_email or "").strip() if receiving_group else ""
        case_context = _handoff_forward_body(
            db,
            state,
            ticket=ticket_record,
            handoff=handoff_record,
            to_email=team_email or "not configured",
        )
        linked_ticket_record = _create_linked_handoff_ticket(
            db,
            state,
            source_ticket=ticket_record,
            handoff=handoff_record,
            case_context=case_context,
        )
        handoff_record.linked_ticket_id = linked_ticket_record.id
        handoff = handoff_from_record(handoff_record)
        state.handoffs[handoff.id] = handoff
        event = _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.handoff_requested,
            channel=ChannelType.internal,
            actor=request.requested_by,
            body=f"Handoff requested for {request.to_team}: {request.reason}",
            public=False,
            metadata={
                "handoff_id": handoff.id,
                "linked_ticket_id": linked_ticket_record.id,
                "linked_ticket_public_id": linked_ticket_record.public_id,
                "handoff_forward_status": "pending",
            },
        )
        timeline_record = db.get(TimelineEventRecord, event.id)
        if timeline_record is not None and team_email:
            outbound_repository.queue_handoff_forward(
                db,
                state,
                ticket=ticket_record,
                timeline_event=timeline_record,
                handoff_id=handoff_record.id,
                to_team=handoff_record.to_team,
                to_email=team_email,
                actor=request.requested_by,
                subject=_handoff_forward_subject(
                    ticket_record,
                    handoff_record.to_team,
                    linked_ticket_record.public_id,
                ),
                body=case_context,
                linked_ticket_id=linked_ticket_record.id,
                linked_ticket_public_id=linked_ticket_record.public_id,
            )
        else:
            if timeline_record is not None:
                timeline_record.event_metadata = {
                    **timeline_record.event_metadata,
                    "handoff_forward_status": "skipped",
                    "handoff_forward_reason": "team_email_not_configured",
                }
            _audit(
                db,
                state,
                actor=request.requested_by,
                action="handoff.forward.skip",
                entity_type="handoff",
                entity_id=handoff_record.id,
                market_id=market_id,
                details={
                    "ticket_id": ticket_id,
                    "to_team": request.to_team,
                    "reason": "team_email_not_configured",
                },
            )
        db.commit()
        db.refresh(handoff_record)
        handoff = handoff_from_record(handoff_record)
        state.handoffs[handoff.id] = handoff
        return handoff

    def list_handoffs(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[Handoff]:
        handoffs = [
            handoff_from_record(record)
            for record in db.scalars(
                select(HandoffRecord)
                .where(HandoffRecord.market_id == market_id)
                .order_by(HandoffRecord.updated_at.desc())
            ).all()
        ]
        state.handoffs = {
            **{key: value for key, value in state.handoffs.items() if value.market_id != market_id},
            **{handoff.id: handoff for handoff in handoffs},
        }
        return handoffs

    def update_handoff(
        self,
        db: Session,
        state: InMemoryStore,
        handoff_id: str,
        request: UpdateHandoffRequest,
        market_id: str,
    ) -> Handoff:
        handoff_record = db.get(HandoffRecord, handoff_id)
        if handoff_record is None or handoff_record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Handoff not found")
        status_was = handoff_record.status
        if request.status is not None:
            handoff_record.status = request.status.value
        if request.due_at is not None:
            handoff_record.due_at = request.due_at
        if request.blocker is not None:
            handoff_record.blocker = request.blocker
            handoff_record.status = HandoffStatus.blocked.value
        if request.checklist_item_id and request.checklist_item_complete is not None:
            checklist = [dict(item) for item in handoff_record.checklist]
            for item in checklist:
                if item["id"] == request.checklist_item_id:
                    item["complete"] = request.checklist_item_complete
                    break
            handoff_record.checklist = checklist
        handoff_record.updated_at = utc_now()
        ticket_record = _ticket_record_or_404(db, handoff_record.ticket_id, market_id)
        event_type = TimelineEventType.status_change
        if handoff_record.status == HandoffStatus.accepted.value:
            event_type = TimelineEventType.handoff_accepted
        elif handoff_record.status == HandoffStatus.resolved.value:
            event_type = TimelineEventType.handoff_resolved
        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=event_type,
            channel=ChannelType.internal,
            actor="handoff-service",
            body=f"Handoff {handoff_record.status}: {handoff_record.to_team}",
            public=False,
            metadata={
                "handoff_id": handoff_record.id,
                "blocker": handoff_record.blocker,
                "status_was": status_was,
                "due_at": handoff_record.due_at.isoformat(),
            },
        )
        db.commit()
        db.refresh(handoff_record)
        handoff = handoff_from_record(handoff_record)
        state.handoffs[handoff.id] = handoff
        return handoff

    def list_connector_events(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[ConnectorEvent]:
        events = [
            connector_event_from_record(record)
            for record in db.scalars(
                select(ConnectorEventRecord)
                .where(ConnectorEventRecord.market_id == market_id)
                .order_by(ConnectorEventRecord.created_at.asc())
            ).all()
        ]
        state.connector_events = {
            **{
                key: value
                for key, value in state.connector_events.items()
                if value.market_id != market_id
            },
            **{event.id: event for event in events},
        }
        return events

    def ingest_connector(
        self,
        db: Session,
        state: InMemoryStore,
        request: ConnectorInboundRequest,
        market_id: str,
        *,
        ai_enabled: bool,
    ) -> dict:
        existing_record = db.scalar(
            select(ConnectorEventRecord).where(
                ConnectorEventRecord.market_id == market_id,
                ConnectorEventRecord.provider == request.provider.value,
                ConnectorEventRecord.external_id == request.external_id,
            )
        )
        if existing_record is not None:
            if existing_record.ticket_id is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Connector event was seen before but ticket is unavailable",
                )
            ticket_record = _ticket_record_or_404(db, existing_record.ticket_id, market_id)
            ticket = _sync_ticket(db, state, ticket_record)
            connector_event = connector_event_from_record(existing_record)
            state.connector_events[connector_event.id] = connector_event
            db.commit()
            return {
                "deduplicated": True,
                "ticket": ticket,
                "connector_event": connector_event,
            }

        thread_target, thread_match = _thread_target_from_request(
            db,
            market_id=market_id,
            request=request,
        )
        if thread_target is not None:
            return _append_threaded_connector_reply(
                db,
                state,
                target_ticket=thread_target,
                request=request,
                match=thread_match,
                market_id=market_id,
            )

        customer_record = db.scalar(
            select(CustomerRecord).where(
                CustomerRecord.market_id == market_id,
                CustomerRecord.email == str(request.customer_email),
            )
        )
        if customer_record is None:
            customer_record = CustomerRecord(
                id=_new_id("customer"),
                market_id=market_id,
                name=request.customer_name,
                email=str(request.customer_email),
                preferred_channels=[request.provider.value],
                contact_points=[
                    {
                        "channel": request.provider.value,
                        "value": request.handle or str(request.customer_email),
                        "verified": True,
                    }
                ],
                tags=["connector-intake"],
                notes=f"Created from {request.provider.value} connector intake.",
            )
            db.add(customer_record)
            db.flush()
            customer = customer_from_record(customer_record)
            state.customers[customer.id] = customer
            _audit(
                db,
                state,
                actor="connector-service",
                action="customer.create_from_connector",
                entity_type="customer",
                entity_id=customer.id,
                market_id=market_id,
                details={"provider": request.provider.value},
            )
        else:
            preferred_channels = list(customer_record.preferred_channels)
            if request.provider.value not in preferred_channels:
                preferred_channels.append(request.provider.value)
                customer_record.preferred_channels = preferred_channels
            contact_points = list(customer_record.contact_points)
            contact_value = request.handle or str(request.customer_email)
            if not any(
                point.get("channel") == request.provider.value
                and point.get("value") == contact_value
                for point in contact_points
            ):
                contact_points.append(
                    {
                        "channel": request.provider.value,
                        "value": contact_value,
                        "verified": True,
                    }
                )
                customer_record.contact_points = contact_points
            customer = customer_from_record(customer_record)
            state.customers[customer.id] = customer

        ticket = self.create_ticket(
            db,
            state,
            CreateTicketRequest(
                subject=request.subject,
                description=request.body,
                customer_id=customer_record.id,
                channel=request.provider,
                external_id=request.external_id,
                tags=["connector-intake"],
            ),
            market_id,
            ai_enabled=ai_enabled,
        )
        ticket_record = _ticket_record_or_404(db, ticket.id, market_id)
        connector_record = ConnectorEventRecord(
            id=_new_id("connector"),
            market_id=market_id,
            provider=request.provider.value,
            direction=ConnectorDirection.inbound.value,
            external_id=request.external_id,
            ticket_id=ticket.id,
            status="ticket-created",
            payload=request.model_dump(mode="json"),
        )
        db.add(connector_record)
        db.flush()
        connector_event = connector_event_from_record(connector_record)
        state.connector_events[connector_event.id] = connector_event
        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.connector_receipt,
            channel=request.provider,
            actor=f"{request.provider.value} connector",
            body=f"Inbound {request.provider.value} event received and linked.",
            public=False,
            metadata={
                "connector_event_id": connector_event.id,
                "external_id": request.external_id,
            },
        )
        _audit(
            db,
            state,
            actor="connector-service",
            action="connector.ingest",
            entity_type="connector_event",
            entity_id=connector_event.id,
            market_id=market_id,
            details={
                "provider": request.provider.value,
                "ticket_id": ticket.id,
                "deduplicated": False,
            },
        )
        db.commit()
        db.refresh(ticket_record)
        return {
            "deduplicated": False,
            "ticket": _sync_ticket(db, state, ticket_record),
            "connector_event": connector_event,
        }


ticket_repository = TicketRepository()


def _next_public_case_id(db: Session) -> str:
    public_ids = db.scalars(select(CaseRecord.public_id)).all()
    numbers = [
        int(public_id.split("-")[-1])
        for public_id in public_ids
        if public_id.startswith("CASE-") and public_id.split("-")[-1].isdigit()
    ]
    return f"CASE-{max(numbers, default=1000) + 1}"


def _case_record_or_404(db: Session, case_id: str, market_id: str) -> CaseRecord:
    record = db.get(CaseRecord, case_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    return record


class CaseRepository:
    """Cases group multiple tickets (across channels) for one customer."""

    def list_cases(self, db: Session, market_id: str) -> list[Case]:
        records = db.scalars(
            select(CaseRecord)
            .where(CaseRecord.market_id == market_id)
            .order_by(CaseRecord.updated_at.desc())
        ).all()
        tickets_by_case: dict[str, list[TicketRecord]] = {}
        for ticket in db.scalars(
            select(TicketRecord).where(
                TicketRecord.market_id == market_id,
                TicketRecord.case_id.is_not(None),
            )
        ).all():
            if ticket.case_id is not None:
                tickets_by_case.setdefault(ticket.case_id, []).append(ticket)
        return [case_from_record(record, tickets_by_case.get(record.id, [])) for record in records]

    def get_case(self, db: Session, market_id: str, case_id: str) -> Case:
        record = _case_record_or_404(db, case_id, market_id)
        tickets = list(
            db.scalars(
                select(TicketRecord).where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.case_id == case_id,
                )
            ).all()
        )
        return case_from_record(record, tickets)

    def create_case(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        payload: CreateCaseRequest,
        actor: str,
    ) -> Case:
        customer = _customer_record_or_404(db, payload.customer_id, market_id)
        record = CaseRecord(
            id=_new_id("case"),
            market_id=market_id,
            public_id=_next_public_case_id(db),
            customer_id=customer.id,
            title=payload.title.strip(),
            status=CaseStatus.open.value,
            priority=payload.priority.value,
            summary=payload.summary.strip(),
            opened_by=(payload.opened_by or actor).strip(),
        )
        db.add(record)
        db.flush()
        attached: list[TicketRecord] = []
        for ticket_id in payload.ticket_ids:
            ticket = _ticket_record_or_404(db, ticket_id, market_id)
            self._link_ticket(db, state, record, ticket, actor)
            attached.append(ticket)
        record.updated_at = utc_now()
        db.flush()
        self._audit_case(
            db, state, record, actor, "case.create", {"ticket_ids": [t.id for t in attached]}
        )
        db.commit()
        return case_from_record(record, attached)

    def update_case(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        case_id: str,
        payload: UpdateCaseRequest,
        actor: str,
    ) -> Case:
        record = _case_record_or_404(db, case_id, market_id)
        changes: dict[str, object] = {}
        if payload.title is not None:
            record.title = payload.title.strip()
            changes["title"] = record.title
        if payload.status is not None:
            record.status = payload.status.value
            changes["status"] = record.status
        if payload.priority is not None:
            record.priority = payload.priority.value
            changes["priority"] = record.priority
        if payload.summary is not None:
            record.summary = payload.summary.strip()
            changes["summary"] = record.summary
        record.updated_at = utc_now()
        db.flush()
        self._audit_case(db, state, record, actor, "case.update", changes)
        db.commit()
        return self.get_case(db, market_id, case_id)

    def attach_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        case_id: str,
        ticket_id: str,
        actor: str,
    ) -> Case:
        record = _case_record_or_404(db, case_id, market_id)
        ticket = _ticket_record_or_404(db, ticket_id, market_id)
        self._link_ticket(db, state, record, ticket, actor)
        record.updated_at = utc_now()
        db.flush()
        self._audit_case(db, state, record, actor, "case.attach_ticket", {"ticket_id": ticket.id})
        db.commit()
        return self.get_case(db, market_id, case_id)

    def detach_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        case_id: str,
        ticket_id: str,
        actor: str,
    ) -> Case:
        record = _case_record_or_404(db, case_id, market_id)
        ticket = _ticket_record_or_404(db, ticket_id, market_id)
        if ticket.case_id == record.id:
            ticket.case_id = None
            _add_timeline_record(
                db,
                state,
                ticket,
                event_type=TimelineEventType.internal_note,
                channel=ChannelType(ticket.channel),
                actor=actor,
                body=f"Unlinked from case {record.public_id}.",
                public=False,
            )
        record.updated_at = utc_now()
        db.flush()
        self._audit_case(db, state, record, actor, "case.detach_ticket", {"ticket_id": ticket.id})
        db.commit()
        return self.get_case(db, market_id, case_id)

    def _link_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        record: CaseRecord,
        ticket: TicketRecord,
        actor: str,
    ) -> None:
        if ticket.customer_id != record.customer_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Ticket belongs to a different customer than the case",
            )
        if ticket.case_id == record.id:
            return
        ticket.case_id = record.id
        _add_timeline_record(
            db,
            state,
            ticket,
            event_type=TimelineEventType.internal_note,
            channel=ChannelType(ticket.channel),
            actor=actor,
            body=f"Linked to case {record.public_id}: {record.title}.",
            public=False,
        )

    def _audit_case(
        self,
        db: Session,
        state: InMemoryStore,
        record: CaseRecord,
        actor: str,
        action: str,
        details: dict,
    ) -> None:
        _audit(
            db,
            state,
            actor=actor,
            action=action,
            entity_type="case",
            entity_id=record.id,
            market_id=record.market_id,
            details=details,
        )


case_repository = CaseRepository()
