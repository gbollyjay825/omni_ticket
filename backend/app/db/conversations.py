from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.store import store
from app.db.audit import write_audit_event
from app.db.mappers import case_from_record, customer_from_record, ticket_from_record
from app.db.models import (
    CaseRecord,
    ChatConversationRecord,
    ChatMessageRecord,
    ChatParticipantRecord,
    ConversationAssignmentRecord,
    ConversationAttachmentRecord,
    ConversationTicketLinkRecord,
    ConversationTopicRecord,
    ConversationViewRecord,
    CustomerRecord,
    FeatureFlagRecord,
    MessageReceiptRecord,
    SupportGroupRecord,
    TicketRecord,
    UserRecord,
)
from app.db.outbound import outbound_repository
from app.models.conversations import (
    AssignConversationRequest,
    ChangeConversationStatusRequest,
    Conversation,
    ConversationAssignment,
    ConversationAttachment,
    ConversationContext,
    ConversationMessage,
    ConversationMessagePage,
    ConversationPage,
    ConversationParticipant,
    ConversationTopic,
    ConversationView,
    CreateConversationMessageRequest,
    CreateConversationRequest,
    CreateConversationTopicRequest,
    CreateConversationViewRequest,
    FeatureCapability,
    FeatureFlag,
    IntelliAssignConversationRequest,
    MessageReceipt,
    UpdateConversationRequest,
    UpdateConversationTopicRequest,
    UpdateConversationViewRequest,
    UpdateFeatureFlagRequest,
)
from app.models.domain import ChannelType, utc_now


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _conversation_or_404(
    db: Session, conversation_id: str, market_id: str
) -> ChatConversationRecord:
    record = db.get(ChatConversationRecord, conversation_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return record


def _check_version(record: ChatConversationRecord, expected_version: int) -> None:
    if record.version != expected_version:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail={
                "message": "Conversation has changed; refresh before retrying.",
                "expected_version": expected_version,
                "current_version": record.version,
            },
        )


def _topic_from_record(record: ConversationTopicRecord) -> ConversationTopic:
    return ConversationTopic.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "description": record.description,
            "active": record.active,
            "position": record.position,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _participant_from_record(record: ChatParticipantRecord) -> ConversationParticipant:
    return ConversationParticipant.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "conversation_id": record.conversation_id,
            "participant_type": record.participant_type,
            "user_id": record.user_id,
            "customer_id": record.customer_id,
            "display_name": record.display_name,
            "role": record.role,
            "joined_at": record.joined_at,
            "left_at": record.left_at,
        }
    )


def _assignment_from_record(record: ConversationAssignmentRecord) -> ConversationAssignment:
    return ConversationAssignment.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "conversation_id": record.conversation_id,
            "from_user_id": record.from_user_id,
            "to_user_id": record.to_user_id,
            "from_group_id": record.from_group_id,
            "to_group_id": record.to_group_id,
            "reason": record.reason,
            "routed_by": record.routed_by,
            "created_at": record.created_at,
        }
    )


def _message_from_record(record: ChatMessageRecord) -> ConversationMessage:
    return ConversationMessage.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "conversation_id": record.conversation_id,
            "sender_type": record.sender_type,
            "sender_id": record.sender_id,
            "sender_name": record.sender_name,
            "visibility": record.visibility,
            "body": record.body,
            "content": record.content,
            "delivery_state": record.delivery_state,
            "provider_message_id": record.provider_message_id,
            "reply_to_id": record.reply_to_id,
            "version": record.version,
            "sent_at": record.sent_at,
            "delivered_at": record.delivered_at,
            "read_at": record.read_at,
            "metadata": record.message_metadata,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _view_from_record(record: ConversationViewRecord) -> ConversationView:
    return ConversationView.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "owner_user_id": record.owner_user_id,
            "name": record.name,
            "filters": record.filters,
            "sort_by": record.sort_by,
            "sort_order": record.sort_order,
            "position": record.position,
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _attachment_from_record(record: ConversationAttachmentRecord) -> ConversationAttachment:
    return ConversationAttachment.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "conversation_id": record.conversation_id,
            "message_id": record.message_id,
            "filename": record.filename,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "storage_provider": record.storage_provider,
            "scan_status": record.scan_status,
            "scan_result": record.scan_result,
            "lifecycle_status": record.lifecycle_status,
            "uploaded_by": record.uploaded_by,
            "retained_until": record.retained_until,
            "deleted_at": record.deleted_at,
            "deleted_by": record.deleted_by,
            "deletion_reason": record.deletion_reason,
            "purged_at": record.purged_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _feature_flag_from_record(record: FeatureFlagRecord) -> FeatureFlag:
    return FeatureFlag.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "key": record.key,
            "enabled": record.enabled,
            "allowed_roles": record.allowed_roles,
            "allowed_user_ids": record.allowed_user_ids,
            "configuration": record.configuration,
            "updated_by": record.updated_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


