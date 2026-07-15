from __future__ import annotations

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CaseRecord,
    CustomerIdentityRecord,
    CustomerRecord,
    ExternalIdMappingRecord,
    ImportRunRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.session import get_engine
from app.importers.clients import FreshdeskClient
from app.importers.service import freshworks_import_service


CONTACT = {
    "id": 9001,
    "name": "Import Customer",
    "email": "import.customer@example.com",
    "mobile": "+234 801 234 5678",
    "created_at": "2026-06-01T08:00:00Z",
    "updated_at": "2026-07-01T08:00:00Z",
    "tags": ["vip"],
}


def _ticket(ticket_id: int, status: int, updated_at: str) -> dict:
    return {
        "id": ticket_id,
        "requester_id": CONTACT["id"],
        "subject": f"Imported request {ticket_id}",
        "description_text": f"Customer message for {ticket_id}",
        "status": status,
        "priority": 3,
        "source": 7,
        "group_id": 72,
        "tags": ["migration"],
        "custom_fields": {"booking_reference": f"BR-{ticket_id}"},
        "created_at": "2026-07-01T09:00:00Z",
        "updated_at": updated_at,
        "fr_due_by": "2026-07-01T10:00:00Z",
        "due_by": "2026-07-02T09:00:00Z",
    }


TICKETS = [
    _ticket(10001, 2, "2026-07-01T09:10:00Z"),
    _ticket(10002, 3, "2026-07-01T09:20:00Z"),
]


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    page = int(request.url.params.get("page", "1"))
    if page > 1:
        return httpx.Response(200, json=[])
    if path == "/api/v2/contacts":
        return httpx.Response(200, json=[CONTACT])
    if path == "/api/v2/tickets":
        return httpx.Response(200, json=TICKETS)
    if path.startswith("/api/v2/tickets/") and path.endswith("/conversations"):
        ticket_id = int(path.split("/")[4])
        return httpx.Response(
            200,
            json=[
                {
                    "id": ticket_id + 50000,
                    "user_id": CONTACT["id"],
                    "incoming": True,
                    "private": False,
                    "body_text": f"Follow-up for {ticket_id}",
                    "created_at": "2026-07-01T09:05:00Z",
                    "updated_at": "2026-07-01T09:06:00Z",
                    "attachments": [],
                }
            ],
        )
    raise AssertionError(f"Unexpected Freshdesk request: {request.url}")


def _client() -> FreshdeskClient:
    return FreshdeskClient(
        base_url="https://wakanowteam.freshdesk.com",
        api_key="test-key",
        transport=httpx.MockTransport(_handler),
        sleeper=lambda _: None,
    )


def test_freshdesk_import_is_idempotent_and_uses_one_active_case() -> None:
    with Session(get_engine()) as db, _client() as client:
        first = freshworks_import_service.run_freshdesk_incremental(
            db,
            client=client,
            market_id="market-ng",
            updated_since="2026-07-01T00:00:00Z",
            batch_size=1,
            started_by="test",
        )

    assert first["status"] == "completed"
    assert first["statistics"] == {
        "contacts_created": 1,
        "conversations_created": 2,
        "tickets_created": 2,
    }

    with Session(get_engine()) as db:
        customer = db.scalar(
            select(CustomerRecord).where(CustomerRecord.email == CONTACT["email"])
        )
        assert customer is not None
        tickets = db.scalars(
            select(TicketRecord).where(TicketRecord.customer_id == customer.id)
        ).all()
        assert {ticket.public_id for ticket in tickets} == {"FD-10001", "FD-10002"}
        assert {ticket.channel for ticket in tickets} == {"chat"}
        assert len({ticket.case_id for ticket in tickets}) == 1
        active_cases = db.scalars(
            select(CaseRecord).where(
                CaseRecord.customer_id == customer.id,
                CaseRecord.status == "open",
            )
        ).all()
        assert len(active_cases) == 1
        assert db.scalar(
            select(func.count(TimelineEventRecord.id)).where(
                TimelineEventRecord.ticket_id.in_([ticket.id for ticket in tickets])
            )
        ) == 4
        assert db.scalar(
            select(func.count(CustomerIdentityRecord.id)).where(
                CustomerIdentityRecord.customer_id == customer.id
            )
        ) == 3
        assert db.scalar(
            select(func.count(ExternalIdMappingRecord.id)).where(
                ExternalIdMappingRecord.provider == "freshdesk"
            )
        ) == 5

    with Session(get_engine()) as db, _client() as client:
        second = freshworks_import_service.run_freshdesk_incremental(
            db,
            client=client,
            market_id="market-ng",
            updated_since="2026-07-01T00:00:00Z",
            batch_size=10,
            started_by="test",
        )

    assert second["statistics"] == {
        "contacts_unchanged": 1,
        "conversations_unchanged": 2,
        "tickets_unchanged": 2,
    }
    with Session(get_engine()) as db:
        assert db.scalar(
            select(func.count(TicketRecord.id)).where(TicketRecord.public_id.like("FD-%"))
        ) == 2
        assert db.scalar(select(func.count(ImportRunRecord.id))) == 2


def test_freshdesk_dry_run_keeps_only_the_run_record() -> None:
    with Session(get_engine()) as db, _client() as client:
        result = freshworks_import_service.run_freshdesk_incremental(
            db,
            client=client,
            market_id="market-ng",
            updated_since="2026-07-01T00:00:00Z",
            dry_run=True,
            started_by="test",
        )

    assert result["status"] == "completed"
    assert result["dry_run"] is True
    assert result["statistics"]["tickets_created"] == 2
    with Session(get_engine()) as db:
        assert db.scalar(
            select(func.count(TicketRecord.id)).where(TicketRecord.public_id.like("FD-%"))
        ) == 0
        assert db.scalar(
            select(func.count(ExternalIdMappingRecord.id)).where(
                ExternalIdMappingRecord.provider == "freshdesk"
            )
        ) == 0
        assert db.scalar(select(func.count(ImportRunRecord.id))) == 1
