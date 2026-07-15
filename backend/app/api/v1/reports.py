from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.core.config import settings
from app.db.audit import write_audit_event
from app.db.models import ReportDeliveryRecord
from app.db.session import get_db
from app.services.report_delivery import report_delivery_service
from app.services.reporting import ReportType, reporting_service

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCatalogItem(BaseModel):
    id: str
    name: str
    description: str
    report_type: ReportType


class ReportDeliveryResponse(BaseModel):
    id: str
    saved_report_id: str
    period_key: str
    report_type: str
    cadence: str
    status: str
    recipients: list[str]
    filename: str
    content_checksum: str
    row_count: int
    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None
    sent_at: datetime | None
    last_error: str | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime


class ReportDeliveryRunResponse(BaseModel):
    queued_ids: list[str]
    skipped: dict[str, str]
    processed_ids: list[str]
    sent_ids: list[str]
    retrying_ids: list[str]
    blocked_ids: list[str]
    dead_lettered_ids: list[str]


REPORT_CATALOG = [
    ReportCatalogItem(
        id="ticket-operations",
        name="Ticket operations",
        description="Market tickets with status, priority, ownership, SLA outcome, and lifecycle timestamps.",
        report_type="tickets",
    ),
    ReportCatalogItem(
        id="chat-operations",
        name="Chat operations",
        description="Chat and messaging work across web chat, WhatsApp, Facebook, and Instagram.",
        report_type="chat",
    ),
    ReportCatalogItem(
        id="customer-satisfaction",
        name="Customer satisfaction",
        description="Customer ratings, comments, source, ticket, and submission time.",
        report_type="csat",
    ),
    ReportCatalogItem(
        id="team-capacity",
        name="Team capacity",
        description="Market agent availability, occupancy, capacity, role, skills, and languages.",
        report_type="team",
    ),
    ReportCatalogItem(
        id="ai-activity",
        name="AI activity",
        description="Audited AI decisions and automation activity recorded for the active market.",
        report_type="ai",
    ),
]


@router.get("/catalog", response_model=list[ReportCatalogItem])
def report_catalog(context: RequestContext = Depends(require_context)) -> list[ReportCatalogItem]:
    require_supervisor(context)
    return REPORT_CATALOG


def _delivery_response(record: ReportDeliveryRecord) -> ReportDeliveryResponse:
    return ReportDeliveryResponse(
        id=record.id,
        saved_report_id=record.saved_report_id,
        period_key=record.period_key,
        report_type=record.report_type,
        cadence=record.cadence,
        status=record.status,
        recipients=list(record.recipients),
        filename=record.filename,
        content_checksum=record.content_checksum,
        row_count=record.row_count,
        attempts=record.attempts,
        max_attempts=record.max_attempts,
        next_attempt_at=record.next_attempt_at,
        sent_at=record.sent_at,
        last_error=record.last_error,
        external_id=record.external_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/deliveries", response_model=list[ReportDeliveryResponse])
def list_report_deliveries(
    limit: int = Query(default=100, ge=1, le=500),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ReportDeliveryResponse]:
    require_supervisor(context)
    records = db.scalars(
        select(ReportDeliveryRecord)
        .where(ReportDeliveryRecord.market_id == context.market_id)
        .order_by(ReportDeliveryRecord.created_at.desc())
        .limit(limit)
    ).all()
    return [_delivery_response(record) for record in records]


@router.post("/deliveries/process-due", response_model=ReportDeliveryRunResponse)
def process_due_report_deliveries(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ReportDeliveryRunResponse:
    require_supervisor(context)
    scheduled = report_delivery_service.schedule_due(
        db,
        market_id=context.market_id,
        actor=context.user.id,
    )
    dispatched = report_delivery_service.dispatch_due(
        db,
        market_id=context.market_id,
        actor=context.user.id,
    )
    db.commit()
    return ReportDeliveryRunResponse(
        queued_ids=scheduled.queued_ids,
        skipped=scheduled.skipped,
        processed_ids=dispatched.processed_ids,
        sent_ids=dispatched.sent_ids,
        retrying_ids=dispatched.retrying_ids,
        blocked_ids=dispatched.blocked_ids,
        dead_lettered_ids=dispatched.dead_lettered_ids,
    )


@router.get("/export")
def export_report(
    report_type: ReportType = Query(),
    limit: int = Query(default=5000, ge=1, le=50000),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_supervisor(context)
    bounded_limit = min(limit, settings.audit_export_max_rows)
    document = reporting_service.build_document(
        db,
        market_id=context.market_id,
        market_code=context.market.code,
        report_type=report_type,
        limit=bounded_limit,
    )

    write_audit_event(
        db,
        actor=context.user.id,
        action="report.export",
        entity_type="report",
        entity_id=report_type,
        market_id=context.market_id,
        details={
            "report_type": report_type,
            "row_count": document.row_count,
            "limit": bounded_limit,
        },
        commit=True,
    )
    return Response(
        content=document.content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.filename}"'},
    )
