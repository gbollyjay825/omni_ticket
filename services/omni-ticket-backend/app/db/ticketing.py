from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    attachment_from_record,
    ai_decision_from_record,
    automation_rule_from_record,
    audit_event_from_record,
    company_from_record,
    connector_event_from_record,
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
    CompanyRecord,
    ConnectorEventRecord,
    CustomerRecord,
    HandoffRecord,
    OutboundMessageRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.outbound import outbound_repository
from app.models.domain import (
    AppendEventRequest,
    Attachment,
    AttachmentScanStatus,
    ChannelType,
    ConnectorEvent,
    ConnectorDirection,
    ConnectorInboundRequest,
    CreateHandoffRequest,
    CreateAttachmentRequest,
    CreateTicketRequest,
    Handoff,
    HandoffStatus,
    Priority,
    ReplyRequest,
    Ticket,
    TicketTask,
    TimelineEvent,
    TimelineEventType,
    UpdateHandoffRequest,
    UpdateTicketRequest,
    WorkQueueOverrideRequest,
    default_sla,
    utc_now,
)
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


def _trigger_channels(trigger: str) -> set[str]:
    return {channel.value for channel in ChannelType if channel.value in trigger}


def _trigger_sentiments(trigger: str) -> set[str]:
    return {"positive", "neutral", "frustrated", "angry"} & set(trigger.replace(",", " ").split())


DANGEROUS_ATTACHMENT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}


def _scan_attachment(filename: str, content_type: str) -> tuple[AttachmentScanStatus, str]:
    normalized = filename.strip().lower()
    suffix = f".{normalized.rsplit('.', 1)[-1]}" if "." in normalized else ""
    if suffix in DANGEROUS_ATTACHMENT_SUFFIXES:
        return (
            AttachmentScanStatus.blocked,
            f"Blocked because {suffix} files are not allowed in customer conversations.",
        )
    if content_type.strip().lower() in {"application/x-msdownload", "application/x-sh"}:
        return (
            AttachmentScanStatus.blocked,
            "Blocked because the content type is not allowed in customer conversations.",
        )
    return AttachmentScanStatus.clean, "Passed local metadata policy scan."


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
            ticket.sla = default_sla(Priority.urgent, ticket.created_at).model_dump(mode="json")
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


def _sync_ticket(db: Session, state: InMemoryStore, ticket: TicketRecord) -> Ticket:
    domain_ticket = ticket_from_record(ticket)
    domain_ticket.sla = sla_service.refresh(domain_ticket.sla)
    ticket.sla = domain_ticket.sla.model_dump(mode="json")
    state.tickets[domain_ticket.id] = domain_ticket
    return domain_ticket


class TicketRepository:
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
    ) -> list[Ticket]:
        query = select(TicketRecord).where(TicketRecord.market_id == market_id)
        if status_filter:
            query = query.where(TicketRecord.status == status_filter)
        if channel:
            query = query.where(TicketRecord.channel == channel.value)
        if priority:
            query = query.where(TicketRecord.priority == priority.value)
        if customer_id:
            query = query.where(TicketRecord.customer_id == customer_id)
        records = db.scalars(query.order_by(TicketRecord.updated_at.desc())).all()
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
        }

    def create_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateTicketRequest,
        market_id: str,
        *,
        ai_enabled: bool,
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
            tasks=[
                _task("Acknowledge customer"),
                _task("Clear blocker"),
                _task("Close promise"),
            ],
            sla=sla_service.refresh(default_sla(priority, now)),
            created_at=now,
            updated_at=now,
        )
        ticket.ai_summary = automation_service.summary(ticket, customer)
        ticket.recommended_action = automation_service.recommended_action(ticket, customer)
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
            ticket.ai_summary = automation_service.summary(ticket, customer)
            ticket.recommended_action = automation_service.recommended_action(ticket, customer)
            ticket_record.ai_summary = ticket.ai_summary
            ticket_record.recommended_action = ticket.recommended_action
        if ai_enabled:
            decision = automation_service.make_decision(ticket)
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
            actor="api",
            action="ticket.create",
            entity_type="ticket",
            entity_id=ticket.id,
            market_id=market_id,
            details={"ai_enabled": ai_enabled, "channel": request.channel.value},
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
        patch = request.model_dump(exclude_unset=True, mode="json")
        task_item_id = patch.pop("task_item_id", None)
        task_item_complete = patch.pop("task_item_complete", None)
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
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
        record.updated_at = utc_now()
        _add_timeline_record(
            db,
            state,
            record,
            event_type=TimelineEventType.status_change,
            channel=ChannelType.internal,
            actor="api",
            body="Ticket fields updated.",
            public=False,
            metadata=patch,
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
    ) -> Attachment:
        ticket_record = _ticket_record_or_404(db, ticket_id, market_id)
        filename = request.filename.strip()
        if not filename:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Attachment filename is required",
            )

        attachment_id = attachment_id or _new_id("attachment")
        scan_status, scan_result = _scan_attachment(filename, request.content_type)
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
        handoff = handoff_from_record(handoff_record)
        state.handoffs[handoff.id] = handoff
        _add_timeline_record(
            db,
            state,
            ticket_record,
            event_type=TimelineEventType.handoff_requested,
            channel=ChannelType.internal,
            actor=request.requested_by,
            body=f"Handoff requested for {request.to_team}: {request.reason}",
            public=False,
            metadata={"handoff_id": handoff.id},
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
