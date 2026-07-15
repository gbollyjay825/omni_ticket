from datetime import datetime, time
from hashlib import sha256
from secrets import token_urlsafe
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_store
from app.core.config import settings as app_settings
from app.core.rate_limit import RateLimitExceeded, raise_rate_limit_exceeded
from app.core.store import InMemoryStore
from app.core.widget_tokens import create_widget_token, parse_widget_token
from app.db.mappers import market_from_record
from app.db.mappers import customer_from_record
from app.db.models import (
    BusinessHoursRecord,
    ChannelRecord,
    CustomerRecord,
    MarketRecord,
    TicketRecord,
)
from app.db.rate_limit import database_rate_limiter
from app.db.session import get_db
from app.db.settings import get_or_create_workspace_settings
from app.db.ticketing import ticket_repository
from app.db.widget_settings import widget_settings_repository
from app.models.domain import ChannelType, CreateTicketRequest, utc_now
from app.models.portal import (
    PortalConfiguration,
    PortalMarketSummary,
    WidgetConversationMessage,
    WidgetConversationMessageRequest,
    WidgetConversationResponse,
    WidgetConversationStartRequest,
    WidgetPublicConfiguration,
)

router = APIRouter(tags=["portal"])


def _active_market(db: Session, market_code: str) -> MarketRecord:
    market = db.scalar(
        select(MarketRecord).where(
            func.lower(MarketRecord.code) == market_code.strip().lower(),
            MarketRecord.active.is_(True),
        )
    )
    if market is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
    return market


