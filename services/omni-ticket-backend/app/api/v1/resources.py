import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_store
from app.api.v1.security import RequestContext, require_context
from app.core.store import InMemoryStore
from app.core.webhooks import verify_webhook_signature
from app.db.connectors import connector_account_repository
from app.db.management import management_repository
from app.db.mappers import company_from_record, customer_from_record, market_from_record, user_from_record
from app.db.models import CompanyRecord, CustomerRecord, MarketRecord, UserRecord
from app.db.operations import operations_repository
from app.db.outbound import outbound_repository
from app.db.session import get_db
from app.db.settings import get_or_create_workspace_settings, workspace_settings_from_record
from app.db.store_sync import persist_store_state
from app.db.ticketing import ticket_repository
from app.models.domain import (
    Agent,
    AnalyticsSnapshot,
    AppendEventRequest,
    AutomationRule,
    AuditEvent,
    Channel,
    ChannelType,
    Company,
    ConnectorAccount,
    ConnectorEvent,
    ConnectorInboundRequest,
    CreateAutomationRuleRequest,
    CreateCompanyRequest,
    CreateConnectorAccountRequest,
    CreateHandoffRequest,
    CreateCustomerRequest,
    CreateKnowledgeArticleRequest,
    CreateTicketRequest,
    Customer,
    Handoff,
    KnowledgeArticle,
    OutboundMessage,
    OutboundMessageStatus,
    Priority,
    ReplyRequest,
    RetryOutboundMessageRequest,
    Ticket,
    TimelineEvent,
    UpdateAutomationRuleRequest,
    UpdateAgentStatusRequest,
    UpdateChannelRequest,
    UpdateCompanyRequest,
    UpdateConnectorAccountRequest,
    UpdateCustomerRequest,
    UpdateHandoffRequest,
    UpdateKnowledgeArticleRequest,
    UpdateTicketRequest,
    UserRole,
    WorkQueueItem,
    WorkQueueOverrideRequest,
)

router = APIRouter(tags=["operations"])


def _require_operator(context: RequestContext) -> None:
    if context.user.role == UserRole.auditor:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Operator access required")


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


def _sync_company_to_store(state: InMemoryStore, company: Company) -> None:
    state.companies[company.id] = company


def _sync_customer_to_store(state: InMemoryStore, customer: Customer) -> None:
    state.customers[customer.id] = customer


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
    return management_repository.update_agent_status(db, state, agent_id, request, context.market_id)