class ConversationRepository:
    def _serialize(
        self,
        db: Session,
        record: ChatConversationRecord,
        *,
        viewer_user_id: str | None = None,
    ) -> Conversation:
        customer = db.get(CustomerRecord, record.customer_id)
        assignee = db.get(UserRecord, record.assignee_id) if record.assignee_id else None
        group = db.get(SupportGroupRecord, record.assigned_group_id) if record.assigned_group_id else None
        topic = db.get(ConversationTopicRecord, record.topic_id) if record.topic_id else None
        latest = db.scalar(
            select(ChatMessageRecord)
            .where(ChatMessageRecord.conversation_id == record.id)
            .order_by(ChatMessageRecord.sent_at.desc(), ChatMessageRecord.id.desc())
            .limit(1)
        )
        unread_count = 0
        if viewer_user_id:
            read_message_ids = select(MessageReceiptRecord.message_id).where(
                MessageReceiptRecord.conversation_id == record.id,
                MessageReceiptRecord.user_id == viewer_user_id,
                MessageReceiptRecord.receipt_type == "read",
            )
            unread_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(ChatMessageRecord)
                    .where(
                        ChatMessageRecord.conversation_id == record.id,
                        ChatMessageRecord.sender_type == "customer",
                        ChatMessageRecord.visibility == "public",
                        ChatMessageRecord.id.not_in(read_message_ids),
                    )
                )
                or 0
            )
        return Conversation.model_validate(
            {
                "id": record.id,
                "market_id": record.market_id,
                "public_id": record.public_id,
                "case_id": record.case_id,
                "customer_id": record.customer_id,
                "channel": record.channel,
                "subject": record.subject,
                "status": record.status,
                "priority": record.priority,
                "topic_id": record.topic_id,
                "assignee_id": record.assignee_id,
                "assigned_group_id": record.assigned_group_id,
                "source_account_id": record.source_account_id,
                "external_id": record.external_id,
                "version": record.version,
                "last_message_at": record.last_message_at,
                "resolved_at": record.resolved_at,
                "reopened_at": record.reopened_at,
                "metadata": record.conversation_metadata,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "customer_name": customer.name if customer else "",
                "customer_email": customer.email if customer else "",
                "assignee_name": assignee.name if assignee else "",
                "group_name": group.name if group else "",
                "topic_name": topic.name if topic else "",
                "latest_message": latest.body if latest else "",
                "unread_count": unread_count,
            }
        )

    def _filters_from_view(
        self, db: Session, *, market_id: str, user_id: str, view_id: str | None
    ) -> dict[str, Any]:
        if not view_id:
            return {}
        view = db.get(ConversationViewRecord, view_id)
        if (
            view is None
            or view.market_id != market_id
            or not view.active
            or view.owner_user_id not in {None, user_id}
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation view not found")
        return dict(view.filters or {})

    def list_conversations(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        cursor: str | None,
        limit: int,
        view_id: str | None = None,
        status_filter: str | None = None,
        channel: str | None = None,
        assignee_id: str | None = None,
        group_id: str | None = None,
        topic_id: str | None = None,
        query: str | None = None,
    ) -> ConversationPage:
        view_filters = self._filters_from_view(
            db, market_id=market_id, user_id=user_id, view_id=view_id
        )
        status_filter = status_filter or view_filters.get("status")
        channel = channel or view_filters.get("channel")
        assignee_id = assignee_id or view_filters.get("assignee_id")
        group_id = group_id or view_filters.get("group_id")
        topic_id = topic_id or view_filters.get("topic_id")

        statement = (
            select(ChatConversationRecord)
            .join(CustomerRecord, CustomerRecord.id == ChatConversationRecord.customer_id)
            .where(ChatConversationRecord.market_id == market_id)
        )
        if status_filter:
            statuses = [item.strip() for item in status_filter.split(",") if item.strip()]
            statement = statement.where(ChatConversationRecord.status.in_(statuses))
        if channel:
            statement = statement.where(ChatConversationRecord.channel == channel)
        if assignee_id:
            statement = statement.where(ChatConversationRecord.assignee_id == assignee_id)
        if group_id:
            statement = statement.where(ChatConversationRecord.assigned_group_id == group_id)
        if topic_id:
            statement = statement.where(ChatConversationRecord.topic_id == topic_id)
        if query:
            term = f"%{query.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(ChatConversationRecord.subject).like(term),
                    func.lower(ChatConversationRecord.public_id).like(term),
                    func.lower(CustomerRecord.name).like(term),
                    func.lower(CustomerRecord.email).like(term),
                )
            )
        if cursor:
            cursor_record = _conversation_or_404(db, cursor, market_id)
            statement = statement.where(
                or_(
                    ChatConversationRecord.last_message_at < cursor_record.last_message_at,
                    and_(
                        ChatConversationRecord.last_message_at == cursor_record.last_message_at,
                        ChatConversationRecord.id < cursor_record.id,
                    ),
                )
            )
        rows = list(
            db.scalars(
                statement.order_by(
                    ChatConversationRecord.last_message_at.desc(),
                    ChatConversationRecord.id.desc(),
                ).limit(limit + 1)
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        return ConversationPage(
            items=[self._serialize(db, row, viewer_user_id=user_id) for row in page_rows],
            next_cursor=page_rows[-1].id if has_more and page_rows else None,
            has_more=has_more,
        )

    def create_conversation(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        actor_name: str,
        payload: CreateConversationRequest,
    ) -> Conversation:
        customer = db.get(CustomerRecord, payload.customer_id)
        if customer is None or customer.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
        if payload.topic_id:
            topic = db.get(ConversationTopicRecord, payload.topic_id)
            if topic is None or topic.market_id != market_id or not topic.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation topic not found")
        if payload.assignee_id:
            assignee = db.get(UserRecord, payload.assignee_id)
            if assignee is None or market_id not in (assignee.market_ids or []) or not assignee.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assignee not found")
        if payload.assigned_group_id:
            group = db.get(SupportGroupRecord, payload.assigned_group_id)
            if group is None or group.market_id != market_id or not group.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Support group not found")
        if payload.external_id:
            existing = db.scalar(
                select(ChatConversationRecord).where(
                    ChatConversationRecord.market_id == market_id,
                    ChatConversationRecord.channel == payload.channel.value,
                    ChatConversationRecord.external_id == payload.external_id,
                )
            )
            if existing is not None:
                return self._serialize(db, existing, viewer_user_id=actor_id)

        db.execute(
            select(CustomerRecord.id)
            .where(CustomerRecord.id == customer.id, CustomerRecord.market_id == market_id)
            .with_for_update()
        )
        case = db.scalar(
            select(CaseRecord).where(
                CaseRecord.market_id == market_id,
                CaseRecord.customer_id == customer.id,
                CaseRecord.status == "open",
            )
        )
        if case is None:
            case = CaseRecord(
                id=_new_id("case"),
                market_id=market_id,
                public_id=f"CASE-{uuid4().hex[:8].upper()}",
                customer_id=customer.id,
                title=payload.subject.strip() or f"Conversation with {customer.name}",
                status="open",
                priority=payload.priority.value,
                summary=(payload.initial_message or "").strip(),
                opened_by=actor_name,
            )
            db.add(case)
            db.flush()

        now = utc_now()
        record = ChatConversationRecord(
            id=_new_id("conversation"),
            market_id=market_id,
            public_id=f"CHAT-{uuid4().hex[:8].upper()}",
            case_id=case.id,
            customer_id=customer.id,
            channel=payload.channel.value,
            subject=payload.subject.strip(),
            status="open",
            priority=payload.priority.value,
            topic_id=payload.topic_id,
            assignee_id=payload.assignee_id,
            assigned_group_id=payload.assigned_group_id,
            source_account_id=payload.source_account_id,
            external_id=payload.external_id,
            version=1,
            last_message_at=now,
            conversation_metadata=payload.metadata,
        )
        db.add(record)
        db.flush()
        db.add(
            ChatParticipantRecord(
                id=_new_id("participant"),
                market_id=market_id,
                conversation_id=record.id,
                participant_type="customer",
                customer_id=customer.id,
                display_name=customer.name,
                role="customer",
                joined_at=now,
            )
        )
        if payload.assignee_id:
            assignee = db.get(UserRecord, payload.assignee_id)
            db.add(
                ChatParticipantRecord(
                    id=_new_id("participant"),
                    market_id=market_id,
                    conversation_id=record.id,
                    participant_type="agent",
                    user_id=payload.assignee_id,
                    display_name=assignee.name if assignee else "",
                    role="assignee",
                    joined_at=now,
                )
            )
            db.add(
                ConversationAssignmentRecord(
                    id=_new_id("assignment"),
                    market_id=market_id,
                    conversation_id=record.id,
                    to_user_id=payload.assignee_id,
                    to_group_id=payload.assigned_group_id,
                    reason="Initial assignment",
                    routed_by=actor_id,
                    created_at=now,
                )
            )
        if payload.initial_message:
            sender_is_customer = payload.initial_sender == "customer"
            db.add(
                ChatMessageRecord(
                    id=_new_id("message"),
                    market_id=market_id,
                    conversation_id=record.id,
                    sender_type=payload.initial_sender,
                    sender_id=customer.id if sender_is_customer else actor_id,
                    sender_name=customer.name if sender_is_customer else actor_name,
                    visibility="public",
                    body=payload.initial_message.strip(),
                    content={},
                    delivery_state="received" if sender_is_customer else "pending_provider",
                    sent_at=now,
                    message_metadata={"source": "conversation.create"},
                )
            )
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.create",
            entity_type="conversation",
            entity_id=record.id,
            market_id=market_id,
            details={"customer_id": customer.id, "case_id": case.id, "channel": record.channel},
        )
        db.commit()
        db.refresh(record)
        return self._serialize(db, record, viewer_user_id=actor_id)

    def get_conversation(
        self, db: Session, *, market_id: str, user_id: str, conversation_id: str
    ) -> Conversation:
        return self._serialize(
            db,
            _conversation_or_404(db, conversation_id, market_id),
            viewer_user_id=user_id,
        )

    def update_conversation(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        payload: UpdateConversationRequest,
    ) -> Conversation:
        record = _conversation_or_404(db, conversation_id, market_id)
        _check_version(record, payload.expected_version)
        patch = payload.model_dump(exclude_unset=True, mode="json")
        patch.pop("expected_version", None)
        if "topic_id" in patch and patch["topic_id"]:
            topic = db.get(ConversationTopicRecord, patch["topic_id"])
            if topic is None or topic.market_id != market_id or not topic.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation topic not found")
        if "metadata" in patch:
            record.conversation_metadata = patch.pop("metadata")
        for key, value in patch.items():
            setattr(record, key, value.value if hasattr(value, "value") else value)
        record.version += 1
        record.updated_at = utc_now()
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.update",
            entity_type="conversation",
            entity_id=record.id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        return self._serialize(db, record, viewer_user_id=actor_id)

    def assign(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        payload: AssignConversationRequest,
    ) -> Conversation:
        record = _conversation_or_404(db, conversation_id, market_id)
        _check_version(record, payload.expected_version)
        if payload.assignee_id:
            assignee = db.get(UserRecord, payload.assignee_id)
            if assignee is None or market_id not in (assignee.market_ids or []) or not assignee.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assignee not found")
        if payload.group_id:
            group = db.get(SupportGroupRecord, payload.group_id)
            if group is None or group.market_id != market_id or not group.active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Support group not found")
        history = ConversationAssignmentRecord(
            id=_new_id("assignment"),
            market_id=market_id,
            conversation_id=record.id,
            from_user_id=record.assignee_id,
            to_user_id=payload.assignee_id,
            from_group_id=record.assigned_group_id,
            to_group_id=payload.group_id,
            reason=payload.reason.strip(),
            routed_by=actor_id,
            created_at=utc_now(),
        )
        db.add(history)
        record.assignee_id = payload.assignee_id
        record.assigned_group_id = payload.group_id
        record.version += 1
        record.updated_at = utc_now()
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.assign",
            entity_type="conversation",
            entity_id=record.id,
            market_id=market_id,
            details={
                "assignee_id": payload.assignee_id,
                "group_id": payload.group_id,
                "reason": payload.reason,
            },
        )
        db.commit()
        db.refresh(record)
        return self._serialize(db, record, viewer_user_id=actor_id)

    def intelli_assign(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        payload: IntelliAssignConversationRequest,
    ) -> Conversation:
        record = _conversation_or_404(db, conversation_id, market_id)
        _check_version(record, payload.expected_version)
        candidates = list(
            db.scalars(
                select(UserRecord).where(
                    UserRecord.active.is_(True),
                    UserRecord.role.in_(["agent", "supervisor", "admin"]),
                )
            ).all()
        )
        candidates = [user for user in candidates if market_id in (user.market_ids or [])]
        if not candidates:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="No active operators are available for this market.",
            )
        active_counts: dict[str, int] = {
            assignee_id: int(count)
            for assignee_id, count in db.execute(
                select(ChatConversationRecord.assignee_id, func.count())
                .where(
                    ChatConversationRecord.market_id == market_id,
                    ChatConversationRecord.status.in_(["open", "pending"]),
                    ChatConversationRecord.assignee_id.is_not(None),
                )
                .group_by(ChatConversationRecord.assignee_id)
            ).all()
            if assignee_id is not None
        }
        selected = min(
            candidates,
            key=lambda user: (int(active_counts.get(user.id, 0)), user.name.lower(), user.id),
        )
        return self.assign(
            db,
            market_id=market_id,
            actor_id=actor_id,
            conversation_id=conversation_id,
            payload=AssignConversationRequest(
                expected_version=payload.expected_version,
                assignee_id=selected.id,
                group_id=record.assigned_group_id,
                reason=(
                    f"{payload.reason.strip() or 'IntelliAssign'}; selected least-loaded operator "
                    f"with {int(active_counts.get(selected.id, 0))} active conversation(s)"
                ),
            ),
        )

    def change_status(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        next_status: str,
        payload: ChangeConversationStatusRequest,
    ) -> Conversation:
        record = _conversation_or_404(db, conversation_id, market_id)
        _check_version(record, payload.expected_version)
        previous = record.status
        now = utc_now()
        record.status = next_status
        record.resolved_at = now if next_status == "resolved" else None
        if next_status == "open" and previous in {"resolved", "closed"}:
            record.reopened_at = now
        record.version += 1
        record.updated_at = now
        write_audit_event(
            db,
            actor=actor_id,
            action=f"conversation.{next_status}",
            entity_type="conversation",
            entity_id=record.id,
            market_id=market_id,
            details={"previous_status": previous, "reason": payload.reason},
        )
        db.commit()
        db.refresh(record)
        return self._serialize(db, record, viewer_user_id=actor_id)

    def list_messages(
        self,
        db: Session,
        *,
        market_id: str,
        conversation_id: str,
        cursor: str | None,
        limit: int,
    ) -> ConversationMessagePage:
        _conversation_or_404(db, conversation_id, market_id)
        statement = select(ChatMessageRecord).where(
            ChatMessageRecord.market_id == market_id,
            ChatMessageRecord.conversation_id == conversation_id,
        )
        if cursor:
            cursor_record = db.get(ChatMessageRecord, cursor)
            if (
                cursor_record is None
                or cursor_record.market_id != market_id
                or cursor_record.conversation_id != conversation_id
            ):
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Message cursor is invalid")
            statement = statement.where(
                or_(
                    ChatMessageRecord.sent_at < cursor_record.sent_at,
                    and_(
                        ChatMessageRecord.sent_at == cursor_record.sent_at,
                        ChatMessageRecord.id < cursor_record.id,
                    ),
                )
            )
        rows = list(
            db.scalars(
                statement.order_by(
                    ChatMessageRecord.sent_at.desc(), ChatMessageRecord.id.desc()
                ).limit(limit + 1)
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = page_rows[-1].id if has_more and page_rows else None
        page_rows.reverse()
        return ConversationMessagePage(
            items=[_message_from_record(row) for row in page_rows],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def create_message(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        actor_name: str,
        conversation_id: str,
        payload: CreateConversationMessageRequest,
    ) -> ConversationMessage:
        record = _conversation_or_404(db, conversation_id, market_id)
        _check_version(record, payload.expected_version)
        if payload.idempotency_key:
            existing = db.scalar(
                select(ChatMessageRecord).where(
                    ChatMessageRecord.conversation_id == conversation_id,
                    ChatMessageRecord.idempotency_key == payload.idempotency_key,
                )
            )
            if existing is not None:
                return _message_from_record(existing)
        if payload.reply_to_id:
            parent = db.get(ChatMessageRecord, payload.reply_to_id)
            if parent is None or parent.conversation_id != conversation_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Reply message not found")
        now = utc_now()
        delivery_state = "internal" if payload.visibility == "private" else "pending_provider"
        message = ChatMessageRecord(
            id=_new_id("message"),
            market_id=market_id,
            conversation_id=conversation_id,
            sender_type="agent",
            sender_id=actor_id,
            sender_name=actor_name,
            visibility=payload.visibility,
            body=payload.body.strip(),
            content=payload.content,
            delivery_state=delivery_state,
            idempotency_key=payload.idempotency_key,
            reply_to_id=payload.reply_to_id,
            sent_at=now,
            message_metadata={"source": "conversation.reply"},
        )
        db.add(message)
        db.flush()
        attachment_ids = payload.content.get("attachment_ids", [])
        if attachment_ids:
            if (
                not isinstance(attachment_ids, list)
                or len(attachment_ids) > 20
                or any(not isinstance(item, str) or not item for item in attachment_ids)
            ):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="attachment_ids must contain up to 20 attachment IDs.",
                )
            normalized_attachment_ids = list(dict.fromkeys(attachment_ids))
            attachments = list(
                db.scalars(
                    select(ConversationAttachmentRecord).where(
                        ConversationAttachmentRecord.id.in_(normalized_attachment_ids),
                        ConversationAttachmentRecord.market_id == market_id,
                        ConversationAttachmentRecord.conversation_id == conversation_id,
                    )
                ).all()
            )
            if len(attachments) != len(normalized_attachment_ids):
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="One or more conversation attachments were not found.",
                )
            for attachment in attachments:
                if attachment.lifecycle_status != "active":
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        detail="Deleted attachments cannot be added to a message.",
                    )
                if attachment.scan_status != "clean":
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        detail="Attachments must pass security scanning before sending.",
                    )
                if attachment.message_id and attachment.message_id != message.id:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        detail="An attachment is already linked to another message.",
                    )
                attachment.message_id = message.id
        record.last_message_at = now
        record.version += 1
        record.updated_at = now
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.private_note" if payload.visibility == "private" else "conversation.reply",
            entity_type="conversation_message",
            entity_id=message.id,
            market_id=market_id,
            details={
                "conversation_id": conversation_id,
                "visibility": payload.visibility,
                "delivery_state": delivery_state,
            },
        )
        if payload.visibility == "public":
            try:
                provider = ChannelType(record.channel)
            except ValueError:
                message.delivery_state = "failed"
                message.message_metadata = {
                    **message.message_metadata,
                    "delivery_error": f"Unsupported outbound channel: {record.channel}.",
                }
            else:
                outbound_message = outbound_repository.queue_conversation_reply(
                    db,
                    store,
                    conversation=record,
                    chat_message=message,
                    provider=provider,
                    actor=actor_name,
                    body=message.body,
                    idempotency_key=payload.idempotency_key,
                )
                outbound_repository.process_message(
                    db,
                    store,
                    outbound_message.id,
                    market_id,
                    actor="outbound-queue",
                )
        db.commit()
        db.refresh(message)
        return _message_from_record(message)

    def list_attachments(
        self,
        db: Session,
        *,
        market_id: str,
        conversation_id: str,
        include_deleted: bool = False,
    ) -> list[ConversationAttachment]:
        _conversation_or_404(db, conversation_id, market_id)
        statement = select(ConversationAttachmentRecord).where(
            ConversationAttachmentRecord.market_id == market_id,
            ConversationAttachmentRecord.conversation_id == conversation_id,
        )
        if not include_deleted:
            statement = statement.where(
                ConversationAttachmentRecord.lifecycle_status == "active"
            )
        records = db.scalars(
            statement.order_by(ConversationAttachmentRecord.created_at.asc())
        ).all()
        return [_attachment_from_record(record) for record in records]

    def get_attachment_record(
        self,
        db: Session,
        *,
        market_id: str,
        conversation_id: str,
        attachment_id: str,
    ) -> ConversationAttachmentRecord:
        _conversation_or_404(db, conversation_id, market_id)
        record = db.get(ConversationAttachmentRecord, attachment_id)
        if (
            record is None
            or record.market_id != market_id
            or record.conversation_id != conversation_id
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        return record

    def create_attachment(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        attachment_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_provider: str,
        storage_key: str,
        scan_status: str,
        scan_result: str,
        message_id: str | None = None,
    ) -> ConversationAttachment:
        _conversation_or_404(db, conversation_id, market_id)
        if message_id:
            message = db.get(ChatMessageRecord, message_id)
            if message is None or message.conversation_id != conversation_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
        record = ConversationAttachmentRecord(
            id=attachment_id,
            market_id=market_id,
            conversation_id=conversation_id,
            message_id=message_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_provider=storage_provider,
            storage_key=storage_key,
            scan_status=scan_status,
            scan_result=scan_result,
            lifecycle_status="active",
            uploaded_by=actor_id,
            retained_until=utc_now() + timedelta(days=settings.attachment_retention_days),
        )
        db.add(record)
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.attachment.create",
            entity_type="conversation_attachment",
            entity_id=attachment_id,
            market_id=market_id,
            details={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
                "scan_status": scan_status,
                "storage_provider": storage_provider,
            },
        )
        db.commit()
        db.refresh(record)
        return _attachment_from_record(record)

    def delete_attachment(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        attachment_id: str,
        reason: str,
        purge_storage: bool,
        storage_delete: Callable[[str], bool],
    ) -> ConversationAttachment:
        record = self.get_attachment_record(
            db,
            market_id=market_id,
            conversation_id=conversation_id,
            attachment_id=attachment_id,
        )
        now = utc_now()
        record.deleted_at = record.deleted_at or now
        record.deleted_by = actor_id
        record.deletion_reason = reason
        record.lifecycle_status = "deleted"
        storage_deleted = False
        if purge_storage:
            try:
                storage_deleted = storage_delete(record.storage_key)
            except (OSError, ValueError):
                storage_deleted = False
            record.lifecycle_status = "purged"
            record.purged_at = now
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation.attachment.delete",
            entity_type="conversation_attachment",
            entity_id=attachment_id,
            market_id=market_id,
            details={
                "conversation_id": conversation_id,
                "reason": reason,
                "purge_storage": purge_storage,
                "storage_deleted": storage_deleted,
            },
        )
        db.commit()
        db.refresh(record)
        return _attachment_from_record(record)

    def record_receipt(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        conversation_id: str,
        message_id: str,
        receipt_type: str,
    ) -> MessageReceipt:
        _conversation_or_404(db, conversation_id, market_id)
        message = db.get(ChatMessageRecord, message_id)
        if message is None or message.conversation_id != conversation_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
        record = db.scalar(
            select(MessageReceiptRecord).where(
                MessageReceiptRecord.message_id == message_id,
                MessageReceiptRecord.user_id == user_id,
                MessageReceiptRecord.receipt_type == receipt_type,
            )
        )
        if record is None:
            record = MessageReceiptRecord(
                id=_new_id("receipt"),
                market_id=market_id,
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=user_id,
                receipt_type=receipt_type,
                recorded_at=utc_now(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        return MessageReceipt.model_validate(
            {
                "id": record.id,
                "market_id": record.market_id,
                "conversation_id": record.conversation_id,
                "message_id": record.message_id,
                "user_id": record.user_id,
                "receipt_type": record.receipt_type,
                "recorded_at": record.recorded_at,
            }
        )

    def context(
        self, db: Session, *, market_id: str, user_id: str, conversation_id: str
    ) -> ConversationContext:
        record = _conversation_or_404(db, conversation_id, market_id)
        customer = db.get(CustomerRecord, record.customer_id)
        case = db.get(CaseRecord, record.case_id)
        if customer is None or case is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Conversation customer or case is missing"
            )
        participants = db.scalars(
            select(ChatParticipantRecord)
            .where(ChatParticipantRecord.conversation_id == record.id)
            .order_by(ChatParticipantRecord.joined_at.asc())
        ).all()
        assignments = db.scalars(
            select(ConversationAssignmentRecord)
            .where(ConversationAssignmentRecord.conversation_id == record.id)
            .order_by(ConversationAssignmentRecord.created_at.desc())
        ).all()
        links = db.scalars(
            select(ConversationTicketLinkRecord).where(
                ConversationTicketLinkRecord.conversation_id == record.id
            )
        ).all()
        tickets = [db.get(TicketRecord, link.ticket_id) for link in links]
        attachments = db.scalars(
            select(ConversationAttachmentRecord)
            .where(
                ConversationAttachmentRecord.conversation_id == record.id,
                ConversationAttachmentRecord.lifecycle_status == "active",
            )
            .order_by(ConversationAttachmentRecord.created_at.desc())
        ).all()
        history = db.scalars(
            select(ChatConversationRecord)
            .where(
                ChatConversationRecord.market_id == market_id,
                ChatConversationRecord.customer_id == customer.id,
                ChatConversationRecord.id != record.id,
            )
            .order_by(ChatConversationRecord.last_message_at.desc())
            .limit(20)
        ).all()
        case_tickets = list(
            db.scalars(
                select(TicketRecord).where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.case_id == case.id,
                )
            ).all()
        )
        allowed_actions = ["assign", "private_note", "link_ticket", "view_customer"]
        if record.status in {"open", "pending"}:
            allowed_actions.extend(["reply", "resolve"])
        else:
            allowed_actions.append("reopen")
        return ConversationContext(
            conversation=self._serialize(db, record, viewer_user_id=user_id),
            customer=customer_from_record(customer),
            case=case_from_record(case, case_tickets),
            participants=[_participant_from_record(item) for item in participants],
            assignments=[_assignment_from_record(item) for item in assignments],
            linked_tickets=[ticket_from_record(item) for item in tickets if item is not None],
            attachments=[_attachment_from_record(item) for item in attachments],
            customer_history=[
                self._serialize(db, item, viewer_user_id=user_id) for item in history
            ],
            allowed_actions=allowed_actions,
        )

    def link_ticket(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        conversation_id: str,
        ticket_id: str,
        relationship: str,
    ) -> ConversationContext:
        record = _conversation_or_404(db, conversation_id, market_id)
        ticket = db.get(TicketRecord, ticket_id)
        if ticket is None or ticket.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        if ticket.customer_id != record.customer_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Conversation and ticket must belong to the same customer",
            )
        link = db.scalar(
            select(ConversationTicketLinkRecord).where(
                ConversationTicketLinkRecord.conversation_id == conversation_id,
                ConversationTicketLinkRecord.ticket_id == ticket_id,
            )
        )
        if link is None:
            link = ConversationTicketLinkRecord(
                id=_new_id("conversation_ticket"),
                market_id=market_id,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                relationship=relationship,
                created_by=actor_id,
                created_at=utc_now(),
            )
            db.add(link)
            write_audit_event(
                db,
                actor=actor_id,
                action="conversation.link_ticket",
                entity_type="conversation",
                entity_id=conversation_id,
                market_id=market_id,
                details={"ticket_id": ticket_id, "relationship": relationship},
            )
            db.commit()
        return self.context(
            db, market_id=market_id, user_id=actor_id, conversation_id=conversation_id
        )

    def list_topics(self, db: Session, *, market_id: str) -> list[ConversationTopic]:
        records = db.scalars(
            select(ConversationTopicRecord)
            .where(ConversationTopicRecord.market_id == market_id)
            .order_by(ConversationTopicRecord.position.asc(), ConversationTopicRecord.name.asc())
        ).all()
        return [_topic_from_record(record) for record in records]

    def create_topic(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        payload: CreateConversationTopicRequest,
    ) -> ConversationTopic:
        record = ConversationTopicRecord(
            id=_new_id("topic"),
            market_id=market_id,
            name=payload.name.strip(),
            description=payload.description.strip(),
            active=payload.active,
            position=payload.position,
        )
        db.add(record)
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation_topic.create",
            entity_type="conversation_topic",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name},
        )
        db.commit()
        db.refresh(record)
        return _topic_from_record(record)

    def update_topic(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        topic_id: str,
        payload: UpdateConversationTopicRequest,
    ) -> ConversationTopic:
        record = db.get(ConversationTopicRecord, topic_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation topic not found")
        patch = payload.model_dump(exclude_unset=True)
        for key, value in patch.items():
            setattr(record, key, value.strip() if isinstance(value, str) else value)
        write_audit_event(
            db,
            actor=actor_id,
            action="conversation_topic.update",
            entity_type="conversation_topic",
            entity_id=record.id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        return _topic_from_record(record)

    def list_views(
        self, db: Session, *, market_id: str, user_id: str
    ) -> list[ConversationView]:
        records = db.scalars(
            select(ConversationViewRecord)
            .where(
                ConversationViewRecord.market_id == market_id,
                ConversationViewRecord.active.is_(True),
                or_(
                    ConversationViewRecord.owner_user_id.is_(None),
                    ConversationViewRecord.owner_user_id == user_id,
                ),
            )
            .order_by(ConversationViewRecord.position.asc(), ConversationViewRecord.name.asc())
        ).all()
        return [_view_from_record(record) for record in records]

    def create_view(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        is_admin: bool,
        payload: CreateConversationViewRequest,
    ) -> ConversationView:
        if payload.shared and not is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
        record = ConversationViewRecord(
            id=_new_id("view"),
            market_id=market_id,
            owner_user_id=None if payload.shared else user_id,
            name=payload.name.strip(),
            filters=payload.filters,
            sort_by=payload.sort_by,
            sort_order=payload.sort_order,
            position=payload.position,
            active=True,
        )
        db.add(record)
        write_audit_event(
            db,
            actor=user_id,
            action="conversation_view.create",
            entity_type="conversation_view",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "shared": payload.shared},
        )
        db.commit()
        db.refresh(record)
        return _view_from_record(record)

    def update_view(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        is_admin: bool,
        view_id: str,
        payload: UpdateConversationViewRequest,
    ) -> ConversationView:
        record = db.get(ConversationViewRecord, view_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation view not found")
        if record.owner_user_id not in {user_id} and not is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
        patch = payload.model_dump(exclude_unset=True)
        for key, value in patch.items():
            setattr(record, key, value.strip() if isinstance(value, str) else value)
        write_audit_event(
            db,
            actor=user_id,
            action="conversation_view.update",
            entity_type="conversation_view",
            entity_id=record.id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        return _view_from_record(record)

    def list_feature_capabilities(
        self, db: Session, *, market_id: str, user_id: str, role: str
    ) -> list[FeatureCapability]:
        known_keys = ("omnichat_parity", "ticket_workspace_parity")
        records = {
            record.key: record
            for record in db.scalars(
                select(FeatureFlagRecord).where(
                    FeatureFlagRecord.market_id == market_id,
                    FeatureFlagRecord.key.in_(known_keys),
                )
            ).all()
        }
        capabilities: list[FeatureCapability] = []
        for key in known_keys:
            record = records.get(key)
            if record is None:
                capabilities.append(
                    FeatureCapability(
                        key=key,
                        available=False,
                        enabled=False,
                        reason="Not enabled for this market",
                    )
                )
                continue
            allowed = (
                record.enabled
                and (not record.allowed_roles or role in record.allowed_roles)
                and (not record.allowed_user_ids or user_id in record.allowed_user_ids)
            )
            capabilities.append(
                FeatureCapability(
                    key=key,
                    available=allowed,
                    enabled=record.enabled,
                    reason="Enabled" if allowed else "Not enabled for this user or role",
                    configuration=record.configuration,
                )
            )
        return capabilities

    def upsert_feature_flag(
        self,
        db: Session,
        *,
        market_id: str,
        actor_id: str,
        key: str,
        payload: UpdateFeatureFlagRequest,
    ) -> FeatureFlag:
        record = db.scalar(
            select(FeatureFlagRecord).where(
                FeatureFlagRecord.market_id == market_id,
                FeatureFlagRecord.key == key,
            )
        )
        if record is None:
            record = FeatureFlagRecord(
                id=_new_id("flag"),
                market_id=market_id,
                key=key,
                enabled=payload.enabled,
                allowed_roles=payload.allowed_roles,
                allowed_user_ids=payload.allowed_user_ids,
                configuration=payload.configuration,
                updated_by=actor_id,
            )
            db.add(record)
        else:
            record.enabled = payload.enabled
            record.allowed_roles = payload.allowed_roles
            record.allowed_user_ids = payload.allowed_user_ids
            record.configuration = payload.configuration
            record.updated_by = actor_id
        write_audit_event(
            db,
            actor=actor_id,
            action="feature_flag.update",
            entity_type="feature_flag",
            entity_id=record.id,
            market_id=market_id,
            details={"key": key, "enabled": payload.enabled},
        )
        db.commit()
        db.refresh(record)
        return _feature_flag_from_record(record)


conversation_repository = ConversationRepository()
