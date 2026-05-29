from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore, store
from app.core.passwords import hash_password
from app.db.models import (
    AgentRecord,
    AiDecisionRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    Base,
    ChannelRecord,
    ConnectorAccountRecord,
    CompanyRecord,
    ConnectorEventRecord,
    CustomerRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    MarketRecord,
    TicketRecord,
    TimelineEventRecord,
    UserRecord,
    WorkspaceSettingsRecord,
)
from app.db.session import get_engine
from app.db.store_sync import hydrate_store_state


def _payload(model: object) -> dict:
    data = model.model_dump(mode="json")  # type: ignore[attr-defined]
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return data


def create_schema(engine: Engine | None = None) -> None:
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)


def table_names(engine: Engine | None = None) -> list[str]:
    target_engine = engine or get_engine()
    return sorted(inspect(target_engine).get_table_names())


CONNECTOR_ACCOUNT_DEFAULTS: dict[str, dict] = {
    "email": {
        "status": "connected",
        "required_credentials": ["Mailbox OAuth or IMAP credentials", "SMTP or provider send API"],
        "capabilities": ["inbound sync", "outbound send", "thread mapping", "attachments"],
        "outbound_enabled": True,
        "webhook_verified": True,
        "secret_configured": True,
        "credential_ref": "local-dev:mailbox",
    },
    "whatsapp": {
        "status": "pending_credentials",
        "required_credentials": ["WhatsApp Business API token", "verified phone number", "message templates"],
        "capabilities": ["webhook intake", "template replies", "media", "delivery receipts"],
    },
    "facebook": {
        "status": "pending_credentials",
        "required_credentials": ["Meta app", "page access token", "webhook subscription"],
        "capabilities": ["Messenger DMs", "private replies", "delivery receipts"],
    },
    "instagram": {
        "status": "action_required",
        "required_credentials": ["Meta app", "Instagram business account", "webhook subscription"],
        "capabilities": ["Instagram DM", "comment-to-DM handoff", "media"],
        "last_error": "Business account review is required before live DM sync.",
        "failure_count": 1,
    },
    "sms": {
        "status": "pending_credentials",
        "required_credentials": ["SMS provider account", "sender ID", "delivery callback secret"],
        "capabilities": ["inbound text", "outbound text", "delivery receipts"],
    },
    "voice": {
        "status": "pending_credentials",
        "required_credentials": ["Voice provider account", "call webhook secret", "recording storage policy"],
        "capabilities": ["call logs", "callback requests", "voicemail summaries"],
    },
}


def _connector_identifier(market: MarketRecord, provider: str) -> str:
    if provider == "email":
        return market.support_email
    if provider == "whatsapp":
        return market.whatsapp_number or ""
    if provider == "facebook":
        return market.facebook_page or ""
    if provider == "instagram":
        return market.instagram_handle or ""
    if provider == "sms":
        return f"{market.code} sender ID pending"
    if provider == "voice":
        return f"{market.code} voice line pending"
    return ""


def seed_connector_accounts(session: Session) -> None:
    markets = session.scalars(select(MarketRecord)).all()
    for market in markets:
        for provider, defaults in CONNECTOR_ACCOUNT_DEFAULTS.items():
            existing = session.scalar(
                select(ConnectorAccountRecord).where(
                    ConnectorAccountRecord.market_id == market.id,
                    ConnectorAccountRecord.provider == provider,
                )
            )
            if existing is not None:
                continue
            account = ConnectorAccountRecord(
                id=f"connector-{market.code.lower()}-{provider}",
                market_id=market.id,
                provider=provider,
                display_name=f"{market.name} {provider.replace('_', ' ').title()}",
                account_identifier=_connector_identifier(market, provider),
                status=defaults["status"],
                intake_enabled=defaults.get("status") not in {"disabled", "error"},
                outbound_enabled=defaults.get("outbound_enabled", False),
                webhook_url=f"/api/v1/webhooks/{provider}/{market.code.lower()}",
                webhook_verified=defaults.get("webhook_verified", False),
                credential_ref=defaults.get("credential_ref"),
                secret_configured=defaults.get("secret_configured", False),
                last_error=defaults.get("last_error"),
                failure_count=defaults.get("failure_count", 0),
                required_credentials=defaults["required_credentials"],
                capabilities=defaults["capabilities"],
            )
            session.add(account)
    session.commit()


