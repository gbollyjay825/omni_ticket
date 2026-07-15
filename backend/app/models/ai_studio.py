from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.domain import ChannelType

AiAgentStatus = Literal["draft", "active", "paused"]


class CreateAiAgentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=500)
    instructions: str = Field(min_length=20, max_length=12000)
    channels: list[ChannelType] = Field(min_length=1, max_length=12)
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=20)
    handoff_team: str = Field(default="", max_length=160)
    confidence_threshold: int = Field(default=75, ge=0, le=100)
    auto_send: bool = False

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, values: list[str]) -> list[str]:
        normalized = sorted({value.strip().lower() for value in values if value.strip()})
        if not normalized:
            raise ValueError("Add at least one language")
        return normalized


class UpdateAiAgentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, min_length=20, max_length=12000)
    status: AiAgentStatus | None = None
    channels: list[ChannelType] | None = Field(default=None, min_length=1, max_length=12)
    languages: list[str] | None = Field(default=None, min_length=1, max_length=20)
    handoff_team: str | None = Field(default=None, max_length=160)
    confidence_threshold: int | None = Field(default=None, ge=0, le=100)
    auto_send: bool | None = None

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = sorted({value.strip().lower() for value in values if value.strip()})
        if not normalized:
            raise ValueError("Add at least one language")
        return normalized


class AiAgentResponse(BaseModel):
    id: str
    market_id: str
    name: str
    description: str
    instructions: str
    status: AiAgentStatus
    channels: list[ChannelType]
    languages: list[str]
    handoff_team: str
    confidence_threshold: int
    auto_send: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class AiReadinessResponse(BaseModel):
    provider: str
    configured: bool
    model: str
    automation_enabled: bool
    can_send_customer_messages: bool
    active_agents: int
    detail: str


class UpdateAiPolicyRequest(BaseModel):
    automation_enabled: bool | None = None
    can_send_customer_messages: bool | None = None


class AiDecisionResponse(BaseModel):
    id: str
    ticket_id: str
    ticket_number: str
    decision_type: str
    confidence: int
    summary: str
    model_version: str
    input_reference: str
    override_allowed: bool
    created_at: datetime
