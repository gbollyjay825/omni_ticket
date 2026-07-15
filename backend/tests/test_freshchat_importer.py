from __future__ import annotations

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CaseRecord,
    ChatConversationRecord,
    ChatMessageRecord,
    ChatParticipantRecord,
    CustomerIdentityRecord,
    CustomerRecord,
    ExternalIdMappingRecord,
    TicketRecord,
)
from app.db.session import get_engine
from app.importers.clients import FreshchatClient
from app.importers.service import freshworks_import_service

USER_ID = "user-2deb2a22"
CONVERSATION_IDS = ["conversation-one", "conversation-two"]


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == f"/v2/users/{USER_ID}":
        return httpx.Response(
            200,
            json={
                "id": USER_ID,
                "first_name": "Chat",
                "last_name": "Customer",
                "phone": "+234 802 111 2222",
                "reference_id": "booking-chat-customer",
                "created_time": "2026-07-01T08:00:00Z",
                "updated_time": "2026-07-01T08:30:00Z",
            },
        )
    if path == f"/v2/users/{USER_ID}/conversations":
        return httpx.Response(
            200,
            json={"conversations": [{"id": value} for value in CONVERSATION_IDS]},
        )
    if path.startswith("/v2/conversations/") and not path.endswith("/messages"):
        conversation_id = path.split("/")[3]
        return httpx.Response(
            200,
            json={
                "id": conversation_id,
                "status": "assigned",
                "channel_id": "channel-web",
                "assigned_group_id": "chat-care",
                "created_time": "2026-07-01T09:00:00Z",
                "updated_time": "2026-07-01T09:30:00Z",
            },
        )
    if path.startswith("/v2/conversations/") and path.endswith("/messages"):
        conversation_id = path.split("/")[3]
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "id": f"{conversation_id}-message-{page}",
                        "actor": {"actor_type": "user", "actor_id": USER_ID},
                        "message_type": "normal",
                        "message_parts": [
                            {"text": {"content": f"Please help with {conversation_id}"}}
                        ],
                        "created_time": "2026-07-01T09:05:00Z",
                        "updated_time": "2026-07-01T09:05:30Z",
                    }
                ],
                "pagination": {"current_page": page, "total_pages": 1},
            },
        )
    raise AssertionError(f"Unexpected Freshchat request: {request.url}")


def _client() -> FreshchatClient:
    return FreshchatClient(
        base_url="https://wakanow.freshchat.com",
        api_token="test-token",
        transport=httpx.MockTransport(_handler),
        sleeper=lambda _: None,
    )


def test_freshchat_known_user_sync_is_idempotent() -> None:
    with Session(get_engine()) as db, _client() as client:
        first = freshworks_import_service.run_freshchat_known_users(
            db,
            client=client,
            market_id="market-ng",
            user_ids=[USER_ID, USER_ID],
            from_time="2026-07-01T00:00:00Z",
            batch_size=1,
            started_by="test",
        )

    assert first["status"] == "completed"
    assert first["statistics"] == {
        "chat_conversations_created": 2,
        "messages_created": 2,
        "users_created": 1,
    }

    with Session(get_engine()) as db:
        customer = db.scalar(
            select(CustomerRecord).where(CustomerRecord.name == "Chat Customer")
        )
        assert customer is not None
        assert customer.email.endswith("@identity.omni.invalid")
        assert customer.preferred_channels == ["chat"]
        conversations = db.scalars(
            select(ChatConversationRecord).where(
                ChatConversationRecord.customer_id == customer.id
            )
        ).all()
        assert len(conversations) == 2
        assert {conversation.channel for conversation in conversations} == {"chat"}
        assert len({conversation.case_id for conversation in conversations}) == 1
        assert all(
            conversation.subject.startswith("Please help")
            for conversation in conversations
        )
        assert db.scalar(
            select(func.count(TicketRecord.id)).where(
                TicketRecord.customer_id == customer.id
            )
        ) == 0
        assert db.scalar(
            select(func.count(CaseRecord.id)).where(
                CaseRecord.customer_id == customer.id,
                CaseRecord.status == "open",
            )
        ) == 1
        assert db.scalar(
            select(func.count(CustomerIdentityRecord.id)).where(
                CustomerIdentityRecord.customer_id == customer.id
            )
        ) == 2
        assert db.scalar(
            select(func.count(ChatMessageRecord.id)).where(
                ChatMessageRecord.conversation_id.in_(
                    [conversation.id for conversation in conversations]
                )
            )
        ) == 2
        assert db.scalar(
            select(func.count(ChatParticipantRecord.id)).where(
                ChatParticipantRecord.conversation_id.in_(
                    [conversation.id for conversation in conversations]
                )
            )
        ) == 2
        assert db.scalar(
            select(func.count(ExternalIdMappingRecord.id)).where(
                ExternalIdMappingRecord.provider == "freshchat"
            )
        ) == 5

    with Session(get_engine()) as db, _client() as client:
        second = freshworks_import_service.run_freshchat_known_users(
            db,
            client=client,
            market_id="market-ng",
            user_ids=[USER_ID],
            from_time="2026-07-01T00:00:00Z",
            started_by="test",
        )

    assert second["statistics"] == {
        "chat_conversations_unchanged": 2,
        "messages_unchanged": 2,
        "users_unchanged": 1,
    }
