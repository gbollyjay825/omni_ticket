import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    audit_event_from_record,
    automation_rule_from_record,
    business_hours_from_record,
    channel_from_record,
    csat_survey_from_record,
    custom_field_definition_from_record,
    custom_object_from_record,
    discussion_comment_from_record,
    discussion_topic_from_record,
    email_notification_from_record,
    product_from_record,
    saved_report_from_record,
    service_appointment_from_record,
    scenario_automation_from_record,
    knowledge_article_from_record,
    response_macro_from_record,
    sla_policy_from_record,
    support_group_from_record,
    tag_from_record,
    ticket_field_from_record,
    ticket_template_from_record,
)
from app.db.models import (
    AgentRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    BusinessHoursRecord,
    ChannelRecord,
    CsatSurveyRecord,
    CustomFieldDefinitionRecord,
    CustomObjectRecord,
    DiscussionCommentRecord,
    DiscussionTopicRecord,
    EmailNotificationRecord,
    HandoffRecord,
    ProductRecord,
    SavedReportRecord,
    ServiceAppointmentRecord,
    KnowledgeArticleRecord,
    ResponseMacroRecord,
    ScenarioAutomationRecord,
    SlaPolicyRecord,
    SupportGroupRecord,
    TagRecord,
    TicketFieldRecord,
    TicketRecord,
    TicketTemplateRecord,
)
from app.models.domain import (
    Agent,
    AutomationRule,
    BusinessHours,
    Channel,
    ChannelHealth,
    CreateAutomationRuleRequest,
    CreateBusinessHoursRequest,
    CreateCsatSurveyRequest,
    CreateCustomFieldDefinitionRequest,
    CreateCustomObjectRequest,
    CreateEmailNotificationRequest,
    CreateProductRequest,
    CreateSavedReportRequest,
    CreateServiceAppointmentRequest,
    CreateDiscussionTopicRequest,
    CreateDiscussionCommentRequest,
    CreateKnowledgeArticleRequest,
    CreateResponseMacroRequest,
    CreateScenarioAutomationRequest,
    CreateSlaPolicyRequest,
    CreateSupportGroupRequest,
    CreateTagRequest,
    CreateTicketFieldRequest,
    CreateTicketTemplateRequest,
    CsatSurvey,
    CustomFieldDefinition,
    CustomObject,
    DiscussionComment,
    DiscussionTopic,
    EmailNotification,
    KnowledgeArticle,
    Product,
    KnowledgeSuggestion,
    KnowledgeArticleStatus,
    ResponseMacro,
    ResponseMacroSuggestion,
    SavedReport,
    ScenarioAutomation,
    ServiceAppointment,
    SlaPolicy,
    SupportGroup,
    Tag,
    TicketField,
    TicketFieldType,
    TicketTemplate,
    UpdateAgentStatusRequest,
    UpdateAutomationRuleRequest,
    UpdateBusinessHoursRequest,
    UpdateChannelRequest,
    UpdateCsatSurveyRequest,
    UpdateCustomFieldDefinitionRequest,
    UpdateCustomObjectRequest,
    UpdateEmailNotificationRequest,
    UpdateProductRequest,
    UpdateKnowledgeArticleRequest,
    UpdateResponseMacroRequest,
    UpdateSavedReportRequest,
    UpdateScenarioAutomationRequest,
    UpdateServiceAppointmentRequest,
    UpdateDiscussionTopicRequest,
    UpdateSlaPolicyRequest,
    UpdateSupportGroupRequest,
    UpdateTagRequest,
    UpdateTicketFieldRequest,
    UpdateTicketTemplateRequest,
    utc_now,
)


_SUGGESTABLE_ARTICLE_STATUSES = {
    KnowledgeArticleStatus.approved.value,
    KnowledgeArticleStatus.published.value,
}
_TOKEN_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "has",
    "have",
    "into",
    "the",
    "this",
    "that",
    "with",
    "your",
}
_OPTION_FIELD_TYPES = {TicketFieldType.select.value, TicketFieldType.multiselect.value}
_OPEN_TICKET_STATUSES = {"open", "pending", "waiting"}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _tokens(*parts: object) -> set[str]:
    text = " ".join(str(part).lower() for part in parts if part)
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text)
        if len(token) >= 3 and token not in _TOKEN_STOPWORDS
    }


def _normalized_options(options: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for option in options:
        value = option.strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _validate_ticket_field_payload(payload: dict) -> None:
    field_type = payload.get("field_type")
    options = _normalized_options(payload.get("options") or [])
    payload["options"] = options
    if field_type in _OPTION_FIELD_TYPES and not options:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select and multiselect ticket fields require at least one option",
        )
    if field_type not in _OPTION_FIELD_TYPES:
        payload["options"] = []


def _article_scope_matches(record: KnowledgeArticleRecord, market_id: str, channel: str) -> bool:
    return (
        market_id in record.market_ids
        and record.status in _SUGGESTABLE_ARTICLE_STATUSES
        and (not record.channels or channel in record.channels)
    )


def _macro_scope_matches(record: ResponseMacroRecord, market_id: str, channel: str) -> bool:
    return (
        record.market_id == market_id
        and record.active
        and (not record.channels or channel in record.channels)
    )


def _knowledge_suggestion_for_ticket(
    record: KnowledgeArticleRecord,
    ticket: TicketRecord,
) -> KnowledgeSuggestion | None:
    article_tokens = _tokens(record.title, record.body, " ".join(record.tags or []))
    title_tokens = _tokens(record.title)
    body_tokens = _tokens(record.body)
    ticket_tokens = _tokens(
        ticket.public_id,
        ticket.subject,
        ticket.description,
        ticket.channel,
        ticket.status,
        ticket.priority,
        ticket.sentiment,
        ticket.team,
        ticket.ai_summary,
        ticket.recommended_action,
        " ".join(ticket.tags or []),
    )
    tag_matches = sorted(set(record.tags or []) & set(ticket.tags or []))
    title_matches = sorted(title_tokens & ticket_tokens)
    body_matches = sorted((body_tokens & ticket_tokens) - set(title_matches))
    article_matches = sorted((article_tokens & ticket_tokens) - set(title_matches) - set(body_matches))
    reasons: list[str] = []
    score = 0

    if ticket.channel in record.channels:
        score += 25
        reasons.append(f"Matches {ticket.channel} channel")
    elif not record.channels:
        score += 8
        reasons.append("General article for any channel")
    if tag_matches:
        score += min(30, len(tag_matches) * 12)
        reasons.append("Tag match: " + ", ".join(tag_matches[:3]))
    if title_matches:
        score += min(30, len(title_matches) * 10)
        reasons.append("Title match: " + ", ".join(title_matches[:3]))
    if body_matches:
        score += min(20, len(body_matches) * 4)
        reasons.append("Body match: " + ", ".join(body_matches[:3]))
    if ticket.priority in {"high", "urgent"} and {"escalation", "sla", "priority"} & set(record.tags or []):
        score += 10
        reasons.append("Priority escalation fit")
    if ticket.sentiment in {"frustrated", "angry"} and {"complaint", "recovery", "escalation"} & set(record.tags or []):
        score += 10
        reasons.append("Customer recovery fit")
    if record.status == KnowledgeArticleStatus.published.value:
        score += 5
        reasons.append("Published answer")

    matched_terms = sorted(set(tag_matches + title_matches + body_matches + article_matches))[:10]
    if score <= 0:
        return None
    return KnowledgeSuggestion(
        article=knowledge_article_from_record(record),
        score=min(score, 100),
        reasons=reasons[:4],
        matched_terms=matched_terms,
    )


