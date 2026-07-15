from datetime import datetime, timezone
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.email_settings import email_provider_settings_repository
from app.db.models import AuditEventRecord, ReportDeliveryRecord
from app.db.session import get_engine
from app.services.report_delivery import (
    ReportTransportResult,
    report_delivery_service,
)


FIXED_NOW = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)


class SuccessfulTransport:
    def __init__(self) -> None:
        self.delivery_ids: list[str] = []

    def send(self, **kwargs) -> ReportTransportResult:
        delivery = kwargs["delivery"]
        self.delivery_ids.append(delivery.id)
        return ReportTransportResult(
            succeeded=True,
            external_id=f"smtp:{delivery.id}",
        )


class FailingTransport:
    def send(self, **kwargs) -> ReportTransportResult:
        return ReportTransportResult(succeeded=False, error="SMTP timeout")


def _enable_smtp(db: Session) -> None:
    record = email_provider_settings_repository.get_or_create(db, market_id="market-ng")
    record.outbound_enabled = True
    record.outbound_host = "smtp.example.com"
    record.outbound_port = 587
    record.outbound_from_email = "reports@wakanow.com"
    record.outbound_use_starttls = True
    record.outbound_use_ssl = False
    db.flush()


def test_scheduled_reports_are_idempotent_and_block_without_smtp() -> None:
    with Session(get_engine()) as db:
        first = report_delivery_service.schedule_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
        )
        second = report_delivery_service.schedule_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
        )
        blocked = report_delivery_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
        )
        db.commit()

        records = db.scalars(select(ReportDeliveryRecord)).all()
        assert len(first.queued_ids) == 3
        assert not second.queued_ids
        assert len(second.skipped) == 3
        assert len(records) == 3
        assert {record.status for record in records} == {"blocked"}
        assert {record.attempts for record in records} == {0}
        assert all(record.content.startswith("Ticket ID") or record.content for record in records)
        assert all(len(record.content_checksum) == 64 for record in records)
        assert set(blocked.blocked_ids) == {record.id for record in records}


def test_scheduled_report_delivery_sends_stable_csv_snapshot() -> None:
    sender = SuccessfulTransport()
    with Session(get_engine()) as db:
        _enable_smtp(db)
        scheduled = report_delivery_service.schedule_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
        )
        dispatched = report_delivery_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
            transport=sender,
        )
        db.commit()

        records = db.scalars(select(ReportDeliveryRecord)).all()
        assert set(dispatched.sent_ids) == set(scheduled.queued_ids)
        assert set(sender.delivery_ids) == set(scheduled.queued_ids)
        assert {record.status for record in records} == {"sent"}
        assert {record.attempts for record in records} == {1}
        assert all(
            record.sent_at is not None
            and record.sent_at.replace(tzinfo=timezone.utc) == FIXED_NOW
            for record in records
        )
        assert all(record.external_id == f"smtp:{record.id}" for record in records)

        sent_audits = db.scalars(
            select(AuditEventRecord).where(AuditEventRecord.action == "report.delivery.sent")
        ).all()
        assert {event.entity_id for event in sent_audits} == set(scheduled.queued_ids)


def test_failed_scheduled_report_delivery_retries_then_dead_letters() -> None:
    with Session(get_engine()) as db:
        _enable_smtp(db)
        scheduled = report_delivery_service.schedule_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
        )
        first = report_delivery_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test",
            now=FIXED_NOW,
            transport=FailingTransport(),
        )
        second_time = datetime(2026, 7, 14, 8, 3, tzinfo=timezone.utc)
        second = report_delivery_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test",
            now=second_time,
            transport=FailingTransport(),
        )
        third_time = datetime(2026, 7, 14, 8, 8, tzinfo=timezone.utc)
        third = report_delivery_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test",
            now=third_time,
            transport=FailingTransport(),
        )
        db.commit()

        assert set(first.retrying_ids) == set(scheduled.queued_ids)
        assert set(second.retrying_ids) == set(scheduled.queued_ids)
        assert set(third.dead_lettered_ids) == set(scheduled.queued_ids)
        records = db.scalars(select(ReportDeliveryRecord)).all()
        assert {record.status for record in records} == {"dead_lettered"}
        assert {record.attempts for record in records} == {3}
        assert {record.last_error for record in records} == {"SMTP timeout"}


def test_report_delivery_api_is_market_scoped_and_supervisor_only(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    processed = client.post("/api/v1/reports/deliveries/process-due")
    assert processed.status_code == 200
    assert len(processed.json()["blocked_ids"]) == 3

    listing = client.get("/api/v1/reports/deliveries")
    assert listing.status_code == 200
    assert len(listing.json()) == 3
    assert {item["status"] for item in listing.json()} == {"blocked"}
    assert all("content" not in item for item in listing.json())

    gh_listing = client.get(
        "/api/v1/reports/deliveries",
        headers=login_as("kofi.gh@omniticket.example.com", "market-gh"),
    )
    assert gh_listing.status_code == 403
