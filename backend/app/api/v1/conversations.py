from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_admin, require_operator, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.core.attachment_tokens import (
    create_attachment_download_token,
    parse_attachment_download_token,
)
from app.core.config import settings as app_settings
from app.db.audit import write_audit_event
from app.db.conversations import conversation_repository
from app.db.session import get_db
from app.models.conversations import (
    AssignConversationRequest,
    ChangeConversationStatusRequest,
    Conversation,
    ConversationAttachment,
    ConversationContext,
    ConversationMessage,
    ConversationMessagePage,
    ConversationPage,
    ConversationTopic,
    ConversationView,
    CreateConversationMessageRequest,
    CreateConversationRequest,
    CreateConversationTopicRequest,
    CreateConversationViewRequest,
    CreateMessageReceiptRequest,
    FeatureCapability,
    FeatureFlag,
    IntelliAssignConversationRequest,
    LinkConversationTicketRequest,
    MessageReceipt,
    UpdateConversationRequest,
    UpdateConversationTopicRequest,
    UpdateConversationViewRequest,
    UpdateFeatureFlagRequest,
)
from app.models.domain import (
    AttachmentDownloadLink,
    DeleteAttachmentRequest,
    ChannelType,
    UserRole,
)
from app.services import attachments as attachment_services

router = APIRouter(tags=["conversations"])


def _set_version_etag(response: Response, version: int) -> None:
    response.headers["ETag"] = f'"{version}"'


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    cursor: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    view_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    channel: ChannelType | None = None,
    assignee_id: str | None = None,
    group_id: str | None = None,
    topic_id: str | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=180),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationPage:
    return conversation_repository.list_conversations(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        cursor=cursor,
        limit=limit,
        view_id=view_id,
        status_filter=status_filter,
        channel=channel.value if channel else None,
        assignee_id=assignee_id,
        group_id=group_id,
        topic_id=topic_id,
        query=q,
    )


