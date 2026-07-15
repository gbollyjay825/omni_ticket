from __future__ import annotations

import gzip
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChatConversationRecord,
    ChatMessageRecord,
    ExternalIdMappingRecord,
    ImportCursorRecord,
    TicketRecord,
)
from app.db.session import get_engine
from app.importers.service import freshworks_import_service, iter_export_records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(f"{json.dumps(record)}\n" for record in records), encoding="utf-8")


def test_export_reader_supports_gzipped_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "users.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write('{"id":"one"}\n')
        handle.write('{"id":"two"}\n')
    assert list(iter_export_records(path)) == [{"id": "one"}, {"id": "two"}]


def test_freshchat_export_imports_streams_in_dependency_order(tmp_path: Path) -> None:
    users = tmp_path / "users.jsonl"
    conversations = tmp_path / "conversations.json"
    messages = tmp_path / "messages.csv"
    _write_jsonl(
        users,
        [
            {
                "id": "export-user",
                "email": "export.user@example.com",
                "first_name": "Export",
                "last_name": "User",
                "created_time": "2026-01-01T00:00:00Z",
                "updated_time": "2026-07-01T00:00:00Z",
            }
        ],
    )
    conversations.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": "export-conversation",
                        "user_id": "export-user",
                        "status": "assigned",
                        "created_time": "2026-07-01T01:00:00Z",
                        "updated_time": "2026-07-01T01:30:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    messages.write_text(
        "id,conversation_id,actor_type,actor_id,message_parts,created_time\n"
        'export-message,export-conversation,user,export-user,"[{""text"": '
        '{""content"": ""Exported chat body""}}]",2026-07-01T01:05:00Z\n',
        encoding="utf-8",
    )

    with Session(get_engine()) as db:
        result = freshworks_import_service.run_freshchat_export(
            db,
            market_id="market-ng",
            users_path=users,
            conversations_path=conversations,
            messages_path=messages,
            batch_size=1,
            started_by="test",
        )

    assert result["status"] == "completed"
    assert result["next_cursor"]["files"] == {
        "conversations": 1,
        "messages": 1,
        "users": 1,
    }
    with Session(get_engine()) as db:
        conversation = db.scalar(
            select(ChatConversationRecord).where(ChatConversationRecord.public_id.like("FC-%"))
        )
        assert conversation is not None
        assert conversation.subject == "Exported chat body"
        message = db.scalar(
            select(ChatMessageRecord).where(
                ChatMessageRecord.conversation_id == conversation.id
            )
        )
        assert message is not None
        assert message.body == "Exported chat body"
        assert db.scalar(
            select(func.count(TicketRecord.id)).where(TicketRecord.public_id.like("FC-%"))
        ) == 0
        assert db.scalar(
            select(func.count(ExternalIdMappingRecord.id)).where(
                ExternalIdMappingRecord.provider == "freshchat"
            )
        ) == 3
        cursors = db.scalars(
            select(ImportCursorRecord).where(ImportCursorRecord.provider == "freshchat")
        ).all()
        assert {cursor.resource for cursor in cursors} == {"users", "conversations", "messages"}
        assert all(cursor.cursor.get("complete") is True for cursor in cursors)


def test_freshdesk_export_requires_contacts_before_tickets(tmp_path: Path) -> None:
    contacts = tmp_path / "contacts.json"
    tickets = tmp_path / "tickets.jsonl"
    conversations = tmp_path / "conversations.json"
    contacts.write_text(
        json.dumps(
            [
                {
                    "id": 20,
                    "name": "Desk Export",
                    "email": "desk.export@example.com",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-07-01T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        tickets,
        [
            {
                "id": 30,
                "requester_id": 20,
                "subject": "Exported ticket",
                "description_text": "Exported ticket body",
                "status": 5,
                "priority": 2,
                "source": 1,
                "created_at": "2026-07-01T01:00:00Z",
                "updated_at": "2026-07-01T02:00:00Z",
            }
        ],
    )
    conversations.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": 40,
                        "ticket_id": 30,
                        "incoming": False,
                        "private": False,
                        "body_text": "Agent reply",
                        "created_at": "2026-07-01T01:30:00Z",
                        "updated_at": "2026-07-01T01:30:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with Session(get_engine()) as db:
        result = freshworks_import_service.run_freshdesk_export(
            db,
            market_id="market-ng",
            contacts_path=contacts,
            tickets_path=tickets,
            conversations_path=conversations,
            batch_size=1,
            started_by="test",
        )

    assert result["status"] == "completed"
    assert result["statistics"] == {
        "contacts_created": 1,
        "conversations_created": 1,
        "tickets_created": 1,
    }
    with Session(get_engine()) as db:
        ticket = db.scalar(select(TicketRecord).where(TicketRecord.public_id == "FD-30"))
        assert ticket is not None
        assert ticket.status == "closed"
