from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from hashlib import sha256
import smtplib
from typing import Protocol, cast
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.audit import write_audit_event
from app.db.email_settings import (
    RuntimeEmailProviderSettings,
    email_provider_settings_repository,
)
from app.db.models import MarketRecord, ReportDeliveryRecord, SavedReportRecord
from app.models.domain import utc_now
from app.services.reporting import ReportType, reporting_service


REPORT_TYPES = {"tickets", "chat", "csat", "team", "ai"}
REPORT_CADENCES = {"daily", "weekly", "monthly"}
REPORT_DUE_STATUSES = {"queued", "retrying", "blocked"}


@dataclass(frozen=True)
class ReportTransportResult:
    succeeded: bool
    external_id: str | None = None
    error: str | None = None


class ReportEmailTransport(Protocol):
    def send(
        self,
        *,
        delivery: ReportDeliveryRecord,
        report_name: str,
        from_address: str,
        email_settings: RuntimeEmailProviderSettings,
    ) -> ReportTransportResult: ...


class SmtpReportEmailTransport:
    def send(
        self,
        *,
        delivery: ReportDeliveryRecord,
        report_name: str,
        from_address: str,
        email_settings: RuntimeEmailProviderSettings,
    ) -> ReportTransportResult:
        if not email_settings.outbound_live:
            return ReportTransportResult(
                succeeded=False,
                error="SMTP email delivery is not configured.",
            )
        if not from_address:
            return ReportTransportResult(
                succeeded=False,
                error="Scheduled report delivery requires a sender address.",
            )
        message = EmailMessage()
        message["From"] = from_address
        message["To"] = ", ".join(delivery.recipients)
        message["Subject"] = f"Omni scheduled report: {report_name}"
        message["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])
        message["X-Omni-Market-ID"] = delivery.market_id
        message["X-Omni-Report-ID"] = delivery.saved_report_id
        message["X-Omni-Report-Period"] = delivery.period_key
        message.set_content(
            f"Your scheduled {delivery.cadence} report is attached.\n\n"
            f"Report: {report_name}\n"
            f"Period: {delivery.period_key}\n"
            f"Rows: {delivery.row_count}\n"
        )
        message.add_attachment(
            delivery.content.encode("utf-8"),
            maintype="text",
            subtype="csv",
            filename=delivery.filename,
        )
        smtp_class = smtplib.SMTP_SSL if email_settings.outbound_use_ssl else smtplib.SMTP
        try:
            with smtp_class(
                email_settings.outbound_host,
                email_settings.outbound_port,
                timeout=settings.email_smtp_timeout_seconds,
            ) as smtp:
                if email_settings.outbound_use_starttls and not email_settings.outbound_use_ssl:
                    smtp.starttls()
                if email_settings.outbound_username:
                    smtp.login(
                        email_settings.outbound_username,
                        email_settings.outbound_password or "",
                    )
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            return ReportTransportResult(succeeded=False, error=str(exc))
        return ReportTransportResult(
            succeeded=True,
            external_id=str(message["Message-ID"]),
        )


@dataclass
class ReportScheduleSummary:
    queued_ids: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


@dataclass
class ReportDispatchSummary:
    processed_ids: list[str] = field(default_factory=list)
    sent_ids: list[str] = field(default_factory=list)
    retrying_ids: list[str] = field(default_factory=list)
    blocked_ids: list[str] = field(default_factory=list)
    dead_lettered_ids: list[str] = field(default_factory=list)


def report_period_key(cadence: str, now: datetime) -> str:
    if cadence == "daily":
        return now.strftime("%Y-%m-%d")
    if cadence == "weekly":
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if cadence == "monthly":
        return now.strftime("%Y-%m")
    raise ValueError(f"Unsupported report cadence: {cadence}")


class ReportDeliveryService:
    def schedule_due(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        now: datetime | None = None,
    ) -> ReportScheduleSummary:
        current_time = now or utc_now()
        market = db.get(MarketRecord, market_id)
        if market is None:
            return ReportScheduleSummary(skipped={market_id: "Market not found"})
        reports = db.scalars(
            select(SavedReportRecord).where(
                SavedReportRecord.market_id == market_id,
                SavedReportRecord.active.is_(True),
                SavedReportRecord.cadence.in_(REPORT_CADENCES),
            )
        ).all()
        summary = ReportScheduleSummary()
        for report in reports:
            if report.report_type not in REPORT_TYPES:
                summary.skipped[report.id] = f"Unsupported report type: {report.report_type}"
                continue
            if not report.recipients:
                summary.skipped[report.id] = "No recipients configured"
                continue
            period_key = report_period_key(report.cadence, current_time)
            existing = db.scalar(
                select(ReportDeliveryRecord.id).where(
                    ReportDeliveryRecord.saved_report_id == report.id,
                    ReportDeliveryRecord.period_key == period_key,
                )
            )
            if existing is not None:
                summary.skipped[report.id] = "Delivery already exists for this period"
                continue
            report_type = cast(ReportType, report.report_type)
            document = reporting_service.build_document(
                db,
                market_id=market_id,
                market_code=market.code,
                report_type=report_type,
                limit=settings.audit_export_max_rows,
            )
            delivery = ReportDeliveryRecord(
                id=f"report_delivery_{uuid4().hex}",
                market_id=market_id,
                saved_report_id=report.id,
                period_key=period_key,
                report_type=report.report_type,
                cadence=report.cadence,
                status="queued",
                recipients=list(report.recipients),
                filename=document.filename,
                content_type=document.content_type,
                content=document.content,
                content_checksum=sha256(document.content.encode("utf-8")).hexdigest(),
                row_count=document.row_count,
                attempts=0,
                max_attempts=3,
            )
            db.add(delivery)
            db.flush()
            write_audit_event(
                db,
                actor=actor,
                action="report.delivery.queue",
                entity_type="report_delivery",
                entity_id=delivery.id,
                market_id=market_id,
                details={
                    "saved_report_id": report.id,
                    "report_type": report.report_type,
                    "cadence": report.cadence,
                    "period_key": period_key,
                    "row_count": document.row_count,
                    "recipient_count": len(report.recipients),
                    "content_checksum": delivery.content_checksum,
                },
            )
            summary.queued_ids.append(delivery.id)
        return summary

    def dispatch_due(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        limit: int = 20,
        now: datetime | None = None,
        transport: ReportEmailTransport | None = None,
    ) -> ReportDispatchSummary:
        current_time = now or utc_now()
        delivery_ids = list(
            db.scalars(
                select(ReportDeliveryRecord.id)
                .where(
                    ReportDeliveryRecord.market_id == market_id,
                    ReportDeliveryRecord.status.in_(REPORT_DUE_STATUSES),
                    or_(
                        ReportDeliveryRecord.next_attempt_at.is_(None),
                        ReportDeliveryRecord.next_attempt_at <= current_time,
                    ),
                )
                .order_by(ReportDeliveryRecord.created_at.asc())
                .limit(max(1, limit))
            )
        )
        summary = ReportDispatchSummary(processed_ids=delivery_ids)
        email_settings = email_provider_settings_repository.runtime_settings(
            db,
            market_id=market_id,
        )
        market = db.get(MarketRecord, market_id)
        from_address = email_settings.outbound_from_email or (market.support_email if market else "")
        sender = transport or SmtpReportEmailTransport()

        for delivery_id in delivery_ids:
            delivery = db.get(ReportDeliveryRecord, delivery_id)
            if delivery is None:
                continue
            report = db.get(SavedReportRecord, delivery.saved_report_id)
            if report is None:
                delivery.status = "dead_lettered"
                delivery.last_error = "Saved report no longer exists."
                delivery.next_attempt_at = None
                summary.dead_lettered_ids.append(delivery.id)
                continue
            if not email_settings.outbound_live:
                changed = delivery.status != "blocked" or delivery.last_error != (
                    "SMTP email delivery is not configured."
                )
                delivery.status = "blocked"
                delivery.last_error = "SMTP email delivery is not configured."
                delivery.next_attempt_at = current_time + timedelta(minutes=5)
                summary.blocked_ids.append(delivery.id)
                if changed:
                    write_audit_event(
                        db,
                        actor=actor,
                        action="report.delivery.blocked",
                        entity_type="report_delivery",
                        entity_id=delivery.id,
                        market_id=market_id,
                        details={"reason": delivery.last_error},
                    )
                continue

            delivery.attempts += 1
            result = sender.send(
                delivery=delivery,
                report_name=report.name,
                from_address=from_address,
                email_settings=email_settings,
            )
            if result.succeeded:
                delivery.status = "sent"
                delivery.sent_at = current_time
                delivery.next_attempt_at = None
                delivery.last_error = None
                delivery.external_id = result.external_id
                summary.sent_ids.append(delivery.id)
                action = "report.delivery.sent"
            elif delivery.attempts >= delivery.max_attempts:
                delivery.status = "dead_lettered"
                delivery.next_attempt_at = None
                delivery.last_error = result.error or "Report delivery failed."
                summary.dead_lettered_ids.append(delivery.id)
                action = "report.delivery.dead_lettered"
            else:
                delivery.status = "retrying"
                delivery.last_error = result.error or "Report delivery failed."
                delivery.next_attempt_at = current_time + timedelta(
                    minutes=min(2 ** delivery.attempts, 60)
                )
                summary.retrying_ids.append(delivery.id)
                action = "report.delivery.retry"
            write_audit_event(
                db,
                actor=actor,
                action=action,
                entity_type="report_delivery",
                entity_id=delivery.id,
                market_id=market_id,
                details={
                    "saved_report_id": delivery.saved_report_id,
                    "attempts": delivery.attempts,
                    "status": delivery.status,
                    "error": delivery.last_error,
                    "external_id": delivery.external_id,
                },
            )
        db.flush()
        return summary


report_delivery_service = ReportDeliveryService()
