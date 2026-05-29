from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChannelType(StrEnum):
    email = "email"
    whatsapp = "whatsapp"
    facebook = "facebook"
    instagram = "instagram"
    sms = "sms"
    voice = "voice"
    portal = "portal"
    api = "api"
    internal = "internal"


class ChannelHealth(StrEnum):
    healthy = "healthy"
    degraded = "degraded"
    paused = "paused"


class TicketStatus(StrEnum):
    open = "open"
    pending = "pending"
    waiting = "waiting"
    solved = "solved"
    closed = "closed"


class Priority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Sentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    frustrated = "frustrated"
    angry = "angry"


class AgentStatus(StrEnum):
    available = "available"
    busy = "busy"
    away = "away"
    offline = "offline"


class TimelineEventType(StrEnum):
    inbound = "inbound"
    public_reply = "public_reply"
    internal_note = "internal_note"
    attachment_added = "attachment_added"
    handoff_requested = "handoff_requested"
    handoff_accepted = "handoff_accepted"
    handoff_resolved = "handoff_resolved"
    status_change = "status_change"
    ai_decision = "ai_decision"
    connector_receipt = "connector_receipt"


class HandoffStatus(StrEnum):
    requested = "requested"
    accepted = "accepted"
    blocked = "blocked"
    resolved = "resolved"
    cancelled = "cancelled"


class ConnectorDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class ConnectorAccountStatus(StrEnum):
    mocked = "mocked"
    connected = "connected"
    pending_credentials = "pending_credentials"
    action_required = "action_required"
    disabled = "disabled"
    error = "error"