def _knowledge_suggestion_for_query(
    record: KnowledgeArticleRecord,
    query: str,
    *,
    channel: str,
) -> KnowledgeSuggestion | None:
    article_tokens = _tokens(record.title, record.body, " ".join(record.tags or []))
    title_tokens = _tokens(record.title)
    body_tokens = _tokens(record.body)
    query_tokens = _tokens(query)
    tag_matches = sorted(set(record.tags or []) & query_tokens)
    title_matches = sorted(title_tokens & query_tokens)
    body_matches = sorted((body_tokens & query_tokens) - set(title_matches))
    article_matches = sorted((article_tokens & query_tokens) - set(title_matches) - set(body_matches))
    reasons: list[str] = []
    score = 0

    if channel in record.channels:
        score += 25
        reasons.append(f"Matches {channel} channel")
    elif not record.channels:
        score += 8
        reasons.append("General answer")
    if tag_matches:
        score += min(30, len(tag_matches) * 12)
        reasons.append("Tag match: " + ", ".join(tag_matches[:3]))
    if title_matches:
        score += min(30, len(title_matches) * 10)
        reasons.append("Title match: " + ", ".join(title_matches[:3]))
    if body_matches:
        score += min(20, len(body_matches) * 4)
        reasons.append("Body match: " + ", ".join(body_matches[:3]))
    if record.status == KnowledgeArticleStatus.published.value:
        score += 5
        reasons.append("Published answer")
    if not query_tokens and record.status == KnowledgeArticleStatus.published.value:
        score += 5

    matched_terms = sorted(set(tag_matches + title_matches + body_matches + article_matches))[:10]
    if score <= 0:
        return None
    return KnowledgeSuggestion(
        article=knowledge_article_from_record(record),
        score=min(score, 100),
        reasons=reasons[:4],
        matched_terms=matched_terms,
    )


def _response_macro_suggestion_for_ticket(
    record: ResponseMacroRecord,
    ticket: TicketRecord,
) -> ResponseMacroSuggestion | None:
    macro_tokens = _tokens(record.name, record.body, record.shortcut, " ".join(record.tags or []))
    name_tokens = _tokens(record.name, record.shortcut)
    body_tokens = _tokens(record.body)
    ticket_tokens = _tokens(
        ticket.public_id,
        ticket.subject,
        ticket.description,
        ticket.channel,
        ticket.status,
        ticket.priority,
        ticket.sentiment,
        ticket.team,
        ticket.ai_summary,
        ticket.recommended_action,
        " ".join(ticket.tags or []),
    )
    tag_matches = sorted(set(record.tags or []) & set(ticket.tags or []))
    name_matches = sorted(name_tokens & ticket_tokens)
    body_matches = sorted((body_tokens & ticket_tokens) - set(name_matches))
    macro_matches = sorted((macro_tokens & ticket_tokens) - set(name_matches) - set(body_matches))
    reasons: list[str] = []
    score = 0

    if ticket.channel in record.channels:
        score += 25
        reasons.append(f"Matches {ticket.channel} channel")
    elif not record.channels:
        score += 8
        reasons.append("Available for any channel")
    if tag_matches:
        score += min(30, len(tag_matches) * 12)
        reasons.append("Tag match: " + ", ".join(tag_matches[:3]))
    if name_matches:
        score += min(24, len(name_matches) * 8)
        reasons.append("Name match: " + ", ".join(name_matches[:3]))
    if body_matches:
        score += min(18, len(body_matches) * 4)
        reasons.append("Reply text match: " + ", ".join(body_matches[:3]))
    if ticket.priority in {"high", "urgent"} and {"escalation", "sla", "priority"} & set(record.tags or []):
        score += 12
        reasons.append("Priority escalation fit")
    if ticket.sentiment in {"frustrated", "angry"} and {"complaint", "recovery", "escalation"} & set(record.tags or []):
        score += 12
        reasons.append("Customer recovery fit")
    if record.usage_count:
        score += min(10, record.usage_count)
        reasons.append("Previously used by agents")

    matched_terms = sorted(set(tag_matches + name_matches + body_matches + macro_matches))[:10]
    if score <= 0:
        return None
    return ResponseMacroSuggestion(
        macro=response_macro_from_record(record),
        score=min(score, 100),
        reasons=reasons[:4],
        matched_terms=matched_terms,
    )


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str,
    details: dict,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


def _clean_group_name(value: str) -> str:
    return " ".join(value.strip().split())


def _clean_group_text_values(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = " ".join(value.strip().split())
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        cleaned.append(label)
    return cleaned


def _support_group_payload(request: CreateSupportGroupRequest | UpdateSupportGroupRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Support group name is required",
            )
    if "description" in payload and payload["description"] is not None:
        payload["description"] = payload["description"].strip()
    if "team_email" in payload:
        payload["team_email"] = str(payload["team_email"] or "").strip().lower()
    if "skills" in payload and payload["skills"] is not None:
        payload["skills"] = _clean_group_text_values(payload["skills"])
    return payload


def _sla_policy_payload(request: CreateSlaPolicyRequest | UpdateSlaPolicyRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="SLA policy name is required",
            )
    if "business_hours" in payload and payload["business_hours"] is not None:
        payload["business_hours"] = _clean_group_name(payload["business_hours"])
        if not payload["business_hours"]:
            payload["business_hours"] = "Business hours"
    if "channels" in payload and payload["channels"] is not None:
        channels: list[str] = []
        seen: set[str] = set()
        for channel in payload["channels"]:
            if channel in seen:
                continue
            seen.add(channel)
            channels.append(channel)
        payload["channels"] = channels
    return payload


def _business_hours_payload(
    request: CreateBusinessHoursRequest | UpdateBusinessHoursRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Business hours name is required",
            )
    if "timezone" in payload and payload["timezone"] is not None:
        payload["timezone"] = payload["timezone"].strip() or "Africa/Lagos"
    return payload


def _default_business_days() -> list[dict]:
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    weekend = ["Saturday", "Sunday"]
    return [
        {"day": day, "enabled": True, "open": "09:00", "close": "17:00"} for day in weekdays
    ] + [{"day": day, "enabled": False, "open": "09:00", "close": "17:00"} for day in weekend]


def _ticket_template_payload(
    request: CreateTicketTemplateRequest | UpdateTicketTemplateRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Ticket template name is required",
            )
    if "subject" in payload and payload["subject"] is not None:
        payload["subject"] = payload["subject"].strip()
        if not payload["subject"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Ticket template subject is required",
            )
    if "tags" in payload and payload["tags"] is not None:
        seen: set[str] = set()
        tags: list[str] = []
        for tag in payload["tags"]:
            cleaned = str(tag).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                tags.append(cleaned)
        payload["tags"] = tags
    return payload


def _tag_payload(request: CreateTagRequest | UpdateTagRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = payload["name"].strip()
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tag name is required",
            )
    if "color" in payload and payload["color"] is not None:
        payload["color"] = payload["color"].strip() or "#2f6fed"
    return payload


def _csat_survey_payload(request: CreateCsatSurveyRequest | UpdateCsatSurveyRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CSAT survey name is required",
            )
    if "question" in payload and payload["question"] is not None:
        payload["question"] = payload["question"].strip()
        if not payload["question"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CSAT survey question is required",
            )
    if "channels" in payload and payload["channels"] is not None:
        seen: set[str] = set()
        channels: list[str] = []
        for channel in payload["channels"]:
            if channel not in seen:
                seen.add(channel)
                channels.append(channel)
        payload["channels"] = channels
    return payload


def _email_notification_payload(
    request: CreateEmailNotificationRequest | UpdateEmailNotificationRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Email notification name is required",
            )
    if "event" in payload and payload["event"] is not None:
        payload["event"] = payload["event"].strip() or "ticket_created"
    if "recipients" in payload and payload["recipients"] is not None:
        seen: set[str] = set()
        recipients: list[str] = []
        for recipient in payload["recipients"]:
            cleaned = str(recipient).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                recipients.append(cleaned)
        payload["recipients"] = recipients
    return payload


def _scenario_automation_payload(
    request: CreateScenarioAutomationRequest | UpdateScenarioAutomationRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Scenario automation name is required",
            )
    if "actions" in payload and payload["actions"] is not None:
        actions: list[dict] = []
        for action in payload["actions"]:
            action_type = str(action.get("type", "")).strip()
            if not action_type:
                continue
            actions.append({"type": action_type, "value": str(action.get("value", "")).strip()})
        payload["actions"] = actions
    return payload


def _custom_field_payload(
    request: CreateCustomFieldDefinitionRequest | UpdateCustomFieldDefinitionRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "label" in payload and payload["label"] is not None:
        payload["label"] = payload["label"].strip()
        if not payload["label"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Custom field label is required",
            )
    if "entity" in payload and payload["entity"] is not None:
        entity = payload["entity"].strip().lower()
        if entity not in {"contact", "company"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Custom field entity must be 'contact' or 'company'",
            )
        payload["entity"] = entity
    if "options" in payload and payload["options"] is not None:
        payload["options"] = _normalized_options(payload["options"])
    if "field_type" in payload and payload["field_type"] is not None:
        if payload["field_type"] not in _OPTION_FIELD_TYPES:
            payload["options"] = []
        elif not payload.get("options"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Select fields need at least one option",
            )
    return payload


def _custom_object_payload(
    request: CreateCustomObjectRequest | UpdateCustomObjectRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Custom object name is required",
            )
    if "description" in payload and payload["description"] is not None:
        payload["description"] = payload["description"].strip()
    if "fields" in payload and payload["fields"] is not None:
        seen: set[str] = set()
        fields: list[dict] = []
        for field in payload["fields"]:
            key = str(field.get("key", "")).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            field_type = field.get("field_type", "text")
            options = _normalized_options(field.get("options") or [])
            if field_type not in _OPTION_FIELD_TYPES:
                options = []
            fields.append(
                {
                    "key": key,
                    "label": str(field.get("label", "")).strip() or key,
                    "field_type": field_type,
                    "required": bool(field.get("required", False)),
                    "options": options,
                }
            )
        payload["fields"] = fields
    return payload


def _product_payload(request: CreateProductRequest | UpdateProductRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Product name is required",
            )
    if "code" in payload and payload["code"] is not None:
        payload["code"] = payload["code"].strip()
    if "description" in payload and payload["description"] is not None:
        payload["description"] = payload["description"].strip()
    return payload


_SAVED_REPORT_CADENCES = {"none", "daily", "weekly", "monthly"}


def _saved_report_payload(request: CreateSavedReportRequest | UpdateSavedReportRequest) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Saved report name is required",
            )
    if "cadence" in payload and payload["cadence"] is not None:
        cadence = payload["cadence"].strip().lower() or "none"
        if cadence not in _SAVED_REPORT_CADENCES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cadence must be none, daily, weekly, or monthly",
            )
        payload["cadence"] = cadence
    if "recipients" in payload and payload["recipients"] is not None:
        seen: set[str] = set()
        recipients: list[str] = []
        for recipient in payload["recipients"]:
            cleaned = str(recipient).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                recipients.append(cleaned)
        payload["recipients"] = recipients
    return payload


