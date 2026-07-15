from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PortalMarketSummary(BaseModel):
    code: str
    name: str
    default_locale: str


class PortalConfiguration(BaseModel):
    market_id: str
    market_code: str
    market_name: str
    default_locale: str
    support_email: str
    public_brand_name: str
    portal_support_name: str
    portal_primary_color: str
    portal_logo_url: str
    portal_welcome_message: str


class WidgetPublicConfiguration(BaseModel):
    market_code: str
    enabled: bool
    available: bool
    availability: str
    display_name: str
    welcome_message: str
    primary_color: str
    launcher_label: str
    position: str
    auto_open_seconds: int
    collect_email: bool
    offline_message: str


class WidgetConversationStartRequest(BaseModel):
    name: str | None = Field(default=None, max_length=180)
    email: EmailStr | None = None
    message: str = Field(min_length=2, max_length=8000)
    subject: str | None = Field(default=None, max_length=255)
    visitor_id: str | None = Field(default=None, max_length=160)


class WidgetConversationMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class WidgetConversationMessage(BaseModel):
    id: str
    actor: str
    body: str
    channel: str
    direction: str
    created_at: datetime


class WidgetConversationResponse(BaseModel):
    ticket_id: str
    public_id: str
    status: str
    subject: str
    customer_status: str
    created_at: datetime
    updated_at: datetime
    messages: list[WidgetConversationMessage] = Field(default_factory=list)
    access_token: str | None = None
    token_expires_at: datetime | None = None