def seed_reference_data(session: Session, source: InMemoryStore = store) -> None:
    if session.scalar(select(MarketRecord.id).limit(1)):
        seed_connector_accounts(session)
        return

    session.add_all(
        [
            MarketRecord(**_payload(market))
            for market in source.markets.values()
        ]
    )
    session.flush()
    user_records = []
    for user in source.users.values():
        payload = _payload(user)
        payload["password_hash"] = hash_password("omni-demo")
        payload["password_reset_required"] = False
        user_records.append(UserRecord(**payload))
    session.add_all(user_records)
    session.add_all(
        [
            WorkspaceSettingsRecord(**_payload(settings))
            for settings in source.settings_by_market.values()
        ]
    )
    session.add_all(
        [
            ChannelRecord(**_payload(channel))
            for channel in source.channels.values()
        ]
    )
    session.add_all(
        [
            AgentRecord(
                id=agent.id,
                market_ids=agent.market_ids,
                name=agent.name,
                email=str(agent.email),
                role=agent.team,
                status=agent.status.value,
                occupancy=agent.occupancy,
                capacity=agent.capacity,
                skills=[skill.value for skill in agent.skills],
                languages=agent.languages,
            )
            for agent in source.agents.values()
        ]
    )
    session.add_all(
        [
            CompanyRecord(**_payload(company))
            for company in source.companies.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            CustomerRecord(**_payload(customer))
            for customer in source.customers.values()
        ]
    )
    session.add_all(
        [
            KnowledgeArticleRecord(**_payload(article))
            for article in source.knowledge.values()
        ]
    )
    session.add_all(
        [
            AutomationRuleRecord(**_payload(rule))
            for rule in source.rules.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            TicketRecord(**_payload(ticket))
            for ticket in source.tickets.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            TimelineEventRecord(
                **{key: value for key, value in payload.items() if key != "metadata"},
                market_id=source.tickets[event.ticket_id].market_id,
                event_metadata=payload["metadata"],
            )
            for events in source.timeline.values()
            for event in events
            for payload in [_payload(event)]
        ]
    )
    session.add_all(
        [
            HandoffRecord(**_payload(handoff))
            for handoff in source.handoffs.values()
        ]
    )
    session.add_all(
        [
            ConnectorEventRecord(**_payload(event))
            for event in source.connector_events.values()
        ]
    )
    session.flush()
    seed_connector_accounts(session)
    session.add_all(
        [
            AiDecisionRecord(
                id=decision.id,
                market_id=source.tickets[decision.ticket_id].market_id,
                ticket_id=decision.ticket_id,
                decision_type=decision.decision_type,
                confidence=int(round(decision.confidence * 100)),
                summary=decision.summary,
                model_version=decision.model_version,
                input_reference=decision.input_reference,
                override_allowed=decision.override_allowed,
                created_at=decision.created_at,
            )
            for decision in source.ai_decisions
        ]
    )
    session.add_all(
        [
            AuditEventRecord(**_payload(event))
            for event in source.audit
        ]
    )
    session.commit()


def initialize_database(engine: Engine | None = None) -> None:
    target_engine = engine or get_engine()
    create_schema(target_engine)
    with Session(target_engine) as session:
        seed_reference_data(session)
        hydrate_store_state(session, store)


def reset_database(engine: Engine | None = None, source: InMemoryStore = store) -> None:
    target_engine = engine or get_engine()
    Base.metadata.drop_all(bind=target_engine)
    create_schema(target_engine)
    with Session(target_engine) as session:
        seed_reference_data(session, source)
        hydrate_store_state(session, source)