class OutboundMessageStatus(StrEnum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    retrying = "retrying"
    dead_lettered = "dead_lettered"


class AttachmentScanStatus(StrEnum):
    pending = "pending"
    clean = "clean"
    blocked = "blocked"
    failed = "failed"


class UserRole(StrEnum):
    agent = "agent"
    supervisor = "supervisor"
    admin = "admin"
    auditor = "auditor"


class Market(BaseModel):
    id: str
    code: str
    name: str
    timezone: str
    currency: str
    default_locale: str = "en"
    support_email: EmailStr
    whatsapp_number: str | None = None
    facebook_page: str | None = None
    instagram_handle: str | None = None
    active: bool = True


class User(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: UserRole
    market_ids: list[str]
    default_market_id: str
    active: bool = True
    password_reset_required: bool = False
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    market_id: str | None = None


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    temporary_password: str = Field(min_length=8)
    role: UserRole = UserRole.agent
    market_ids: list[str] = Field(default_factory=list)
    default_market_id: str | None = None
    active: bool = True


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    temporary_password: str | None = Field(default=None, min_length=8)
    role: UserRole | None = None
    market_ids: list[str] | None = None
    default_market_id: str | None = None
    active: bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AuthSession(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
    market: Market
    available_markets: list[Market]


class WorkspaceSettings(BaseModel):
    market_id: str = "market-ng"
    ai_work_queue_automation_enabled: bool = True
    ai_can_send_customer_messages: bool = False
    default_timezone: str = "Africa/Lagos"
    business_hours: str = "Mon-Fri 08:00-18:00"
    public_brand_name: str = "Omni Ticket"


class Channel(BaseModel):
    id: str
    market_id: str = "market-ng"
    type: ChannelType
    name: str
    handle: str
    health: ChannelHealth = ChannelHealth.healthy
    queued: int = 0
    active: int = 0
    sla_risk: int = 0
    capabilities: list[str] = Field(default_factory=list)


class Agent(BaseModel):
    id: str
    market_ids: list[str] = Field(default_factory=lambda: ["market-ng"])
    name: str
    email: EmailStr
    team: str
    status: AgentStatus = AgentStatus.available
    occupancy: int = 0
    capacity: int = 8
    skills: list[ChannelType] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["en"])


class Company(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    tier: str = "standard"
    health_score: int = 75
    account_value: int = 0


class ContactPoint(BaseModel):
    channel: ChannelType
    value: str
    verified: bool = True


class Customer(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    email: EmailStr
    company_id: str | None = None
    location: str = ""
    sentiment: Sentiment = Sentiment.neutral
    preferred_channels: list[ChannelType] = Field(default_factory=list)
    contact_points: list[ContactPoint] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class SlaState(BaseModel):
    first_response_due_at: datetime
    resolution_due_at: datetime
    risk: str = "on_track"
    breached: bool = False


class TicketTask(BaseModel):
    id: str
    label: str
    complete: bool = False


class AiDecision(BaseModel):
    id: str
    ticket_id: str
    created_at: datetime = Field(default_factory=utc_now)
    decision_type: str
    confidence: float = 0.0
    summary: str
    model_version: str = "rules-v1"
    input_reference: str = "local-seed"
    override_allowed: bool = True


class TimelineEvent(BaseModel):
    id: str
    ticket_id: str
    type: TimelineEventType
    channel: ChannelType
    actor: str
    body: str
    created_at: datetime = Field(default_factory=utc_now)
    public: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class Ticket(BaseModel):
    id: str
    market_id: str = "market-ng"
    public_id: str
    subject: str
    description: str
    customer_id: str
    channel: ChannelType
    status: TicketStatus = TicketStatus.open
    priority: Priority = Priority.normal
    sentiment: Sentiment = Sentiment.neutral
    assignee_id: str | None = None
    team: str = "General Support"
    tags: list[str] = Field(default_factory=list)
    tasks: list[TicketTask] = Field(default_factory=list)
    sla: SlaState
    ai_summary: str = ""
    recommended_action: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Handoff(BaseModel):
    id: str
    market_id: str = "market-ng"
    ticket_id: str
    from_team: str
    to_team: str
    requested_by: str
    reason: str
    status: HandoffStatus = HandoffStatus.requested
    due_at: datetime
    checklist: list[TicketTask] = Field(default_factory=list)
    blocker: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeArticle(BaseModel):
    id: str
    market_ids: list[str] = Field(default_factory=lambda: ["market-ng"])
    title: str
    status: str = "published"
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str
    updated_at: datetime = Field(default_factory=utc_now)


class AutomationRule(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    enabled: bool = True
    trigger: str
    action: str
    last_fired_at: datetime | None = None
    failure_count: int = 0


class ConnectorEvent(BaseModel):
    id: str
    market_id: str = "market-ng"
    provider: ChannelType
    direction: ConnectorDirection
    external_id: str
    ticket_id: str | None = None
    status: str = "received"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ConnectorAccount(BaseModel):
    id: str
    market_id: str = "market-ng"
    provider: ChannelType
    display_name: str
    account_identifier: str
    status: ConnectorAccountStatus = ConnectorAccountStatus.pending_credentials
    intake_enabled: bool = True
    outbound_enabled: bool = False
    webhook_url: str = ""
    webhook_verified: bool = False
    credential_ref: str | None = None
    secret_configured: bool = False
    last_sync_at: datetime | None = None
    last_error: str | None = None
    failure_count: int = 0
    required_credentials: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OutboundMessage(BaseModel):
    id: str
    market_id: str = "market-ng"
    ticket_id: str
    timeline_event_id: str | None = None
    connector_event_id: str | None = None
    provider: ChannelType
    status: OutboundMessageStatus = OutboundMessageStatus.queued
    actor: str
    body: str
    idempotency_key: str
    attempts: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Attachment(BaseModel):
    id: str
    market_id: str = "market-ng"
    ticket_id: str
    timeline_event_id: str | None = None
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    storage_key: str
    uploaded_by: str
    scan_status: AttachmentScanStatus = AttachmentScanStatus.pending
    scan_result: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str
    market_id: str | None = None
    actor: str
    action: str
    entity_type: str
    entity_id: str
    created_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class WorkQueueItem(BaseModel):
    ticket: Ticket
    customer: Customer
    assignee: Agent | None
    score: int
    reasons: list[str]


class AnalyticsSnapshot(BaseModel):
    open_tickets: int
    at_risk_tickets: int
    breached_tickets: int
    channel_volume: dict[ChannelType, int]
    active_agents: int
    avg_occupancy: int


class CreateTicketRequest(BaseModel):
    market_id: str | None = None
    subject: str
    description: str
    customer_id: str
    channel: ChannelType
    priority: Priority | None = None
    external_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateCompanyRequest(BaseModel):
    market_id: str | None = None
    name: str
    tier: str = "standard"
    health_score: int = 75
    account_value: int = 0


class UpdateCompanyRequest(BaseModel):
    name: str | None = None
    tier: str | None = None
    health_score: int | None = None
    account_value: int | None = None


class CreateCustomerRequest(BaseModel):
    market_id: str | None = None
    name: str
    email: EmailStr
    company_id: str | None = None
    location: str = ""
    preferred_channels: list[ChannelType] = Field(default_factory=list)
    contact_points: list[ContactPoint] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class UpdateCustomerRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    company_id: str | None = None
    location: str | None = None
    sentiment: Sentiment | None = None
    preferred_channels: list[ChannelType] | None = None
    contact_points: list[ContactPoint] | None = None
    tags: list[str] | None = None
    notes: str | None = None


class UpdateChannelRequest(BaseModel):
    health: ChannelHealth | None = None
    queued: int | None = None
    active: int | None = None
    sla_risk: int | None = None


class UpdateAgentStatusRequest(BaseModel):
    status: AgentStatus


class UpdateTicketRequest(BaseModel):
    status: TicketStatus | None = None
    priority: Priority | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    task_item_id: str | None = None
    task_item_complete: bool | None = None
    recommended_action: str | None = None


class WorkQueueOverrideRequest(BaseModel):
    reason: str
    status: TicketStatus | None = None
    priority: Priority | None = None
    assignee_id: str | None = None
    recommended_action: str | None = None
    tags: list[str] | None = None


class AppendEventRequest(BaseModel):
    type: TimelineEventType
    channel: ChannelType
    actor: str
    body: str
    public: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplyRequest(BaseModel):
    channel: ChannelType
    actor: str
    body: str
    public: bool = True
    idempotency_key: str | None = None


class RetryOutboundMessageRequest(BaseModel):
    reason: str = "Manual retry"


class CreateAttachmentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=160)
    size_bytes: int = Field(ge=1, le=25 * 1024 * 1024)
    storage_key: str | None = Field(default=None, max_length=500)


class CreateHandoffRequest(BaseModel):
    to_team: str
    requested_by: str
    reason: str
    due_minutes: int = 60
    checklist: list[str] = Field(default_factory=list)


class UpdateHandoffRequest(BaseModel):
    status: HandoffStatus | None = None
    due_at: datetime | None = None
    blocker: str | None = None
    checklist_item_id: str | None = None
    checklist_item_complete: bool | None = None


class ConnectorInboundRequest(BaseModel):
    market_id: str | None = None
    provider: ChannelType
    external_id: str
    customer_name: str
    customer_email: EmailStr
    subject: str
    body: str
    handle: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateConnectorAccountRequest(BaseModel):
    provider: ChannelType
    display_name: str
    account_identifier: str
    status: ConnectorAccountStatus = ConnectorAccountStatus.pending_credentials
    intake_enabled: bool = True
    outbound_enabled: bool = False
    webhook_url: str = ""
    webhook_verified: bool = False
    credential_ref: str | None = None
    secret_configured: bool = False
    last_error: str | None = None
    required_credentials: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class UpdateConnectorAccountRequest(BaseModel):
    display_name: str | None = None
    account_identifier: str | None = None
    status: ConnectorAccountStatus | None = None
    intake_enabled: bool | None = None
    outbound_enabled: bool | None = None
    webhook_url: str | None = None
    webhook_verified: bool | None = None
    credential_ref: str | None = None
    secret_configured: bool | None = None
    last_error: str | None = None
    failure_count: int | None = None
    required_credentials: list[str] | None = None
    capabilities: list[str] | None = None


class CreateKnowledgeArticleRequest(BaseModel):
    market_ids: list[str] | None = None
    title: str
    status: str = "draft"
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str


class UpdateKnowledgeArticleRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    language: str | None = None
    channels: list[ChannelType] | None = None
    tags: list[str] | None = None
    body: str | None = None


class CreateAutomationRuleRequest(BaseModel):
    market_id: str | None = None
    name: str
    enabled: bool = True
    trigger: str
    action: str


class UpdateAutomationRuleRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    trigger: str | None = None
    action: str | None = None


def default_sla(priority: Priority, now: datetime | None = None) -> SlaState:
    base = now or utc_now()
    response_minutes = {
        Priority.urgent: 15,
        Priority.high: 30,
        Priority.normal: 120,
        Priority.low: 240,
    }[priority]
    resolution_hours = {
        Priority.urgent: 4,
        Priority.high: 8,
        Priority.normal: 24,
        Priority.low: 48,
    }[priority]
    return SlaState(
        first_response_due_at=base + timedelta(minutes=response_minutes),
        resolution_due_at=base + timedelta(hours=resolution_hours),
    )
