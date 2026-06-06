from app.db.models import (
    AgentRecord,
    AttachmentRecord,
    AiDecisionRecord,
    AnalyticsRollupRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    BusinessHoursRecord,
    ChannelRecord,
    ConnectorAccountRecord,
    CompanyRecord,
    ConnectorEventRecord,
    CsatFeedbackRecord,
    CsatSurveyRecord,
    CustomFieldDefinitionRecord,
    CustomObjectRecord,
    CustomerRecord,
    EmailNotificationRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    OperationalAlertDeliveryRecord,
    MarketRecord,
    OperationalAlertRecord,
    OutboundMessageRecord,
    ProductionAccountReferenceRecord,
    ResponseMacroRecord,
    ScenarioAutomationRecord,
    SlaPolicyRecord,
    SupportGroupRecord,
    TagRecord,
    TicketRecord,
    TicketFieldRecord,
    TicketTemplateRecord,
    TimelineEventRecord,
    UserRecord,
    WorkspaceSettingsRecord,
)
from app.core.permissions import effective_permissions_for, normalize_permission_overrides
from app.models.domain import (
    Agent,
    AgentStatus,
    AiDecision,
    AnalyticsRollup,
    AuditEvent,
    Attachment,
    AttachmentLifecycleStatus,
    AttachmentScanStatus,
    AutomationRule,
    BusinessHours,
    Channel,
    ChannelHealth,
    ChannelType,
    Company,
    ConnectorEvent,
    ConnectorAccount,
    ConnectorAccountStatus,
    ContactPoint,
    CsatFeedback,
    CsatSource,
    CsatSurvey,
    Customer,
    CustomFieldDefinition,
    CustomObject,
    EmailNotification,
    Handoff,
    KnowledgeArticle,
    Market,
    OperationalAlert,
    OperationalAlertDelivery,
    OperationalAlertDeliveryStatus,
    OperationalAlertSeverity,
    OperationalAlertStatus,
    OutboundMessage,
    OutboundMessageStatus,
    ProductionAccountReference,
    ResponseMacro,
    ScenarioAutomation,
    SlaPolicy,
    SupportGroup,
    Tag,
    TicketField,
    TicketTemplate,
    Sentiment,
    Ticket,
    TimelineEvent,
    User,
    PermissionProfile,
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
    permission_overrides = normalize_permission_overrides(record.permission_overrides)
    permission_profile = PermissionProfile(record.permission_profile)
    return User(
        id=record.id,
        name=record.name,
        email=record.email,
        role=UserRole(record.role),
        market_ids=record.market_ids,
        default_market_id=record.default_market_id,
        active=record.active,
        password_reset_required=record.password_reset_required,
        mfa_enabled=record.mfa_enabled,
        mfa_confirmed_at=record.mfa_confirmed_at,
        mfa_last_verified_at=record.mfa_last_verified_at,
        permission_profile=permission_profile,
        permission_overrides=permission_overrides,
        effective_permissions=effective_permissions_for(
            record.role,
            permission_profile,
            permission_overrides,
        ),
        external_identity_provider=record.external_identity_provider,
        external_subject=record.external_subject,
        external_last_login_at=record.external_last_login_at,
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


def support_group_from_record(
    record: SupportGroupRecord,
    *,
    member_count: int = 0,
    open_ticket_count: int = 0,
    sla_risk_count: int = 0,
) -> SupportGroup:
    return SupportGroup.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "description": record.description,
            "team_email": record.team_email or None,
            "active": record.active,
            "channels": record.channels,
            "skills": record.skills,
            "member_count": member_count,
            "open_ticket_count": open_ticket_count,
            "sla_risk_count": sla_risk_count,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def sla_policy_from_record(record: SlaPolicyRecord) -> SlaPolicy:
    return SlaPolicy.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "active": record.active,
            "channels": record.channels,
            "priority": record.priority,
            "first_response_minutes": record.first_response_minutes,
            "resolution_minutes": record.resolution_minutes,
            "business_hours": record.business_hours,
            "position": record.position,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def business_hours_from_record(record: BusinessHoursRecord) -> BusinessHours:
    return BusinessHours.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "timezone": record.timezone,
            "active": record.active,
            "days": record.days or [],
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def csat_survey_from_record(record: CsatSurveyRecord) -> CsatSurvey:
    return CsatSurvey.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "question": record.question,
            "scale": record.scale,
            "channels": record.channels or [],
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def email_notification_from_record(record: EmailNotificationRecord) -> EmailNotification:
    return EmailNotification.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "event": record.event,
            "recipients": record.recipients or [],
            "subject": record.subject,
            "body": record.body,
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def custom_field_definition_from_record(
    record: CustomFieldDefinitionRecord,
) -> CustomFieldDefinition:
    return CustomFieldDefinition.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "entity": record.entity,
            "key": record.key,
            "label": record.label,
            "field_type": record.field_type,
            "required": record.required,
            "active": record.active,
            "options": record.options or [],
            "help_text": record.help_text,
            "position": record.position,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def custom_object_from_record(record: CustomObjectRecord) -> CustomObject:
    return CustomObject.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "key": record.key,
            "name": record.name,
            "description": record.description,
            "fields": record.fields or [],
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def scenario_automation_from_record(record: ScenarioAutomationRecord) -> ScenarioAutomation:
    return ScenarioAutomation.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "description": record.description,
            "actions": record.actions or [],
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def tag_from_record(record: TagRecord) -> Tag:
    return Tag.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "color": record.color,
            "description": record.description,
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def ticket_template_from_record(record: TicketTemplateRecord) -> TicketTemplate:
    return TicketTemplate.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "subject": record.subject,
            "description": record.description,
            "priority": record.priority,
            "channel": record.channel,
            "group": record.group,
            "tags": record.tags or [],
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
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
            "custom_fields": record.custom_fields,
            "tasks": record.tasks,
            "sla": record.sla,
            "ai_summary": record.ai_summary,
            "recommended_action": record.recommended_action,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def ticket_field_from_record(record: TicketFieldRecord) -> TicketField:
    return TicketField.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "key": record.key,
            "label": record.label,
            "field_type": record.field_type,
            "required": record.required,
            "active": record.active,
            "system": record.system,
            "options": record.options,
            "channels": record.channels,
            "placeholder": record.placeholder,
            "help_text": record.help_text,
            "position": record.position,
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


def csat_feedback_from_record(record: CsatFeedbackRecord) -> CsatFeedback:
    return CsatFeedback.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "ticket_id": record.ticket_id,
            "customer_id": record.customer_id,
            "rating": record.rating,
            "comment": record.comment,
            "source": CsatSource(record.source),
            "submitted_by": record.submitted_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def handoff_from_record(record: HandoffRecord) -> Handoff:
    return Handoff.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "ticket_id": record.ticket_id,
            "linked_ticket_id": record.linked_ticket_id,
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
            "submitted_for_review_at": record.submitted_for_review_at,
            "approved_at": record.approved_at,
            "approved_by": record.approved_by,
            "updated_at": record.updated_at,
        }
    )


