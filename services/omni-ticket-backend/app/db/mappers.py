from app.db.models import (
    AgentRecord,
    AttachmentRecord,
    AiDecisionRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    ChannelRecord,
    ConnectorAccountRecord,
    CompanyRecord,
    ConnectorEventRecord,
    CustomerRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    MarketRecord,
    OutboundMessageRecord,
    TicketRecord,
    TimelineEventRecord,
    UserRecord,
    WorkspaceSettingsRecord,
)
from app.models.domain import (
    Agent,
    AgentStatus,
    AiDecision,
    AuditEvent,
    Attachment,
    AttachmentScanStatus,
    AutomationRule,
    Channel,
    ChannelHealth,
    ChannelType,
    Company,
    ConnectorEvent,
    ConnectorAccount,
    ConnectorAccountStatus,
    ContactPoint,
    Customer,
    Handoff,
    KnowledgeArticle,
    Market,
    OutboundMessage,
    OutboundMessageStatus,
    Sentiment,
    Ticket,
    TimelineEvent,
    User,
    UserRole,
    WorkspaceSettings,
)


def market_from_record(record: MarketRecord) -> Market:
    return Market(
        id=record.id,
        code=record.code,
        name=record.name,
        timezone=record.timezone,
        currency=record.currency,
        default_locale=record.default_locale,
        support_email=record.support_email,
        whatsapp_number=record.whatsapp_number,
        facebook_page=record.facebook_page,
        instagram_handle=record.instagram_handle,
        active=record.active,
    )


def user_from_record(record: UserRecord) -> User:
    return User(
        id=record.id,
        name=record.name,
        email=record.email,
        role=UserRole(record.role),
        market_ids=record.market_ids,
        default_market_id=record.default_market_id,
        active=record.active,
        password_reset_required=record.password_reset_required,
        last_login_at=record.last_login_at,
    )


def workspace_settings_from_record(record: WorkspaceSettingsRecord) -> WorkspaceSettings:
    return WorkspaceSettings(
        market_id=record.market_id,
        ai_work_queue_automation_enabled=record.ai_work_queue_automation_enabled,
        ai_can_send_customer_messages=record.ai_can_send_customer_messages,
        default_timezone=record.default_timezone,
        business_hours=record.business_hours,
        public_brand_name=record.public_brand_name,
    )


def channel_from_record(record: ChannelRecord) -> Channel:
    return Channel(
        id=record.id,
        market_id=record.market_id,
        type=ChannelType(record.type),
        name=record.name,
        handle=record.handle,
        health=ChannelHealth(record.health),
        queued=record.queued,
        active=record.active,
        sla_risk=record.sla_risk,
        capabilities=record.capabilities,
    )


def agent_from_record(record: AgentRecord) -> Agent:
    return Agent(
        id=record.id,
        market_ids=record.market_ids,
        name=record.name,
        email=record.email,
        team=record.role,
        status=AgentStatus(record.status),
        occupancy=record.occupancy,
        capacity=record.capacity,
        skills=[ChannelType(skill) for skill in record.skills],
        languages=record.languages,
    )


def company_from_record(record: CompanyRecord) -> Company:
    return Company(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        tier=record.tier,
        health_score=record.health_score,
        account_value=record.account_value,
    )


def customer_from_record(record: CustomerRecord) -> Customer:
    return Customer(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        email=record.email,
        company_id=record.company_id,
        location=record.location,
        sentiment=Sentiment(record.sentiment),
        preferred_channels=[ChannelType(channel) for channel in record.preferred_channels],
        contact_points=[ContactPoint.model_validate(point) for point in record.contact_points],
        tags=record.tags,
        notes=record.notes,
    )


def ticket_from_record(record: TicketRecord) -> Ticket:
    return Ticket.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "public_id": record.public_id,
            "subject": record.subject,
            "description": record.description,
            "customer_id": record.customer_id,
            "channel": record.channel,
            "status": record.status,
            "priority": record.priority,
            "sentiment": record.sentiment,
            "assignee_id": record.assignee_id,
            "team": record.team,
            "tags": record.tags,
            "tasks": record.tasks,
            "sla": record.sla,
            "ai_summary": record.ai_summary,
            "recommended_action": record.recommended_action,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def timeline_event_from_record(record: TimelineEventRecord) -> TimelineEvent:
    return TimelineEvent.model_validate(
        {
            "id": record.id,
            "ticket_id": record.ticket_id,
            "type": record.type,
            "channel": record.channel,
            "actor": record.actor,
            "body": record.body,
            "created_at": record.created_at,
            "public": record.public,
            "metadata": record.event_metadata,
        }
    )