@router.get("/customers", response_model=list[Customer])
def list_customers(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[Customer]:
    records = db.scalars(
        select(CustomerRecord).where(CustomerRecord.market_id == context.market_id)
    ).all()
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
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Company:
    payload = request.model_dump(mode="json")
    payload["market_id"] = context.market_id
    company_id = f"company_{uuid4().hex}"
    record = CompanyRecord(id=company_id, **payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    company = company_from_record(record)
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
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Company:
    record = _company_record_or_404(db, company_id, context.market_id)
    patch = request.model_dump(exclude_unset=True, mode="json")
    for key, value in patch.items():
        if value is not None:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    company = company_from_record(record)
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
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Customer:
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
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    customer_record = _customer_record_or_404(db, customer_id, context.market_id)
    customer = customer_from_record(customer_record)
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
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Customer:
    record = _customer_record_or_404(db, customer_id, context.market_id)
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
    status_filter: str | None = Query(None, alias="status"),
    channel: ChannelType | None = None,
    priority: Priority | None = None,
    customer_id: str | None = None,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    return ticket_repository.list_tickets(
        db,
        state,
        market_id=context.market_id,
        status_filter=status_filter,
        channel=channel,
        priority=priority,
        customer_id=customer_id,
    )


@router.post("/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(
    request: CreateTicketRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    customer_record = _customer_record_or_404(db, request.customer_id, context.market_id)
    customer = customer_from_record(customer_record)
    _sync_customer_to_store(state, customer)
    if customer.company_id:
        company_record = _company_record_or_404(db, customer.company_id, context.market_id)
        _sync_company_to_store(state, company_from_record(company_record))
    settings = workspace_settings_from_record(get_or_create_workspace_settings(db, context.market))
    return ticket_repository.create_ticket(
        db,
        state,
        request,
        context.market_id,
        ai_enabled=settings.ai_work_queue_automation_enabled,
    )


@router.get("/tickets/{ticket_id}")
def read_ticket(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_repository.get_ticket_context(db, state, ticket_id, context.market_id)


@router.patch("/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(
    ticket_id: str,
    request: UpdateTicketRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    return ticket_repository.update_ticket(db, state, ticket_id, request, context.market_id)


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
    return ticket_repository.append_event(db, state, ticket_id, request, context.market_id)


@router.post("/tickets/{ticket_id}/reply", response_model=TimelineEvent)
def reply_to_ticket(
    ticket_id: str,
    request: ReplyRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> TimelineEvent:
    return ticket_repository.reply(db, state, ticket_id, request, context.market_id)


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
    _require_operator(context)
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


@router.get("/work-queue", response_model=list[WorkQueueItem])
def read_work_queue(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[WorkQueueItem]:
    return operations_repository.read_work_queue(db, state, context.market_id)


@router.post("/work-queue/{ticket_id}/override", response_model=Ticket)
def override_work_queue(
    ticket_id: str,
    request: WorkQueueOverrideRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> Ticket:
    _require_operator(context)
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
    return management_repository.create_knowledge_article(db, state, request, context.market_id)


@router.patch("/knowledge/{article_id}", response_model=KnowledgeArticle)
def update_knowledge_article(
    article_id: str,
    request: UpdateKnowledgeArticleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> KnowledgeArticle:
    return management_repository.update_knowledge_article(
        db,
        state,
        article_id,
        request,
        context.market_id,
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
    return management_repository.create_automation_rule(db, state, request, context.market_id)


@router.patch("/automation-rules/{rule_id}", response_model=AutomationRule)
def update_automation_rule(
    rule_id: str,
    request: UpdateAutomationRuleRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AutomationRule:
    return management_repository.update_automation_rule(
        db,
        state,
        rule_id,
        request,
        context.market_id,
    )


@router.get("/analytics/summary", response_model=AnalyticsSnapshot)
def read_analytics_summary(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AnalyticsSnapshot:
    return operations_repository.analytics_summary(db, state, context.market_id)


@router.get("/analytics/overview", response_model=AnalyticsSnapshot)
def read_analytics_overview(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> AnalyticsSnapshot:
    return operations_repository.analytics_summary(db, state, context.market_id)


@router.post("/connectors/inbound", status_code=201)
def ingest_connector(
    request: ConnectorInboundRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    market_id = request.market_id or context.market_id
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
    provider: ChannelType,
    market_code: str,
    http_request: Request,
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> dict:
    market_record = db.scalar(select(MarketRecord).where(MarketRecord.code == market_code.upper()))
    if market_record is None or not market_record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")

    account = connector_account_repository.get_account_for_provider(
        db,
        market_id=market_record.id,
        provider=provider,
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
        payload = json.loads(raw_body.decode() or "{}")
    except json.JSONDecodeError as exc:
        connector_account_repository.record_webhook_failure(
            db,
            state,
            account=account,
            error="Invalid webhook JSON body",
            delivery_id=verification.delivery_id,
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON body") from exc

    external_id = str(payload.get("external_id") or "").strip()
    delivery_seen = verification.delivery_id and connector_account_repository.delivery_id_seen(
        db,
        market_id=market_record.id,
        provider=provider,
        delivery_id=verification.delivery_id,
    )
    external_seen = connector_account_repository.external_event_seen(
        db,
        market_id=market_record.id,
        provider=provider,
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

    try:
        inbound = ConnectorInboundRequest(
            provider=provider,
            external_id=external_id,
            customer_name=payload.get("customer_name", ""),
            customer_email=payload.get("customer_email", ""),
            subject=payload.get("subject", ""),
            body=payload.get("body", ""),
            handle=payload.get("handle"),
            metadata=metadata,
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
    state: InMemoryStore = Depends(get_store),
) -> list[AuditEvent]:
    return [event for event in state.audit if event.market_id in {None, context.market_id}]


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
        "current_status": "Local backend vertical slice is running with durable operational state mirroring and passing smoke tests",
        "known_dependencies": [
            "Production PostgreSQL provider",
            "Identity provider",
            "WhatsApp Business API credentials",
            "Meta app credentials for Facebook Messenger and Instagram DM",
            "Mailbox provider credentials",
            "SMS and voice provider credentials",
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
    user_records = db.scalars(select(UserRecord)).all()
    users = [
        user_from_record(record)
        for record in user_records
        if context.user.role == "admin" or context.market_id in record.market_ids
    ]
    return {
        "session": {"user": context.user, "market": context.market},
        "users": users,
        "settings": settings,
        "channels": management_repository.list_channels(db, state, context.market_id),
        "agents": management_repository.list_agents(db, state, context.market_id),
        "companies": companies,
        "customers": customers,
        "tickets": [
            ticket_repository.get_ticket_context(db, state, ticket.id, context.market_id)
            for ticket in tickets
        ],
        "handoffs": ticket_repository.list_handoffs(db, state, context.market_id),
        "outbound_messages": outbound_repository.list_messages(db, state, context.market_id),
        "connector_accounts": connector_account_repository.list_accounts(db, context.market_id),
        "knowledge": management_repository.list_knowledge(db, state, context.market_id),
        "rules": management_repository.list_automation_rules(db, state, context.market_id),
        "analytics": operations_repository.analytics_summary(db, state, context.market_id),
        "tracker": read_tracker(context),
    }
