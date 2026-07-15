from typing import Any

from pydantic import BaseModel, Field

from app.models.domain import (
    Agent,
    Attachment,
    Case,
    Company,
    Customer,
    DuplicateTicketSuggestion,
    Handoff,
    KnowledgeSuggestion,
    ResponseMacroSuggestion,
    ServiceAppointment,
    Ticket,
    TicketTask,
    TicketTimeEntry,
    TimelineEvent,
    User,
)


class TicketWorkspaceSuggestions(BaseModel):
    knowledge: list[KnowledgeSuggestion] = Field(default_factory=list)
    macros: list[ResponseMacroSuggestion] = Field(default_factory=list)
    duplicates: list[DuplicateTicketSuggestion] = Field(default_factory=list)


class TicketWorkspace(BaseModel):
    ticket: Ticket
    case: Case | None = None
    customer: Customer
    company: Company | None = None
    assignee: Agent | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    watchers: list[User] = Field(default_factory=list)
    watching: bool = False
    tasks: list[TicketTask] = Field(default_factory=list)
    time_entries: list[TicketTimeEntry] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    linked_tickets: list[Ticket] = Field(default_factory=list)
    service_tasks: list[ServiceAppointment] = Field(default_factory=list)
    handoffs: list[Handoff] = Field(default_factory=list)
    suggestions: TicketWorkspaceSuggestions
    previous_ticket_id: str | None = None
    next_ticket_id: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
