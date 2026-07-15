from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.domain import Case, ChannelType, Customer, Priority, Ticket

ConversationStatus = Literal["open", "pending", "resolved", "closed"]
MessageVisibility = Literal["public", "private"]
MessageSenderType = Literal["customer", "agent", "system", "bot"]
ReceiptType = Literal["delivered", "read"]


class ConversationTopic(BaseModel):
    id: str
    market_id: str
    name: str
    description: str = ""
    active: bool = True
    position: int = 100
    created_at: datetime
    updated_at: datetime


class CreateConversationTopicRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=500)
    active: bool = True
    position: int = Field(default=100, ge=0, le=10000)


class UpdateConversationTopicRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    position: int | None = Field(default=None, ge=0, le=10000)


class ConversationParticipant(BaseModel):
    id: str
    market_id: str
    conversation_id: str
    participant_type: Literal["customer", "agent", "bot", "system"]
    user_id: str | None = None
    customer_id: str | None = None
    display_name: str
    role: str
    joined_at: datetime
    left_at: datetime | None = None


class ConversationAssignment(BaseModel):
    id: str
    market_id: str
    conversation_id: str
    from_user_id: str | None = None
    to_user_id: str | None = None
    from_group_id: str | None = None
    to_group_id: str | None = None
    reason: str = ""
    routed_by: str
    created_at: datetime


class Conversation(BaseModel):
    id: str
    market_id: str
    public_id: str
    case_id: str
    customer_id: str
    channel: ChannelType
    subject: str = ""
    status: ConversationStatus
    priority: Priority
    topic_id: str | None = None
    assignee_id: str | None = None
    assigned_group_id: str | None = None
    source_account_id: str | None = None
    external_id: str | None = None
    version: int
    last_message_at: datetime
    resolved_at: datetime | None = None
    reopened_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    customer_name: str = ""
    customer_email: str = ""
    assignee_name: str = ""
    group_name: str = ""
    topic_name: str = ""
    latest_message: str = ""
    unread_count: int = 0


class ConversationPage(BaseModel):
    items: list[Conversation]
    next_cursor: str | None = None
    has_more: bool = False


class CreateConversationRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    channel: ChannelType
    subject: str = Field(default="", max_length=255)
    priority: Priority = Priority.normal
    topic_id: str | None = Field(default=None, max_length=64)
    assigned_group_id: str | None = Field(default=None, max_length=64)
    assignee_id: str | None = Field(default=None, max_length=64)
    source_account_id: str | None = Field(default=None, max_length=160)
    external_id: str | None = Field(default=None, max_length=255)
    initial_message: str | None = Field(default=None, max_length=20000)
    initial_sender: Literal["customer", "agent"] = "customer"
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateConversationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    subject: str | None = Field(default=None, max_length=255)
    priority: Priority | None = None
    topic_id: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] | None = None


class AssignConversationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    assignee_id: str | None = Field(default=None, max_length=64)
    group_id: str | None = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=500)


class IntelliAssignConversationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(default="IntelliAssign from Omnichat workspace", max_length=500)


class ChangeConversationStatusRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


class ConversationMessage(BaseModel):
    id: str
    market_id: str
    conversation_id: str
    sender_type: MessageSenderType
    sender_id: str | None = None
    sender_name: str
    visibility: MessageVisibility
    body: str
    content: dict[str, Any] = Field(default_factory=dict)
    delivery_state: str
    provider_message_id: str | None = None
    reply_to_id: str | None = None
    version: int
    sent_at: datetime
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConversationMessagePage(BaseModel):
    items: list[ConversationMessage]
    next_cursor: str | None = None
    has_more: bool = False


class CreateConversationMessageRequest(BaseModel):
    expected_version: int = Field(ge=1)
    body: str = Field(default="", max_length=20000)
    visibility: MessageVisibility = "public"
    reply_to_id: str | None = Field(default=None, max_length=64)
    content: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def require_body_or_content(self) -> "CreateConversationMessageRequest":
        if not self.body.strip() and not self.content:
            raise ValueError("A message body or structured content is required")
        return self


class MessageReceipt(BaseModel):
    id: str
    market_id: str
    conversation_id: str
    message_id: str
    user_id: str
    receipt_type: ReceiptType
    recorded_at: datetime


class CreateMessageReceiptRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=64)
    receipt_type: ReceiptType


class ConversationView(BaseModel):
    id: str
    market_id: str
    owner_user_id: str | None = None
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: str
    sort_order: Literal["asc", "desc"]
    position: int
    active: bool
    created_at: datetime
    updated_at: datetime


class CreateConversationViewRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: Literal["last_message_at", "created_at", "priority"] = "last_message_at"
    sort_order: Literal["asc", "desc"] = "desc"
    position: int = Field(default=100, ge=0, le=10000)
    shared: bool = False


class UpdateConversationViewRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    filters: dict[str, Any] | None = None
    sort_by: Literal["last_message_at", "created_at", "priority"] | None = None
    sort_order: Literal["asc", "desc"] | None = None
    position: int | None = Field(default=None, ge=0, le=10000)
    active: bool | None = None


class ConversationAttachment(BaseModel):
    id: str
    market_id: str
    conversation_id: str
    message_id: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    storage_provider: str
    scan_status: str
    scan_result: str
    lifecycle_status: str
    uploaded_by: str
    retained_until: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    deletion_reason: str | None = None
    purged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ConversationContext(BaseModel):
    conversation: Conversation
    customer: Customer
    case: Case
    participants: list[ConversationParticipant]
    assignments: list[ConversationAssignment]
    linked_tickets: list[Ticket]
    attachments: list[ConversationAttachment]
    customer_history: list[Conversation]
    allowed_actions: list[str]


class LinkConversationTicketRequest(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=64)
    relationship: Literal["linked", "converted", "escalated"] = "linked"


class FeatureFlag(BaseModel):
    id: str
    market_id: str
    key: str
    enabled: bool
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    updated_by: str
    created_at: datetime
    updated_at: datetime


class FeatureCapability(BaseModel):
    key: str
    available: bool
    enabled: bool
    reason: str
    configuration: dict[str, Any] = Field(default_factory=dict)


class UpdateFeatureFlagRequest(BaseModel):
    enabled: bool
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
