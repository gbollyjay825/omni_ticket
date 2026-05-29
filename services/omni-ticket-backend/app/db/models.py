from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.domain import utc_now


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MarketRecord(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    default_locale: Mapped[str] = mapped_column(String(16), default="en")
    support_email: Mapped[str] = mapped_column(String(255), nullable=False)
    whatsapp_number: Mapped[str | None] = mapped_column(String(64))
    facebook_page: Mapped[str | None] = mapped_column(String(160))
    instagram_handle: Mapped[str | None] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserRecord(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_reset_required: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    default_market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    market_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SessionRecord(TimestampMixin, Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceSettingsRecord(TimestampMixin, Base):
    __tablename__ = "workspace_settings"

    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    ai_work_queue_automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_can_send_customer_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    default_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    business_hours: Mapped[str] = mapped_column(String(120), default="Mon-Fri 08:00-18:00")
    public_brand_name: Mapped[str] = mapped_column(String(160), default="Omni Ticket")


class AgentRecord(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="available")
    occupancy: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=8)
    market_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)


class ChannelRecord(TimestampMixin, Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    health: Mapped[str] = mapped_column(String(32), default="healthy")
    queued: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[int] = mapped_column(Integer, default=0)
    sla_risk: Mapped[int] = mapped_column(Integer, default=0)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)


class CompanyRecord(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    tier: Mapped[str] = mapped_column(String(40), default="standard")
    health_score: Mapped[int] = mapped_column(Integer, default=75)
    account_value: Mapped[int] = mapped_column(Integer, default=0)


class CustomerRecord(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    location: Mapped[str] = mapped_column(String(180), default="")
    sentiment: Mapped[str] = mapped_column(String(32), default="neutral")
    preferred_channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    contact_points: Mapped[list[dict]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (UniqueConstraint("market_id", "email", name="uq_customer_market_email"),)


class TicketRecord(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(40), index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    sentiment: Mapped[str] = mapped_column(String(32), default="neutral")
    assignee_id: Mapped[str | None] = mapped_column(String(64), index=True)
    team: Mapped[str] = mapped_column(String(120), default="General Support")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    tasks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    sla: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")


class TimelineEventRecord(TimestampMixin, Base):
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class HandoffRecord(TimestampMixin, Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    from_team: Mapped[str] = mapped_column(String(120), nullable=False)
    to_team: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(180), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="requested")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checklist: Mapped[list[dict]] = mapped_column(JSON, default=list)
    blocker: Mapped[str | None] = mapped_column(Text)


class KnowledgeArticleRecord(TimestampMixin, Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    language: Mapped[str] = mapped_column(String(16), default="en")
    market_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    body: Mapped[str] = mapped_column(Text, default="")


class AutomationRuleRecord(TimestampMixin, Base):
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class ConnectorEventRecord(TimestampMixin, Base):
    __tablename__ = "connector_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(180), index=True)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id"))
    status: Mapped[str] = mapped_column(String(80), default="received")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("market_id", "provider", "external_id", name="uq_connector_market_event"),
    )


class ConnectorAccountRecord(TimestampMixin, Base):
    __tablename__ = "connector_accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    account_identifier: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="pending_credentials")
    intake_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_url: Mapped[str] = mapped_column(String(500), default="")
    webhook_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_ref: Mapped[str | None] = mapped_column(String(255))
    secret_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    required_credentials: Mapped[list[str]] = mapped_column(JSON, default=list)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint("market_id", "provider", name="uq_connector_account_market_provider"),
    )


class OutboundMessageRecord(TimestampMixin, Base):
    __tablename__ = "outbound_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    timeline_event_id: Mapped[str | None] = mapped_column(ForeignKey("timeline_events.id"))
    connector_event_id: Mapped[str | None] = mapped_column(ForeignKey("connector_events.id"))
    provider: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="queued")
    actor: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("market_id", "provider", "idempotency_key", name="uq_outbound_market_provider_key"),
    )


class RateLimitRecord(TimestampMixin, Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)


class AiDecisionRecord(TimestampMixin, Base):
    __tablename__ = "ai_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    model_version: Mapped[str] = mapped_column(String(80), default="rules-v1")
    input_reference: Mapped[str] = mapped_column(String(180), default="local-seed")
    override_allowed: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEventRecord(TimestampMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str | None] = mapped_column(ForeignKey("markets.id"), index=True)
    actor: Mapped[str] = mapped_column(String(180), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