def handoff_from_record(record: HandoffRecord) -> Handoff:
    return Handoff.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "ticket_id": record.ticket_id,
            "from_team": record.from_team,
            "to_team": record.to_team,
            "requested_by": record.requested_by,
            "reason": record.reason,
            "status": record.status,
            "due_at": record.due_at,
            "checklist": record.checklist,
            "blocker": record.blocker,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def knowledge_article_from_record(record: KnowledgeArticleRecord) -> KnowledgeArticle:
    return KnowledgeArticle.model_validate(
        {
            "id": record.id,
            "market_ids": record.market_ids,
            "title": record.title,
            "status": record.status,
            "language": record.language,
            "channels": record.channels,
            "tags": record.tags,
            "body": record.body,
            "updated_at": record.updated_at,
        }
    )


def automation_rule_from_record(record: AutomationRuleRecord) -> AutomationRule:
    return AutomationRule(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        enabled=record.enabled,
        trigger=record.trigger,
        action=record.action,
        last_fired_at=record.last_fired_at,
        failure_count=record.failure_count,
    )


def connector_event_from_record(record: ConnectorEventRecord) -> ConnectorEvent:
    return ConnectorEvent.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "provider": record.provider,
            "direction": record.direction,
            "external_id": record.external_id,
            "ticket_id": record.ticket_id,
            "status": record.status,
            "payload": record.payload,
            "created_at": record.created_at,
        }
    )


def connector_account_from_record(record: ConnectorAccountRecord) -> ConnectorAccount:
    return ConnectorAccount.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "provider": record.provider,
            "display_name": record.display_name,
            "account_identifier": record.account_identifier,
            "status": ConnectorAccountStatus(record.status),
            "intake_enabled": record.intake_enabled,
            "outbound_enabled": record.outbound_enabled,
            "webhook_url": record.webhook_url,
            "webhook_verified": record.webhook_verified,
            "credential_ref": record.credential_ref,
            "secret_configured": record.secret_configured,
            "last_sync_at": record.last_sync_at,
            "last_error": record.last_error,
            "failure_count": record.failure_count,
            "required_credentials": record.required_credentials,
            "capabilities": record.capabilities,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def outbound_message_from_record(record: OutboundMessageRecord) -> OutboundMessage:
    return OutboundMessage.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "ticket_id": record.ticket_id,
            "timeline_event_id": record.timeline_event_id,
            "connector_event_id": record.connector_event_id,
            "provider": record.provider,
            "status": OutboundMessageStatus(record.status),
            "actor": record.actor,
            "body": record.body,
            "idempotency_key": record.idempotency_key,
            "attempts": record.attempts,
            "max_attempts": record.max_attempts,
            "next_attempt_at": record.next_attempt_at,
            "sent_at": record.sent_at,
            "last_error": record.last_error,
            "payload": record.payload,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def attachment_from_record(record: AttachmentRecord) -> Attachment:
    return Attachment.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "ticket_id": record.ticket_id,
            "timeline_event_id": record.timeline_event_id,
            "filename": record.filename,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "storage_key": record.storage_key,
            "uploaded_by": record.uploaded_by,
            "scan_status": AttachmentScanStatus(record.scan_status),
            "scan_result": record.scan_result,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def ai_decision_from_record(record: AiDecisionRecord) -> AiDecision:
    return AiDecision(
        id=record.id,
        ticket_id=record.ticket_id,
        created_at=record.created_at,
        decision_type=record.decision_type,
        confidence=record.confidence / 100,
        summary=record.summary,
        model_version=record.model_version,
        input_reference=record.input_reference,
        override_allowed=record.override_allowed,
    )


def audit_event_from_record(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        id=record.id,
        market_id=record.market_id,
        actor=record.actor,
        action=record.action,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        created_at=record.created_at,
        details=record.details,
    )
