from fastapi import HTTPException, status

from app.core.store import InMemoryStore, store
from app.models.domain import (
    AppendEventRequest,
    ChannelType,
    ConnectorDirection,
    CreateTicketRequest,
    Priority,
    ReplyRequest,
    Ticket,
    TimelineEvent,
    TimelineEventType,
    UpdateTicketRequest,
    default_sla,
    utc_now,
)
from app.services.ai import automation_service
from app.services.sla import sla_service


class TicketService:
    def list_tickets(
        self,
        state: InMemoryStore,
        *,
        market_id: str | None = None,
        status_filter: str | None = None,
        channel: ChannelType | None = None,
        priority: Priority | None = None,
        customer_id: str | None = None,
    ) -> list[Ticket]:
        tickets = list(state.tickets.values())
        for ticket in tickets:
            ticket.sla = sla_service.refresh(ticket.sla)
        if market_id:
            tickets = [ticket for ticket in tickets if ticket.market_id == market_id]
        if status_filter:
            tickets = [ticket for ticket in tickets if ticket.status == status_filter]
        if channel:
            tickets = [ticket for ticket in tickets if ticket.channel == channel]
        if priority:
            tickets = [ticket for ticket in tickets if ticket.priority == priority]
        if customer_id:
            tickets = [ticket for ticket in tickets if ticket.customer_id == customer_id]
        return sorted(tickets, key=lambda ticket: ticket.updated_at, reverse=True)

    def get_ticket(self, state: InMemoryStore, ticket_id: str, market_id: str | None = None) -> Ticket:
        ticket = state.tickets.get(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        if market_id and ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        ticket.sla = sla_service.refresh(ticket.sla)
        return ticket

    def get_ticket_context(
        self, state: InMemoryStore, ticket_id: str, market_id: str | None = None
    ) -> dict:
        ticket = self.get_ticket(state, ticket_id, market_id)
        return {
            "ticket": ticket,
            "customer": state.customers[ticket.customer_id],
            "company": state.companies.get(state.customers[ticket.customer_id].company_id or ""),
            "assignee": state.agents.get(ticket.assignee_id or ""),
            "timeline": state.timeline.get(ticket.id, []),
            "handoffs": [
                handoff for handoff in state.handoffs.values() if handoff.ticket_id == ticket.id
            ],
            "ai_decisions": [
                decision for decision in state.ai_decisions if decision.ticket_id == ticket.id
            ],
        }

    def create_ticket(
        self,
        state: InMemoryStore,
        request: CreateTicketRequest,
        market_id: str,
        *,
        ai_enabled: bool | None = None,
    ) -> Ticket:
        customer = state.customers.get(request.customer_id)
        if customer is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
        if customer.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found in market")

        text = f"{request.subject} {request.description}"
        if ai_enabled is None:
            ai_enabled = state.settings_for(market_id).ai_work_queue_automation_enabled
        priority = automation_service.classify_priority(text, request.priority)
        sentiment = automation_service.classify_sentiment(text)
        tags = automation_service.classify_tags(text, request.channel, request.tags)
        assignee = automation_service.choose_agent(state, request.channel, market_id) if ai_enabled else None
        team = assignee.team if assignee else "Unassigned"
        if ai_enabled:
            tags = sorted(set(tags) | {"ai-routed"})

        ticket = state.create_ticket_record(
            subject=request.subject,
            market_id=market_id,
            description=request.description,
            customer_id=request.customer_id,
            channel=request.channel,
            priority=priority,
            sentiment=sentiment,
            assignee_id=assignee.id if assignee else None,
            team=team,
            tags=tags,
            ai_summary="",
            recommended_action="",
        )
        ticket.sla = default_sla(ticket.priority)
        ticket.sla = sla_service.refresh(ticket.sla)
        ticket.ai_summary = automation_service.summary(ticket, customer)
        ticket.recommended_action = automation_service.recommended_action(ticket, customer)

        state.append_timeline(
            TimelineEvent(
                id=state.next_id("event"),
                ticket_id=ticket.id,
                type=TimelineEventType.inbound,
                channel=request.channel,
                actor=customer.name,
                body=request.description,
                public=True,
                metadata={"external_id": request.external_id},
            )
        )
        if ai_enabled:
            decision = automation_service.make_decision(ticket)
            state.ai_decisions.append(decision)
            state.append_timeline(
                TimelineEvent(
                    id=state.next_id("event"),
                    ticket_id=ticket.id,
                    type=TimelineEventType.ai_decision,
                    channel=ChannelType.internal,
                    actor="AI Work Queue",
                    body=decision.summary,
                    public=False,
                    metadata={"confidence": decision.confidence},
                )
            )
        state.audit_event(
            actor="api",
            action="ticket.create",
            entity_type="ticket",
            entity_id=ticket.id,
            market_id=market_id,
            details={"ai_enabled": ai_enabled, "channel": request.channel.value},
        )
        return ticket

    def update_ticket(
        self,
        state: InMemoryStore,
        ticket_id: str,
        request: UpdateTicketRequest,
        market_id: str | None = None,
    ) -> Ticket:
        ticket = self.get_ticket(state, ticket_id, market_id)
        patch = request.model_dump(exclude_unset=True)
        task_item_id = patch.pop("task_item_id", None)
        task_item_complete = patch.pop("task_item_complete", None)
        for key, value in patch.items():
            if value is not None:
                setattr(ticket, key, value)
        if task_item_id and task_item_complete is not None:
            for task in ticket.tasks:
                if task.id == task_item_id:
                    task.complete = task_item_complete
                    break
        ticket.updated_at = utc_now()
        state.append_timeline(
            TimelineEvent(
                id=state.next_id("event"),
                ticket_id=ticket.id,
                type=TimelineEventType.status_change,
                channel=ChannelType.internal,
                actor="api",
                body="Ticket fields updated.",
                public=False,
                metadata=patch,
            )
        )
        return ticket

    def append_event(
        self,
        state: InMemoryStore,
        ticket_id: str,
        request: AppendEventRequest,
        market_id: str | None = None,
    ) -> TimelineEvent:
        self.get_ticket(state, ticket_id, market_id)
        return state.append_timeline(
            TimelineEvent(
                id=state.next_id("event"),
                ticket_id=ticket_id,
                type=request.type,
                channel=request.channel,
                actor=request.actor,
                body=request.body,
                public=request.public,
                metadata=request.metadata,
            )
        )

    def reply(
        self, state: InMemoryStore, ticket_id: str, request: ReplyRequest, market_id: str | None = None
    ) -> TimelineEvent:
        ticket = self.get_ticket(state, ticket_id, market_id)
        event_type = (
            TimelineEventType.public_reply if request.public else TimelineEventType.internal_note
        )
        event = state.append_timeline(
            TimelineEvent(
                id=state.next_id("event"),
                ticket_id=ticket_id,
                type=event_type,
                channel=request.channel,
                actor=request.actor,
                body=request.body,
                public=request.public,
            )
        )
        state.record_connector_event(
            market_id=ticket.market_id,
            provider=request.channel,
            direction=ConnectorDirection.outbound,
            external_id=state.next_id("outbound"),
            ticket_id=ticket_id,
            status="queued" if request.public else "internal-only",
            payload={"body": request.body, "actor": request.actor},
        )
        return event


ticket_service = TicketService()


def get_store() -> InMemoryStore:
    return store
