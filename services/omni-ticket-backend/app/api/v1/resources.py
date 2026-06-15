import csv
from dataclasses import asdict
from datetime import datetime, timezone
import io
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_store
from app.api.v1.rbac import require_admin, require_audit_reader, require_operator, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.core.attachment_tokens import (
    create_attachment_download_token,
    parse_attachment_download_token,
)
from app.core.config import settings as app_settings
from app.core.rate_limit import (
    RateLimitExceeded,
    raise_rate_limit_exceeded,
)
from app.core.store import InMemoryStore
from app.core.webhooks import verify_webhook_signature
from app.db.audit import (
    audit_retention_policy,
    list_audit_events as list_audit_event_records,
    prune_audit_events,
    write_audit_event,
)
from app.db.alert_deliveries import operational_alert_delivery_repository
from app.db.alerts import operational_alert_repository
from app.db.connectors import connector_account_repository
from app.db.email_settings import email_provider_settings_repository
from app.db.integration_credentials import integration_credential_settings_repository
from app.db.sso_settings import sso_provider_settings_repository
from app.db.widget_settings import widget_settings_repository
from app.db.management import management_repository
from app.db.mappers import (
    audit_event_from_record,
    company_from_record,
    customer_from_record,
    market_from_record,
    user_from_record,
)
from app.db.models import AuditEventRecord, CompanyRecord, CustomerRecord, MarketRecord, TicketRecord, UserRecord
from app.db.operations import operations_repository
from app.db.outbound import outbound_repository
from app.db.production_accounts import production_account_reference_repository
from app.db.rate_limit import database_rate_limiter
from app.db.session import get_db
from app.db.settings import get_or_create_workspace_settings, workspace_settings_from_record
from app.db.store_sync import persist_store_state
from app.db.ticketing import case_repository, ticket_repository
from app.models.domain import (
    Agent,
    AnalyticsRollup,
    AnalyticsSnapshot,
    AppendEventRequest,
    AutomationRule,
    Attachment,
    AttachmentDownloadLink,
    AttachmentLifecycleStatus,
    AttachmentProviderConfig,
    AttachmentRetentionPolicy,
    AttachmentRetentionResult,
    AuditEvent,
    AuditRetentionPolicy,
    AuditRetentionResult,
    BusinessHours,
    InboundProviderConfig,
    Channel,
    ChannelType,
    Company,
    ConnectorAccount,
    ConnectorEvent,
    ConnectorInboundRequest,
    CsatFeedback,
    CsatSurvey,
    CustomFieldDefinition,
    CustomObject,
    EmailNotification,
    Product,
    SavedReport,
    ServiceAppointment,
    ScenarioAutomation,
    CreateAutomationRuleRequest,
    CreateAttachmentRequest,
    CreateBusinessHoursRequest,
    CreateCompanyRequest,
    CreateConnectorAccountRequest,
    CreateCsatFeedbackRequest,
    CreateHandoffRequest,
    CreateCustomerRequest,
    CreateKnowledgeArticleRequest,
    CreateProductionAccountReferenceRequest,
    CreateResponseMacroRequest,
    CreateSlaPolicyRequest,
    CreateSupportGroupRequest,
    CreateTagRequest,
    CreateCsatSurveyRequest,
    CreateEmailNotificationRequest,
    CreateScenarioAutomationRequest,
    CreateCustomFieldDefinitionRequest,
    CreateCustomObjectRequest,
    CreateProductRequest,
    CreateSavedReportRequest,
    CreateServiceAppointmentRequest,
    CreateDiscussionTopicRequest,
    CreateDiscussionCommentRequest,
    CreateCaseRequest,
    CreateTicketFieldRequest,
    CreateTicketRequest,
    CreateTicketTemplateRequest,
    Case,
    CaseTicketRequest,
    UpdateCaseRequest,
    Customer,
    DeleteAttachmentRequest,
    DiscussionComment,
    DiscussionTopic,
    DuplicateTicketSuggestion,
    EmailProviderSettings,
    GlobalSearchResult,
    Handoff,
    IntegrationCredentialSettings,
    KnowledgeArticle,
    KnowledgeSuggestion,
    MergeTicketsRequest,
    MergeTicketsResponse,
    OperationalAlert,
    OperationalAlertDelivery,
    OperationalAlertDeliveryConfig,
    OperationalAlertStatus,
    OutboundMessage,
    OutboundMessageStatus,
    OutboundProviderConfig,
    Permission,
    ProductionAccountRequestDelivery,
    ProductionAccountRequestPack,
    ProductionAccountReference,
    ProductionAccountReferenceDocs,
    ProductionReadinessChecklist,
    PortalAttachmentResponse,
    PortalAnswersResponse,
    PortalAnswerSuggestion,
    PortalTicketDetailResponse,
    PortalTicketReplyRequest,
    PortalTicketResponse,
    PortalTicketTimelineEvent,
    Priority,
    ReplyRequest,
    ResponseMacro,
    ResponseMacroSuggestion,
    RetryOutboundMessageRequest,
    SlaPolicy,
    SsoProviderSettings,
    SupervisorRecommendation,
    SupportGroup,
    Tag,
    Ticket,
    TicketField,
    TicketTemplate,
    TimelineEvent,
    TimelineEventType,
    CreatePortalTicketRequest,
    UpdateAutomationRuleRequest,
    UpdateAgentStatusRequest,
    UpdateBusinessHoursRequest,
    UpdateChannelRequest,
    UpdateCompanyRequest,
    UpdateConnectorAccountRequest,
    UpdateCustomerRequest,
    UpdateEmailProviderSettingsRequest,
    UpdateHandoffRequest,
    UpdateIntegrationCredentialSettingsRequest,
    UpdateKnowledgeArticleRequest,
    UpdateOperationalAlertRequest,
    UpdateProductionAccountReferenceRequest,
    UpdateResponseMacroRequest,
    UpdateSlaPolicyRequest,
    UpdateSupportGroupRequest,
    UpdateTagRequest,
    UpdateCsatSurveyRequest,
    UpdateEmailNotificationRequest,
    UpdateScenarioAutomationRequest,
    UpdateCustomFieldDefinitionRequest,
    UpdateCustomObjectRequest,
    UpdateProductRequest,
    UpdateSavedReportRequest,
    UpdateServiceAppointmentRequest,
    UpdateDiscussionTopicRequest,
    UpdateSsoProviderSettingsRequest,
    UpdateTicketFieldRequest,
    UpdateTicketRequest,
    UpdateTicketTemplateRequest,
    UpdateWidgetSettingsRequest,
    WidgetSettings,
    WorkQueueItem,
    WorkQueueOverrideRequest,
    utc_now,
)
from app.services import attachments as attachment_services
from app.services.alert_delivery import alert_delivery_service
from app.services.facebook_webhooks import facebook_webhook_adapter
from app.services.global_search import global_search_service
from app.services.inbound_adapters import inbound_adapter_router
from app.services.instagram_webhooks import instagram_webhook_adapter
from app.services.outbound_adapters import outbound_adapter_router
from app.services.production_readiness import (
    production_account_request_pack,
    production_readiness_checklist,
    queue_production_account_request_email,
)
from app.services.sms_webhooks import sms_webhook_adapter
from app.services.supervisor_recommendations import supervisor_recommendation_service
from app.services.voice_webhooks import voice_webhook_adapter
from app.services.whatsapp_webhooks import whatsapp_webhook_adapter

router = APIRouter(tags=["operations"])