def response_macro_from_record(record: ResponseMacroRecord) -> ResponseMacro:
    return ResponseMacro.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "body": record.body,
            "language": record.language,
            "channels": record.channels,
            "tags": record.tags,
            "shortcut": record.shortcut,
            "active": record.active,
            "usage_count": record.usage_count,
            "last_used_at": record.last_used_at,
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


def production_account_reference_from_record(
    record: ProductionAccountReferenceRecord,
) -> ProductionAccountReference:
    return ProductionAccountReference.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "provider": record.provider,
            "area": record.area,
            "account_name": record.account_name,
            "account_identifier": record.account_identifier,
            "status": record.status,
            "owner_email": record.owner_email or None,
            "credential_reference": record.credential_reference,
            "docs_reference": record.docs_reference,
            "callback_urls": record.callback_urls,
            "notes": record.notes,
            "created_by": record.created_by,
            "updated_by": record.updated_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def analytics_rollup_from_record(record: AnalyticsRollupRecord) -> AnalyticsRollup:
    return AnalyticsRollup.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "period_start": record.period_start,
            "period_end": record.period_end,
            "open_tickets": record.open_tickets,
            "at_risk_tickets": record.at_risk_tickets,
            "breached_tickets": record.breached_tickets,
            "active_agents": record.active_agents,
            "avg_occupancy": record.avg_occupancy,
            "avg_csat": record.avg_csat,
            "channel_volume": {
                ChannelType(channel): count
                for channel, count in record.channel_volume.items()
            },
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def operational_alert_from_record(record: OperationalAlertRecord) -> OperationalAlert:
    return OperationalAlert.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "severity": OperationalAlertSeverity(record.severity),
            "status": OperationalAlertStatus(record.status),
            "source": record.source,
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
            "dedupe_key": record.dedupe_key,
            "title": record.title,
            "message": record.message,
            "details": record.details,
            "occurrence_count": record.occurrence_count,
            "first_seen_at": record.first_seen_at,
            "last_seen_at": record.last_seen_at,
            "acknowledged_at": record.acknowledged_at,
            "acknowledged_by": record.acknowledged_by,
            "resolved_at": record.resolved_at,
            "resolved_by": record.resolved_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def operational_alert_delivery_from_record(
    record: OperationalAlertDeliveryRecord,
) -> OperationalAlertDelivery:
    return OperationalAlertDelivery.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "alert_id": record.alert_id,
            "destination_type": record.destination_type,
            "destination_name": record.destination_name,
            "status": OperationalAlertDeliveryStatus(record.status),
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
            "lifecycle_status": AttachmentLifecycleStatus(record.lifecycle_status),
            "retained_until": record.retained_until,
            "deleted_at": record.deleted_at,
            "deleted_by": record.deleted_by,
            "deletion_reason": record.deletion_reason,
            "purged_at": record.purged_at,
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