_SERVICE_APPOINTMENT_STATUSES = {
    "scheduled",
    "en_route",
    "in_progress",
    "completed",
    "cancelled",
}


def _service_appointment_payload(
    request: CreateServiceAppointmentRequest | UpdateServiceAppointmentRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"] is not None:
        payload["title"] = payload["title"].strip()
        if not payload["title"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Appointment title is required",
            )
    if "status" in payload and payload["status"] is not None:
        appointment_status = payload["status"].strip().lower() or "scheduled"
        if appointment_status not in _SERVICE_APPOINTMENT_STATUSES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid appointment status",
            )
        payload["status"] = appointment_status
    return payload


_DISCUSSION_TOPIC_STATUSES = {"open", "answered", "closed"}


def _discussion_topic_payload(
    request: CreateDiscussionTopicRequest | UpdateDiscussionTopicRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "title" in payload and payload["title"] is not None:
        payload["title"] = " ".join(payload["title"].split())
        if not payload["title"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Topic title is required",
            )
    if "category" in payload and payload["category"] is not None:
        payload["category"] = payload["category"].strip() or "General"
    if "status" in payload and payload["status"] is not None:
        topic_status = payload["status"].strip().lower() or "open"
        if topic_status not in _DISCUSSION_TOPIC_STATUSES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Topic status must be open, answered, or closed",
            )
        payload["status"] = topic_status
    return payload


def _apply_knowledge_status(
    record: KnowledgeArticleRecord,
    next_status: KnowledgeArticleStatus,
    actor: str,
) -> None:
    now = utc_now()
    record.status = next_status.value
    if next_status == KnowledgeArticleStatus.draft:
        record.submitted_for_review_at = None
        record.approved_at = None
        record.approved_by = None
        return
    if next_status == KnowledgeArticleStatus.in_review:
        record.submitted_for_review_at = record.submitted_for_review_at or now
        record.approved_at = None
        record.approved_by = None
        return
    if next_status in {KnowledgeArticleStatus.approved, KnowledgeArticleStatus.published}:
        record.submitted_for_review_at = record.submitted_for_review_at or now
        if record.approved_at is None:
            record.approved_at = now
            record.approved_by = actor


