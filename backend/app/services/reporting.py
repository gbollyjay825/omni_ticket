from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import AgentRecord, AuditEventRecord, CsatFeedbackRecord, TicketRecord


ReportType = Literal["tickets", "chat", "csat", "team", "ai"]


@dataclass(frozen=True)
class ReportDocument:
    report_type: ReportType
    filename: str
    content_type: str
    content: str
    row_count: int


def _render_csv(headers: list[str], rows: list[list[Any]]) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


class ReportingService:
    def build_document(
        self,
        db: Session,
        *,
        market_id: str,
        market_code: str,
        report_type: ReportType,
        limit: int,
    ) -> ReportDocument:
        headers: list[str]
        rows: list[list[Any]]

        if report_type in {"tickets", "chat"}:
            query = select(TicketRecord).where(TicketRecord.market_id == market_id)
            if report_type == "chat":
                query = query.where(
                    TicketRecord.channel.in_(["chat", "whatsapp", "facebook", "instagram"])
                )
            ticket_records = db.scalars(
                query.order_by(TicketRecord.created_at.desc()).limit(limit)
            ).all()
            headers = [
                "Ticket ID",
                "Public ID",
                "Subject",
                "Customer ID",
                "Channel",
                "Status",
                "Priority",
                "Sentiment",
                "Assignee ID",
                "Team",
                "Case ID",
                "SLA resolution met",
                "Created at",
                "Updated at",
                "Resolved at",
                "Closed at",
            ]
            rows = [
                [
                    record.id,
                    record.public_id,
                    record.subject,
                    record.customer_id,
                    record.channel,
                    record.status,
                    record.priority,
                    record.sentiment,
                    record.assignee_id or "",
                    record.team,
                    record.case_id or "",
                    "" if record.sla_resolution_met is None else record.sla_resolution_met,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.resolved_at.isoformat() if record.resolved_at else "",
                    record.closed_at.isoformat() if record.closed_at else "",
                ]
                for record in ticket_records
            ]
        elif report_type == "csat":
            csat_records = db.scalars(
                select(CsatFeedbackRecord)
                .where(CsatFeedbackRecord.market_id == market_id)
                .order_by(CsatFeedbackRecord.created_at.desc())
                .limit(limit)
            ).all()
            headers = [
                "Feedback ID",
                "Ticket ID",
                "Customer ID",
                "Rating",
                "Comment",
                "Source",
                "Submitted by",
                "Created at",
            ]
            rows = [
                [
                    record.id,
                    record.ticket_id,
                    record.customer_id,
                    record.rating,
                    record.comment or "",
                    record.source,
                    record.submitted_by or "",
                    record.created_at.isoformat(),
                ]
                for record in csat_records
            ]
        elif report_type == "team":
            agent_records = [
                record
                for record in db.scalars(select(AgentRecord).order_by(AgentRecord.name)).all()
                if market_id in (record.market_ids or [])
            ][:limit]
            headers = [
                "Agent ID",
                "Name",
                "Email",
                "Role",
                "Status",
                "Occupancy",
                "Capacity",
                "Skills",
                "Languages",
            ]
            rows = [
                [
                    record.id,
                    record.name,
                    record.email,
                    record.role,
                    record.status,
                    record.occupancy,
                    record.capacity,
                    json.dumps(record.skills or [], separators=(",", ":")),
                    json.dumps(record.languages or [], separators=(",", ":")),
                ]
                for record in agent_records
            ]
        elif report_type == "ai":
            audit_records = db.scalars(
                select(AuditEventRecord)
                .where(
                    AuditEventRecord.market_id == market_id,
                    or_(
                        AuditEventRecord.action.like("ai.%"),
                        AuditEventRecord.entity_type.in_(["ai", "ai_decision"]),
                    ),
                )
                .order_by(AuditEventRecord.created_at.desc())
                .limit(limit)
            ).all()
            headers = [
                "Event ID",
                "Actor",
                "Action",
                "Entity type",
                "Entity ID",
                "Details",
                "Created at",
            ]
            rows = [
                [
                    record.id,
                    record.actor,
                    record.action,
                    record.entity_type,
                    record.entity_id,
                    json.dumps(record.details or {}, separators=(",", ":"), sort_keys=True),
                    record.created_at.isoformat(),
                ]
                for record in audit_records
            ]
        else:
            raise RuntimeError(f"Unsupported report type: {report_type}")

        return ReportDocument(
            report_type=report_type,
            filename=f"omni-{report_type}-{market_code.lower()}.csv",
            content_type="text/csv",
            content=_render_csv(headers, rows),
            row_count=len(rows),
        )


reporting_service = ReportingService()
