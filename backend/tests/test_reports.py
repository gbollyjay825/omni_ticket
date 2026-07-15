import csv
from io import StringIO
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentRecord, AuditEventRecord, TicketRecord
from app.db.session import get_engine


def _csv_rows(response_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response_text)))


def test_report_catalog_requires_supervisor_access(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    response = client.get(
        "/api/v1/reports/catalog",
        headers=login_as("amara.ng@omniticket.example.com"),
    )
    assert response.status_code == 200
    assert {item["report_type"] for item in response.json()} == {
        "tickets",
        "chat",
        "csat",
        "team",
        "ai",
    }

    forbidden = client.get(
        "/api/v1/reports/catalog",
        headers=login_as("kofi.gh@omniticket.example.com", "market-gh"),
    )
    assert forbidden.status_code == 403


def test_ticket_and_chat_exports_use_market_scoped_records(client: TestClient) -> None:
    with Session(get_engine()) as db:
        ng_public_ids = set(
            db.scalars(
                select(TicketRecord.public_id).where(TicketRecord.market_id == "market-ng")
            ).all()
        )
        gh_public_ids = set(
            db.scalars(
                select(TicketRecord.public_id).where(TicketRecord.market_id == "market-gh")
            ).all()
        )

    response = client.get("/api/v1/reports/export", params={"report_type": "tickets"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "omni-tickets-ng.csv" in response.headers["content-disposition"]
    ticket_rows = _csv_rows(response.text)
    exported_public_ids = {row["Public ID"] for row in ticket_rows}
    assert exported_public_ids == ng_public_ids
    assert exported_public_ids.isdisjoint(gh_public_ids)

    chat_response = client.get("/api/v1/reports/export", params={"report_type": "chat"})
    assert chat_response.status_code == 200
    chat_rows = _csv_rows(chat_response.text)
    assert {row["Channel"] for row in chat_rows} <= {
        "chat",
        "whatsapp",
        "facebook",
        "instagram",
    }


def test_csat_team_and_ai_exports_have_real_market_data_and_audit(
    client: TestClient,
) -> None:
    with Session(get_engine()) as db:
        ng_agent_emails = {
            record.email
            for record in db.scalars(select(AgentRecord)).all()
            if "market-ng" in (record.market_ids or [])
        }
        db.add_all(
            [
                AuditEventRecord(
                    id="audit-test-ai-ng",
                    market_id="market-ng",
                    actor="test",
                    action="ai.classify",
                    entity_type="ai_decision",
                    entity_id="ticket-ng",
                    details={"label": "billing"},
                ),
                AuditEventRecord(
                    id="audit-test-ai-gh",
                    market_id="market-gh",
                    actor="test",
                    action="ai.classify",
                    entity_type="ai_decision",
                    entity_id="ticket-gh",
                    details={"label": "flight"},
                ),
            ]
        )
        db.commit()

    csat_response = client.get("/api/v1/reports/export", params={"report_type": "csat"})
    assert csat_response.status_code == 200
    assert list(csv.reader(StringIO(csat_response.text)))[0] == [
        "Feedback ID",
        "Ticket ID",
        "Customer ID",
        "Rating",
        "Comment",
        "Source",
        "Submitted by",
        "Created at",
    ]

    team_response = client.get("/api/v1/reports/export", params={"report_type": "team"})
    assert team_response.status_code == 200
    assert {row["Email"] for row in _csv_rows(team_response.text)} == ng_agent_emails

    ai_response = client.get("/api/v1/reports/export", params={"report_type": "ai"})
    assert ai_response.status_code == 200
    ai_rows = _csv_rows(ai_response.text)
    assert "ticket-ng" in {row["Entity ID"] for row in ai_rows}
    assert "ticket-gh" not in {row["Entity ID"] for row in ai_rows}

    with Session(get_engine()) as db:
        report_exports = db.scalars(
            select(AuditEventRecord).where(AuditEventRecord.action == "report.export")
        ).all()
    assert {record.entity_id for record in report_exports} >= {"csat", "team", "ai"}


def test_report_export_rejects_unknown_type(client: TestClient) -> None:
    response = client.get("/api/v1/reports/export", params={"report_type": "unknown"})
    assert response.status_code == 422
