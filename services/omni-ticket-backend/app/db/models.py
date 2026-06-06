from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_pending_secret: Mapped[str | None] = mapped_column(String(96))
    mfa_secret: Mapped[str | None] = mapped_column(String(96))
    mfa_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permission_profile: Mapped[str] = mapped_column(String(40), default="role_default")
    permission_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    external_identity_provider: Mapped[str | None] = mapped_column(String(80))
    external_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    external_last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class OidcLoginStateRecord(TimestampMixin, Base):
    __tablename__ = "oidc_login_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    return_to: Mapped[str | None] = mapped_column(String(500))
    code_verifier: Mapped[str] = mapped_column(String(160), nullable=False)
    nonce: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class WorkspaceSettingsRecord(TimestampMixin, Base):
    __tablename__ = "workspace_settings"

    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    ai_work_queue_automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_can_send_customer_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    default_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    business_hours: Mapped[str] = mapped_column(String(120), default="Mon-Fri 08:00-18:00")
    public_brand_name: Mapped[str] = mapped_column(String(160), default="Omni Ticket")


class EmailProviderSettingsRecord(TimestampMixin, Base):
    __tablename__ = "email_provider_settings"

    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    inbound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    inbound_host: Mapped[str] = mapped_column(String(255), default="")
    inbound_port: Mapped[int] = mapped_column(Integer, default=993)
    inbound_username: Mapped[str] = mapped_column(String(255), default="")
    inbound_password: Mapped[str | None] = mapped_column(Text)
    inbound_mailbox: Mapped[str] = mapped_column(String(120), default="INBOX")
    inbound_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    inbound_mark_seen: Mapped[bool] = mapped_column(Boolean, default=True)
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    outbound_host: Mapped[str] = mapped_column(String(255), default="")
    outbound_port: Mapped[int] = mapped_column(Integer, default=587)
    outbound_username: Mapped[str] = mapped_column(String(255), default="")
    outbound_password: Mapped[str | None] = mapped_column(Text)
    outbound_from_email: Mapped[str] = mapped_column(String(255), default="")
    outbound_use_starttls: Mapped[bool] = mapped_column(Boolean, default=True)
    outbound_use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)


class IntegrationCredentialSettingsRecord(TimestampMixin, Base):
    __tablename__ = "integration_credential_settings"

    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    ai_provider: Mapped[str] = mapped_column(String(32), default="auto")
    anthropic_api_key: Mapped[str | None] = mapped_column(Text)
    anthropic_api_base_url: Mapped[str] = mapped_column(
        String(255),
        default="https://api.anthropic.com",
    )
    anthropic_model: Mapped[str] = mapped_column(String(120), default="claude-sonnet-4-6")
    alert_webhook_url: Mapped[str] = mapped_column(String(500), default="")
    alert_webhook_secret: Mapped[str | None] = mapped_column(Text)
    alert_delivery_min_severity: Mapped[str] = mapped_column(String(32), default="warning")
    sms_http_endpoint: Mapped[str] = mapped_column(String(500), default="")
    sms_http_auth_token: Mapped[str | None] = mapped_column(Text)
    sms_http_from: Mapped[str] = mapped_column(String(120), default="")
    sms_http_auth_header: Mapped[str] = mapped_column(String(120), default="Authorization")
    sms_http_auth_scheme: Mapped[str] = mapped_column(String(80), default="Bearer")
    sms_http_delivery_callback_url: Mapped[str] = mapped_column(String(500), default="")
    voice_http_endpoint: Mapped[str] = mapped_column(String(500), default="")
    voice_http_auth_token: Mapped[str | None] = mapped_column(Text)
    voice_http_from: Mapped[str] = mapped_column(String(120), default="")
    voice_http_auth_header: Mapped[str] = mapped_column(String(120), default="Authorization")
    voice_http_auth_scheme: Mapped[str] = mapped_column(String(80), default="Bearer")
    voice_http_status_callback_url: Mapped[str] = mapped_column(String(500), default="")
    whatsapp_cloud_api_base_url: Mapped[str] = mapped_column(
        String(255),
        default="https://graph.facebook.com/v25.0",
    )
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String(160), default="")
    whatsapp_access_token: Mapped[str | None] = mapped_column(Text)
    whatsapp_preview_urls: Mapped[bool] = mapped_column(Boolean, default=False)
    facebook_graph_api_base_url: Mapped[str] = mapped_column(
        String(255),
        default="https://graph.facebook.com/v25.0",
    )
    facebook_page_id: Mapped[str] = mapped_column(String(160), default="")
    facebook_page_access_token: Mapped[str | None] = mapped_column(Text)
    facebook_messaging_type: Mapped[str] = mapped_column(String(40), default="RESPONSE")
    instagram_graph_api_base_url: Mapped[str] = mapped_column(
        String(255),
        default="https://graph.instagram.com/v25.0",
    )
    instagram_business_account_id: Mapped[str] = mapped_column(String(160), default="")
    instagram_access_token: Mapped[str | None] = mapped_column(Text)


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


class SupportGroupRecord(TimestampMixin, Base):
    __tablename__ = "support_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    team_email: Mapped[str] = mapped_column(String(255), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_support_group_market_name"),
    )


class SlaPolicyRecord(TimestampMixin, Base):
    __tablename__ = "sla_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    first_response_minutes: Mapped[int] = mapped_column(Integer, default=120)
    resolution_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    business_hours: Mapped[str] = mapped_column(String(120), default="Business hours")
    position: Mapped[int] = mapped_column(Integer, default=100)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_sla_policy_market_name"),
    )


class BusinessHoursRecord(TimestampMixin, Base):
    __tablename__ = "business_hours"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    days: Mapped[list] = mapped_column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_business_hours_market_name"),
    )