@router.post(
    "/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED
)
def create_conversation(
    payload: CreateConversationRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.create_conversation(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        actor_name=context.user.name,
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.get("/conversations/{conversation_id}", response_model=Conversation)
def read_conversation(
    conversation_id: str,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    result = conversation_repository.get_conversation(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        conversation_id=conversation_id,
    )
    _set_version_etag(response, result.version)
    return result


@router.patch("/conversations/{conversation_id}", response_model=Conversation)
def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.update_conversation(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.post("/conversations/{conversation_id}/assignment", response_model=Conversation)
def assign_conversation(
    conversation_id: str,
    payload: AssignConversationRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.assign(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.post("/conversations/{conversation_id}/intelli-assign", response_model=Conversation)
def intelli_assign_conversation(
    conversation_id: str,
    payload: IntelliAssignConversationRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.intelli_assign(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.post("/conversations/{conversation_id}/resolve", response_model=Conversation)
def resolve_conversation(
    conversation_id: str,
    payload: ChangeConversationStatusRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.change_status(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        next_status="resolved",
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.post("/conversations/{conversation_id}/reopen", response_model=Conversation)
def reopen_conversation(
    conversation_id: str,
    payload: ChangeConversationStatusRequest,
    response: Response,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Conversation:
    require_operator(context)
    result = conversation_repository.change_status(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        next_status="open",
        payload=payload,
    )
    _set_version_etag(response, result.version)
    return result


@router.get(
    "/conversations/{conversation_id}/messages", response_model=ConversationMessagePage
)
def list_conversation_messages(
    conversation_id: str,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationMessagePage:
    return conversation_repository.list_messages(
        db,
        market_id=context.market_id,
        conversation_id=conversation_id,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessage,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_message(
    conversation_id: str,
    payload: CreateConversationMessageRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationMessage:
    require_operator(context)
    return conversation_repository.create_message(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        actor_name=context.user.name,
        conversation_id=conversation_id,
        payload=payload,
    )


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[ConversationAttachment],
)
def list_conversation_attachments(
    conversation_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ConversationAttachment]:
    return conversation_repository.list_attachments(
        db,
        market_id=context.market_id,
        conversation_id=conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/attachments/binary",
    response_model=ConversationAttachment,
    status_code=status.HTTP_201_CREATED,
)
async def upload_conversation_attachment(
    conversation_id: str,
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    message_id: str | None = Query(default=None, max_length=64),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationAttachment:
    require_operator(context)
    content = await request.body()
    if not content:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Attachment content is required",
        )
    if len(content) > app_settings.attachment_max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Attachment is too large",
        )
    attachment_id = f"conversation_attachment_{uuid4().hex}"
    content_type = request.headers.get("content-type") or "application/octet-stream"
    scan_status, scan_result = attachment_services.scan_attachment_binary(
        filename=filename,
        content_type=content_type,
        data=content,
    )
    if scan_status.value == "clean":
        storage_key = attachment_services.attachment_storage.write(
            market_id=context.market_id,
            ticket_id=conversation_id,
            attachment_id=attachment_id,
            filename=filename,
            data=content,
            content_type=content_type,
        )
    else:
        storage_key = attachment_services.blocked_storage_key(
            market_id=context.market_id,
            ticket_id=conversation_id,
            attachment_id=attachment_id,
            filename=filename,
        )
    return conversation_repository.create_attachment(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        message_id=message_id,
        attachment_id=attachment_id,
        filename=attachment_services.attachment_storage.safe_filename(filename),
        content_type=content_type,
        size_bytes=len(content),
        storage_provider=attachment_services.attachment_storage.scheme.rstrip(":"),
        storage_key=storage_key,
        scan_status=scan_status.value,
        scan_result=scan_result,
    )


def _conversation_attachment_download_response(record) -> Response:
    if record.lifecycle_status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Attachment is no longer active")
    if record.scan_status != "clean":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Attachment is not cleared for download",
        )
    try:
        content = attachment_services.attachment_storage.read(record.storage_key)
    except (OSError, ValueError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment content not found") from exc
    safe_name = attachment_services.attachment_storage.safe_filename(record.filename)
    return Response(
        content=content,
        media_type=record.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}/download")
def download_conversation_attachment(
    conversation_id: str,
    attachment_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    record = conversation_repository.get_attachment_record(
        db,
        market_id=context.market_id,
        conversation_id=conversation_id,
        attachment_id=attachment_id,
    )
    return _conversation_attachment_download_response(record)


@router.post(
    "/conversations/{conversation_id}/attachments/{attachment_id}/download-link",
    response_model=AttachmentDownloadLink,
)
def create_conversation_attachment_download_link(
    conversation_id: str,
    attachment_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AttachmentDownloadLink:
    record = conversation_repository.get_attachment_record(
        db,
        market_id=context.market_id,
        conversation_id=conversation_id,
        attachment_id=attachment_id,
    )
    if record.lifecycle_status != "active" or record.scan_status != "clean":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Attachment is not available for download",
        )
    token, expires_at = create_attachment_download_token(
        market_id=context.market_id,
        ticket_id=conversation_id,
        attachment_id=attachment_id,
        created_by=context.user.id,
    )
    write_audit_event(
        db,
        actor=context.user.id,
        action="conversation.attachment.download_link.create",
        entity_type="conversation_attachment",
        entity_id=attachment_id,
        market_id=context.market_id,
        details={"conversation_id": conversation_id, "expires_at": expires_at.isoformat()},
        commit=True,
    )
    return AttachmentDownloadLink(
        url=(
            f"/api/v1/conversations/{conversation_id}/attachments/"
            f"{attachment_id}/download/signed?token={token}"
        ),
        expires_at=expires_at,
    )


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}/download/signed")
def download_conversation_attachment_with_signed_link(
    conversation_id: str,
    attachment_id: str,
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    payload = parse_attachment_download_token(token)
    if (
        payload is None
        or payload.ticket_id != conversation_id
        or payload.attachment_id != attachment_id
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid attachment download link")
    record = conversation_repository.get_attachment_record(
        db,
        market_id=payload.market_id,
        conversation_id=conversation_id,
        attachment_id=attachment_id,
    )
    write_audit_event(
        db,
        actor="signed-download",
        action="conversation.attachment.download",
        entity_type="conversation_attachment",
        entity_id=attachment_id,
        market_id=payload.market_id,
        details={
            "conversation_id": conversation_id,
            "token_id": payload.token_id,
            "created_by": payload.created_by,
        },
        commit=True,
    )
    return _conversation_attachment_download_response(record)


@router.delete(
    "/conversations/{conversation_id}/attachments/{attachment_id}",
    response_model=ConversationAttachment,
)
def delete_conversation_attachment(
    conversation_id: str,
    attachment_id: str,
    payload: DeleteAttachmentRequest = Body(default_factory=DeleteAttachmentRequest),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationAttachment:
    require_supervisor(context)
    return conversation_repository.delete_attachment(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        attachment_id=attachment_id,
        reason=payload.reason,
        purge_storage=payload.purge_storage,
        storage_delete=attachment_services.attachment_storage.delete,
    )


@router.post(
    "/conversations/{conversation_id}/receipts",
    response_model=MessageReceipt,
    status_code=status.HTTP_201_CREATED,
)
def create_message_receipt(
    conversation_id: str,
    payload: CreateMessageReceiptRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> MessageReceipt:
    return conversation_repository.record_receipt(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        conversation_id=conversation_id,
        message_id=payload.message_id,
        receipt_type=payload.receipt_type,
    )


@router.get("/conversations/{conversation_id}/context", response_model=ConversationContext)
def read_conversation_context(
    conversation_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationContext:
    return conversation_repository.context(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        conversation_id=conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/linked-tickets", response_model=ConversationContext
)
def link_conversation_ticket(
    conversation_id: str,
    payload: LinkConversationTicketRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationContext:
    require_operator(context)
    return conversation_repository.link_ticket(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        conversation_id=conversation_id,
        ticket_id=payload.ticket_id,
        relationship=payload.relationship,
    )


@router.get("/conversation-topics", response_model=list[ConversationTopic])
def list_conversation_topics(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ConversationTopic]:
    return conversation_repository.list_topics(db, market_id=context.market_id)


@router.post(
    "/conversation-topics",
    response_model=ConversationTopic,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_topic(
    payload: CreateConversationTopicRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationTopic:
    require_admin(context)
    return conversation_repository.create_topic(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        payload=payload,
    )


@router.patch("/conversation-topics/{topic_id}", response_model=ConversationTopic)
def update_conversation_topic(
    topic_id: str,
    payload: UpdateConversationTopicRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationTopic:
    require_admin(context)
    return conversation_repository.update_topic(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        topic_id=topic_id,
        payload=payload,
    )


@router.get("/conversation-views", response_model=list[ConversationView])
def list_conversation_views(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ConversationView]:
    return conversation_repository.list_views(
        db, market_id=context.market_id, user_id=context.user.id
    )


@router.post(
    "/conversation-views",
    response_model=ConversationView,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_view(
    payload: CreateConversationViewRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationView:
    return conversation_repository.create_view(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        is_admin=context.user.role == UserRole.admin,
        payload=payload,
    )


@router.patch("/conversation-views/{view_id}", response_model=ConversationView)
def update_conversation_view(
    view_id: str,
    payload: UpdateConversationViewRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ConversationView:
    return conversation_repository.update_view(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        is_admin=context.user.role == UserRole.admin,
        view_id=view_id,
        payload=payload,
    )


@router.get("/features", response_model=list[FeatureCapability])
def list_feature_capabilities(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[FeatureCapability]:
    return conversation_repository.list_feature_capabilities(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        role=context.user.role.value,
    )


@router.put("/features/{key}", response_model=FeatureFlag)
def update_feature_flag(
    key: str,
    payload: UpdateFeatureFlagRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> FeatureFlag:
    require_admin(context)
    return conversation_repository.upsert_feature_flag(
        db,
        market_id=context.market_id,
        actor_id=context.user.id,
        key=key,
        payload=payload,
    )