class ManagementRepository:
    def list_channels(self, db: Session, state: InMemoryStore, market_id: str) -> list[Channel]:
        channels = [
            channel_from_record(record)
            for record in db.scalars(
                select(ChannelRecord).where(ChannelRecord.market_id == market_id)
            ).all()
        ]
        # Queue stats are computed live from the market's real open tickets — the
        # seeded queued/active/sla_risk numbers are placeholders only. A stored
        # health of "paused" is an operator override and is preserved.
        open_tickets = db.scalars(
            select(TicketRecord).where(
                TicketRecord.market_id == market_id,
                TicketRecord.status.not_in(["solved", "closed"]),
            )
        ).all()
        stats: dict[str, dict[str, int]] = {}
        for record in open_tickets:
            bucket = stats.setdefault(
                record.channel, {"queued": 0, "active": 0, "risk": 0, "breached": 0}
            )
            bucket["queued"] += 1
            if record.assignee_id:
                bucket["active"] += 1
            sla = record.sla if isinstance(record.sla, dict) else {}
            if sla.get("breached"):
                bucket["breached"] += 1
                bucket["risk"] += 1
            elif sla.get("risk") not in (None, "on_track"):
                bucket["risk"] += 1
        # Wiring state comes from real configuration: a channel is only "live" when
        # its intake path (IMAP credentials / verified signed webhook) is fully set up.
        from app.services.inbound_adapters import inbound_adapter_router
        from app.services.outbound_adapters import outbound_adapter_router

        inbound_configs = {
            config.provider.value: config
            for config in inbound_adapter_router.config_summary(db, market_id)
        }
        outbound_configs = {
            config.provider.value: config
            for config in outbound_adapter_router.config_summary(db, market_id)
        }
        always_on = {
            "portal": "Public Help Center — always able to receive requests.",
            "api": "Authenticated API intake — always able to receive events.",
            "internal": "Internal channel.",
        }
        for channel in channels:
            bucket = stats.get(
                channel.type.value, {"queued": 0, "active": 0, "risk": 0, "breached": 0}
            )
            channel.queued = bucket["queued"]
            channel.active = bucket["active"]
            channel.sla_risk = bucket["risk"]
            if channel.health != ChannelHealth.paused:
                channel.health = (
                    ChannelHealth.degraded if bucket["risk"] > 0 else ChannelHealth.healthy
                )
            key = channel.type.value
            if key in always_on:
                channel.intake_live = True
                channel.intake_note = always_on[key]
                channel.outbound_live = key != "internal"
                channel.outbound_note = always_on[key]
                continue
            inbound = inbound_configs.get(key)
            channel.intake_live = bool(inbound and inbound.live_intake)
            channel.intake_note = (
                (inbound.notes if inbound else "No intake adapter for this channel.")
                if channel.intake_live or not inbound or not inbound.missing_settings
                else "Missing: " + ", ".join(inbound.missing_settings)
            )
            outbound = outbound_configs.get(key)
            outbound_live = bool(outbound and getattr(outbound, "live_delivery", False))
            channel.outbound_live = outbound_live
            outbound_missing = list(getattr(outbound, "missing_settings", []) or []) if outbound else []
            channel.outbound_note = (
                "Delivery live."
                if outbound_live
                else ("Missing: " + ", ".join(outbound_missing) if outbound_missing else "Delivery not configured.")
            )
        state.channels = {
            **{key: value for key, value in state.channels.items() if value.market_id != market_id},
            **{channel.id: channel for channel in channels},
        }
        return channels

    def update_channel(
        self,
        db: Session,
        state: InMemoryStore,
        channel_id: str,
        request: UpdateChannelRequest,
        market_id: str,
    ) -> Channel:
        record = db.get(ChannelRecord, channel_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Channel not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            actor="api",
            action="channel.update",
            entity_type="channel",
            entity_id=channel_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        channel = channel_from_record(record)
        state.channels[channel.id] = channel
        return channel

    def list_agents(self, db: Session, state: InMemoryStore, market_id: str) -> list[Agent]:
        agents = [
            agent_from_record(record)
            for record in db.scalars(select(AgentRecord)).all()
            if market_id in record.market_ids
        ]
        state.agents = {
            **{key: value for key, value in state.agents.items() if market_id not in value.market_ids},
            **{agent.id: agent for agent in agents},
        }
        return agents

    def update_agent_status(
        self,
        db: Session,
        state: InMemoryStore,
        agent_id: str,
        request: UpdateAgentStatusRequest,
        market_id: str,
    ) -> Agent:
        record = db.get(AgentRecord, agent_id)
        if record is None or market_id not in record.market_ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
        record.status = request.status.value
        _audit(
            db,
            state,
            actor="api",
            action="agent.status.update",
            entity_type="agent",
            entity_id=agent_id,
            market_id=market_id,
            details={"status": request.status.value},
        )
        db.commit()
        db.refresh(record)
        agent = agent_from_record(record)
        state.agents[agent.id] = agent
        return agent

    def _support_group_counts(
        self,
        db: Session,
        *,
        market_id: str,
        group_name: str,
    ) -> tuple[int, int, int]:
        agent_records = db.scalars(select(AgentRecord)).all()
        ticket_records = db.scalars(
            select(TicketRecord).where(TicketRecord.market_id == market_id)
        ).all()
        member_count = sum(
            1
            for record in agent_records
            if market_id in record.market_ids and record.role == group_name
        )
        open_tickets = [
            record
            for record in ticket_records
            if record.team == group_name and record.status in _OPEN_TICKET_STATUSES
        ]
        sla_risk_count = sum(
            1
            for record in open_tickets
            if record.sla.get("risk") in {"at_risk", "breached"} or record.sla.get("breached")
        )
        return member_count, len(open_tickets), sla_risk_count

    def _support_group_from_record(
        self,
        db: Session,
        record: SupportGroupRecord,
    ) -> SupportGroup:
        member_count, open_ticket_count, sla_risk_count = self._support_group_counts(
            db,
            market_id=record.market_id,
            group_name=record.name,
        )
        return support_group_from_record(
            record,
            member_count=member_count,
            open_ticket_count=open_ticket_count,
            sla_risk_count=sla_risk_count,
        )

    def list_support_groups(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[SupportGroup]:
        records = db.scalars(
            select(SupportGroupRecord).where(SupportGroupRecord.market_id == market_id)
        ).all()
        groups = [self._support_group_from_record(db, record) for record in records]
        groups.sort(key=lambda group: (not group.active, group.name.lower()))
        state.support_groups = {
            **{
                key: value
                for key, value in state.support_groups.items()
                if value.market_id != market_id
            },
            **{group.id: group for group in groups},
        }
        return groups

    def create_support_group(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateSupportGroupRequest,
        market_id: str,
        actor: str,
    ) -> SupportGroup:
        payload = _support_group_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(SupportGroupRecord).where(
                SupportGroupRecord.market_id == market_id,
                SupportGroupRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Support group already exists")
        record = SupportGroupRecord(id=_new_id("group"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="support_group.create",
            entity_type="support_group",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        group = self._support_group_from_record(db, record)
        state.support_groups[group.id] = group
        return group

    def update_support_group(
        self,
        db: Session,
        state: InMemoryStore,
        group_id: str,
        request: UpdateSupportGroupRequest,
        market_id: str,
        actor: str,
    ) -> SupportGroup:
        record = db.get(SupportGroupRecord, group_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Support group not found")
        patch = _support_group_payload(request)
        old_name = record.name
        if "name" in patch and patch["name"] != old_name:
            duplicate = db.scalar(
                select(SupportGroupRecord).where(
                    SupportGroupRecord.market_id == market_id,
                    SupportGroupRecord.name == patch["name"],
                    SupportGroupRecord.id != group_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Support group already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        renamed_to = patch.get("name")
        if renamed_to and renamed_to != old_name:
            for agent in db.scalars(select(AgentRecord)).all():
                if market_id in agent.market_ids and agent.role == old_name:
                    agent.role = renamed_to
            for ticket in db.scalars(
                select(TicketRecord).where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.team == old_name,
                )
            ).all():
                ticket.team = renamed_to
            for handoff in db.scalars(
                select(HandoffRecord).where(HandoffRecord.market_id == market_id)
            ).all():
                if handoff.from_team == old_name:
                    handoff.from_team = renamed_to
                if handoff.to_team == old_name:
                    handoff.to_team = renamed_to
        _audit(
            db,
            state,
            actor=actor,
            action="support_group.update",
            entity_type="support_group",
            entity_id=group_id,
            market_id=market_id,
            details={**patch, "renamed_from": old_name if renamed_to else None},
        )
        db.commit()
        db.refresh(record)
        group = self._support_group_from_record(db, record)
        state.support_groups[group.id] = group
        return group

    def list_sla_policies(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[SlaPolicy]:
        records = db.scalars(
            select(SlaPolicyRecord).where(SlaPolicyRecord.market_id == market_id)
        ).all()
        policies = [sla_policy_from_record(record) for record in records]
        policies.sort(
            key=lambda policy: (
                not policy.active,
                policy.priority.value,
                policy.position,
                policy.name.lower(),
            )
        )
        state.sla_policies = {
            **{
                key: value
                for key, value in state.sla_policies.items()
                if value.market_id != market_id
            },
            **{policy.id: policy for policy in policies},
        }
        return policies

    def create_sla_policy(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateSlaPolicyRequest,
        market_id: str,
        actor: str,
    ) -> SlaPolicy:
        payload = _sla_policy_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(SlaPolicyRecord).where(
                SlaPolicyRecord.market_id == market_id,
                SlaPolicyRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="SLA policy already exists")
        record = SlaPolicyRecord(id=_new_id("sla"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="sla_policy.create",
            entity_type="sla_policy",
            entity_id=record.id,
            market_id=market_id,
            details={
                "name": record.name,
                "priority": record.priority,
                "channels": record.channels,
                "active": record.active,
            },
        )
        db.commit()
        db.refresh(record)
        policy = sla_policy_from_record(record)
        state.sla_policies[policy.id] = policy
        return policy

    def update_sla_policy(
        self,
        db: Session,
        state: InMemoryStore,
        policy_id: str,
        request: UpdateSlaPolicyRequest,
        market_id: str,
        actor: str,
    ) -> SlaPolicy:
        record = db.get(SlaPolicyRecord, policy_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SLA policy not found")
        patch = _sla_policy_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(SlaPolicyRecord).where(
                    SlaPolicyRecord.market_id == market_id,
                    SlaPolicyRecord.name == patch["name"],
                    SlaPolicyRecord.id != policy_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="SLA policy already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="sla_policy.update",
            entity_type="sla_policy",
            entity_id=policy_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        policy = sla_policy_from_record(record)
        state.sla_policies[policy.id] = policy
        return policy

    def list_business_hours(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[BusinessHours]:
        records = db.scalars(
            select(BusinessHoursRecord).where(BusinessHoursRecord.market_id == market_id)
        ).all()
        calendars = [business_hours_from_record(record) for record in records]
        calendars.sort(key=lambda calendar: (not calendar.active, calendar.name.lower()))
        state.business_hours = {
            **{
                key: value
                for key, value in state.business_hours.items()
                if value.market_id != market_id
            },
            **{calendar.id: calendar for calendar in calendars},
        }
        return calendars

    def create_business_hours(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateBusinessHoursRequest,
        market_id: str,
        actor: str,
    ) -> BusinessHours:
        payload = _business_hours_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(BusinessHoursRecord).where(
                BusinessHoursRecord.market_id == market_id,
                BusinessHoursRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Business hours already exist")
        if not payload.get("days"):
            payload["days"] = _default_business_days()
        record = BusinessHoursRecord(id=_new_id("bh"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="business_hours.create",
            entity_type="business_hours",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "timezone": record.timezone, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        calendar = business_hours_from_record(record)
        state.business_hours[calendar.id] = calendar
        return calendar

    def update_business_hours(
        self,
        db: Session,
        state: InMemoryStore,
        business_hours_id: str,
        request: UpdateBusinessHoursRequest,
        market_id: str,
        actor: str,
    ) -> BusinessHours:
        record = db.get(BusinessHoursRecord, business_hours_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Business hours not found")
        patch = _business_hours_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(BusinessHoursRecord).where(
                    BusinessHoursRecord.market_id == market_id,
                    BusinessHoursRecord.name == patch["name"],
                    BusinessHoursRecord.id != business_hours_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Business hours already exist")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="business_hours.update",
            entity_type="business_hours",
            entity_id=business_hours_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        calendar = business_hours_from_record(record)
        state.business_hours[calendar.id] = calendar
        return calendar

    def list_ticket_templates(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[TicketTemplate]:
        records = db.scalars(
            select(TicketTemplateRecord).where(TicketTemplateRecord.market_id == market_id)
        ).all()
        templates = [ticket_template_from_record(record) for record in records]
        templates.sort(key=lambda template: (not template.active, template.name.lower()))
        state.ticket_templates = {
            **{
                key: value
                for key, value in state.ticket_templates.items()
                if value.market_id != market_id
            },
            **{template.id: template for template in templates},
        }
        return templates

    def create_ticket_template(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateTicketTemplateRequest,
        market_id: str,
        actor: str,
    ) -> TicketTemplate:
        payload = _ticket_template_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(TicketTemplateRecord).where(
                TicketTemplateRecord.market_id == market_id,
                TicketTemplateRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Ticket template already exists")
        record = TicketTemplateRecord(id=_new_id("tpl"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="ticket_template.create",
            entity_type="ticket_template",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "priority": record.priority, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        template = ticket_template_from_record(record)
        state.ticket_templates[template.id] = template
        return template

    def update_ticket_template(
        self,
        db: Session,
        state: InMemoryStore,
        template_id: str,
        request: UpdateTicketTemplateRequest,
        market_id: str,
        actor: str,
    ) -> TicketTemplate:
        record = db.get(TicketTemplateRecord, template_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket template not found")
        patch = _ticket_template_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(TicketTemplateRecord).where(
                    TicketTemplateRecord.market_id == market_id,
                    TicketTemplateRecord.name == patch["name"],
                    TicketTemplateRecord.id != template_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Ticket template already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="ticket_template.update",
            entity_type="ticket_template",
            entity_id=template_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        template = ticket_template_from_record(record)
        state.ticket_templates[template.id] = template
        return template

    def list_tags(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[Tag]:
        records = db.scalars(select(TagRecord).where(TagRecord.market_id == market_id)).all()
        tags = [tag_from_record(record) for record in records]
        tags.sort(key=lambda tag: (not tag.active, tag.name.lower()))
        state.tags = {
            **{key: value for key, value in state.tags.items() if value.market_id != market_id},
            **{tag.id: tag for tag in tags},
        }
        return tags

    def create_tag(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateTagRequest,
        market_id: str,
        actor: str,
    ) -> Tag:
        payload = _tag_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(TagRecord).where(TagRecord.market_id == market_id, TagRecord.name == name)
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Tag already exists")
        record = TagRecord(id=_new_id("tag"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="tag.create",
            entity_type="tag",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        tag = tag_from_record(record)
        state.tags[tag.id] = tag
        return tag

    def update_tag(
        self,
        db: Session,
        state: InMemoryStore,
        tag_id: str,
        request: UpdateTagRequest,
        market_id: str,
        actor: str,
    ) -> Tag:
        record = db.get(TagRecord, tag_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tag not found")
        patch = _tag_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(TagRecord).where(
                    TagRecord.market_id == market_id,
                    TagRecord.name == patch["name"],
                    TagRecord.id != tag_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Tag already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="tag.update",
            entity_type="tag",
            entity_id=tag_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        tag = tag_from_record(record)
        state.tags[tag.id] = tag
        return tag

    def list_csat_surveys(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[CsatSurvey]:
        records = db.scalars(
            select(CsatSurveyRecord).where(CsatSurveyRecord.market_id == market_id)
        ).all()
        surveys = [csat_survey_from_record(record) for record in records]
        surveys.sort(key=lambda survey: (not survey.active, survey.name.lower()))
        state.csat_surveys = {
            **{
                key: value
                for key, value in state.csat_surveys.items()
                if value.market_id != market_id
            },
            **{survey.id: survey for survey in surveys},
        }
        return surveys

    def create_csat_survey(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateCsatSurveyRequest,
        market_id: str,
        actor: str,
    ) -> CsatSurvey:
        payload = _csat_survey_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(CsatSurveyRecord).where(
                CsatSurveyRecord.market_id == market_id,
                CsatSurveyRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="CSAT survey already exists")
        record = CsatSurveyRecord(id=_new_id("csat"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="csat_survey.create",
            entity_type="csat_survey",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        survey = csat_survey_from_record(record)
        state.csat_surveys[survey.id] = survey
        return survey

    def update_csat_survey(
        self,
        db: Session,
        state: InMemoryStore,
        survey_id: str,
        request: UpdateCsatSurveyRequest,
        market_id: str,
        actor: str,
    ) -> CsatSurvey:
        record = db.get(CsatSurveyRecord, survey_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="CSAT survey not found")
        patch = _csat_survey_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(CsatSurveyRecord).where(
                    CsatSurveyRecord.market_id == market_id,
                    CsatSurveyRecord.name == patch["name"],
                    CsatSurveyRecord.id != survey_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="CSAT survey already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="csat_survey.update",
            entity_type="csat_survey",
            entity_id=survey_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        survey = csat_survey_from_record(record)
        state.csat_surveys[survey.id] = survey
        return survey

    def list_email_notifications(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[EmailNotification]:
        records = db.scalars(
            select(EmailNotificationRecord).where(EmailNotificationRecord.market_id == market_id)
        ).all()
        notifications = [email_notification_from_record(record) for record in records]
        notifications.sort(key=lambda item: (not item.active, item.name.lower()))
        state.email_notifications = {
            **{
                key: value
                for key, value in state.email_notifications.items()
                if value.market_id != market_id
            },
            **{item.id: item for item in notifications},
        }
        return notifications

    def create_email_notification(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateEmailNotificationRequest,
        market_id: str,
        actor: str,
    ) -> EmailNotification:
        payload = _email_notification_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(EmailNotificationRecord).where(
                EmailNotificationRecord.market_id == market_id,
                EmailNotificationRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Email notification already exists"
            )
        record = EmailNotificationRecord(id=_new_id("notif"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="email_notification.create",
            entity_type="email_notification",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "event": record.event, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        notification = email_notification_from_record(record)
        state.email_notifications[notification.id] = notification
        return notification

    def update_email_notification(
        self,
        db: Session,
        state: InMemoryStore,
        notification_id: str,
        request: UpdateEmailNotificationRequest,
        market_id: str,
        actor: str,
    ) -> EmailNotification:
        record = db.get(EmailNotificationRecord, notification_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Email notification not found")
        patch = _email_notification_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(EmailNotificationRecord).where(
                    EmailNotificationRecord.market_id == market_id,
                    EmailNotificationRecord.name == patch["name"],
                    EmailNotificationRecord.id != notification_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, detail="Email notification already exists"
                )
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="email_notification.update",
            entity_type="email_notification",
            entity_id=notification_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        notification = email_notification_from_record(record)
        state.email_notifications[notification.id] = notification
        return notification

    def list_scenario_automations(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[ScenarioAutomation]:
        records = db.scalars(
            select(ScenarioAutomationRecord).where(
                ScenarioAutomationRecord.market_id == market_id
            )
        ).all()
        scenarios = [scenario_automation_from_record(record) for record in records]
        scenarios.sort(key=lambda item: (not item.active, item.name.lower()))
        state.scenario_automations = {
            **{
                key: value
                for key, value in state.scenario_automations.items()
                if value.market_id != market_id
            },
            **{item.id: item for item in scenarios},
        }
        return scenarios

    def create_scenario_automation(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateScenarioAutomationRequest,
        market_id: str,
        actor: str,
    ) -> ScenarioAutomation:
        payload = _scenario_automation_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(ScenarioAutomationRecord).where(
                ScenarioAutomationRecord.market_id == market_id,
                ScenarioAutomationRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Scenario automation already exists"
            )
        record = ScenarioAutomationRecord(id=_new_id("scenario"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="scenario_automation.create",
            entity_type="scenario_automation",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        scenario = scenario_automation_from_record(record)
        state.scenario_automations[scenario.id] = scenario
        return scenario

    def update_scenario_automation(
        self,
        db: Session,
        state: InMemoryStore,
        scenario_id: str,
        request: UpdateScenarioAutomationRequest,
        market_id: str,
        actor: str,
    ) -> ScenarioAutomation:
        record = db.get(ScenarioAutomationRecord, scenario_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scenario automation not found")
        patch = _scenario_automation_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(ScenarioAutomationRecord).where(
                    ScenarioAutomationRecord.market_id == market_id,
                    ScenarioAutomationRecord.name == patch["name"],
                    ScenarioAutomationRecord.id != scenario_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, detail="Scenario automation already exists"
                )
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="scenario_automation.update",
            entity_type="scenario_automation",
            entity_id=scenario_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        scenario = scenario_automation_from_record(record)
        state.scenario_automations[scenario.id] = scenario
        return scenario

    def list_custom_field_definitions(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[CustomFieldDefinition]:
        records = db.scalars(
            select(CustomFieldDefinitionRecord).where(
                CustomFieldDefinitionRecord.market_id == market_id
            )
        ).all()
        fields = [custom_field_definition_from_record(record) for record in records]
        fields.sort(key=lambda field: (field.entity, not field.active, field.position, field.label.lower()))
        state.custom_field_definitions = {
            **{
                key: value
                for key, value in state.custom_field_definitions.items()
                if value.market_id != market_id
            },
            **{field.id: field for field in fields},
        }
        return fields

    def create_custom_field_definition(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateCustomFieldDefinitionRequest,
        market_id: str,
        actor: str,
    ) -> CustomFieldDefinition:
        payload = _custom_field_payload(request)
        duplicate = db.scalar(
            select(CustomFieldDefinitionRecord).where(
                CustomFieldDefinitionRecord.market_id == market_id,
                CustomFieldDefinitionRecord.entity == payload["entity"],
                CustomFieldDefinitionRecord.key == payload["key"],
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Custom field key already exists")
        record = CustomFieldDefinitionRecord(id=_new_id("cfd"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="custom_field.create",
            entity_type="custom_field",
            entity_id=record.id,
            market_id=market_id,
            details={"entity": record.entity, "key": record.key, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        field = custom_field_definition_from_record(record)
        state.custom_field_definitions[field.id] = field
        return field

    def update_custom_field_definition(
        self,
        db: Session,
        state: InMemoryStore,
        field_id: str,
        request: UpdateCustomFieldDefinitionRequest,
        market_id: str,
        actor: str,
    ) -> CustomFieldDefinition:
        record = db.get(CustomFieldDefinitionRecord, field_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Custom field not found")
        patch = _custom_field_payload(request)
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="custom_field.update",
            entity_type="custom_field",
            entity_id=field_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        field = custom_field_definition_from_record(record)
        state.custom_field_definitions[field.id] = field
        return field

    def list_custom_objects(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[CustomObject]:
        records = db.scalars(
            select(CustomObjectRecord).where(CustomObjectRecord.market_id == market_id)
        ).all()
        objects = [custom_object_from_record(record) for record in records]
        objects.sort(key=lambda obj: (not obj.active, obj.name.lower()))
        state.custom_objects = {
            **{
                key: value
                for key, value in state.custom_objects.items()
                if value.market_id != market_id
            },
            **{obj.id: obj for obj in objects},
        }
        return objects

    def create_custom_object(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateCustomObjectRequest,
        market_id: str,
        actor: str,
    ) -> CustomObject:
        payload = _custom_object_payload(request)
        payload["key"] = payload["key"].strip().lower()
        duplicate = db.scalar(
            select(CustomObjectRecord).where(
                CustomObjectRecord.market_id == market_id,
                CustomObjectRecord.key == payload["key"],
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Custom object key already exists")
        record = CustomObjectRecord(id=_new_id("object"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="custom_object.create",
            entity_type="custom_object",
            entity_id=record.id,
            market_id=market_id,
            details={"key": record.key, "name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        custom_object = custom_object_from_record(record)
        state.custom_objects[custom_object.id] = custom_object
        return custom_object

    def update_custom_object(
        self,
        db: Session,
        state: InMemoryStore,
        object_id: str,
        request: UpdateCustomObjectRequest,
        market_id: str,
        actor: str,
    ) -> CustomObject:
        record = db.get(CustomObjectRecord, object_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Custom object not found")
        patch = _custom_object_payload(request)
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="custom_object.update",
            entity_type="custom_object",
            entity_id=object_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        custom_object = custom_object_from_record(record)
        state.custom_objects[custom_object.id] = custom_object
        return custom_object

    def list_products(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[Product]:
        records = db.scalars(
            select(ProductRecord).where(ProductRecord.market_id == market_id)
        ).all()
        products = [product_from_record(record) for record in records]
        products.sort(key=lambda product: (not product.active, product.name.lower()))
        state.products = {
            **{
                key: value
                for key, value in state.products.items()
                if value.market_id != market_id
            },
            **{product.id: product for product in products},
        }
        return products

    def create_product(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateProductRequest,
        market_id: str,
        actor: str,
    ) -> Product:
        payload = _product_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(ProductRecord).where(
                ProductRecord.market_id == market_id,
                ProductRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Product already exists")
        record = ProductRecord(id=_new_id("product"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="product.create",
            entity_type="product",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "code": record.code, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        product = product_from_record(record)
        state.products[product.id] = product
        return product

    def update_product(
        self,
        db: Session,
        state: InMemoryStore,
        product_id: str,
        request: UpdateProductRequest,
        market_id: str,
        actor: str,
    ) -> Product:
        record = db.get(ProductRecord, product_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
        patch = _product_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(ProductRecord).where(
                    ProductRecord.market_id == market_id,
                    ProductRecord.name == patch["name"],
                    ProductRecord.id != product_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Product already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="product.update",
            entity_type="product",
            entity_id=product_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        product = product_from_record(record)
        state.products[product.id] = product
        return product

    def list_saved_reports(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[SavedReport]:
        records = db.scalars(
            select(SavedReportRecord).where(SavedReportRecord.market_id == market_id)
        ).all()
        reports = [saved_report_from_record(record) for record in records]
        reports.sort(key=lambda report: (not report.active, report.name.lower()))
        state.saved_reports = {
            **{
                key: value
                for key, value in state.saved_reports.items()
                if value.market_id != market_id
            },
            **{report.id: report for report in reports},
        }
        return reports

    def create_saved_report(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateSavedReportRequest,
        market_id: str,
        actor: str,
    ) -> SavedReport:
        payload = _saved_report_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(SavedReportRecord).where(
                SavedReportRecord.market_id == market_id,
                SavedReportRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Saved report already exists")
        record = SavedReportRecord(id=_new_id("report"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="saved_report.create",
            entity_type="saved_report",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "cadence": record.cadence, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        report = saved_report_from_record(record)
        state.saved_reports[report.id] = report
        return report

    def update_saved_report(
        self,
        db: Session,
        state: InMemoryStore,
        report_id: str,
        request: UpdateSavedReportRequest,
        market_id: str,
        actor: str,
    ) -> SavedReport:
        record = db.get(SavedReportRecord, report_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Saved report not found")
        patch = _saved_report_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(SavedReportRecord).where(
                    SavedReportRecord.market_id == market_id,
                    SavedReportRecord.name == patch["name"],
                    SavedReportRecord.id != report_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Saved report already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="saved_report.update",
            entity_type="saved_report",
            entity_id=report_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        report = saved_report_from_record(record)
        state.saved_reports[report.id] = report
        return report

    def list_service_appointments(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[ServiceAppointment]:
        records = db.scalars(
            select(ServiceAppointmentRecord).where(ServiceAppointmentRecord.market_id == market_id)
        ).all()
        appointments = [service_appointment_from_record(record) for record in records]
        appointments.sort(key=lambda appointment: appointment.scheduled_at)
        state.service_appointments = {
            **{
                key: value
                for key, value in state.service_appointments.items()
                if value.market_id != market_id
            },
            **{appointment.id: appointment for appointment in appointments},
        }
        return appointments

    def create_service_appointment(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateServiceAppointmentRequest,
        market_id: str,
        actor: str,
    ) -> ServiceAppointment:
        payload = _service_appointment_payload(request)
        record = ServiceAppointmentRecord(id=_new_id("appt"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="service_appointment.create",
            entity_type="service_appointment",
            entity_id=record.id,
            market_id=market_id,
            details={"title": record.title, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        appointment = service_appointment_from_record(record)
        state.service_appointments[appointment.id] = appointment
        return appointment

    def update_service_appointment(
        self,
        db: Session,
        state: InMemoryStore,
        appointment_id: str,
        request: UpdateServiceAppointmentRequest,
        market_id: str,
        actor: str,
    ) -> ServiceAppointment:
        record = db.get(ServiceAppointmentRecord, appointment_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Service appointment not found")
        patch = _service_appointment_payload(request)
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="service_appointment.update",
            entity_type="service_appointment",
            entity_id=appointment_id,
            market_id=market_id,
            details={"title": record.title, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        appointment = service_appointment_from_record(record)
        state.service_appointments[appointment.id] = appointment
        return appointment

    def list_discussion_topics(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[DiscussionTopic]:
        records = db.scalars(
            select(DiscussionTopicRecord).where(DiscussionTopicRecord.market_id == market_id)
        ).all()
        topics = [discussion_topic_from_record(record) for record in records]
        topics.sort(key=lambda topic: (not topic.pinned, topic.updated_at), reverse=False)
        # pinned first, then most-recently updated
        topics.sort(key=lambda topic: topic.updated_at, reverse=True)
        topics.sort(key=lambda topic: topic.pinned, reverse=True)
        state.discussion_topics = {
            **{
                key: value
                for key, value in state.discussion_topics.items()
                if value.market_id != market_id
            },
            **{topic.id: topic for topic in topics},
        }
        return topics

    def create_discussion_topic(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateDiscussionTopicRequest,
        market_id: str,
        actor: str,
    ) -> DiscussionTopic:
        payload = _discussion_topic_payload(request)
        record = DiscussionTopicRecord(
            id=_new_id("topic"),
            market_id=market_id,
            author=actor,
            reply_count=0,
            **payload,
        )
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="discussion_topic.create",
            entity_type="discussion_topic",
            entity_id=record.id,
            market_id=market_id,
            details={"title": record.title, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        topic = discussion_topic_from_record(record)
        state.discussion_topics[topic.id] = topic
        return topic

    def update_discussion_topic(
        self,
        db: Session,
        state: InMemoryStore,
        topic_id: str,
        request: UpdateDiscussionTopicRequest,
        market_id: str,
        actor: str,
    ) -> DiscussionTopic:
        record = db.get(DiscussionTopicRecord, topic_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Discussion topic not found")
        patch = _discussion_topic_payload(request)
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="discussion_topic.update",
            entity_type="discussion_topic",
            entity_id=topic_id,
            market_id=market_id,
            details={"title": record.title, "status": record.status, "pinned": record.pinned},
        )
        db.commit()
        db.refresh(record)
        topic = discussion_topic_from_record(record)
        state.discussion_topics[topic.id] = topic
        return topic

    def list_discussion_comments(
        self,
        db: Session,
        state: InMemoryStore,
        topic_id: str,
        market_id: str,
    ) -> list[DiscussionComment]:
        topic = db.get(DiscussionTopicRecord, topic_id)
        if topic is None or topic.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Discussion topic not found")
        records = db.scalars(
            select(DiscussionCommentRecord)
            .where(DiscussionCommentRecord.topic_id == topic_id)
            .order_by(DiscussionCommentRecord.created_at.asc())
        ).all()
        comments = [discussion_comment_from_record(record) for record in records]
        state.discussion_comments = {
            **{key: value for key, value in state.discussion_comments.items() if value.topic_id != topic_id},
            **{comment.id: comment for comment in comments},
        }
        return comments

    def create_discussion_comment(
        self,
        db: Session,
        state: InMemoryStore,
        topic_id: str,
        request: CreateDiscussionCommentRequest,
        market_id: str,
        actor: str,
    ) -> DiscussionComment:
        topic = db.get(DiscussionTopicRecord, topic_id)
        if topic is None or topic.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Discussion topic not found")
        record = DiscussionCommentRecord(
            id=_new_id("comment"),
            topic_id=topic_id,
            market_id=market_id,
            author=request.author.strip() or actor,
            body=request.body.strip(),
        )
        db.add(record)
        topic.reply_count = (topic.reply_count or 0) + 1
        topic.updated_at = utc_now()
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="discussion_comment.create",
            entity_type="discussion_topic",
            entity_id=topic_id,
            market_id=market_id,
            details={"comment_id": record.id},
        )
        db.commit()
        db.refresh(record)
        db.refresh(topic)
        comment = discussion_comment_from_record(record)
        state.discussion_comments[comment.id] = comment
        state.discussion_topics[topic.id] = discussion_topic_from_record(topic)
        return comment

    def list_knowledge(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[KnowledgeArticle]:
        articles = [
            knowledge_article_from_record(record)
            for record in db.scalars(select(KnowledgeArticleRecord)).all()
            if market_id in record.market_ids
        ]
        state.knowledge = {
            **{
                key: value
                for key, value in state.knowledge.items()
                if market_id not in value.market_ids
            },
            **{article.id: article for article in articles},
        }
        return articles

    def list_ticket_fields(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        active_only: bool = False,
        channel: str | None = None,
    ) -> list[TicketField]:
        records = db.scalars(
            select(TicketFieldRecord).where(TicketFieldRecord.market_id == market_id)
        ).all()
        fields = [
            ticket_field_from_record(record)
            for record in records
            if (not active_only or record.active)
            and (channel is None or not record.channels or channel in record.channels)
        ]
        fields.sort(key=lambda field: (field.position, field.label.lower()))
        state.ticket_fields = {
            **{
                key: value
                for key, value in state.ticket_fields.items()
                if value.market_id != market_id
            },
            **{field.id: field for field in fields},
        }
        return fields

    def create_ticket_field(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateTicketFieldRequest,
        market_id: str,
        actor: str,
    ) -> TicketField:
        payload = request.model_dump(mode="json")
        payload["market_id"] = market_id
        payload["key"] = payload["key"].strip().lower()
        payload["label"] = payload["label"].strip()
        if not payload["label"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Ticket field label is required")
        duplicate = db.scalar(
            select(TicketFieldRecord).where(
                TicketFieldRecord.market_id == market_id,
                TicketFieldRecord.key == payload["key"],
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Ticket field key already exists")
        _validate_ticket_field_payload(payload)
        record = TicketFieldRecord(id=_new_id("field"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="ticket_field.create",
            entity_type="ticket_field",
            entity_id=record.id,
            market_id=market_id,
            details={"key": record.key, "required": record.required, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        field = ticket_field_from_record(record)
        state.ticket_fields[field.id] = field
        return field

    def update_ticket_field(
        self,
        db: Session,
        state: InMemoryStore,
        field_id: str,
        request: UpdateTicketFieldRequest,
        market_id: str,
        actor: str,
    ) -> TicketField:
        record = db.get(TicketFieldRecord, field_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket field not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        if "label" in patch:
            patch["label"] = patch["label"].strip()
            if not patch["label"]:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Ticket field label is required")
        next_payload = {
            "field_type": patch.get("field_type", record.field_type),
            "options": patch.get("options", record.options),
        }
        _validate_ticket_field_payload(next_payload)
        if "field_type" in patch:
            record.field_type = patch["field_type"]
            patch["options"] = next_payload["options"]
        elif "options" in patch:
            patch["options"] = next_payload["options"]
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="ticket_field.update",
            entity_type="ticket_field",
            entity_id=field_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        field = ticket_field_from_record(record)
        state.ticket_fields[field.id] = field
        return field

    def list_response_macros(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        active_only: bool = False,
        channel: str | None = None,
        query: str | None = None,
    ) -> list[ResponseMacro]:
        records = db.scalars(
            select(ResponseMacroRecord).where(ResponseMacroRecord.market_id == market_id)
        ).all()
        query_tokens = _tokens(query) if query else set()
        macros = [
            response_macro_from_record(record)
            for record in records
            if (not active_only or record.active)
            and (channel is None or not record.channels or channel in record.channels)
            and (
                not query_tokens
                or query_tokens
                & _tokens(record.name, record.body, record.shortcut, " ".join(record.tags or []))
            )
        ]
        macros.sort(key=lambda macro: (not macro.active, -macro.usage_count, macro.name.lower()))
        state.response_macros = {
            **{
                key: value
                for key, value in state.response_macros.items()
                if value.market_id != market_id
            },
            **{macro.id: macro for macro in macros},
        }
        return macros

    def suggest_response_macros_for_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
        *,
        limit: int = 3,
    ) -> list[ResponseMacroSuggestion]:
        ticket = db.get(TicketRecord, ticket_id)
        if ticket is None or ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        records = db.scalars(
            select(ResponseMacroRecord).where(ResponseMacroRecord.market_id == market_id)
        ).all()
        suggestions = [
            suggestion
            for record in records
            if _macro_scope_matches(record, market_id, ticket.channel)
            for suggestion in [_response_macro_suggestion_for_ticket(record, ticket)]
            if suggestion is not None
        ]
        suggestions.sort(
            key=lambda suggestion: (
                -suggestion.score,
                -suggestion.macro.usage_count,
                suggestion.macro.name.lower(),
            )
        )
        for suggestion in suggestions[:limit]:
            state.response_macros[suggestion.macro.id] = suggestion.macro
        return suggestions[:limit]

    def create_response_macro(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateResponseMacroRequest,
        market_id: str,
        actor: str,
    ) -> ResponseMacro:
        payload = request.model_dump(mode="json")
        payload["market_id"] = market_id
        record = ResponseMacroRecord(id=_new_id("macro"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="response_macro.create",
            entity_type="response_macro",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        macro = response_macro_from_record(record)
        state.response_macros[macro.id] = macro
        return macro

    def update_response_macro(
        self,
        db: Session,
        state: InMemoryStore,
        macro_id: str,
        request: UpdateResponseMacroRequest,
        market_id: str,
        actor: str,
    ) -> ResponseMacro:
        record = db.get(ResponseMacroRecord, macro_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Response macro not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="response_macro.update",
            entity_type="response_macro",
            entity_id=macro_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        macro = response_macro_from_record(record)
        state.response_macros[macro.id] = macro
        return macro

    def record_response_macro_use(
        self,
        db: Session,
        state: InMemoryStore,
        macro_id: str,
        market_id: str,
        *,
        actor: str,
        ticket_id: str | None = None,
    ) -> ResponseMacro:
        record = db.get(ResponseMacroRecord, macro_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Response macro not found")
        if not record.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Response macro is inactive")
        now = utc_now()
        record.usage_count += 1
        record.last_used_at = now
        _audit(
            db,
            state,
            actor=actor,
            action="response_macro.use",
            entity_type="response_macro",
            entity_id=macro_id,
            market_id=market_id,
            details={"ticket_id": ticket_id, "usage_count": record.usage_count},
        )
        db.commit()
        db.refresh(record)
        macro = response_macro_from_record(record)
        state.response_macros[macro.id] = macro
        return macro

    def suggest_knowledge_for_ticket(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_id: str,
        market_id: str,
        *,
        limit: int = 3,
    ) -> list[KnowledgeSuggestion]:
        ticket = db.get(TicketRecord, ticket_id)
        if ticket is None or ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        records = db.scalars(select(KnowledgeArticleRecord)).all()
        suggestions = [
            suggestion
            for record in records
            if _article_scope_matches(record, market_id, ticket.channel)
            for suggestion in [_knowledge_suggestion_for_ticket(record, ticket)]
            if suggestion is not None
        ]
        suggestions.sort(
            key=lambda suggestion: (
                -suggestion.score,
                suggestion.article.status != KnowledgeArticleStatus.published,
                suggestion.article.title.lower(),
            )
        )
        for suggestion in suggestions[:limit]:
            state.knowledge[suggestion.article.id] = suggestion.article
        return suggestions[:limit]

    def suggest_public_knowledge(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        query: str,
        *,
        channel: str = "portal",
        limit: int = 5,
    ) -> list[KnowledgeSuggestion]:
        search = query.strip()
        records = db.scalars(select(KnowledgeArticleRecord)).all()
        suggestions = [
            suggestion
            for record in records
            if _article_scope_matches(record, market_id, channel)
            for suggestion in [_knowledge_suggestion_for_query(record, search, channel=channel)]
            if suggestion is not None
        ]
        suggestions.sort(
            key=lambda suggestion: (
                -suggestion.score,
                suggestion.article.title.lower(),
            )
        )
        selected = suggestions[:limit]
        for suggestion in selected:
            state.knowledge[suggestion.article.id] = suggestion.article
        return selected

    def create_knowledge_article(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateKnowledgeArticleRequest,
        market_id: str,
        actor: str,
    ) -> KnowledgeArticle:
        payload = request.model_dump(mode="json")
        payload["market_ids"] = payload["market_ids"] or [market_id]
        record = KnowledgeArticleRecord(id=_new_id("article"), **payload)
        _apply_knowledge_status(record, request.status, actor)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="knowledge.create",
            entity_type="knowledge_article",
            entity_id=record.id,
            market_id=market_id,
            details={"title": record.title, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        article = knowledge_article_from_record(record)
        state.knowledge[article.id] = article
        return article

    def update_knowledge_article(
        self,
        db: Session,
        state: InMemoryStore,
        article_id: str,
        request: UpdateKnowledgeArticleRequest,
        market_id: str,
        actor: str,
    ) -> KnowledgeArticle:
        record = db.get(KnowledgeArticleRecord, article_id)
        if record is None or market_id not in record.market_ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge article not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                if key == "status":
                    assert request.status is not None
                    _apply_knowledge_status(record, request.status, actor)
                else:
                    setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="knowledge.update",
            entity_type="knowledge_article",
            entity_id=article_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        article = knowledge_article_from_record(record)
        state.knowledge[article.id] = article
        return article

    def list_automation_rules(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[AutomationRule]:
        rules = [
            automation_rule_from_record(record)
            for record in db.scalars(
                select(AutomationRuleRecord).where(AutomationRuleRecord.market_id == market_id)
            ).all()
        ]
        state.rules = {
            **{key: value for key, value in state.rules.items() if value.market_id != market_id},
            **{rule.id: rule for rule in rules},
        }
        return rules

    def create_automation_rule(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateAutomationRuleRequest,
        market_id: str,
    ) -> AutomationRule:
        payload = request.model_dump(mode="json")
        payload["market_id"] = market_id
        record = AutomationRuleRecord(id=_new_id("rule"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor="api",
            action="automation_rule.create",
            entity_type="automation_rule",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name},
        )
        db.commit()
        db.refresh(record)
        rule = automation_rule_from_record(record)
        state.rules[rule.id] = rule
        return rule

    def update_automation_rule(
        self,
        db: Session,
        state: InMemoryStore,
        rule_id: str,
        request: UpdateAutomationRuleRequest,
        market_id: str,
    ) -> AutomationRule:
        record = db.get(AutomationRuleRecord, rule_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Automation rule not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            actor="api",
            action="automation_rule.update",
            entity_type="automation_rule",
            entity_id=rule_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        rule = automation_rule_from_record(record)
        state.rules[rule.id] = rule
        return rule


management_repository = ManagementRepository()