def _request_origin(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    proto = (forwarded_proto or request.url.scheme or "https").split(",", 1)[0].strip()
    host = (forwarded_host or request.headers.get("host") or request.url.netloc).split(",", 1)[0].strip()
    return f"{proto}://{host}".rstrip("/")


_CUSTOMER_SORT_COLUMNS = {
    "name": CustomerRecord.name,
    "email": CustomerRecord.email,
    "sentiment": CustomerRecord.sentiment,
    "created_at": CustomerRecord.created_at,
    "updated_at": CustomerRecord.updated_at,
}


def _etag_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_etag(record: Any) -> str:
    return f'"{_etag_timestamp(record.updated_at)}"'


def _set_resource_etag(response: Response, record: Any) -> None:
    response.headers["ETag"] = _record_etag(record)


def _assert_fresh_record(record: Any, if_match: str | None) -> None:
    if not if_match:
        return
    expected = _record_etag(record)
    expected_unquoted = expected.strip('"')
    candidates = {candidate.strip() for candidate in if_match.split(",") if candidate.strip()}
    if "*" in candidates or expected in candidates or expected_unquoted in candidates:
        return
    raise HTTPException(
        status.HTTP_412_PRECONDITION_FAILED,
        detail="Resource has changed; refresh before retrying.",
    )


def _set_list_headers(
    response: Response,
    *,
    total: int,
    returned: int,
    limit: int | None,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> None:
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Returned-Count"] = str(returned)
    response.headers["X-Limit"] = str(limit if limit is not None else total)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Sort"] = f"{sort_by}:{sort_order}"


def _company_record_or_404(db: Session, company_id: str, market_id: str) -> CompanyRecord:
    company = db.get(CompanyRecord, company_id)
    if company is None or company.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def _customer_record_or_404(db: Session, customer_id: str, market_id: str) -> CustomerRecord:
    customer = db.get(CustomerRecord, customer_id)
    if customer is None or customer.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def _ticket_record_or_404(db: Session, ticket_id: str, market_id: str) -> TicketRecord:
    ticket = db.get(TicketRecord, ticket_id)
    if ticket is None or ticket.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _sync_company_to_store(state: InMemoryStore, company: Company) -> None:
    state.companies[company.id] = company


def _sync_customer_to_store(state: InMemoryStore, customer: Customer) -> None:
    state.customers[customer.id] = customer


def _signed_webhook_adapter(provider: ChannelType) -> Any | None:
    return {
        ChannelType.facebook: facebook_webhook_adapter,
        ChannelType.instagram: instagram_webhook_adapter,
        ChannelType.sms: sms_webhook_adapter,
        ChannelType.voice: voice_webhook_adapter,
        ChannelType.whatsapp: whatsapp_webhook_adapter,
    }.get(provider)


def _ticket_context_with_suggestions(
    db: Session,
    state: InMemoryStore,
    *,
    ticket_id: str,
    market_id: str,
) -> dict:
    ticket_context = ticket_repository.get_ticket_context(db, state, ticket_id, market_id)
    ticket_context["knowledge_suggestions"] = management_repository.suggest_knowledge_for_ticket(
        db,
        state,
        ticket_id,
        market_id,
    )
    ticket_context["macro_suggestions"] = management_repository.suggest_response_macros_for_ticket(
        db,
        state,
        ticket_id,
        market_id,
    )
    ticket_context["duplicate_suggestions"] = ticket_repository.suggest_duplicate_tickets(
        db,
        state,
        ticket_id,
        market_id,
    )
    return ticket_context


def _portal_market_record_or_404(db: Session, market_code: str) -> MarketRecord:
    code = market_code.strip().lower()
    record = db.scalar(
        select(MarketRecord).where(
            func.lower(MarketRecord.code) == code,
            MarketRecord.active.is_(True),
        )
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market portal not found")
    return record


def _client_rate_limit_identity(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _portal_suggestion_payload(suggestion: Any) -> PortalAnswerSuggestion:
    article = suggestion.article
    return PortalAnswerSuggestion(
        article_id=article.id,
        title=article.title,
        body=article.body,
        language=article.language,
        tags=article.tags,
        score=suggestion.score,
        reasons=suggestion.reasons,
        matched_terms=suggestion.matched_terms,
        updated_at=article.updated_at,
    )


def _portal_contact_points(email: str, phone: str | None) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = [
        {"channel": ChannelType.email.value, "value": email, "verified": False},
        {"channel": ChannelType.portal.value, "value": email, "verified": False},
    ]
    if phone:
        points.append({"channel": ChannelType.voice.value, "value": phone, "verified": False})
    return points


def _portal_ticket_record_for_email_or_404(
    db: Session,
    *,
    market_id: str,
    public_id: str,
    email: str,
) -> tuple[TicketRecord, CustomerRecord]:
    ticket = db.scalar(
        select(TicketRecord).where(
            TicketRecord.market_id == market_id,
            func.lower(TicketRecord.public_id) == public_id.strip().lower(),
        )
    )
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    customer = db.get(CustomerRecord, ticket.customer_id)
    if (
        customer is None
        or customer.market_id != market_id
        or customer.email.lower() != email.strip().lower()
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket, customer


def _portal_customer_status(status_value: str) -> str:
    if status_value == "open":
        return "Support is reviewing your request"
    if status_value == "pending":
        return "Waiting for your reply"
    if status_value == "waiting":
        return "Waiting for a partner update"
    if status_value == "solved":
        return "Resolved"
    if status_value == "closed":
        return "Closed"
    return "In progress"


def _portal_next_step(status_value: str) -> str:
    if status_value == "pending":
        return "Reply here with the requested details so the support team can continue."
    if status_value == "waiting":
        return "The support team is tracking the next external update."
    if status_value in {"solved", "closed"}:
        return "Reply here if you still need help and the ticket will return to the support queue."
    return "The support team has the request and will post the next public update here."


def _portal_public_event_payload(event: TimelineEvent) -> PortalTicketTimelineEvent:
    return PortalTicketTimelineEvent(
        id=event.id,
        type=event.type,
        channel=event.channel,
        actor=event.actor,
        body=event.body,
        created_at=event.created_at,
    )


def _portal_attachment_payload(attachment: Attachment) -> PortalAttachmentResponse:
    return PortalAttachmentResponse(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        scan_status=attachment.scan_status,
        lifecycle_status=attachment.lifecycle_status,
        created_at=attachment.created_at,
    )


def _portal_visible_attachments(
    db: Session,
    state: InMemoryStore,
    *,
    market_id: str,
    ticket_id: str,
) -> list[PortalAttachmentResponse]:
    return [
        _portal_attachment_payload(attachment)
        for attachment in ticket_repository.list_attachments(db, state, ticket_id, market_id)
        if attachment.uploaded_by.startswith("customer-portal:")
        and attachment.lifecycle_status != AttachmentLifecycleStatus.purged
    ]


def _portal_ticket_detail_payload(
    db: Session,
    state: InMemoryStore,
    *,
    market_id: str,
    market_code: str,
    ticket_id: str,
) -> PortalTicketDetailResponse:
    context = ticket_repository.get_ticket_context(db, state, ticket_id, market_id)
    ticket: Ticket = context["ticket"]
    public_events = [
        _portal_public_event_payload(event)
        for event in context["timeline"]
        if event.public
    ]
    suggestion_query = " ".join(
        [ticket.subject, ticket.description, *[event.body for event in public_events[-3:]]]
    )
    suggestions = management_repository.suggest_public_knowledge(
        db,
        state,
        market_id,
        suggestion_query,
        channel=ChannelType.portal.value,
        limit=3,
    )
    return PortalTicketDetailResponse(
        ticket_id=ticket.id,
        public_id=ticket.public_id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        customer_status=_portal_customer_status(ticket.status.value),
        priority=ticket.priority,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        next_step=_portal_next_step(ticket.status.value),
        reply_allowed=True,
        timeline=public_events,
        attachments=_portal_visible_attachments(
            db,
            state,
            market_id=market_id,
            ticket_id=ticket_id,
        ),
        article_suggestions=[_portal_suggestion_payload(suggestion) for suggestion in suggestions],
    )


@router.get("/portal/{market_code}/answers", response_model=PortalAnswersResponse)
def read_portal_answers(
    market_code: str,
    request: Request,
    q: str = Query("", max_length=500),
    limit: int = Query(5, ge=1, le=10),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> PortalAnswersResponse:
    market = _portal_market_record_or_404(db, market_code)
    try:
        database_rate_limiter.check(
            db,
            f"portal-answers:{market.id}:{_client_rate_limit_identity(request)}",
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)
    suggestions = management_repository.suggest_public_knowledge(
        db,
        state,
        market.id,
        q,
        channel=ChannelType.portal.value,
        limit=limit,
    )
    ticket_fields = management_repository.list_ticket_fields(
        db,
        state,
        market.id,
        active_only=True,
        channel=ChannelType.portal.value,
    )
    return PortalAnswersResponse(
        market_id=market.id,
        market_code=market.code.lower(),
        query=q.strip(),
        suggestions=[_portal_suggestion_payload(suggestion) for suggestion in suggestions],
        ticket_fields=ticket_fields,
    )


@router.post(
    "/portal/{market_code}/tickets",
    response_model=PortalTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_portal_ticket(
    market_code: str,
    request_body: CreatePortalTicketRequest,
    request: Request,
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> PortalTicketResponse:
    market = _portal_market_record_or_404(db, market_code)
    email = str(request_body.email).lower()
    try:
        database_rate_limiter.check(
            db,
            f"portal-ticket:{market.id}:{_client_rate_limit_identity(request)}:{email}",
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)
    customer = db.scalar(
        select(CustomerRecord).where(
            CustomerRecord.market_id == market.id,
            CustomerRecord.email == email,
        )
    )
    contact_points = _portal_contact_points(email, request_body.phone)
    if customer is None:
        customer = CustomerRecord(
            id=f"customer_{uuid4().hex}",
            market_id=market.id,
            name=request_body.name.strip(),
            email=email,
            preferred_channels=[ChannelType.portal.value],
            contact_points=contact_points,
            tags=["portal"],
            notes="Created from public Help Center ticket intake.",
        )
        db.add(customer)
        db.flush()
    else:
        merged_points = list(customer.contact_points or [])
        for point in contact_points:
            if not any(
                existing.get("channel") == point["channel"]
                and existing.get("value") == point["value"]
                for existing in merged_points
            ):
                merged_points.append(point)
        customer.name = request_body.name.strip() or customer.name
        customer.preferred_channels = sorted(
            set(customer.preferred_channels or []) | {ChannelType.portal.value}
        )
        customer.contact_points = merged_points
        customer.tags = sorted(set(customer.tags or []) | {"portal"})
        customer.updated_at = utc_now()
        db.flush()
    state.customers[customer.id] = customer_from_record(customer)
    settings = workspace_settings_from_record(get_or_create_workspace_settings(db, market_from_record(market)))
    ticket = ticket_repository.create_ticket(
        db,
        state,
        CreateTicketRequest(
            subject=request_body.subject.strip(),
            description=request_body.description.strip(),
            customer_id=customer.id,
            channel=ChannelType.portal,
            priority=request_body.priority,
            tags=["portal", "customer-submitted"],
            custom_fields=request_body.custom_fields,
        ),
        market.id,
        ai_enabled=settings.ai_work_queue_automation_enabled,
        actor="customer-portal",
        source="portal",
    )
    suggestions = management_repository.suggest_public_knowledge(
        db,
        state,
        market.id,
        request_body.search_query or f"{request_body.subject} {request_body.description}",
        channel=ChannelType.portal.value,
        limit=3,
    )
    return PortalTicketResponse(
        ticket_id=ticket.id,
        public_id=ticket.public_id,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at,
        article_suggestions=[_portal_suggestion_payload(suggestion) for suggestion in suggestions],
    )


@router.get(
    "/portal/{market_code}/tickets/{public_id}",
    response_model=PortalTicketDetailResponse,
)
def read_portal_ticket(
    market_code: str,
    public_id: str,
    request: Request,
    email: str = Query(..., min_length=3, max_length=254),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> PortalTicketDetailResponse:
    market = _portal_market_record_or_404(db, market_code)
    email = email.strip().lower()
    try:
        database_rate_limiter.check(
            db,
            f"portal-ticket-view:{market.id}:{_client_rate_limit_identity(request)}:{public_id}:{email}",
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)
    ticket, _customer = _portal_ticket_record_for_email_or_404(
        db,
        market_id=market.id,
        public_id=public_id,
        email=email,
    )
    return _portal_ticket_detail_payload(
        db,
        state,
        market_id=market.id,
        market_code=market.code.lower(),
        ticket_id=ticket.id,
    )


@router.post(
    "/portal/{market_code}/tickets/{public_id}/reply",
    response_model=PortalTicketDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_portal_ticket_reply(
    market_code: str,
    public_id: str,
    request_body: PortalTicketReplyRequest,
    request: Request,
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> PortalTicketDetailResponse:
    market = _portal_market_record_or_404(db, market_code)
    email = str(request_body.email).lower()
    try:
        database_rate_limiter.check(
            db,
            f"portal-ticket-reply:{market.id}:{_client_rate_limit_identity(request)}:{public_id}:{email}",
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)
    ticket, customer = _portal_ticket_record_for_email_or_404(
        db,
        market_id=market.id,
        public_id=public_id,
        email=email,
    )
    ticket_repository.portal_customer_reply(
        db,
        state,
        ticket.id,
        market.id,
        actor=customer.name,
        body=request_body.body.strip(),
        submitted_by=email,
    )
    return _portal_ticket_detail_payload(
        db,
        state,
        market_id=market.id,
        market_code=market.code.lower(),
        ticket_id=ticket.id,
    )


@router.post(
    "/portal/{market_code}/tickets/{public_id}/attachments",
    response_model=PortalAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_portal_ticket_attachment(
    market_code: str,
    public_id: str,
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    email: str = Query(..., min_length=3, max_length=254),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> PortalAttachmentResponse:
    market = _portal_market_record_or_404(db, market_code)
    email = email.strip().lower()
    try:
        database_rate_limiter.check(
            db,
            f"portal-ticket-attachment:{market.id}:{_client_rate_limit_identity(request)}:{public_id}:{email}",
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)
    ticket, customer = _portal_ticket_record_for_email_or_404(
        db,
        market_id=market.id,
        public_id=public_id,
        email=email,
    )
    content = await request.body()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Attachment content is required")
    if len(content) > app_settings.attachment_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Attachment is too large")
    attachment_id = f"attachment_{uuid4().hex}"
    content_type = request.headers.get("content-type") or "application/octet-stream"
    scan_status, scan_result = attachment_services.scan_attachment_binary(
        filename=filename,
        content_type=content_type,
        data=content,
    )
    if scan_status == "clean":
        storage_key = attachment_services.attachment_storage.write(
            market_id=market.id,
            ticket_id=ticket.id,
            attachment_id=attachment_id,
            filename=filename,
            data=content,
            content_type=content_type,
        )
    else:
        storage_key = attachment_services.blocked_storage_key(
            market_id=market.id,
            ticket_id=ticket.id,
            attachment_id=attachment_id,
            filename=filename,
        )
    attachment = ticket_repository.create_attachment(
        db,
        state,
        ticket.id,
        CreateAttachmentRequest(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_key=storage_key,
        ),
        market.id,
        actor=f"customer-portal:{email}",
        attachment_id=attachment_id,
        scan_status_override=scan_status,
        scan_result_override=f"Public portal upload. {scan_result}",
    )
    ticket_repository.append_event(
        db,
        state,
        ticket.id,
        AppendEventRequest(
            type=TimelineEventType.attachment_added,
            channel=ChannelType.portal,
            actor=customer.name,
            body=f"Attachment received: {attachment.filename}.",
            public=True,
            metadata={
                "source": "portal",
                "attachment_id": attachment.id,
                "filename": attachment.filename,
                "scan_status": attachment.scan_status.value,
                "submitted_by": email,
            },
        ),
        market.id,
    )
    return _portal_attachment_payload(attachment)


@router.get("/audit", response_model=list[AuditEvent])
def read_audit_events(
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    require_audit_reader(context)
    records = list_audit_event_records(
        db,
        market_id=context.market_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [audit_event_from_record(record) for record in records]


@router.get("/audit/export")
def export_audit_events(
    format: str = Query("csv", pattern="^(csv|json)$"),
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(1000, ge=1, le=5000),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_audit_reader(context)
    bounded_limit = min(limit, app_settings.audit_export_max_rows)
    filters = {
        key: value
        for key, value in {
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }.items()
        if value
    }
    records = list_audit_event_records(
        db,
        market_id=context.market_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=bounded_limit,
    )
    events = [audit_event_from_record(record) for record in records]
    write_audit_event(
        db,
        actor=context.user.id,
        action="audit.export",
        entity_type="market",
        entity_id=context.market_id,
        market_id=context.market_id,
        details={"format": format, "rows": len(events), "filters": filters},
        commit=True,
    )
    if format == "json":
        return Response(
            content=json.dumps([event.model_dump(mode="json") for event in events]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=omni-audit-{context.market.code.lower()}.json"},
        )
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "market_id", "actor", "action", "entity_type", "entity_id", "created_at", "details"],
    )
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "id": event.id,
                "market_id": event.market_id or "",
                "actor": event.actor,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "created_at": event.created_at.isoformat(),
                "details": json.dumps(event.details, sort_keys=True),
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=omni-audit-{context.market.code.lower()}.csv"},
    )


@router.get("/audit/retention", response_model=AuditRetentionPolicy)
def read_audit_retention_policy(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AuditRetentionPolicy:
    require_audit_reader(context)
    return AuditRetentionPolicy.model_validate(
        audit_retention_policy(
            db,
            market_id=context.market_id,
            retention_days=app_settings.audit_retention_days,
            export_max_rows=app_settings.audit_export_max_rows,
        )
    )


@router.post("/audit/retention/prune", response_model=AuditRetentionResult)
def prune_audit_retention(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AuditRetentionResult:
    require_admin(context)
    deleted_events = prune_audit_events(
        db,
        market_id=context.market_id,
        retention_days=app_settings.audit_retention_days,
        state=state,
    )
    audit_record = write_audit_event(
        db,
        actor=context.user.id,
        action="audit.retention_prune",
        entity_type="market",
        entity_id=context.market_id,
        market_id=context.market_id,
        details={
            "deleted_events": deleted_events,
            "retention_days": app_settings.audit_retention_days,
        },
    )
    db.commit()
    return AuditRetentionResult(
        policy=AuditRetentionPolicy.model_validate(
            audit_retention_policy(
                db,
                market_id=context.market_id,
                retention_days=app_settings.audit_retention_days,
                export_max_rows=app_settings.audit_export_max_rows,
            )
        ),
        deleted_events=deleted_events,
        audit_event_id=audit_record.id,
    )


@router.get("/attachments/retention", response_model=AttachmentRetentionPolicy)
def read_attachment_retention_policy(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AttachmentRetentionPolicy:
    require_supervisor(context)
    return ticket_repository.attachment_retention_policy(
        db,
        market_id=context.market_id,
        active_retention_days=app_settings.attachment_retention_days,
        deleted_retention_days=app_settings.attachment_deleted_retention_days,
        prune_limit=app_settings.attachment_retention_prune_limit,
    )


@router.post("/attachments/retention/prune", response_model=AttachmentRetentionResult)
def prune_attachment_retention(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AttachmentRetentionResult:
    require_admin(context)
    attachment_ids, audit_event_id = ticket_repository.prune_attachment_retention(
        db,
        state,
        market_id=context.market_id,
        active_retention_days=app_settings.attachment_retention_days,
        deleted_retention_days=app_settings.attachment_deleted_retention_days,
        limit=app_settings.attachment_retention_prune_limit,
        actor=context.user.id,
        storage_delete=attachment_services.attachment_storage.delete,
    )
    return AttachmentRetentionResult(
        policy=ticket_repository.attachment_retention_policy(
            db,
            market_id=context.market_id,
            active_retention_days=app_settings.attachment_retention_days,
            deleted_retention_days=app_settings.attachment_deleted_retention_days,
            prune_limit=app_settings.attachment_retention_prune_limit,
        ),
        purged_attachments=len(attachment_ids),
        attachment_ids=attachment_ids,
        audit_event_id=audit_event_id,
    )


@router.get("/channels", response_model=list[Channel])
def list_channels(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Channel]:
    return management_repository.list_channels(db, state, context.market_id)


@router.patch("/channels/{channel_id}", response_model=Channel)
def update_channel(
    channel_id: str,
    request: UpdateChannelRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Channel:
    require_supervisor(context)
    return management_repository.update_channel(db, state, channel_id, request, context.market_id)


@router.get("/agents", response_model=list[Agent])
def list_agents(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Agent]:
    return management_repository.list_agents(db, state, context.market_id)


@router.patch("/agents/{agent_id}/status", response_model=Agent)
def update_agent_status(
    agent_id: str,
    request: UpdateAgentStatusRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Agent:
    require_supervisor(context)
    return management_repository.update_agent_status(db, state, agent_id, request, context.market_id)


@router.get("/support-groups", response_model=list[SupportGroup])
def list_support_groups(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[SupportGroup]:
    return management_repository.list_support_groups(db, state, context.market_id)


@router.get("/groups", response_model=list[SupportGroup])
def list_groups_alias(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[SupportGroup]:
    return list_support_groups(context, state, db)


@router.post("/support-groups", response_model=SupportGroup, status_code=status.HTTP_201_CREATED)
def create_support_group(
    request: CreateSupportGroupRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SupportGroup:
    require_admin(context)
    return management_repository.create_support_group(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/support-groups/{group_id}", response_model=SupportGroup)
def update_support_group(
    group_id: str,
    request: UpdateSupportGroupRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SupportGroup:
    require_admin(context)
    return management_repository.update_support_group(
        db,
        state,
        group_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/search", response_model=list[GlobalSearchResult])
def global_search(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(12, ge=1, le=50),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[GlobalSearchResult]:
    return global_search_service.search(
        db,
        market_id=context.market_id,
        query=q,
        limit=limit,
    )


@router.get("/sla-policies", response_model=list[SlaPolicy])
def list_sla_policies(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[SlaPolicy]:
    return management_repository.list_sla_policies(db, state, context.market_id)


@router.post("/sla-policies", response_model=SlaPolicy, status_code=status.HTTP_201_CREATED)
def create_sla_policy(
    request: CreateSlaPolicyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SlaPolicy:
    require_admin(context)
    return management_repository.create_sla_policy(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/sla-policies/{policy_id}", response_model=SlaPolicy)
def update_sla_policy(
    policy_id: str,
    request: UpdateSlaPolicyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SlaPolicy:
    require_admin(context)
    return management_repository.update_sla_policy(
        db,
        state,
        policy_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/business-hours", response_model=list[BusinessHours])
def list_business_hours(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[BusinessHours]:
    return management_repository.list_business_hours(db, state, context.market_id)


@router.post("/business-hours", response_model=BusinessHours, status_code=status.HTTP_201_CREATED)
def create_business_hours(
    request: CreateBusinessHoursRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> BusinessHours:
    require_admin(context)
    return management_repository.create_business_hours(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/business-hours/{business_hours_id}", response_model=BusinessHours)
def update_business_hours(
    business_hours_id: str,
    request: UpdateBusinessHoursRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> BusinessHours:
    require_admin(context)
    return management_repository.update_business_hours(
        db,
        state,
        business_hours_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/ticket-templates", response_model=list[TicketTemplate])
def list_ticket_templates(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[TicketTemplate]:
    return management_repository.list_ticket_templates(db, state, context.market_id)


@router.post("/ticket-templates", response_model=TicketTemplate, status_code=status.HTTP_201_CREATED)
def create_ticket_template(
    request: CreateTicketTemplateRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TicketTemplate:
    require_admin(context)
    return management_repository.create_ticket_template(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/ticket-templates/{template_id}", response_model=TicketTemplate)
def update_ticket_template(
    template_id: str,
    request: UpdateTicketTemplateRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TicketTemplate:
    require_admin(context)
    return management_repository.update_ticket_template(
        db,
        state,
        template_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/tags", response_model=list[Tag])
def list_tags(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Tag]:
    return management_repository.list_tags(db, state, context.market_id)


@router.post("/tags", response_model=Tag, status_code=status.HTTP_201_CREATED)
def create_tag(
    request: CreateTagRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Tag:
    require_admin(context)
    return management_repository.create_tag(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/tags/{tag_id}", response_model=Tag)
def update_tag(
    tag_id: str,
    request: UpdateTagRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Tag:
    require_admin(context)
    return management_repository.update_tag(
        db,
        state,
        tag_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/csat-surveys", response_model=list[CsatSurvey])
def list_csat_surveys(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[CsatSurvey]:
    return management_repository.list_csat_surveys(db, state, context.market_id)


@router.post("/csat-surveys", response_model=CsatSurvey, status_code=status.HTTP_201_CREATED)
def create_csat_survey(
    request: CreateCsatSurveyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CsatSurvey:
    require_admin(context)
    return management_repository.create_csat_survey(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/csat-surveys/{survey_id}", response_model=CsatSurvey)
def update_csat_survey(
    survey_id: str,
    request: UpdateCsatSurveyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CsatSurvey:
    require_admin(context)
    return management_repository.update_csat_survey(
        db,
        state,
        survey_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/email-notifications", response_model=list[EmailNotification])
def list_email_notifications(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[EmailNotification]:
    return management_repository.list_email_notifications(db, state, context.market_id)


@router.post(
    "/email-notifications", response_model=EmailNotification, status_code=status.HTTP_201_CREATED
)
def create_email_notification(
    request: CreateEmailNotificationRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> EmailNotification:
    require_admin(context)
    return management_repository.create_email_notification(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/email-notifications/{notification_id}", response_model=EmailNotification)
def update_email_notification(
    notification_id: str,
    request: UpdateEmailNotificationRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> EmailNotification:
    require_admin(context)
    return management_repository.update_email_notification(
        db,
        state,
        notification_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/scenario-automations", response_model=list[ScenarioAutomation])
def list_scenario_automations(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ScenarioAutomation]:
    return management_repository.list_scenario_automations(db, state, context.market_id)


@router.post(
    "/scenario-automations",
    response_model=ScenarioAutomation,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario_automation(
    request: CreateScenarioAutomationRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ScenarioAutomation:
    require_admin(context)
    return management_repository.create_scenario_automation(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/scenario-automations/{scenario_id}", response_model=ScenarioAutomation)
def update_scenario_automation(
    scenario_id: str,
    request: UpdateScenarioAutomationRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ScenarioAutomation:
    require_admin(context)
    return management_repository.update_scenario_automation(
        db,
        state,
        scenario_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/custom-fields", response_model=list[CustomFieldDefinition])
def list_custom_field_definitions(
    entity: str | None = None,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[CustomFieldDefinition]:
    fields = management_repository.list_custom_field_definitions(db, state, context.market_id)
    if entity is not None:
        fields = [field for field in fields if field.entity == entity]
    return fields


@router.post(
    "/custom-fields", response_model=CustomFieldDefinition, status_code=status.HTTP_201_CREATED
)
def create_custom_field_definition(
    request: CreateCustomFieldDefinitionRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomFieldDefinition:
    require_admin(context)
    return management_repository.create_custom_field_definition(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/custom-fields/{field_id}", response_model=CustomFieldDefinition)
def update_custom_field_definition(
    field_id: str,
    request: UpdateCustomFieldDefinitionRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomFieldDefinition:
    require_admin(context)
    return management_repository.update_custom_field_definition(
        db,
        state,
        field_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/custom-objects", response_model=list[CustomObject])
def list_custom_objects(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[CustomObject]:
    return management_repository.list_custom_objects(db, state, context.market_id)


@router.post("/custom-objects", response_model=CustomObject, status_code=status.HTTP_201_CREATED)
def create_custom_object(
    request: CreateCustomObjectRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomObject:
    require_admin(context)
    return management_repository.create_custom_object(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/custom-objects/{object_id}", response_model=CustomObject)
def update_custom_object(
    object_id: str,
    request: UpdateCustomObjectRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomObject:
    require_admin(context)
    return management_repository.update_custom_object(
        db,
        state,
        object_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/products", response_model=list[Product])
def list_products(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Product]:
    return management_repository.list_products(db, state, context.market_id)


@router.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(
    request: CreateProductRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Product:
    require_admin(context)
    return management_repository.create_product(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/products/{product_id}", response_model=Product)
def update_product(
    product_id: str,
    request: UpdateProductRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Product:
    require_admin(context)
    return management_repository.update_product(
        db,
        state,
        product_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/saved-reports", response_model=list[SavedReport])
def list_saved_reports(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[SavedReport]:
    return management_repository.list_saved_reports(db, state, context.market_id)


@router.post("/saved-reports", response_model=SavedReport, status_code=status.HTTP_201_CREATED)
def create_saved_report(
    request: CreateSavedReportRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SavedReport:
    require_admin(context)
    return management_repository.create_saved_report(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/saved-reports/{report_id}", response_model=SavedReport)
def update_saved_report(
    report_id: str,
    request: UpdateSavedReportRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SavedReport:
    require_admin(context)
    return management_repository.update_saved_report(
        db,
        state,
        report_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/service-appointments", response_model=list[ServiceAppointment])
def list_service_appointments(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ServiceAppointment]:
    return management_repository.list_service_appointments(db, state, context.market_id)


@router.post(
    "/service-appointments",
    response_model=ServiceAppointment,
    status_code=status.HTTP_201_CREATED,
)
def create_service_appointment(
    request: CreateServiceAppointmentRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ServiceAppointment:
    require_admin(context)
    return management_repository.create_service_appointment(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/service-appointments/{appointment_id}", response_model=ServiceAppointment)
def update_service_appointment(
    appointment_id: str,
    request: UpdateServiceAppointmentRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ServiceAppointment:
    require_admin(context)
    return management_repository.update_service_appointment(
        db,
        state,
        appointment_id,
        request,
        context.market_id,
        context.user.email,
    )


@router.get("/forums/topics", response_model=list[DiscussionTopic])
def list_discussion_topics(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[DiscussionTopic]:
    return management_repository.list_discussion_topics(db, state, context.market_id)


@router.post(
    "/forums/topics",
    response_model=DiscussionTopic,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_topic(
    request: CreateDiscussionTopicRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> DiscussionTopic:
    require_operator(context)
    return management_repository.create_discussion_topic(
        db,
        state,
        request,
        context.market_id,
        context.user.name or context.user.email,
    )


@router.patch("/forums/topics/{topic_id}", response_model=DiscussionTopic)
def update_discussion_topic(
    topic_id: str,
    request: UpdateDiscussionTopicRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> DiscussionTopic:
    require_supervisor(context)
    return management_repository.update_discussion_topic(
        db,
        state,
        topic_id,
        request,
        context.market_id,
        context.user.name or context.user.email,
    )


@router.get("/forums/topics/{topic_id}/comments", response_model=list[DiscussionComment])
def list_discussion_comments(
    topic_id: str,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[DiscussionComment]:
    return management_repository.list_discussion_comments(db, state, topic_id, context.market_id)


@router.post(
    "/forums/topics/{topic_id}/comments",
    response_model=DiscussionComment,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_comment(
    topic_id: str,
    request: CreateDiscussionCommentRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> DiscussionComment:
    require_operator(context)
    return management_repository.create_discussion_comment(
        db,
        state,
        topic_id,
        request,
        context.market_id,
        context.user.name or context.user.email,
    )


@router.get("/customers", response_model=list[Customer])
def list_customers(
    response: Response,
    q: str | None = Query(None, min_length=1, max_length=160),
    sentiment: str | None = None,
    company_id: str | None = None,
    sort_by: str = Query("name", pattern="^(name|email|sentiment|created_at|updated_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[Customer]:
    query = select(CustomerRecord).where(CustomerRecord.market_id == context.market_id)
    if sentiment:
        query = query.where(CustomerRecord.sentiment == sentiment)
    if company_id:
        query = query.where(CustomerRecord.company_id == company_id)
    search = q.strip().lower() if q else ""
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                func.lower(CustomerRecord.name).like(term),
                func.lower(CustomerRecord.email).like(term),
                func.lower(CustomerRecord.location).like(term),
                func.lower(CustomerRecord.sentiment).like(term),
                func.lower(CustomerRecord.notes).like(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sort_column = _CUSTOMER_SORT_COLUMNS.get(sort_by, CustomerRecord.name)
    order_expr = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    query = query.order_by(order_expr, CustomerRecord.id.asc())
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    records = db.scalars(query).all()
    _set_list_headers(
        response,
        total=total,
        returned=len(records),
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [customer_from_record(record) for record in records]


@router.get("/companies", response_model=list[Company])
def list_companies(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[Company]:
    records = db.scalars(
        select(CompanyRecord).where(CompanyRecord.market_id == context.market_id)
    ).all()
    return [company_from_record(record) for record in records]


@router.post("/companies", response_model=Company, status_code=201)
def create_company(
    request: CreateCompanyRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Company:
    require_operator(context)
    payload = request.model_dump(mode="json")
    payload["market_id"] = context.market_id
    company_id = f"company_{uuid4().hex}"
    record = CompanyRecord(id=company_id, **payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    company = company_from_record(record)
    _set_resource_etag(response, record)
    _sync_company_to_store(state, company)
    state.audit_event(
        actor="api",
        action="company.create",
        entity_type="company",
        entity_id=company.id,
        market_id=context.market_id,
        details={"name": request.name},
    )
    persist_store_state(db, state)
    return company


@router.patch("/companies/{company_id}", response_model=Company)
def update_company(
    company_id: str,
    request: UpdateCompanyRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Company:
    require_operator(context)
    record = _company_record_or_404(db, company_id, context.market_id)
    _assert_fresh_record(record, if_match)
    patch = request.model_dump(exclude_unset=True, mode="json")
    for key, value in patch.items():
        if value is not None:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    company = company_from_record(record)
    _set_resource_etag(response, record)
    _sync_company_to_store(state, company)
    state.audit_event(
        actor="api",
        action="company.update",
        entity_type="company",
        entity_id=company_id,
        market_id=context.market_id,
        details=patch,
    )
    persist_store_state(db, state)
    return company


@router.post("/customers", response_model=Customer, status_code=201)
def create_customer(
    request: CreateCustomerRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Customer:
    require_operator(context)
    if request.company_id:
        company = _company_record_or_404(db, request.company_id, context.market_id)
        _sync_company_to_store(state, company_from_record(company))
    duplicate = db.scalar(
        select(CustomerRecord).where(
            CustomerRecord.market_id == context.market_id,
            CustomerRecord.email == str(request.email),
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Customer already exists")
    payload = request.model_dump(mode="json")
    payload["market_id"] = context.market_id
    customer_id = f"customer_{uuid4().hex}"
    record = CustomerRecord(id=customer_id, **payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    customer = customer_from_record(record)
    _set_resource_etag(response, record)
    _sync_customer_to_store(state, customer)
    state.audit_event(
        actor="api",
        action="customer.create",
        entity_type="customer",
        entity_id=customer.id,
        market_id=context.market_id,
        details={"email": str(customer.email)},
    )
    persist_store_state(db, state)
    return customer


@router.get("/customers/{customer_id}")
def read_customer(
    customer_id: str,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    customer_record = _customer_record_or_404(db, customer_id, context.market_id)
    customer = customer_from_record(customer_record)
    _set_resource_etag(response, customer_record)
    _sync_customer_to_store(state, customer)
    company = None
    if customer.company_id:
        company_record = _company_record_or_404(db, customer.company_id, context.market_id)
        company = company_from_record(company_record)
        _sync_company_to_store(state, company)
    tickets = ticket_repository.list_tickets(
        db,
        state,
        market_id=context.market_id,
        customer_id=customer_id,
    )
    return {"customer": customer, "company": company, "tickets": tickets}


@router.patch("/customers/{customer_id}", response_model=Customer)
def update_customer(
    customer_id: str,
    request: UpdateCustomerRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Customer:
    require_operator(context)
    record = _customer_record_or_404(db, customer_id, context.market_id)
    _assert_fresh_record(record, if_match)
    patch = request.model_dump(exclude_unset=True, mode="json")
    patch.pop("market_id", None)
    if patch.get("company_id"):
        company = _company_record_or_404(db, patch["company_id"], context.market_id)
        _sync_company_to_store(state, company_from_record(company))
    for key, value in patch.items():
        if value is not None:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    customer = customer_from_record(record)
    _set_resource_etag(response, record)
    _sync_customer_to_store(state, customer)
    state.audit_event(
        actor="api",
        action="customer.update",
        entity_type="customer",
        entity_id=customer_id,
        market_id=context.market_id,
        details=patch,
    )
    persist_store_state(db, state)
    return customer


@router.get("/tickets", response_model=list[Ticket])
def list_tickets(
    response: Response,
    q: str | None = Query(None, min_length=1, max_length=180),
    status_filter: str | None = Query(None, alias="status"),
    channel: ChannelType | None = None,
    priority: Priority | None = None,
    customer_id: str | None = None,
    assignee_id: str | None = None,
    team: str | None = None,
    sort_by: str = Query(
        "updated_at",
        pattern="^(updated_at|created_at|public_id|subject|status|priority|channel)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    total = ticket_repository.count_tickets(
        db,
        market_id=context.market_id,
        status_filter=status_filter,
        channel=channel,
        priority=priority,
        customer_id=customer_id,
        assignee_id=assignee_id,
        team=team,
        q=q,
    )
    tickets = ticket_repository.list_tickets(
        db,
        state,
        market_id=context.market_id,
        status_filter=status_filter,
        channel=channel,
        priority=priority,
        customer_id=customer_id,
        assignee_id=assignee_id,
        team=team,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    _set_list_headers(
        response,
        total=total,
        returned=len(tickets),
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return tickets


@router.get("/ticket-fields", response_model=list[TicketField])
def list_ticket_fields(
    active_only: bool = False,
    channel: ChannelType | None = None,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[TicketField]:
    return management_repository.list_ticket_fields(
        db,
        state,
        context.market_id,
        active_only=active_only,
        channel=channel.value if channel else None,
    )


@router.post("/ticket-fields", response_model=TicketField, status_code=status.HTTP_201_CREATED)
def create_ticket_field(
    request: CreateTicketFieldRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TicketField:
    require_admin(context)
    return management_repository.create_ticket_field(
        db,
        state,
        request,
        context.market_id,
        actor=context.user.id,
    )


@router.patch("/ticket-fields/{field_id}", response_model=TicketField)
def update_ticket_field(
    field_id: str,
    request: UpdateTicketFieldRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TicketField:
    require_admin(context)
    return management_repository.update_ticket_field(
        db,
        state,
        field_id,
        request,
        context.market_id,
        actor=context.user.id,
    )


@router.post("/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(
    request: CreateTicketRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    require_operator(context)
    customer_record = _customer_record_or_404(db, request.customer_id, context.market_id)
    customer = customer_from_record(customer_record)
    _sync_customer_to_store(state, customer)
    if customer.company_id:
        company_record = _company_record_or_404(db, customer.company_id, context.market_id)
        _sync_company_to_store(state, company_from_record(company_record))
    settings = workspace_settings_from_record(get_or_create_workspace_settings(db, context.market))
    ticket = ticket_repository.create_ticket(
        db,
        state,
        request,
        context.market_id,
        ai_enabled=settings.ai_work_queue_automation_enabled,
    )
    _set_resource_etag(response, ticket)
    return ticket


@router.get("/tickets/{ticket_id}")
def read_ticket(
    ticket_id: str,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    ticket_context = _ticket_context_with_suggestions(
        db,
        state,
        ticket_id=ticket_id,
        market_id=context.market_id,
    )
    _set_resource_etag(response, ticket_context["ticket"])
    return ticket_context


@router.get("/tickets/{ticket_id}/knowledge-suggestions", response_model=list[KnowledgeSuggestion])
def read_ticket_knowledge_suggestions(
    ticket_id: str,
    limit: int = Query(3, ge=1, le=10),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[KnowledgeSuggestion]:
    return management_repository.suggest_knowledge_for_ticket(
        db,
        state,
        ticket_id,
        context.market_id,
        limit=limit,
    )


@router.get("/tickets/{ticket_id}/macro-suggestions", response_model=list[ResponseMacroSuggestion])
def read_ticket_macro_suggestions(
    ticket_id: str,
    limit: int = Query(3, ge=1, le=10),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ResponseMacroSuggestion]:
    return management_repository.suggest_response_macros_for_ticket(
        db,
        state,
        ticket_id,
        context.market_id,
        limit=limit,
    )


@router.get("/tickets/{ticket_id}/duplicate-suggestions", response_model=list[DuplicateTicketSuggestion])
def read_ticket_duplicate_suggestions(
    ticket_id: str,
    limit: int = Query(5, ge=1, le=10),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[DuplicateTicketSuggestion]:
    return ticket_repository.suggest_duplicate_tickets(
        db,
        state,
        ticket_id,
        context.market_id,
        limit=limit,
    )


@router.post("/tickets/{ticket_id}/merge", response_model=MergeTicketsResponse)
def merge_ticket(
    ticket_id: str,
    request: MergeTicketsRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> MergeTicketsResponse:
    require_operator(context)
    result = ticket_repository.merge_tickets(
        db,
        state,
        ticket_id,
        request,
        context.market_id,
        actor=str(context.user.email),
    )
    _set_resource_etag(response, result.target_ticket)
    return result


@router.get("/cases", response_model=list[Case])
def list_cases(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[Case]:
    return case_repository.list_cases(db, context.market_id)


@router.post("/cases", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CreateCaseRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Case:
    require_operator(context)
    return case_repository.create_case(
        db,
        state,
        market_id=context.market_id,
        payload=request,
        actor=str(context.user.email),
    )


@router.get("/cases/{case_id}", response_model=Case)
def read_case(
    case_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Case:
    return case_repository.get_case(db, context.market_id, case_id)


@router.patch("/cases/{case_id}", response_model=Case)
def update_case(
    case_id: str,
    request: UpdateCaseRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Case:
    require_operator(context)
    return case_repository.update_case(
        db,
        state,
        market_id=context.market_id,
        case_id=case_id,
        payload=request,
        actor=str(context.user.email),
    )


@router.post("/cases/{case_id}/tickets", response_model=Case)
def attach_case_ticket(
    case_id: str,
    request: CaseTicketRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Case:
    require_operator(context)
    return case_repository.attach_ticket(
        db,
        state,
        market_id=context.market_id,
        case_id=case_id,
        ticket_id=request.ticket_id,
        actor=str(context.user.email),
    )


@router.delete("/cases/{case_id}/tickets/{ticket_id}", response_model=Case)
def detach_case_ticket(
    case_id: str,
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Case:
    require_operator(context)
    return case_repository.detach_ticket(
        db,
        state,
        market_id=context.market_id,
        case_id=case_id,
        ticket_id=ticket_id,
        actor=str(context.user.email),
    )


@router.patch("/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(
    ticket_id: str,
    request: UpdateTicketRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    require_operator(context)
    record = _ticket_record_or_404(db, ticket_id, context.market_id)
    _assert_fresh_record(record, if_match)
    ticket = ticket_repository.update_ticket(db, state, ticket_id, request, context.market_id)
    _set_resource_etag(response, ticket)
    return ticket


@router.get("/tickets/{ticket_id}/timeline", response_model=list[TimelineEvent])
def list_timeline(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[TimelineEvent]:
    return ticket_repository.list_timeline(db, state, ticket_id, context.market_id)


@router.post("/tickets/{ticket_id}/timeline", response_model=TimelineEvent)
def append_timeline(
    ticket_id: str,
    request: AppendEventRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TimelineEvent:
    require_operator(context)
    return ticket_repository.append_event(db, state, ticket_id, request, context.market_id)


@router.get("/tickets/{ticket_id}/attachments", response_model=list[Attachment])
def list_ticket_attachments(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Attachment]:
    return ticket_repository.list_attachments(db, state, ticket_id, context.market_id)


@router.post("/tickets/{ticket_id}/attachments", response_model=Attachment, status_code=201)
def create_ticket_attachment(
    ticket_id: str,
    request: CreateAttachmentRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Attachment:
    require_operator(context)
    return ticket_repository.create_attachment(
        db,
        state,
        ticket_id,
        request,
        context.market_id,
        actor=context.user.id,
    )


def _download_attachment_response(attachment: Attachment) -> Response:
    if attachment.lifecycle_status != AttachmentLifecycleStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Attachment is no longer active")
    if attachment.scan_status != "clean":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Attachment is not cleared for download")
    try:
        content = attachment_services.attachment_storage.read(attachment.storage_key)
    except (OSError, ValueError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment content not found") from exc
    safe_name = attachment_services.attachment_storage.safe_filename(attachment.filename)
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/tickets/{ticket_id}/attachments/binary", response_model=Attachment, status_code=201)
async def upload_ticket_attachment(
    ticket_id: str,
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Attachment:
    require_operator(context)
    content = await request.body()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Attachment content is required")
    if len(content) > app_settings.attachment_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Attachment is too large")
    attachment_id = f"attachment_{uuid4().hex}"
    content_type = request.headers.get("content-type") or "application/octet-stream"
    scan_status, scan_result = attachment_services.scan_attachment_binary(
        filename=filename,
        content_type=content_type,
        data=content,
    )
    if scan_status == "clean":
        storage_key = attachment_services.attachment_storage.write(
            market_id=context.market_id,
            ticket_id=ticket_id,
            attachment_id=attachment_id,
            filename=filename,
            data=content,
            content_type=content_type,
        )
    else:
        storage_key = attachment_services.blocked_storage_key(
            market_id=context.market_id,
            ticket_id=ticket_id,
            attachment_id=attachment_id,
            filename=filename,
        )
    return ticket_repository.create_attachment(
        db,
        state,
        ticket_id,
        CreateAttachmentRequest(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_key=storage_key,
        ),
        context.market_id,
        actor=context.user.id,
        attachment_id=attachment_id,
        scan_status_override=scan_status,
        scan_result_override=scan_result,
    )


@router.post(
    "/tickets/{ticket_id}/attachments/{attachment_id}/download-link",
    response_model=AttachmentDownloadLink,
)
def create_ticket_attachment_download_link(
    ticket_id: str,
    attachment_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AttachmentDownloadLink:
    attachment = ticket_repository.get_attachment(db, ticket_id, attachment_id, context.market_id)
    if attachment.lifecycle_status != AttachmentLifecycleStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Attachment is no longer active")
    if attachment.scan_status != "clean":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Attachment is not cleared for download")
    token, expires_at = create_attachment_download_token(
        market_id=context.market_id,
        ticket_id=ticket_id,
        attachment_id=attachment_id,
        created_by=context.user.id,
    )
    parsed_token = parse_attachment_download_token(token)
    write_audit_event(
        db,
        actor=context.user.id,
        action="attachment.download_link.create",
        entity_type="attachment",
        entity_id=attachment_id,
        market_id=context.market_id,
        details={
            "ticket_id": ticket_id,
            "expires_at": expires_at.isoformat(),
            "token_id": parsed_token.token_id if parsed_token else "unknown",
        },
        commit=True,
    )
    return AttachmentDownloadLink(
        url=f"/api/v1/tickets/{ticket_id}/attachments/{attachment_id}/download/signed?token={token}",
        expires_at=expires_at,
    )


@router.delete("/tickets/{ticket_id}/attachments/{attachment_id}", response_model=Attachment)
def delete_ticket_attachment(
    ticket_id: str,
    attachment_id: str,
    request: DeleteAttachmentRequest = Body(default_factory=DeleteAttachmentRequest),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Attachment:
    require_supervisor(context)
    return ticket_repository.delete_attachment(
        db,
        state,
        ticket_id=ticket_id,
        attachment_id=attachment_id,
        market_id=context.market_id,
        actor=context.user.id,
        reason=request.reason,
        purge_storage=request.purge_storage,
        storage_delete=attachment_services.attachment_storage.delete,
    )


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}/download")
def download_ticket_attachment(
    ticket_id: str,
    attachment_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    attachment = ticket_repository.get_attachment(db, ticket_id, attachment_id, context.market_id)
    return _download_attachment_response(attachment)


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}/download/signed")
def download_ticket_attachment_with_signed_link(
    ticket_id: str,
    attachment_id: str,
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    payload = parse_attachment_download_token(token)
    if (
        payload is None
        or payload.ticket_id != ticket_id
        or payload.attachment_id != attachment_id
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid attachment download link")
    attachment = ticket_repository.get_attachment(db, ticket_id, attachment_id, payload.market_id)
    write_audit_event(
        db,
        actor="signed-download",
        action="attachment.download",
        entity_type="attachment",
        entity_id=attachment_id,
        market_id=payload.market_id,
        details={
            "ticket_id": ticket_id,
            "mode": "signed_link",
            "token_id": payload.token_id,
            "created_by": payload.created_by,
        },
        commit=True,
    )
    return _download_attachment_response(attachment)


@router.post("/tickets/{ticket_id}/reply", response_model=TimelineEvent)
def reply_to_ticket(
    ticket_id: str,
    request: ReplyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TimelineEvent:
    require_operator(context)
    return ticket_repository.reply(db, state, ticket_id, request, context.market_id)


@router.post("/tickets/{ticket_id}/csat", response_model=CsatFeedback)
def submit_ticket_csat_feedback(
    ticket_id: str,
    request: CreateCsatFeedbackRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CsatFeedback:
    require_operator(context)
    return ticket_repository.submit_csat_feedback(
        db,
        state,
        ticket_id,
        request,
        context.market_id,
        actor=context.user.id,
    )


@router.get("/outbound/messages", response_model=list[OutboundMessage])
def list_outbound_messages(
    ticket_id: str | None = None,
    status_filter: OutboundMessageStatus | None = Query(None, alias="status"),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[OutboundMessage]:
    return outbound_repository.list_messages(
        db,
        state,
        context.market_id,
        ticket_id=ticket_id,
        status_filter=status_filter,
    )


@router.post("/outbound/messages/{message_id}/retry", response_model=OutboundMessage)
def retry_outbound_message(
    message_id: str,
    request: RetryOutboundMessageRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> OutboundMessage:
    require_supervisor(context)
    message = outbound_repository.retry_message(
        db,
        state,
        message_id,
        context.market_id,
        actor=context.user.id,
        reason=request.reason,
    )
    db.commit()
    return message


@router.get("/outbound/provider-config", response_model=list[OutboundProviderConfig])
def read_outbound_provider_config(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[OutboundProviderConfig]:
    require_supervisor(context)
    return outbound_adapter_router.config_summary(db, context.market_id)


@router.get("/inbound/provider-config", response_model=list[InboundProviderConfig])
def read_inbound_provider_config(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[InboundProviderConfig]:
    require_supervisor(context)
    return inbound_adapter_router.config_summary(db, context.market_id)


@router.get("/email/settings", response_model=EmailProviderSettings)
def read_email_provider_settings(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> EmailProviderSettings:
    require_supervisor(context)
    result = email_provider_settings_repository.read(db, market_id=context.market_id)
    db.commit()
    return result


@router.patch("/email/settings", response_model=EmailProviderSettings)
def update_email_provider_settings(
    request: UpdateEmailProviderSettingsRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> EmailProviderSettings:
    require_admin(context)
    return email_provider_settings_repository.update(
        db,
        state,
        request,
        market_id=context.market_id,
        actor=context.user.email,
    )


@router.get("/integration-credentials/settings", response_model=IntegrationCredentialSettings)
def read_integration_credential_settings(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> IntegrationCredentialSettings:
    require_supervisor(context)
    result = integration_credential_settings_repository.read(db, market_id=context.market_id)
    db.commit()
    return result


@router.patch("/integration-credentials/settings", response_model=IntegrationCredentialSettings)
def update_integration_credential_settings(
    request: UpdateIntegrationCredentialSettingsRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> IntegrationCredentialSettings:
    require_admin(context)
    return integration_credential_settings_repository.update(
        db,
        state,
        request,
        market_id=context.market_id,
        actor=context.user.email,
    )


@router.get("/sso/settings", response_model=SsoProviderSettings)
def read_sso_provider_settings(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> SsoProviderSettings:
    require_admin(context)
    result = sso_provider_settings_repository.read(db)
    db.commit()
    return result


@router.patch("/sso/settings", response_model=SsoProviderSettings)
def update_sso_provider_settings(
    request: UpdateSsoProviderSettingsRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> SsoProviderSettings:
    require_admin(context)
    return sso_provider_settings_repository.update(
        db,
        state,
        request,
        actor=context.user.email,
        market_id=context.market_id,
    )


@router.get("/widget-settings", response_model=WidgetSettings)
def read_widget_settings(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> WidgetSettings:
    require_supervisor(context)
    result = widget_settings_repository.read(db, market_id=context.market_id)
    db.commit()
    return result


@router.patch("/widget-settings", response_model=WidgetSettings)
def update_widget_settings(
    request: UpdateWidgetSettingsRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WidgetSettings:
    require_admin(context)
    return widget_settings_repository.update(
        db,
        state,
        request,
        market_id=context.market_id,
        actor=context.user.email,
    )


@router.get("/attachments/provider-config", response_model=AttachmentProviderConfig)
def read_attachment_provider_config(
    context: RequestContext = Depends(require_context),
) -> AttachmentProviderConfig:
    require_supervisor(context)
    return attachment_services.attachment_provider_config()


@router.get("/production/account-requests", response_model=ProductionAccountRequestPack)
def read_production_account_requests(
    request: Request,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ProductionAccountRequestPack:
    require_supervisor(context)
    return production_account_request_pack(
        db,
        market_id=context.market_id,
        base_url=_request_origin(request),
    )


@router.get("/production/readiness-checklist", response_model=ProductionReadinessChecklist)
def read_production_readiness_checklist(
    request: Request,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ProductionReadinessChecklist:
    require_supervisor(context)
    return production_readiness_checklist(
        db,
        market_id=context.market_id,
        base_url=_request_origin(request),
    )


@router.post("/production/account-requests/email", response_model=ProductionAccountRequestDelivery)
def send_production_account_request_email(
    request: Request,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ProductionAccountRequestDelivery:
    require_admin(context)
    return queue_production_account_request_email(
        db,
        state,
        market_id=context.market_id,
        base_url=_request_origin(request),
        actor=context.user.email,
    )


@router.get("/production/account-references", response_model=list[ProductionAccountReference])
def list_production_account_references(
    status_filter: str | None = Query(None, alias="status"),
    provider: str | None = None,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ProductionAccountReference]:
    require_supervisor(context)
    return production_account_reference_repository.list_references(
        db,
        market_id=context.market_id,
        status_filter=status_filter,
        provider=provider,
    )


@router.post(
    "/production/account-references",
    response_model=ProductionAccountReference,
    status_code=status.HTTP_201_CREATED,
)
def create_production_account_reference(
    request: CreateProductionAccountReferenceRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ProductionAccountReference:
    require_admin(context)
    return production_account_reference_repository.create_reference(
        db,
        state,
        market_id=context.market_id,
        request=request,
        actor=context.user.email,
    )


@router.patch(
    "/production/account-references/{reference_id}",
    response_model=ProductionAccountReference,
)
def update_production_account_reference(
    reference_id: str,
    request: UpdateProductionAccountReferenceRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ProductionAccountReference:
    require_admin(context)
    return production_account_reference_repository.update_reference(
        db,
        state,
        reference_id=reference_id,
        market_id=context.market_id,
        request=request,
        actor=context.user.email,
    )


@router.get("/production/account-references/docs", response_model=ProductionAccountReferenceDocs)
def read_production_account_reference_docs(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ProductionAccountReferenceDocs:
    require_supervisor(context)
    return ProductionAccountReferenceDocs(
        market_id=context.market_id,
        markdown=production_account_reference_repository.docs_snippet(db, market_id=context.market_id),
    )


@router.get("/alerts", response_model=list[OperationalAlert])
def list_operational_alerts(
    status_filter: OperationalAlertStatus | None = Query(None, alias="status"),
    include_resolved: bool = False,
    limit: int = Query(200, ge=1, le=500),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[OperationalAlert]:
    require_supervisor(context)
    return operational_alert_repository.list_alerts(
        db,
        context.market_id,
        status_filter=status_filter,
        include_resolved=include_resolved,
        limit=limit,
    )


@router.patch("/alerts/{alert_id}", response_model=OperationalAlert)
def update_operational_alert(
    alert_id: str,
    request: UpdateOperationalAlertRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> OperationalAlert:
    require_supervisor(context)
    alert = operational_alert_repository.update_alert_status(
        db,
        alert_id=alert_id,
        market_id=context.market_id,
        status_value=request.status,
        actor=context.user.email,
        note=request.note,
    )
    db.commit()
    return alert


@router.get("/alerts/deliveries", response_model=list[OperationalAlertDelivery])
def list_operational_alert_deliveries(
    include_sent: bool = False,
    limit: int = Query(200, ge=1, le=500),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[OperationalAlertDelivery]:
    require_supervisor(context)
    return operational_alert_delivery_repository.list_deliveries(
        db,
        context.market_id,
        include_sent=include_sent,
        limit=limit,
    )


@router.get("/alerts/delivery-config", response_model=OperationalAlertDeliveryConfig)
def read_operational_alert_delivery_config(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> OperationalAlertDeliveryConfig:
    require_supervisor(context)
    return alert_delivery_service.config_summary(db, context.market_id)


@router.get("/work-queue", response_model=list[WorkQueueItem])
def read_work_queue(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[WorkQueueItem]:
    return operations_repository.read_work_queue(db, state, context.market_id)


@router.get("/operations/recommendations", response_model=list[SupervisorRecommendation])
def read_supervisor_recommendations(
    limit: int = Query(8, ge=1, le=20),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[SupervisorRecommendation]:
    require_supervisor(context)
    return supervisor_recommendation_service.list_recommendations(
        db,
        state,
        context.market_id,
        limit=limit,
    )


@router.post("/work-queue/{ticket_id}/override", response_model=Ticket)
def override_work_queue(
    ticket_id: str,
    request: WorkQueueOverrideRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    require_supervisor(context)
    return ticket_repository.override_work_queue(
        db,
        state,
        ticket_id,
        request,
        context.market_id,
        actor=context.user.id,
    )


@router.post("/tickets/{ticket_id}/handoffs", response_model=Handoff, status_code=201)
def create_handoff(
    ticket_id: str,
    request: CreateHandoffRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Handoff:
    require_operator(context)
    return ticket_repository.create_handoff(db, state, ticket_id, request, context.market_id)


@router.get("/handoffs", response_model=list[Handoff])
def list_handoffs(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Handoff]:
    return ticket_repository.list_handoffs(db, state, context.market_id)


@router.patch("/handoffs/{handoff_id}", response_model=Handoff)
def update_handoff(
    handoff_id: str,
    request: UpdateHandoffRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Handoff:
    require_operator(context)
    return ticket_repository.update_handoff(db, state, handoff_id, request, context.market_id)


@router.get("/knowledge", response_model=list[KnowledgeArticle])
def list_knowledge(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[KnowledgeArticle]:
    return management_repository.list_knowledge(db, state, context.market_id)


@router.post("/knowledge", response_model=KnowledgeArticle, status_code=201)
def create_knowledge_article(
    request: CreateKnowledgeArticleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> KnowledgeArticle:
    require_supervisor(context)
    return management_repository.create_knowledge_article(
        db, state, request, context.market_id, context.user.id
    )


@router.patch("/knowledge/{article_id}", response_model=KnowledgeArticle)
def update_knowledge_article(
    article_id: str,
    request: UpdateKnowledgeArticleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> KnowledgeArticle:
    require_supervisor(context)
    return management_repository.update_knowledge_article(
        db,
        state,
        article_id,
        request,
        context.market_id,
        context.user.id,
    )


@router.get("/macros", response_model=list[ResponseMacro])
def list_response_macros(
    active_only: bool = Query(False),
    channel: ChannelType | None = Query(None),
    query: str | None = Query(None),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ResponseMacro]:
    return management_repository.list_response_macros(
        db,
        state,
        context.market_id,
        active_only=active_only,
        channel=channel.value if channel else None,
        query=query,
    )


@router.post("/macros", response_model=ResponseMacro, status_code=201)
def create_response_macro(
    request: CreateResponseMacroRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ResponseMacro:
    require_supervisor(context)
    return management_repository.create_response_macro(
        db,
        state,
        request,
        context.market_id,
        context.user.id,
    )


@router.patch("/macros/{macro_id}", response_model=ResponseMacro)
def update_response_macro(
    macro_id: str,
    request: UpdateResponseMacroRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ResponseMacro:
    require_supervisor(context)
    return management_repository.update_response_macro(
        db,
        state,
        macro_id,
        request,
        context.market_id,
        context.user.id,
    )


@router.post("/macros/{macro_id}/use", response_model=ResponseMacro)
def record_response_macro_use(
    macro_id: str,
    ticket_id: str | None = Query(None),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ResponseMacro:
    require_operator(context)
    return management_repository.record_response_macro_use(
        db,
        state,
        macro_id,
        context.market_id,
        actor=context.user.id,
        ticket_id=ticket_id,
    )


@router.get("/automation-rules", response_model=list[AutomationRule])
def list_automation_rules(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[AutomationRule]:
    return management_repository.list_automation_rules(db, state, context.market_id)


@router.post("/automation-rules", response_model=AutomationRule, status_code=201)
def create_automation_rule(
    request: CreateAutomationRuleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AutomationRule:
    require_admin(context)
    return management_repository.create_automation_rule(db, state, request, context.market_id)


@router.patch("/automation-rules/{rule_id}", response_model=AutomationRule)
def update_automation_rule(
    rule_id: str,
    request: UpdateAutomationRuleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AutomationRule:
    require_admin(context)
    return management_repository.update_automation_rule(
        db,
        state,
        rule_id,
        request,
        context.market_id,
    )


@router.get("/analytics/summary", response_model=AnalyticsSnapshot)
def read_analytics_summary(
    range: str = Query("all", pattern="^(today|7d|30d|all)$"),
    ticket_group: str | None = Query(None),
    chat_group: str | None = Query(None),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AnalyticsSnapshot:
    return operations_repository.analytics_summary(
        db,
        state,
        context.market_id,
        period=range,
        ticket_group=ticket_group,
        chat_group=chat_group,
    )


@router.get("/analytics/overview", response_model=AnalyticsSnapshot)
def read_analytics_overview(
    range: str = Query("all", pattern="^(today|7d|30d|all)$"),
    ticket_group: str | None = Query(None),
    chat_group: str | None = Query(None),
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AnalyticsSnapshot:
    return operations_repository.analytics_summary(
        db,
        state,
        context.market_id,
        period=range,
        ticket_group=ticket_group,
        chat_group=chat_group,
    )


@router.get("/analytics/rollups", response_model=list[AnalyticsRollup])
def read_analytics_rollups(
    limit: int = Query(24, ge=1, le=168),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[AnalyticsRollup]:
    return operations_repository.recent_analytics_rollups(
        db,
        market_id=context.market_id,
        limit=limit,
    )


@router.get("/csat/feedback", response_model=list[CsatFeedback])
def list_csat_feedback(
    ticket_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[CsatFeedback]:
    require_supervisor(context)
    return ticket_repository.list_csat_feedback(
        db,
        market_id=context.market_id,
        ticket_id=ticket_id,
        limit=limit,
    )


@router.post("/connectors/inbound", status_code=201)
def ingest_connector(
    request: ConnectorInboundRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    require_operator(context)
    market_id = request.market_id or context.market_id
    try:
        database_rate_limiter.check(
            db,
            (
                "connector-inbound:"
                f"{context.user.id}:{market_id}:{request.provider.value}"
            ),
            limit=app_settings.connector_inbound_rate_limit_attempts,
            window_seconds=app_settings.connector_inbound_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)

    if market_id not in context.user.market_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not assigned to this market")
    target_market = context.market
    if market_id != context.market_id:
        market_record = db.get(MarketRecord, market_id)
        if market_record is None or not market_record.active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
        target_market = market_from_record(market_record)
    settings = workspace_settings_from_record(get_or_create_workspace_settings(db, target_market))
    result = ticket_repository.ingest_connector(
        db,
        state,
        request,
        market_id,
        ai_enabled=settings.ai_work_queue_automation_enabled,
    )
    return result


@router.post("/webhooks/{provider}/{market_code}", status_code=201)
async def ingest_signed_webhook(
    provider: str,
    market_code: str,
    http_request: Request,
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    try:
        provider_type = ChannelType(provider)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Connector account not found") from exc

    market_record = db.scalar(select(MarketRecord).where(MarketRecord.code == market_code.upper()))
    if market_record is None or not market_record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
    try:
        database_rate_limiter.check(
            db,
            f"signed-webhook:{provider_type.value}:{market_record.id}",
            limit=app_settings.webhook_rate_limit_attempts,
            window_seconds=app_settings.webhook_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)

    account = connector_account_repository.get_account_for_provider(
        db,
        market_id=market_record.id,
        provider=provider_type,
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Connector account not found")
    if not account.intake_enabled:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Connector intake is disabled",
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Connector intake is disabled")
    if not account.secret_configured or not account.webhook_verified:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Connector webhook is not ready for signed intake",
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Connector webhook is not ready for signed intake",
        )

    raw_body = await http_request.body()
    try:
        verification = verify_webhook_signature(
            account_id=account.id,
            credential_ref=account.credential_ref,
            body=raw_body,
            headers=dict(http_request.headers),
        )
    except ValueError as exc:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error=str(exc),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        loaded_payload = json.loads(raw_body.decode() or "{}")
    except json.JSONDecodeError as exc:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Invalid webhook JSON body",
            delivery_id=verification.delivery_id,
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON body") from exc
    if not isinstance(loaded_payload, dict):
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Invalid webhook JSON body",
            delivery_id=verification.delivery_id,
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid JSON body")
    payload: dict[str, Any] = loaded_payload

    adapter = _signed_webhook_adapter(provider_type)
    external_id = (
        str(adapter.webhook_external_id(payload, verification.delivery_id)).strip()
        if adapter is not None
        else str(payload.get("external_id") or "").strip()
    )

    delivery_seen = bool(
        verification.delivery_id
        and connector_account_repository.delivery_id_seen(
            db,
            market_id=market_record.id,
            provider=provider_type,
            delivery_id=verification.delivery_id,
        )
    )
    external_seen = connector_account_repository.external_event_seen(
        db,
        market_id=market_record.id,
        provider=provider_type,
        external_id=external_id,
    )
    if delivery_seen and not external_seen:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Webhook delivery id was already processed",
            delivery_id=verification.delivery_id,
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Webhook delivery id was already processed",
        )

    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "webhook_delivery_id": verification.delivery_id,
            "webhook_signature_verified": True,
            "webhook_timestamp": verification.timestamp,
            "connector_account_id": account.id,
        }
    )

    webhook_event = None
    if adapter is not None:
        try:
            webhook_event = adapter.parse(
                payload,
                metadata=metadata,
                delivery_id=verification.delivery_id,
            )
        except ValueError as exc:
            connector_account_repository.record_webhook_failure(
                db,
                state,
                account=account,
                error=str(exc),
                delivery_id=verification.delivery_id,
            )
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    if webhook_event is not None and webhook_event.kind == "delivery_receipt":
        receipt = webhook_event.receipt
        if receipt is None:
            connector_account_repository.record_webhook_failure(
                db,
                state,
                account=account,
                error="Webhook delivery receipt failed validation",
                delivery_id=verification.delivery_id,
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Webhook delivery receipt failed validation",
            )
        receipt_payload = asdict(receipt)
        if external_seen:
            connector_account_repository.record_webhook_success(db, account=account)
            db.commit()
            return {"deduplicated": True, "receipt": receipt_payload}
        outbound_message = outbound_repository.record_delivery_receipt(
            db,
            state,
            market_id=market_record.id,
            provider=provider_type,
            status_label=receipt.status,
            provider_message_id=receipt.provider_message_id,
            outbound_message_id=receipt.outbound_message_id,
            idempotency_key=receipt.idempotency_key,
            delivery_id=verification.delivery_id,
            raw_payload=receipt.raw_payload or payload,
        )
        connector_account_repository.record_webhook_success(db, account=account)
        db.commit()
        return {
            "deduplicated": False,
            "receipt": receipt_payload,
            "outbound_message": outbound_message,
        }

    try:
        inbound = (
            webhook_event.inbound
            if webhook_event is not None and webhook_event.inbound is not None
            else ConnectorInboundRequest(
                provider=provider_type,
                external_id=external_id,
                customer_name=payload.get("customer_name", ""),
                customer_email=payload.get("customer_email", ""),
                subject=payload.get("subject", ""),
                body=payload.get("body", ""),
                handle=payload.get("handle"),
                metadata=metadata,
            )
        )
    except ValidationError as exc:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Webhook payload failed validation",
            delivery_id=verification.delivery_id,
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

    settings = workspace_settings_from_record(
        get_or_create_workspace_settings(db, market_from_record(market_record))
    )
    result = ticket_repository.ingest_connector(
        db,
        state,
        inbound,
        market_record.id,
        ai_enabled=settings.ai_work_queue_automation_enabled,
    )
    connector_account_repository.record_webhook_success(db, account=account)
    db.commit()
    return result


@router.get("/connectors/providers")
def list_connector_providers(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[dict]:
    accounts = connector_account_repository.list_accounts(db, context.market_id)
    return [
        {
            "provider": account.provider.value,
            "status": account.status.value,
            "market": context.market.code,
            "account": account.account_identifier,
            "production_dependencies": account.required_credentials,
            "supports": account.capabilities,
            "intake_enabled": account.intake_enabled,
            "outbound_enabled": account.outbound_enabled,
            "webhook_verified": account.webhook_verified,
            "secret_configured": account.secret_configured,
            "failure_count": account.failure_count,
        }
        for account in accounts
    ]


@router.get("/connectors/accounts", response_model=list[ConnectorAccount])
@router.get("/connector-accounts", response_model=list[ConnectorAccount])
def list_connector_accounts(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ConnectorAccount]:
    return connector_account_repository.list_accounts(db, context.market_id)


@router.post("/connectors/accounts", response_model=ConnectorAccount, status_code=201)
@router.post("/connector-accounts", response_model=ConnectorAccount, status_code=201)
def create_connector_account(
    request: CreateConnectorAccountRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ConnectorAccount:
    require_admin(context)
    return connector_account_repository.create_account(db, state, request, context.market_id)


@router.patch("/connectors/accounts/{account_id}", response_model=ConnectorAccount)
@router.patch("/connector-accounts/{account_id}", response_model=ConnectorAccount)
def update_connector_account(
    account_id: str,
    request: UpdateConnectorAccountRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ConnectorAccount:
    require_admin(context)
    return connector_account_repository.update_account(
        db,
        state,
        account_id,
        request,
        context.market_id,
    )


@router.get("/connectors/events", response_model=list[ConnectorEvent])
def list_connector_events(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ConnectorEvent]:
    return ticket_repository.list_connector_events(db, state, context.market_id)


@router.get("/audit", response_model=list[AuditEvent])
def list_audit_events(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    require_audit_reader(context)
    records = db.scalars(
        select(AuditEventRecord)
        .where(or_(AuditEventRecord.market_id.is_(None), AuditEventRecord.market_id == context.market_id))
        .order_by(AuditEventRecord.created_at.desc())
        .limit(500)
    ).all()
    return [audit_event_from_record(record) for record in records]


@router.get("/tracker")
def read_tracker(context: RequestContext = Depends(require_context)) -> dict:
    return {
        "market_id": context.market_id,
        "market": context.market.name,
        "epics": [
            "Repository foundation",
            "Data platform",
            "Auth, tenancy, and security",
            "Ticket and conversation APIs",
            "AI Work Queue automation",
            "SLA and escalation engine",
            "Omnichannel connectors",
            "Handoffs and internal operations",
            "Knowledge and automation rules",
            "Analytics and workforce",
            "Production hardening",
        ],
        "current_status": "Backend vertical slice is running with durable operational state, Anthropic-ready AI guidance, and passing smoke tests",
        "known_dependencies": [
            "Production PostgreSQL provider",
            "Anthropic API key in AI_Key or OMNI_ANTHROPIC_API_KEY",
            "Identity provider",
            "WhatsApp Business API credentials",
            "Meta app credentials for Facebook Messenger and Instagram DM",
            "Mailbox provider credentials",
            "SMS and voice provider credentials",
            "Portal SSO/customer-auth provider",
            "Partner webhook secrets and schema contracts",
        ],
    }


@router.get("/frontend/snapshot")
def read_frontend_snapshot(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    tickets = ticket_repository.list_tickets(db, state, market_id=context.market_id)
    settings = workspace_settings_from_record(get_or_create_workspace_settings(db, context.market))
    companies = [
        company_from_record(record)
        for record in db.scalars(
            select(CompanyRecord).where(CompanyRecord.market_id == context.market_id)
        ).all()
    ]
    customers = [
        customer_from_record(record)
        for record in db.scalars(
            select(CustomerRecord).where(CustomerRecord.market_id == context.market_id)
        ).all()
    ]
    users = []
    if context.user.role in {"admin", "supervisor"}:
        user_records = db.scalars(select(UserRecord)).all()
        users = [
            user_from_record(record)
            for record in user_records
            if context.user.role == "admin" or context.market_id in record.market_ids
        ]
    can_view_supervisor_controls = Permission.supervisor_control in set(
        context.user.effective_permissions
    )
    operational_alerts = []
    alert_deliveries = []
    inbound_provider_config = []
    outbound_provider_config = []
    supervisor_recommendations = []
    attachment_provider_config = None
    email_provider_settings = None
    integration_credential_settings = None
    sso_provider_settings = None
    widget_settings = None
    if can_view_supervisor_controls:
        operational_alerts = operational_alert_repository.list_alerts(db, context.market_id)
        alert_deliveries = operational_alert_delivery_repository.list_deliveries(
            db,
            context.market_id,
        )
        inbound_provider_config = inbound_adapter_router.config_summary(db, context.market_id)
        outbound_provider_config = outbound_adapter_router.config_summary(db, context.market_id)
        supervisor_recommendations = supervisor_recommendation_service.list_recommendations(
            db,
            state,
            context.market_id,
        )
        attachment_provider_config = attachment_services.attachment_provider_config()
        email_provider_settings = email_provider_settings_repository.read(
            db,
            market_id=context.market_id,
        )
        integration_credential_settings = integration_credential_settings_repository.read(
            db,
            market_id=context.market_id,
        )
        widget_settings = widget_settings_repository.read(db, market_id=context.market_id)
        if context.user.role == "admin":
            sso_provider_settings = sso_provider_settings_repository.read(db)
    return {
        "session": {"user": context.user, "market": context.market},
        "users": users,
        "settings": settings,
        "channels": management_repository.list_channels(db, state, context.market_id),
        "ticket_fields": management_repository.list_ticket_fields(db, state, context.market_id),
        "agents": management_repository.list_agents(db, state, context.market_id),
        "support_groups": management_repository.list_support_groups(db, state, context.market_id),
        "sla_policies": management_repository.list_sla_policies(db, state, context.market_id),
        "business_hours": management_repository.list_business_hours(db, state, context.market_id),
        "ticket_templates": management_repository.list_ticket_templates(db, state, context.market_id),
        "tags": management_repository.list_tags(db, state, context.market_id),
        "csat_surveys": management_repository.list_csat_surveys(db, state, context.market_id),
        "email_notifications": management_repository.list_email_notifications(
            db, state, context.market_id
        ),
        "scenario_automations": management_repository.list_scenario_automations(
            db, state, context.market_id
        ),
        "custom_field_definitions": management_repository.list_custom_field_definitions(
            db, state, context.market_id
        ),
        "custom_objects": management_repository.list_custom_objects(db, state, context.market_id),
        "products": management_repository.list_products(db, state, context.market_id),
        "saved_reports": management_repository.list_saved_reports(db, state, context.market_id),
        "service_appointments": management_repository.list_service_appointments(
            db, state, context.market_id
        ),
        "discussion_topics": management_repository.list_discussion_topics(
            db, state, context.market_id
        ),
        "companies": companies,
        "customers": customers,
        "tickets": [
            _ticket_context_with_suggestions(
                db,
                state,
                ticket_id=ticket.id,
                market_id=context.market_id,
            )
            for ticket in tickets
        ],
        "handoffs": ticket_repository.list_handoffs(db, state, context.market_id),
        "cases": case_repository.list_cases(db, context.market_id),
        "outbound_messages": outbound_repository.list_messages(db, state, context.market_id),
        "outbound_provider_config": outbound_provider_config,
        "inbound_provider_config": inbound_provider_config,
        "supervisor_recommendations": supervisor_recommendations,
        "email_provider_settings": email_provider_settings,
        "integration_credential_settings": integration_credential_settings,
        "sso_provider_settings": sso_provider_settings,
        "widget_settings": widget_settings,
        "connector_accounts": connector_account_repository.list_accounts(db, context.market_id),
        "knowledge": management_repository.list_knowledge(db, state, context.market_id),
        "macros": management_repository.list_response_macros(db, state, context.market_id),
        "rules": management_repository.list_automation_rules(db, state, context.market_id),
        "operational_alerts": operational_alerts,
        "alert_deliveries": alert_deliveries,
        "alert_delivery_config": alert_delivery_service.config_summary(db, context.market_id),
        "attachment_provider_config": attachment_provider_config,
        "analytics": operations_repository.analytics_summary(db, state, context.market_id),
        "analytics_rollups": operations_repository.recent_analytics_rollups(
            db,
            market_id=context.market_id,
        ),
        "csat_feedback": ticket_repository.list_csat_feedback(db, market_id=context.market_id),
        "tracker": read_tracker(context),
    }