class TicketTemplateRecord(TimestampMixin, Base):
    __tablename__ = "ticket_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    channel: Mapped[str] = mapped_column(String(32), default="email")
    group: Mapped[str] = mapped_column(String(180), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_ticket_template_market_name"),
    )


class TagRecord(TimestampMixin, Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#2f6fed")
    description: Mapped[str] = mapped_column(String(300), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_tag_market_name"),
    )


class CsatSurveyRecord(TimestampMixin, Base):
    __tablename__ = "csat_surveys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    question: Mapped[str] = mapped_column(String(300), nullable=False)
    scale: Mapped[int] = mapped_column(Integer, default=5)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_csat_survey_market_name"),
    )


class EmailNotificationRecord(TimestampMixin, Base):
    __tablename__ = "email_notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    event: Mapped[str] = mapped_column(String(80), default="ticket_created", index=True)
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_email_notification_market_name"),
    )


class ScenarioAutomationRecord(TimestampMixin, Base):
    __tablename__ = "scenario_automations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    actions: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_scenario_automation_market_name"),
    )


class CustomFieldDefinitionRecord(TimestampMixin, Base):
    __tablename__ = "custom_field_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    entity: Mapped[str] = mapped_column(String(20), default="contact", index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), default="text")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    options: Mapped[list] = mapped_column(JSON, default=list)
    help_text: Mapped[str] = mapped_column(String(300), default="")
    position: Mapped[int] = mapped_column(Integer, default=100)

    __table_args__ = (
        UniqueConstraint("market_id", "entity", "key", name="uq_custom_field_market_entity_key"),
    )


class CustomObjectRecord(TimestampMixin, Base):
    __tablename__ = "custom_objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    fields: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "key", name="uq_custom_object_market_key"),
    )


class ProductRecord(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_product_market_name"),
    )


class SavedReportRecord(TimestampMixin, Base):
    __tablename__ = "saved_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), default="tickets")
    description: Mapped[str] = mapped_column(String(500), default="")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    cadence: Mapped[str] = mapped_column(String(20), default="none", index=True)
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_saved_report_market_name"),
    )


class ServiceAppointmentRecord(TimestampMixin, Base):
    __tablename__ = "service_appointments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), default="")
    technician_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


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
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    tasks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    sla: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")


class TicketFieldRecord(TimestampMixin, Base):
    __tablename__ = "ticket_fields"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), default="text")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    system: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    placeholder: Mapped[str] = mapped_column(String(255), default="")
    help_text: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=100)

    __table_args__ = (
        UniqueConstraint("market_id", "key", name="uq_ticket_field_market_key"),
    )


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


class CsatFeedbackRecord(TimestampMixin, Base):
    __tablename__ = "csat_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="customer_survey", index=True)
    submitted_by: Mapped[str | None] = mapped_column(String(180))

    __table_args__ = (
        UniqueConstraint("market_id", "ticket_id", name="uq_csat_market_ticket"),
    )


class HandoffRecord(TimestampMixin, Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    linked_ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id"), index=True)
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
    submitted_for_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(180))


class ResponseMacroRecord(TimestampMixin, Base):
    __tablename__ = "response_macros"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    shortcut: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class ProductionAccountReferenceRecord(TimestampMixin, Base):
    __tablename__ = "production_account_references"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    area: Mapped[str] = mapped_column(String(160), default="")
    account_name: Mapped[str] = mapped_column(String(180), nullable=False)
    account_identifier: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="requested", index=True)
    owner_email: Mapped[str] = mapped_column(String(255), default="")
    credential_reference: Mapped[str] = mapped_column(String(255), default="")
    docs_reference: Mapped[str] = mapped_column(String(500), default="")
    callback_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(180), default="")
    updated_by: Mapped[str] = mapped_column(String(180), default="")

    __table_args__ = (
        UniqueConstraint(
            "market_id",
            "provider",
            "account_name",
            name="uq_production_account_reference_market_provider_name",
        ),
    )


class OperationalAlertRecord(TimestampMixin, Base):
    __tablename__ = "operational_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    severity: Mapped[str] = mapped_column(String(32), default="warning", index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(180))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(180))

    __table_args__ = (
        UniqueConstraint("market_id", "dedupe_key", name="uq_operational_alert_market_dedupe"),
    )


class OperationalAlertDeliveryRecord(TimestampMixin, Base):
    __tablename__ = "operational_alert_deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("operational_alerts.id"), index=True)
    destination_type: Mapped[str] = mapped_column(String(64), default="webhook", index=True)
    destination_name: Mapped[str] = mapped_column(String(160), default="operations_webhook")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "alert_id",
            "destination_type",
            "destination_name",
            name="uq_alert_delivery_destination",
        ),
    )


class AnalyticsRollupRecord(TimestampMixin, Base):
    __tablename__ = "analytics_rollups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open_tickets: Mapped[int] = mapped_column(Integer, default=0)
    at_risk_tickets: Mapped[int] = mapped_column(Integer, default=0)
    breached_tickets: Mapped[int] = mapped_column(Integer, default=0)
    active_agents: Mapped[int] = mapped_column(Integer, default=0)
    avg_occupancy: Mapped[int] = mapped_column(Integer, default=0)
    avg_csat: Mapped[float | None] = mapped_column(Float)
    channel_volume: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("market_id", "period_start", name="uq_analytics_rollup_market_period"),
    )


class AttachmentRecord(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    timeline_event_id: Mapped[str | None] = mapped_column(ForeignKey("timeline_events.id"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(180), nullable=False)
    scan_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    scan_result: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    retained_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(180))
    deletion_reason: Mapped[str | None] = mapped_column(Text)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


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
