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


class TicketFieldType(StrEnum):
    text = "text"
    textarea = "textarea"
    select = "select"
    multiselect = "multiselect"
    checkbox = "checkbox"
    number = "number"
    date = "date"


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


class CsatSource(StrEnum):
    customer_survey = "customer_survey"
    agent_recorded = "agent_recorded"
    service_import = "service_import"


class HandoffStatus(StrEnum):
    requested = "requested"
    accepted = "accepted"
    in_progress = "in_progress"
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


class ProductionAccountReferenceStatus(StrEnum):
    requested = "requested"
    provisioned = "provisioned"
    connected = "connected"
    blocked = "blocked"
    retired = "retired"


class OperationalAlertSeverity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class OperationalAlertStatus(StrEnum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class OperationalAlertDeliveryStatus(StrEnum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class AttachmentScanStatus(StrEnum):
    pending = "pending"
    clean = "clean"
    blocked = "blocked"
    failed = "failed"


class AttachmentLifecycleStatus(StrEnum):
    active = "active"
    deleted = "deleted"
    purged = "purged"


class KnowledgeArticleStatus(StrEnum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    published = "published"
    archived = "archived"


class UserRole(StrEnum):
    agent = "agent"
    supervisor = "supervisor"
    admin = "admin"
    auditor = "auditor"
    service_account = "service_account"


class Permission(StrEnum):
    operations_write = "operations.write"
    supervisor_control = "supervisor.control"
    audit_read = "audit.read"
    setup_manage = "setup.manage"


class PermissionProfile(StrEnum):
    role_default = "role_default"
    read_only = "read_only"
    operations = "operations"
    supervisor = "supervisor"
    admin = "admin"
    custom = "custom"


class PermissionOverrides(BaseModel):
    allow: list[Permission] = Field(default_factory=list)
    deny: list[Permission] = Field(default_factory=list)


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
    mfa_enabled: bool = False
    mfa_confirmed_at: datetime | None = None
    mfa_last_verified_at: datetime | None = None
    permission_profile: PermissionProfile = PermissionProfile.role_default
    permission_overrides: PermissionOverrides = Field(default_factory=PermissionOverrides)
    effective_permissions: list[Permission] = Field(default_factory=list)
    external_identity_provider: str | None = None
    external_subject: str | None = None
    external_last_login_at: datetime | None = None
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    market_id: str | None = None
    mfa_code: str | None = None


class OidcProviderConfig(BaseModel):
    provider_name: str
    enabled: bool
    configured: bool
    login_available: bool
    authorization_endpoint_configured: bool
    token_endpoint_configured: bool
    userinfo_endpoint_configured: bool
    redirect_url_configured: bool
    client_configured: bool
    auto_provision_enabled: bool
    default_role: UserRole
    default_market_id: str | None = None
    allowed_email_domains: list[str] = Field(default_factory=list)
    required_settings: list[str] = Field(default_factory=list)
    missing_settings: list[str] = Field(default_factory=list)
    notes: str


class OidcStartResponse(BaseModel):
    authorization_url: str
    state: str
    expires_at: datetime


class OidcCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    temporary_password: str = Field(min_length=8)
    role: UserRole = UserRole.agent
    market_ids: list[str] = Field(default_factory=list)
    default_market_id: str | None = None
    active: bool = True
    permission_profile: PermissionProfile = PermissionProfile.role_default
    permission_overrides: PermissionOverrides = Field(default_factory=PermissionOverrides)


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    temporary_password: str | None = Field(default=None, min_length=8)
    role: UserRole | None = None
    market_ids: list[str] | None = None
    default_market_id: str | None = None
    active: bool | None = None
    permission_profile: PermissionProfile | None = None
    permission_overrides: PermissionOverrides | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class MfaEnrollmentResponse(BaseModel):
    secret: str
    otpauth_uri: str
    issuer: str = "Omni Ticket"
    digits: int = 6
    period_seconds: int = 30


class ConfirmMfaRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class DisableMfaRequest(BaseModel):
    current_password: str
    code: str | None = Field(default=None, min_length=6, max_length=12)


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
    portal_logo_url: str = ""
    portal_primary_color: str = "#0b5eea"
    portal_support_name: str = ""
    portal_welcome_message: str = ""


class EmailProviderSettings(BaseModel):
    market_id: str = "market-ng"
    inbound_enabled: bool = False
    inbound_host: str = ""
    inbound_port: int = Field(default=993, ge=1, le=65535)
    inbound_username: str = ""
    inbound_mailbox: str = "INBOX"
    inbound_use_ssl: bool = True
    inbound_mark_seen: bool = True
    inbound_password_configured: bool = False
    outbound_enabled: bool = False
    outbound_host: str = ""
    outbound_port: int = Field(default=587, ge=1, le=65535)
    outbound_username: str = ""
    outbound_from_email: str = ""
    outbound_use_starttls: bool = True
    outbound_use_ssl: bool = False
    outbound_password_configured: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class UpdateEmailProviderSettingsRequest(BaseModel):
    inbound_enabled: bool | None = None
    inbound_host: str | None = Field(default=None, max_length=255)
    inbound_port: int | None = Field(default=None, ge=1, le=65535)
    inbound_username: str | None = Field(default=None, max_length=255)
    inbound_password: str | None = Field(default=None, max_length=500)
    inbound_mailbox: str | None = Field(default=None, max_length=120)
    inbound_use_ssl: bool | None = None
    inbound_mark_seen: bool | None = None
    clear_inbound_password: bool = False
    outbound_enabled: bool | None = None
    outbound_host: str | None = Field(default=None, max_length=255)
    outbound_port: int | None = Field(default=None, ge=1, le=65535)
    outbound_username: str | None = Field(default=None, max_length=255)
    outbound_password: str | None = Field(default=None, max_length=500)
    outbound_from_email: str | None = Field(default=None, max_length=255)
    outbound_use_starttls: bool | None = None
    outbound_use_ssl: bool | None = None
    clear_outbound_password: bool = False


class IntegrationCredentialSettings(BaseModel):
    market_id: str = "market-ng"
    ai_provider: str = "auto"
    anthropic_api_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_api_key_configured: bool = False
    alert_webhook_url: str = ""
    alert_webhook_secret_configured: bool = False
    alert_delivery_min_severity: OperationalAlertSeverity = OperationalAlertSeverity.warning
    sms_http_endpoint: str = ""
    sms_http_from: str = ""
    sms_http_auth_header: str = "Authorization"
    sms_http_auth_scheme: str = "Bearer"
    sms_http_delivery_callback_url: str = ""
    sms_http_auth_token_configured: bool = False
    voice_http_endpoint: str = ""
    voice_http_from: str = ""
    voice_http_auth_header: str = "Authorization"
    voice_http_auth_scheme: str = "Bearer"
    voice_http_status_callback_url: str = ""
    voice_http_auth_token_configured: bool = False
    whatsapp_cloud_api_base_url: str = "https://graph.facebook.com/v25.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_preview_urls: bool = False
    whatsapp_access_token_configured: bool = False
    facebook_graph_api_base_url: str = "https://graph.facebook.com/v25.0"
    facebook_page_id: str = ""
    facebook_messaging_type: str = "RESPONSE"
    facebook_page_access_token_configured: bool = False
    instagram_graph_api_base_url: str = "https://graph.instagram.com/v25.0"
    instagram_business_account_id: str = ""
    instagram_access_token_configured: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class UpdateIntegrationCredentialSettingsRequest(BaseModel):
    ai_provider: str | None = Field(default=None, max_length=32)
    anthropic_api_key: str | None = Field(default=None, max_length=1000)
    anthropic_api_base_url: str | None = Field(default=None, max_length=255)
    anthropic_model: str | None = Field(default=None, max_length=120)
    clear_anthropic_api_key: bool = False
    alert_webhook_url: str | None = Field(default=None, max_length=500)
    alert_webhook_secret: str | None = Field(default=None, max_length=1000)
    alert_delivery_min_severity: OperationalAlertSeverity | None = None
    clear_alert_webhook_secret: bool = False
    sms_http_endpoint: str | None = Field(default=None, max_length=500)
    sms_http_auth_token: str | None = Field(default=None, max_length=1000)
    sms_http_from: str | None = Field(default=None, max_length=120)
    sms_http_auth_header: str | None = Field(default=None, max_length=120)
    sms_http_auth_scheme: str | None = Field(default=None, max_length=80)
    sms_http_delivery_callback_url: str | None = Field(default=None, max_length=500)
    clear_sms_http_auth_token: bool = False
    voice_http_endpoint: str | None = Field(default=None, max_length=500)
    voice_http_auth_token: str | None = Field(default=None, max_length=1000)
    voice_http_from: str | None = Field(default=None, max_length=120)
    voice_http_auth_header: str | None = Field(default=None, max_length=120)
    voice_http_auth_scheme: str | None = Field(default=None, max_length=80)
    voice_http_status_callback_url: str | None = Field(default=None, max_length=500)
    clear_voice_http_auth_token: bool = False
    whatsapp_cloud_api_base_url: str | None = Field(default=None, max_length=255)
    whatsapp_phone_number_id: str | None = Field(default=None, max_length=160)
    whatsapp_access_token: str | None = Field(default=None, max_length=1000)
    whatsapp_preview_urls: bool | None = None
    clear_whatsapp_access_token: bool = False
    facebook_graph_api_base_url: str | None = Field(default=None, max_length=255)
    facebook_page_id: str | None = Field(default=None, max_length=160)
    facebook_page_access_token: str | None = Field(default=None, max_length=1000)
    facebook_messaging_type: str | None = Field(default=None, max_length=40)
    clear_facebook_page_access_token: bool = False
    instagram_graph_api_base_url: str | None = Field(default=None, max_length=255)
    instagram_business_account_id: str | None = Field(default=None, max_length=160)
    instagram_access_token: str | None = Field(default=None, max_length=1000)
    clear_instagram_access_token: bool = False


class WidgetSettings(BaseModel):
    market_id: str = "market-ng"
    enabled: bool = False
    display_name: str = "Chat with us"
    welcome_message: str = "Hi! How can we help you today?"
    primary_color: str = "#0b5eea"
    launcher_label: str = "Support"
    position: str = "bottom-right"
    auto_open_seconds: int = Field(default=0, ge=0, le=600)
    collect_email: bool = True
    offline_message: str = "We're offline right now — leave a message and we'll reply by email."
    updated_at: datetime = Field(default_factory=utc_now)


class UpdateWidgetSettingsRequest(BaseModel):
    enabled: bool | None = None
    display_name: str | None = Field(default=None, max_length=120)
    welcome_message: str | None = Field(default=None, max_length=500)
    primary_color: str | None = Field(default=None, max_length=20)
    launcher_label: str | None = Field(default=None, max_length=80)
    position: str | None = Field(default=None, max_length=20)
    auto_open_seconds: int | None = Field(default=None, ge=0, le=600)
    collect_email: bool | None = None
    offline_message: str | None = Field(default=None, max_length=500)


class SsoProviderSettings(BaseModel):
    enabled: bool = False
    provider_name: str = "Enterprise SSO"
    issuer_url: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    client_id: str = ""
    client_secret_configured: bool = False
    redirect_url: str = ""
    allowed_email_domains: list[str] = Field(default_factory=list)
    auto_provision_enabled: bool = False
    default_role: UserRole = UserRole.agent
    default_market_id: str | None = None
    require_email_verified: bool = True
    managed_in_database: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class UpdateSsoProviderSettingsRequest(BaseModel):
    enabled: bool | None = None
    provider_name: str | None = Field(default=None, max_length=120)
    issuer_url: str | None = Field(default=None, max_length=500)
    authorization_url: str | None = Field(default=None, max_length=500)
    token_url: str | None = Field(default=None, max_length=500)
    userinfo_url: str | None = Field(default=None, max_length=500)
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, max_length=1000)
    clear_client_secret: bool = False
    redirect_url: str | None = Field(default=None, max_length=500)
    allowed_email_domains: list[str] | None = None
    auto_provision_enabled: bool | None = None
    default_role: UserRole | None = None
    default_market_id: str | None = Field(default=None, max_length=64)
    require_email_verified: bool | None = None


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
    # Wiring state, computed from real configuration (IMAP settings, connector
    # accounts, widget/portal) at serialization time — never stored.
    intake_live: bool = False
    intake_note: str = ""
    outbound_live: bool = False
    outbound_note: str = ""


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


class SupportGroup(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    description: str = ""
    team_email: EmailStr | None = None
    active: bool = True
    channels: list[ChannelType] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    member_count: int = 0
    open_ticket_count: int = 0
    sla_risk_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class SlaPolicy(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    active: bool = True
    channels: list[ChannelType] = Field(default_factory=list)
    priority: Priority = Priority.normal
    first_response_minutes: int = Field(default=120, ge=1)
    resolution_minutes: int = Field(default=1440, ge=1)
    business_hours: str = "Business hours"
    position: int = 100
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BusinessHoursDay(BaseModel):
    day: str = Field(max_length=12)
    enabled: bool = True
    open: str = Field(default="09:00", max_length=5)
    close: str = Field(default="17:00", max_length=5)


class BusinessHours(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    timezone: str = "Africa/Lagos"
    active: bool = True
    days: list[BusinessHoursDay] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TicketTemplate(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    subject: str
    description: str = ""
    priority: Priority = Priority.normal
    channel: ChannelType = ChannelType.email
    group: str = ""
    tags: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Tag(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    color: str = "#2f6fed"
    description: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CsatSurvey(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    question: str
    scale: int = Field(default=5, ge=2, le=10)
    channels: list[ChannelType] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EmailNotification(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    event: str = "ticket_created"
    recipients: list[str] = Field(default_factory=list)
    subject: str = ""
    body: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScenarioAction(BaseModel):
    type: str = Field(max_length=40)
    value: str = Field(default="", max_length=300)


class ScenarioAutomation(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    description: str = ""
    actions: list[ScenarioAction] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CustomFieldDefinition(BaseModel):
    id: str
    market_id: str = "market-ng"
    entity: str = "contact"
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str
    field_type: TicketFieldType = TicketFieldType.text
    required: bool = False
    active: bool = True
    options: list[str] = Field(default_factory=list)
    help_text: str = ""
    position: int = 100
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CustomObjectField(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str
    field_type: TicketFieldType = TicketFieldType.text
    required: bool = False
    options: list[str] = Field(default_factory=list)


class CustomObject(BaseModel):
    id: str
    market_id: str = "market-ng"
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    name: str
    description: str = ""
    fields: list[CustomObjectField] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Product(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    code: str = ""
    description: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SavedReport(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    report_type: str = "tickets"
    description: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    cadence: str = "none"
    recipients: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ServiceAppointment(BaseModel):
    id: str
    market_id: str = "market-ng"
    title: str
    customer_id: str = ""
    technician_id: str = ""
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    status: str = "scheduled"
    location: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DiscussionTopic(BaseModel):
    id: str
    market_id: str = "market-ng"
    title: str
    category: str = "General"
    body: str = ""
    status: str = "open"
    pinned: bool = False
    author: str = ""
    reply_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DiscussionComment(BaseModel):
    id: str
    topic_id: str
    market_id: str = "market-ng"
    author: str = ""
    body: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    tasks: list[TicketTask] = Field(default_factory=list)
    sla: SlaState
    ai_summary: str = ""
    recommended_action: str = ""
    case_id: str | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    sla_resolution_met: bool | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Handoff(BaseModel):
    id: str
    market_id: str = "market-ng"
    ticket_id: str
    linked_ticket_id: str | None = None
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
    status: KnowledgeArticleStatus = KnowledgeArticleStatus.published
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str
    submitted_for_review_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeSuggestion(BaseModel):
    article: KnowledgeArticle
    score: int
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class PortalAnswerSuggestion(BaseModel):
    article_id: str
    title: str
    body: str
    language: str
    tags: list[str] = Field(default_factory=list)
    score: int
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    updated_at: datetime


class PortalAnswersResponse(BaseModel):
    market_id: str
    market_code: str
    query: str = ""
    suggestions: list[PortalAnswerSuggestion] = Field(default_factory=list)
    ticket_fields: list["TicketField"] = Field(default_factory=list)


class CreatePortalTicketRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    subject: str = Field(min_length=4, max_length=255)
    description: str = Field(min_length=10, max_length=8000)
    phone: str | None = Field(default=None, max_length=80)
    priority: Priority | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    search_query: str | None = Field(default=None, max_length=500)


class PortalTicketResponse(BaseModel):
    ticket_id: str
    public_id: str
    status: TicketStatus
    priority: Priority
    created_at: datetime
    article_suggestions: list[PortalAnswerSuggestion] = Field(default_factory=list)


class PortalTicketTimelineEvent(BaseModel):
    id: str
    type: TimelineEventType
    channel: ChannelType
    actor: str
    body: str
    created_at: datetime


class PortalAttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    scan_status: AttachmentScanStatus
    lifecycle_status: AttachmentLifecycleStatus
    created_at: datetime


class PortalTicketDetailResponse(BaseModel):
    ticket_id: str
    public_id: str
    subject: str
    description: str
    status: TicketStatus
    customer_status: str
    priority: Priority
    created_at: datetime
    updated_at: datetime
    next_step: str
    reply_allowed: bool = True
    # Customer satisfaction: rating opens once the ticket is resolved/closed.
    csat_allowed: bool = False
    csat_rating: int | None = None
    csat_comment: str | None = None
    timeline: list[PortalTicketTimelineEvent] = Field(default_factory=list)
    attachments: list[PortalAttachmentResponse] = Field(default_factory=list)
    article_suggestions: list[PortalAnswerSuggestion] = Field(default_factory=list)


class PortalTicketReplyRequest(BaseModel):
    email: EmailStr
    body: str = Field(min_length=2, max_length=8000)


class PortalCsatRequest(BaseModel):
    """Public satisfaction rating submitted by the customer from the Help Center."""

    email: EmailStr
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ResponseMacro(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    body: str
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    shortcut: str | None = None
    active: bool = True
    usage_count: int = 0
    last_used_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ResponseMacroSuggestion(BaseModel):
    macro: ResponseMacro
    score: int
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class DuplicateTicketSuggestion(BaseModel):
    ticket: Ticket
    customer: Customer | None = None
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class MergeTicketsRequest(BaseModel):
    source_ticket_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=4, max_length=1000)
    actor: str | None = Field(default=None, max_length=180)
    close_source: bool = True


class MergeTicketsResponse(BaseModel):
    target_ticket: Ticket
    source_ticket: Ticket
    target_timeline_event: TimelineEvent
    source_timeline_event: TimelineEvent
    audit_event_id: str | None = None


class CaseStatus(StrEnum):
    open = "open"
    resolved = "resolved"
    closed = "closed"


class Case(BaseModel):
    """Groups multiple tickets/communications (across channels) for one customer."""

    id: str
    market_id: str = "market-ng"
    public_id: str
    customer_id: str
    title: str
    status: CaseStatus = CaseStatus.open
    priority: Priority = Priority.normal
    summary: str = ""
    opened_by: str = ""
    ticket_ids: list[str] = Field(default_factory=list)
    channels: list[ChannelType] = Field(default_factory=list)
    ticket_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreateCaseRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=255)
    summary: str = Field(default="", max_length=4000)
    opened_by: str = Field(default="", max_length=180)
    priority: Priority = Priority.normal
    ticket_ids: list[str] = Field(default_factory=list)


class UpdateCaseRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    status: CaseStatus | None = None
    priority: Priority | None = None
    summary: str | None = Field(default=None, max_length=4000)
    actor: str | None = Field(default=None, max_length=180)


class CaseTicketRequest(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=64)
    actor: str | None = Field(default=None, max_length=180)


class TicketField(BaseModel):
    id: str
    market_id: str = "market-ng"
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str
    field_type: TicketFieldType = TicketFieldType.text
    required: bool = False
    active: bool = True
    system: bool = False
    options: list[str] = Field(default_factory=list)
    channels: list[ChannelType] = Field(default_factory=list)
    placeholder: str = ""
    help_text: str = ""
    position: int = 100
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


class OutboundProviderConfig(BaseModel):
    provider: ChannelType
    adapter: str
    configured: bool = False
    live_delivery: bool = False
    fallback_adapter: str | None = None
    required_settings: list[str] = Field(default_factory=list)
    missing_settings: list[str] = Field(default_factory=list)
    notes: str = ""


class InboundProviderConfig(BaseModel):
    provider: ChannelType
    adapter: str
    configured: bool = False
    live_intake: bool = False
    polling_enabled: bool = False
    required_settings: list[str] = Field(default_factory=list)
    missing_settings: list[str] = Field(default_factory=list)
    notes: str = ""


class AttachmentProviderConfig(BaseModel):
    storage_backend: str = "local"
    storage_configured: bool = True
    storage_live: bool = True
    scanner_adapter: str = "local"
    scanner_configured: bool = True
    live_scanning: bool = False
    required_settings: list[str] = Field(default_factory=list)
    missing_settings: list[str] = Field(default_factory=list)
    notes: str = ""


class ProductionAccountRequestItem(BaseModel):
    id: str
    area: str
    provider: str
    purpose: str
    backend_use: str
    status: str
    required_credentials: list[str] = Field(default_factory=list)
    missing_settings: list[str] = Field(default_factory=list)
    callback_urls: list[str] = Field(default_factory=list)
    setup_location: str = "Setup"
    credential_reference_name: str = ""
    account_owner: str = ""
    notes: str = ""


class ProductionAccountRequestPack(BaseModel):
    market_id: str
    recipient_email: EmailStr
    generated_at: datetime = Field(default_factory=utc_now)
    total_items: int
    ready_items: int
    missing_items: int
    subject: str
    body: str
    mailto_url: str
    items: list[ProductionAccountRequestItem] = Field(default_factory=list)


class ProductionAccountRequestDelivery(BaseModel):
    pack: ProductionAccountRequestPack
    outbound_message: OutboundMessage
    ticket_id: str
    ticket_public_id: str
    already_queued: bool = False
    queued_at: datetime = Field(default_factory=utc_now)


class ProductionAccountReference(BaseModel):
    id: str
    market_id: str = "market-ng"
    provider: str
    area: str
    account_name: str
    account_identifier: str = ""
    status: ProductionAccountReferenceStatus = ProductionAccountReferenceStatus.requested
    owner_email: EmailStr | None = None
    credential_reference: str = ""
    docs_reference: str = ""
    callback_urls: list[str] = Field(default_factory=list)
    notes: str = ""
    created_by: str = ""
    updated_by: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProductionAccountReferenceDocs(BaseModel):
    market_id: str
    markdown: str
    generated_at: datetime = Field(default_factory=utc_now)


class ProductionReadinessItem(BaseModel):
    id: str
    category: str
    label: str
    status: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    next_action: str = ""
    docs_reference: str = ""


class ProductionReadinessChecklist(BaseModel):
    market_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    overall_status: str
    total_items: int
    ready_items: int
    action_items: int
    blocked_items: int
    items: list[ProductionReadinessItem] = Field(default_factory=list)


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
    lifecycle_status: AttachmentLifecycleStatus = AttachmentLifecycleStatus.active
    retained_until: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    deletion_reason: str | None = None
    purged_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DeleteAttachmentRequest(BaseModel):
    reason: str = "Manual attachment deletion"
    purge_storage: bool = False


class AttachmentRetentionPolicy(BaseModel):
    market_id: str
    active_retention_days: int
    deleted_retention_days: int
    active_cutoff_at: datetime
    deleted_cutoff_at: datetime
    prune_limit: int
    active_attachments: int
    deleted_attachments: int
    purged_attachments: int
    purgeable_attachments: int


class AttachmentRetentionResult(BaseModel):
    policy: AttachmentRetentionPolicy
    purged_attachments: int
    attachment_ids: list[str] = Field(default_factory=list)
    audit_event_id: str | None = None


class AuditEvent(BaseModel):
    id: str
    market_id: str | None = None
    actor: str
    action: str
    entity_type: str
    entity_id: str
    created_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class AuditRetentionPolicy(BaseModel):
    market_id: str
    retention_days: int
    cutoff_at: datetime
    retained_events: int
    prunable_events: int
    export_max_rows: int


class AuditRetentionResult(BaseModel):
    policy: AuditRetentionPolicy
    deleted_events: int
    audit_event_id: str | None = None


class OperationalAlert(BaseModel):
    id: str
    market_id: str
    severity: OperationalAlertSeverity = OperationalAlertSeverity.warning
    status: OperationalAlertStatus = OperationalAlertStatus.open
    source: str
    entity_type: str
    entity_id: str
    dedupe_key: str
    title: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    occurrence_count: int = 1
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OperationalAlertDelivery(BaseModel):
    id: str
    market_id: str
    alert_id: str
    destination_type: str = "webhook"
    destination_name: str = "operations_webhook"
    status: OperationalAlertDeliveryStatus = OperationalAlertDeliveryStatus.queued
    attempts: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OperationalAlertDeliveryConfig(BaseModel):
    webhook_configured: bool = False
    destination_type: str = "webhook"
    destination_name: str = "operations_webhook"
    min_severity: OperationalAlertSeverity = OperationalAlertSeverity.warning
    max_attempts: int = 3


class WorkQueueItem(BaseModel):
    ticket: Ticket
    customer: Customer
    assignee: Agent | None
    score: int
    reasons: list[str]


class SupervisorRecommendation(BaseModel):
    id: str
    market_id: str
    title: str
    summary: str
    action: str
    severity: OperationalAlertSeverity = OperationalAlertSeverity.warning
    category: str
    priority_score: int = Field(ge=0, le=100)
    ticket_id: str | None = None
    handoff_id: str | None = None
    support_group: str | None = None
    owner_id: str | None = None
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class GlobalSearchResultType(StrEnum):
    ticket = "ticket"
    customer = "customer"
    company = "company"
    knowledge = "knowledge"
    support_group = "support_group"
    handoff = "handoff"
    agent = "agent"


class GlobalSearchResult(BaseModel):
    id: str
    type: GlobalSearchResultType
    title: str
    subtitle: str = ""
    description: str = ""
    score: int = Field(ge=0, le=100)
    screen: str | None = None
    entity_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticsSnapshot(BaseModel):
    open_tickets: int
    at_risk_tickets: int
    breached_tickets: int
    channel_volume: dict[ChannelType, int]
    active_agents: int
    avg_occupancy: int
    avg_csat: float | None = None
    avg_first_response_seconds: float | None = None
    resolution_within_sla_pct: int | None = None
    ticket_trends: dict[str, int] = Field(default_factory=dict)
    ticket_performance: dict[str, float | int | None] = Field(default_factory=dict)
    ticket_csat: dict[str, int] = Field(default_factory=dict)
    chat_trends: dict[str, int] = Field(default_factory=dict)
    chat_performance: dict[str, float | None] = Field(default_factory=dict)
    chat_csat: dict[str, float | int | None] = Field(default_factory=dict)
    agent_availability: dict[str, int] = Field(default_factory=dict)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)


class AnalyticsRollup(BaseModel):
    id: str
    market_id: str
    period_start: datetime
    period_end: datetime
    open_tickets: int
    at_risk_tickets: int
    breached_tickets: int
    active_agents: int
    avg_occupancy: int
    avg_csat: float | None = None
    channel_volume: dict[ChannelType, int]
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreateTicketRequest(BaseModel):
    market_id: str | None = None
    subject: str
    description: str
    customer_id: str
    channel: ChannelType
    priority: Priority | None = None
    external_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class CsatFeedback(BaseModel):
    id: str
    market_id: str = "market-ng"
    ticket_id: str
    customer_id: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    source: CsatSource = CsatSource.customer_survey
    submitted_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreateCsatFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    source: CsatSource = CsatSource.customer_survey
    submitted_by: str | None = Field(default=None, max_length=180)


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


class CreateSupportGroupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    team_email: EmailStr | None = None
    active: bool = True
    channels: list[ChannelType] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class UpdateSupportGroupRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    team_email: EmailStr | None = None
    active: bool | None = None
    channels: list[ChannelType] | None = None
    skills: list[str] | None = None


class CreateSlaPolicyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    active: bool = True
    channels: list[ChannelType] = Field(default_factory=list)
    priority: Priority = Priority.normal
    first_response_minutes: int = Field(default=120, ge=1, le=10080)
    resolution_minutes: int = Field(default=1440, ge=1, le=43200)
    business_hours: str = Field(default="Business hours", max_length=120)
    position: int = 100


class UpdateSlaPolicyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    active: bool | None = None
    channels: list[ChannelType] | None = None
    priority: Priority | None = None
    first_response_minutes: int | None = Field(default=None, ge=1, le=10080)
    resolution_minutes: int | None = Field(default=None, ge=1, le=43200)
    business_hours: str | None = Field(default=None, max_length=120)
    position: int | None = None


class CreateBusinessHoursRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    timezone: str = Field(default="Africa/Lagos", max_length=64)
    active: bool = True
    days: list[BusinessHoursDay] = Field(default_factory=list)


class UpdateBusinessHoursRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    timezone: str | None = Field(default=None, max_length=64)
    active: bool | None = None
    days: list[BusinessHoursDay] | None = None


class CreateTicketTemplateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    subject: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    priority: Priority = Priority.normal
    channel: ChannelType = ChannelType.email
    group: str = Field(default="", max_length=180)
    tags: list[str] = Field(default_factory=list)
    active: bool = True


class UpdateTicketTemplateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    priority: Priority | None = None
    channel: ChannelType | None = None
    group: str | None = Field(default=None, max_length=180)
    tags: list[str] | None = None
    active: bool | None = None


class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#2f6fed", max_length=9)
    description: str = Field(default="", max_length=300)
    active: bool = True


class UpdateTagRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=9)
    description: str | None = Field(default=None, max_length=300)
    active: bool | None = None


class CreateCsatSurveyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    question: str = Field(min_length=2, max_length=300)
    scale: int = Field(default=5, ge=2, le=10)
    channels: list[ChannelType] = Field(default_factory=list)
    active: bool = True


class UpdateCsatSurveyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    question: str | None = Field(default=None, min_length=2, max_length=300)
    scale: int | None = Field(default=None, ge=2, le=10)
    channels: list[ChannelType] | None = None
    active: bool | None = None


class CreateEmailNotificationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    event: str = Field(default="ticket_created", max_length=80)
    recipients: list[str] = Field(default_factory=list)
    subject: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=5000)
    active: bool = True


class UpdateEmailNotificationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    event: str | None = Field(default=None, max_length=80)
    recipients: list[str] | None = None
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=5000)
    active: bool | None = None


class CreateScenarioAutomationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=500)
    actions: list[ScenarioAction] = Field(default_factory=list)
    active: bool = True


class UpdateScenarioAutomationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    actions: list[ScenarioAction] | None = None
    active: bool | None = None


class CreateCustomFieldDefinitionRequest(BaseModel):
    entity: str = Field(default="contact", max_length=20)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=120)
    field_type: TicketFieldType = TicketFieldType.text
    required: bool = False
    active: bool = True
    options: list[str] = Field(default_factory=list)
    help_text: str = Field(default="", max_length=300)
    position: int = 100


class UpdateCustomFieldDefinitionRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    field_type: TicketFieldType | None = None
    required: bool | None = None
    active: bool | None = None
    options: list[str] | None = None
    help_text: str | None = Field(default=None, max_length=300)
    position: int | None = None


class CreateCustomObjectRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=500)
    fields: list[CustomObjectField] = Field(default_factory=list)
    active: bool = True


class UpdateCustomObjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    fields: list[CustomObjectField] | None = None
    active: bool | None = None


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    code: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=500)
    active: bool = True


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class CreateSavedReportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    report_type: str = Field(default="tickets", max_length=40)
    description: str = Field(default="", max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)
    cadence: str = Field(default="none", max_length=20)
    recipients: list[str] = Field(default_factory=list)
    active: bool = True


class UpdateSavedReportRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    report_type: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    filters: dict[str, Any] | None = None
    cadence: str | None = Field(default=None, max_length=20)
    recipients: list[str] | None = None
    active: bool | None = None


class CreateServiceAppointmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    customer_id: str = Field(default="", max_length=64)
    technician_id: str = Field(default="", max_length=64)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    status: str = Field(default="scheduled", max_length=20)
    location: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=1000)


class UpdateServiceAppointmentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    customer_id: str | None = Field(default=None, max_length=64)
    technician_id: str | None = Field(default=None, max_length=64)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    status: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class CreateDiscussionTopicRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str = Field(default="General", max_length=80)
    body: str = Field(default="", max_length=5000)
    status: str = Field(default="open", max_length=20)
    pinned: bool = False


class UpdateDiscussionTopicRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=20)
    pinned: bool | None = None


class CreateDiscussionCommentRequest(BaseModel):
    author: str = Field(default="", max_length=160)
    body: str = Field(min_length=1, max_length=5000)


class UpdateTicketRequest(BaseModel):
    status: TicketStatus | None = None
    priority: Priority | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    task_item_id: str | None = None
    task_item_complete: bool | None = None
    recommended_action: str | None = None
    # Close-out extras (only meaningful on a resolve/close transition):
    resolution_note: str | None = None
    notify_customer: bool | None = None


class CreateTicketFieldRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str
    field_type: TicketFieldType = TicketFieldType.text
    required: bool = False
    active: bool = True
    options: list[str] = Field(default_factory=list)
    channels: list[ChannelType] = Field(default_factory=list)
    placeholder: str = ""
    help_text: str = ""
    position: int = 100


class UpdateTicketFieldRequest(BaseModel):
    label: str | None = None
    field_type: TicketFieldType | None = None
    required: bool | None = None
    active: bool | None = None
    options: list[str] | None = None
    channels: list[ChannelType] | None = None
    placeholder: str | None = None
    help_text: str | None = None
    position: int | None = None


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


class AttachmentDownloadLink(BaseModel):
    url: str
    expires_at: datetime


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


class CreateProductionAccountReferenceRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=80)
    area: str = Field(min_length=2, max_length=160)
    account_name: str = Field(min_length=2, max_length=180)
    account_identifier: str = Field(default="", max_length=255)
    status: ProductionAccountReferenceStatus = ProductionAccountReferenceStatus.requested
    owner_email: EmailStr | None = None
    credential_reference: str = Field(default="", max_length=255)
    docs_reference: str = Field(default="", max_length=500)
    callback_urls: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


class UpdateProductionAccountReferenceRequest(BaseModel):
    provider: str | None = Field(default=None, min_length=2, max_length=80)
    area: str | None = Field(default=None, min_length=2, max_length=160)
    account_name: str | None = Field(default=None, min_length=2, max_length=180)
    account_identifier: str | None = Field(default=None, max_length=255)
    status: ProductionAccountReferenceStatus | None = None
    owner_email: EmailStr | None = None
    credential_reference: str | None = Field(default=None, max_length=255)
    docs_reference: str | None = Field(default=None, max_length=500)
    callback_urls: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CreateKnowledgeArticleRequest(BaseModel):
    market_ids: list[str] | None = None
    title: str
    status: KnowledgeArticleStatus = KnowledgeArticleStatus.draft
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str


class UpdateKnowledgeArticleRequest(BaseModel):
    title: str | None = None
    status: KnowledgeArticleStatus | None = None
    language: str | None = None
    channels: list[ChannelType] | None = None
    tags: list[str] | None = None
    body: str | None = None


class CreateResponseMacroRequest(BaseModel):
    market_id: str | None = None
    name: str
    body: str
    language: str = "en"
    channels: list[ChannelType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    shortcut: str | None = None
    active: bool = True


class UpdateResponseMacroRequest(BaseModel):
    name: str | None = None
    body: str | None = None
    language: str | None = None
    channels: list[ChannelType] | None = None
    tags: list[str] | None = None
    shortcut: str | None = None
    active: bool | None = None


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


class UpdateOperationalAlertRequest(BaseModel):
    status: OperationalAlertStatus
    note: str | None = None


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