def _client_identity(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _check_rate_limit(db: Session, key: str) -> None:
    try:
        database_rate_limiter.check(
            db,
            key,
            limit=app_settings.portal_rate_limit_attempts,
            window_seconds=app_settings.portal_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)


def _time_value(value: str) -> time | None:
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _inside_business_hours(db: Session, market: MarketRecord) -> bool:
    calendar = db.scalar(
        select(BusinessHoursRecord)
        .where(
            BusinessHoursRecord.market_id == market.id,
            BusinessHoursRecord.active.is_(True),
        )
        .order_by(BusinessHoursRecord.created_at.asc())
    )
    if calendar is None or not calendar.days:
        return True
    try:
        now = utc_now().astimezone(ZoneInfo(calendar.timezone or market.timezone))
    except ZoneInfoNotFoundError:
        now = utc_now().astimezone(ZoneInfo("UTC"))
    day_name = now.strftime("%A").lower()
    day = next(
        (
            item
            for item in calendar.days
            if str(item.get("day", "")).strip().lower() == day_name
        ),
        None,
    )
    if not day or day.get("enabled") is not True:
        return False
    opens_at = _time_value(str(day.get("open", "")))
    closes_at = _time_value(str(day.get("close", "")))
    if opens_at is None or closes_at is None:
        return False
    current = now.timetz().replace(tzinfo=None)
    if opens_at <= closes_at:
        return opens_at <= current <= closes_at
    return current >= opens_at or current <= closes_at


def _widget_configuration(
    db: Session,
    market: MarketRecord,
) -> WidgetPublicConfiguration:
    widget = widget_settings_repository.read(db, market_id=market.id)
    channel = db.scalar(
        select(ChannelRecord).where(
            ChannelRecord.market_id == market.id,
            ChannelRecord.type == ChannelType.chat.value,
        )
    )
    channel_available = channel is None or channel.health != "paused"
    business_available = _inside_business_hours(db, market)
    available = widget.enabled and channel_available and business_available
    if not widget.enabled:
        availability = "disabled"
    elif not channel_available:
        availability = "paused"
    elif not business_available:
        availability = "outside_business_hours"
    else:
        availability = "online"
    return WidgetPublicConfiguration(
        market_code=market.code.lower(),
        enabled=widget.enabled,
        available=available,
        availability=availability,
        display_name=widget.display_name,
        welcome_message=widget.welcome_message,
        primary_color=widget.primary_color,
        launcher_label=widget.launcher_label,
        position=widget.position,
        auto_open_seconds=widget.auto_open_seconds,
        collect_email=widget.collect_email,
        offline_message=widget.offline_message,
    )


def _widget_customer(
    db: Session,
    state: InMemoryStore,
    *,
    market: MarketRecord,
    request: WidgetConversationStartRequest,
) -> CustomerRecord:
    if request.email:
        email = str(request.email).strip().lower()
    else:
        visitor_id = request.visitor_id or token_urlsafe(24)
        digest = sha256(visitor_id.encode("utf-8")).hexdigest()[:24]
        email = f"widget-{digest}@example.com"
    customer = db.scalar(
        select(CustomerRecord).where(
            CustomerRecord.market_id == market.id,
            CustomerRecord.email == email,
        )
    )
    name = " ".join((request.name or "Website visitor").strip().split()) or "Website visitor"
    contact_points = [
        {"channel": ChannelType.chat.value, "value": email, "verified": False},
    ]
    if request.email:
        contact_points.append(
            {"channel": ChannelType.email.value, "value": email, "verified": False}
        )
    if customer is None:
        customer = CustomerRecord(
            id=f"customer_{token_urlsafe(24)}",
            market_id=market.id,
            name=name,
            email=email,
            preferred_channels=[ChannelType.chat.value],
            contact_points=contact_points,
            tags=["web-widget"],
            notes="Created from the embedded Omni messenger.",
        )
        db.add(customer)
        db.flush()
    else:
        customer.name = name if request.name else customer.name
        customer.preferred_channels = sorted(
            set(customer.preferred_channels or []) | {ChannelType.chat.value}
        )
        existing_points = list(customer.contact_points or [])
        for point in contact_points:
            if point not in existing_points:
                existing_points.append(point)
        customer.contact_points = existing_points
        customer.tags = sorted(set(customer.tags or []) | {"web-widget"})
        customer.updated_at = utc_now()
        db.flush()
    state.customers[customer.id] = customer_from_record(customer)
    return customer


def _customer_status(status_value: str) -> str:
    return {
        "open": "Support is reviewing your message",
        "pending": "Waiting for your reply",
        "waiting": "Waiting for a partner update",
        "solved": "Resolved",
        "closed": "Closed",
    }.get(status_value, "In progress")


def _widget_response(
    db: Session,
    state: InMemoryStore,
    *,
    ticket: TicketRecord,
    access_token: str | None = None,
    token_expires_at: datetime | None = None,
) -> WidgetConversationResponse:
    context = ticket_repository.get_ticket_context(db, state, ticket.id, ticket.market_id)
    return WidgetConversationResponse(
        ticket_id=ticket.id,
        public_id=ticket.public_id,
        status=ticket.status,
        subject=ticket.subject,
        customer_status=_customer_status(ticket.status),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[
            WidgetConversationMessage(
                id=event.id,
                actor=event.actor,
                body=event.body,
                channel=event.channel.value,
                direction="customer" if event.type.value == "inbound" else "support",
                created_at=event.created_at,
            )
            for event in context["timeline"]
            if event.public
        ],
        access_token=access_token,
        token_expires_at=token_expires_at,
    )


def _widget_ticket_from_token(
    db: Session,
    *,
    market: MarketRecord,
    public_id: str,
    authorization: str | None,
) -> tuple[TicketRecord, CustomerRecord]:
    scheme, _, token = (authorization or "").partition(" ")
    payload = parse_widget_token(token) if scheme.lower() == "widget" else None
    if payload is None or payload.market_id != market.id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Widget session is invalid or expired")
    ticket = db.get(TicketRecord, payload.ticket_id)
    customer = db.get(CustomerRecord, payload.customer_id)
    if (
        ticket is None
        or customer is None
        or ticket.market_id != market.id
        or customer.market_id != market.id
        or ticket.customer_id != customer.id
        or ticket.public_id.lower() != public_id.strip().lower()
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ticket, customer


@router.get("/portal/markets", response_model=list[PortalMarketSummary])
def list_portal_markets(db: Session = Depends(get_db)) -> list[PortalMarketSummary]:
    markets = db.scalars(
        select(MarketRecord)
        .where(MarketRecord.active.is_(True))
        .order_by(MarketRecord.name.asc())
    ).all()
    return [
        PortalMarketSummary(
            code=market.code.lower(),
            name=market.name,
            default_locale=market.default_locale,
        )
        for market in markets
    ]


@router.get("/portal/{market_code}/config", response_model=PortalConfiguration)
def read_portal_configuration(
    market_code: str,
    db: Session = Depends(get_db),
) -> PortalConfiguration:
    market = _active_market(db, market_code)
    workspace = get_or_create_workspace_settings(db, market_from_record(market))
    db.commit()
    return PortalConfiguration(
        market_id=market.id,
        market_code=market.code.lower(),
        market_name=market.name,
        default_locale=market.default_locale,
        support_email=market.support_email,
        public_brand_name=workspace.public_brand_name,
        portal_support_name=workspace.portal_support_name,
        portal_primary_color=workspace.portal_primary_color,
        portal_logo_url=workspace.portal_logo_url,
        portal_welcome_message=workspace.portal_welcome_message,
    )


@router.get("/widget/{market_code}/config", response_model=WidgetPublicConfiguration)
def read_widget_configuration(
    market_code: str,
    db: Session = Depends(get_db),
) -> WidgetPublicConfiguration:
    market = _active_market(db, market_code)
    configuration = _widget_configuration(db, market)
    db.commit()
    return configuration


@router.post(
    "/widget/{market_code}/conversations",
    response_model=WidgetConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_widget_conversation(
    market_code: str,
    request_body: WidgetConversationStartRequest,
    request: Request,
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WidgetConversationResponse:
    market = _active_market(db, market_code)
    widget = _widget_configuration(db, market)
    if not widget.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Messenger is not enabled for this market")
    if widget.collect_email and request_body.email is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Email is required")
    _check_rate_limit(
        db,
        f"widget-start:{market.id}:{_client_identity(request)}",
    )
    customer = _widget_customer(db, state, market=market, request=request_body)
    workspace = get_or_create_workspace_settings(db, market_from_record(market))
    subject = (request_body.subject or "").strip() or f"Web chat with {customer.name}"
    ticket = ticket_repository.create_ticket(
        db,
        state,
        CreateTicketRequest(
            customer_id=customer.id,
            subject=subject,
            description=request_body.message.strip(),
            channel=ChannelType.chat,
            tags=["web-widget", "customer-submitted"],
        ),
        market.id,
        ai_enabled=workspace.ai_work_queue_automation_enabled,
        actor="customer-widget",
        source="web_widget",
        notify_customer=request_body.email is not None,
    )
    ticket_record = db.get(TicketRecord, ticket.id)
    if ticket_record is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversation was not created")
    token, expires_at = create_widget_token(
        market_id=market.id,
        ticket_id=ticket.id,
        customer_id=customer.id,
    )
    return _widget_response(
        db,
        state,
        ticket=ticket_record,
        access_token=token,
        token_expires_at=expires_at,
    )


@router.get(
    "/widget/{market_code}/conversations/{public_id}",
    response_model=WidgetConversationResponse,
)
def read_widget_conversation(
    market_code: str,
    public_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WidgetConversationResponse:
    market = _active_market(db, market_code)
    ticket, _customer = _widget_ticket_from_token(
        db,
        market=market,
        public_id=public_id,
        authorization=authorization,
    )
    _check_rate_limit(
        db,
        f"widget-read:{market.id}:{ticket.id}:{_client_identity(request)}",
    )
    return _widget_response(db, state, ticket=ticket)


@router.post(
    "/widget/{market_code}/conversations/{public_id}/messages",
    response_model=WidgetConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_widget_message(
    market_code: str,
    public_id: str,
    request_body: WidgetConversationMessageRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WidgetConversationResponse:
    market = _active_market(db, market_code)
    ticket, customer = _widget_ticket_from_token(
        db,
        market=market,
        public_id=public_id,
        authorization=authorization,
    )
    _check_rate_limit(
        db,
        f"widget-message:{market.id}:{ticket.id}:{_client_identity(request)}",
    )
    ticket_repository.customer_channel_reply(
        db,
        state,
        ticket.id,
        market.id,
        actor=customer.name,
        body=request_body.body.strip(),
        submitted_by="widget-session",
        channel=ChannelType.chat,
        source="web_widget",
        system_actor="customer-widget",
    )
    db.refresh(ticket)
    return _widget_response(db, state, ticket=ticket)
