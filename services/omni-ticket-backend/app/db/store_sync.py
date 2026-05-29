from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    ai_decision_from_record,
    audit_event_from_record,
    automation_rule_from_record,
    channel_from_record,
    company_from_record,
    connector_event_from_record,
    customer_from_record,
    handoff_from_record,
    knowledge_article_from_record,
    market_from_record,
    outbound_message_from_record,
    ticket_from_record,
    timeline_event_from_record,
    user_from_record,
    workspace_settings_from_record,
)
from app.db.models import (
    AgentRecord,
    AiDecisionRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    ChannelRecord,
    CompanyRecord,
    ConnectorEventRecord,
    CustomerRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    MarketRecord,
    OutboundMessageRecord,
    SessionRecord,
    TicketRecord,
    TimelineEventRecord,
    UserRecord,
    WorkspaceSettingsRecord,
)


def _merge_record(db: Session, record_cls: type, payload: dict) -> None:
    db.merge(record_cls(**payload))


def persist_store_state(db: Session, state: InMemoryStore) -> None:
    for market in state.markets.values():
        _merge_record(db, MarketRecord, market.model_dump(mode="json"))
    for user in state.users.values():
        _merge_record(db, UserRecord, user.model_dump(mode="json"))
    for settings in state.settings_by_market.values():
        _merge_record(db, WorkspaceSettingsRecord, settings.model_dump(mode="json"))
    for channel in state.channels.values():
        _merge_record(db, ChannelRecord, channel.model_dump(mode="json"))
    for agent in state.agents.values():
        _merge_record(
            db,
            AgentRecord,
            {
                "id": agent.id,
                "market_ids": agent.market_ids,
                "name": agent.name,
                "email": str(agent.email),
                "role": agent.team,
                "status": agent.status.value,
                "occupancy": agent.occupancy,
                "capacity": agent.capacity,
                "skills": [skill.value for skill in agent.skills],
                "languages": agent.languages,
            },
        )
    for company in state.companies.values():
        _merge_record(db, CompanyRecord, company.model_dump(mode="json"))
    for customer in state.customers.values():
        _merge_record(db, CustomerRecord, customer.model_dump(mode="json"))
    for ticket in state.tickets.values():
        payload = ticket.model_dump(mode="json")
        payload["created_at"] = ticket.created_at
        payload["updated_at"] = ticket.updated_at
        _merge_record(db, TicketRecord, payload)
    for events in state.timeline.values():
        for event in events:
            payload = event.model_dump(mode="json")
            payload["event_metadata"] = payload.pop("metadata")
            payload["market_id"] = state.tickets[event.ticket_id].market_id
            payload["created_at"] = event.created_at
            _merge_record(db, TimelineEventRecord, payload)
    for handoff in state.handoffs.values():
        payload = handoff.model_dump(mode="json")
        payload["due_at"] = handoff.due_at
        payload["created_at"] = handoff.created_at
        payload["updated_at"] = handoff.updated_at
        _merge_record(db, HandoffRecord, payload)
    for article in state.knowledge.values():
        payload = article.model_dump(mode="json")
        payload.pop("updated_at", None)
        _merge_record(db, KnowledgeArticleRecord, payload)
    for rule in state.rules.values():
        payload = rule.model_dump(mode="json")
        payload["last_fired_at"] = rule.last_fired_at
        _merge_record(db, AutomationRuleRecord, payload)
    for connector_event in state.connector_events.values():
        payload = connector_event.model_dump(mode="json")
        payload["created_at"] = connector_event.created_at
        _merge_record(db, ConnectorEventRecord, payload)
    for outbound_message in state.outbound_messages.values():
        payload = outbound_message.model_dump(mode="json")
        payload["next_attempt_at"] = outbound_message.next_attempt_at
        payload["sent_at"] = outbound_message.sent_at
        payload["created_at"] = outbound_message.created_at
        payload["updated_at"] = outbound_message.updated_at
        _merge_record(db, OutboundMessageRecord, payload)
    for decision in state.ai_decisions:
        _merge_record(
            db,
            AiDecisionRecord,
            {
                "id": decision.id,
                "market_id": state.tickets[decision.ticket_id].market_id,
                "ticket_id": decision.ticket_id,
                "decision_type": decision.decision_type,
                "confidence": int(round(decision.confidence * 100)),
                "summary": decision.summary,
                "model_version": decision.model_version,
                "input_reference": decision.input_reference,
                "override_allowed": decision.override_allowed,
                "created_at": decision.created_at,
            },
        )
    for audit_event in state.audit:
        payload = audit_event.model_dump(mode="json")
        payload["created_at"] = audit_event.created_at
        _merge_record(db, AuditEventRecord, payload)
    db.commit()


def hydrate_store_state(db: Session, state: InMemoryStore) -> None:
    state.markets = {
        market.id: market_from_record(market) for market in db.scalars(select(MarketRecord)).all()
    }
    state.users = {user.id: user_from_record(user) for user in db.scalars(select(UserRecord)).all()}
    state.channels = {
        channel.id: channel_from_record(channel) for channel in db.scalars(select(ChannelRecord)).all()
    }
    state.agents = {
        agent.id: agent_from_record(agent) for agent in db.scalars(select(AgentRecord)).all()
    }
    state.companies = {
        company.id: company_from_record(company) for company in db.scalars(select(CompanyRecord)).all()
    }
    state.customers = {
        customer.id: customer_from_record(customer)
        for customer in db.scalars(select(CustomerRecord)).all()
    }
    state.tickets = {
        ticket.id: ticket_from_record(ticket) for ticket in db.scalars(select(TicketRecord)).all()
    }
    timeline_records = db.scalars(
        select(TimelineEventRecord).order_by(TimelineEventRecord.created_at.asc())
    ).all()
    state.timeline = {}
    for record in timeline_records:
        event = timeline_event_from_record(record)
        state.timeline.setdefault(event.ticket_id, []).append(event)
    state.handoffs = {
        handoff.id: handoff_from_record(handoff) for handoff in db.scalars(select(HandoffRecord)).all()
    }
    state.knowledge = {
        article.id: knowledge_article_from_record(article)
        for article in db.scalars(select(KnowledgeArticleRecord)).all()
    }
    state.rules = {
        rule.id: automation_rule_from_record(rule)
        for rule in db.scalars(select(AutomationRuleRecord)).all()
    }
    state.connector_events = {
        event.id: connector_event_from_record(event)
        for event in db.scalars(select(ConnectorEventRecord)).all()
    }
    state.outbound_messages = {
        message.id: outbound_message_from_record(message)
        for message in db.scalars(select(OutboundMessageRecord)).all()
    }
    state.ai_decisions = [
        ai_decision_from_record(decision) for decision in db.scalars(select(AiDecisionRecord)).all()
    ]
    state.audit = [
        audit_event_from_record(event)
        for event in db.scalars(select(AuditEventRecord).order_by(AuditEventRecord.created_at.asc())).all()
    ]
    state.settings_by_market = {
        settings.market_id: workspace_settings_from_record(settings)
        for settings in db.scalars(select(WorkspaceSettingsRecord)).all()
    }
    state.settings = state.settings_by_market.get("market-ng", state.settings)
    state.sessions = {
        session.token: session.user_id for session in db.scalars(select(SessionRecord)).all()
    }
    public_numbers = [
        int(ticket.public_id.split("-")[-1])
        for ticket in state.tickets.values()
        if ticket.public_id.startswith("OMNI-") and ticket.public_id.split("-")[-1].isdigit()
    ]
    state._ticket_sequence = max(public_numbers, default=1000)
