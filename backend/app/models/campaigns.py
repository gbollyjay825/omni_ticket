from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CampaignChannel = Literal["whatsapp", "sms", "facebook", "instagram"]
CampaignStatus = Literal["draft", "scheduled", "running", "paused", "completed", "cancelled"]
CampaignConsentStatus = Literal["opted_in", "opted_out"]
CampaignDeliveryStatus = Literal[
    "queued",
    "sending",
    "sent",
    "delivered",
    "read",
    "failed",
    "dead_lettered",
    "suppressed",
]


class CampaignAudience(BaseModel):
    include_all: bool = False
    tags_any: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_explicit_audience(self) -> "CampaignAudience":
        self.tags_any = sorted({tag.strip().lower() for tag in self.tags_any if tag.strip()})
        if not self.include_all and not self.tags_any:
            raise ValueError("Select at least one audience tag or explicitly include all contacts")
        return self


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    channel: CampaignChannel
    message_body: str = Field(min_length=2, max_length=4000)
    audience: CampaignAudience
    scheduled_at: datetime | None = None
    template_name: str = Field(default="", max_length=180)
    template_language: str = Field(default="en_US", min_length=2, max_length=20)
    template_variables: list[str] = Field(default_factory=list, max_length=20)


class UpdateCampaignRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    message_body: str | None = Field(default=None, min_length=2, max_length=4000)
    audience: CampaignAudience | None = None
    scheduled_at: datetime | None = None
    status: CampaignStatus | None = None
    template_name: str | None = Field(default=None, max_length=180)
    template_language: str | None = Field(default=None, min_length=2, max_length=20)
    template_variables: list[str] | None = Field(default=None, max_length=20)


class CampaignProviderReadiness(BaseModel):
    channel: CampaignChannel
    configured: bool
    detail: str


class CampaignDeliverySummary(BaseModel):
    total: int = 0
    queued: int = 0
    sending: int = 0
    sent: int = 0
    delivered: int = 0
    read: int = 0
    failed: int = 0
    dead_lettered: int = 0
    suppressed: int = 0


class CampaignResponse(BaseModel):
    id: str
    market_id: str
    name: str
    channel: CampaignChannel
    status: CampaignStatus
    message_body: str
    audience: CampaignAudience
    scheduled_at: datetime | None
    template_name: str
    template_language: str
    template_variables: list[str]
    created_by: str
    estimated_recipients: int
    consented_recipients: int
    provider: CampaignProviderReadiness
    delivery_summary: CampaignDeliverySummary
    launched_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CampaignLaunchResponse(BaseModel):
    campaign: CampaignResponse
    created_deliveries: int
    existing_deliveries: int


class SetCampaignConsentRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    channel: CampaignChannel
    status: CampaignConsentStatus
    source: str = Field(min_length=2, max_length=120)
    evidence: str = Field(default="", max_length=1000)


class CampaignConsentResponse(BaseModel):
    id: str
    market_id: str
    customer_id: str
    customer_name: str
    customer_email: str
    channel: CampaignChannel
    status: CampaignConsentStatus
    source: str
    evidence: str
    captured_by: str
    captured_at: datetime
    created_at: datetime
    updated_at: datetime


class CampaignDeliveryResponse(BaseModel):
    id: str
    campaign_id: str
    market_id: str
    customer_id: str
    channel: CampaignChannel
    recipient: str
    status: CampaignDeliveryStatus
    idempotency_key: str
    consent_id: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    external_id: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
