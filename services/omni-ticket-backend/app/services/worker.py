from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record, ticket_from_record
from app.db.models import (
    AuditEventRecord,
    MarketRecord,
    OutboundMessageRecord,
    TicketRecord,
)
from app.db.operations import OPEN_STATUSES, operations_repository
from app.db.outbound import outbound_repository
from app.models.domain import OutboundMessageStatus, utc_now
from app.services.sla import sla_service


WORKER_ACTOR = "omni-worker"
OUTBOUND_DUE_STATUSES = {
    OutboundMessageStatus.queued.value,
    OutboundMessageStatus.failed.value,
    OutboundMessageStatus.retrying.value,
}


@dataclass
class WorkerJobResult:
    name: str
    market_id: str | None = None
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_lettered: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerRunSummary:
    started_at: str
    finished_at: str
    jobs: list[WorkerJobResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit_worker(
    db: Session,
    state: InMemoryStore,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict[str, Any],
    actor: str = WORKER_ACTOR,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class BackgroundWorkerService:
    def market_ids(self, db: Session, requested_market_ids: list[str] | None = None) -> list[str]:
        if requested_market_ids:
            return requested_market_ids
        return list(
            db.scalars(
                select(MarketRecord.id)
                .where(MarketRecord.active.is_(True))
                .order_by(MarketRecord.code.asc())
            )
        )

    def process_due_outbound(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int = 50,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        now = utc_now()
        stale_sending_before = now - timedelta(minutes=10)
        message_ids = list(
            db.scalars(
                select(OutboundMessageRecord.id)
                .where(
                    OutboundMessageRecord.market_id == market_id,
                    or_(
                        and_(
                            OutboundMessageRecord.status.in_(OUTBOUND_DUE_STATUSES),
                            or_(
                                OutboundMessageRecord.next_attempt_at.is_(None),
                                OutboundMessageRecord.next_attempt_at <= now,
                            ),
                        ),
                        and_(
                            OutboundMessageRecord.status == OutboundMessageStatus.sending.value,
                            OutboundMessageRecord.updated_at <= stale_sending_before,
                        ),
                    ),
                )
                .order_by(OutboundMessageRecord.created_at.asc())
                .limit(limit)
            )
        )
        result = WorkerJobResult(
            name="outbound_retry",
            market_id=market_id,
            processed=len(message_ids),
            details={"message_ids": message_ids},
        )
        for message_id in message_ids:
            try:
                message = outbound_repository.process_message(
                    db,
                    state,
                    message_id,
                    market_id,
                    actor=actor,
                )
                if message.status == OutboundMessageStatus.sent:
                    result.succeeded += 1
                elif message.status == OutboundMessageStatus.dead_lettered:
                    result.dead_lettered += 1
                else:
                    result.failed += 1
                db.commit()
            except Exception as exc:  # pragma: no cover - defensive isolation for production workers
                db.rollback()
                result.failed += 1
                _audit_worker(
                    db,
                    state,
                    action="worker.outbound_error",
                    entity_type="outbound_message",
                    entity_id=message_id,
                    market_id=market_id,
                    details={"error": str(exc)},
                    actor=actor,
                )
                db.commit()

        if result.processed:
            _audit_worker(
                db,
                state,
                action="worker.outbound_batch",
                entity_type="market",
                entity_id=market_id,
                market_id=market_id,
                details={
                    "processed": result.processed,
                    "succeeded": result.succeeded,
                    "failed": result.failed,
                    "dead_lettered": result.dead_lettered,
                },
                actor=actor,
            )
            db.commit()
        return result

    def refresh_sla_states(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        records = list(
            db.scalars(
                select(TicketRecord)
                .where(
                    TicketRecord.market_id == market_id,
                    TicketRecord.status.in_(OPEN_STATUSES),
                )
                .order_by(TicketRecord.created_at.asc())
            )
        )
        result = WorkerJobResult(
            name="sla_refresh",
            market_id=market_id,
            processed=len(records),
        )
        changed_ticket_ids: list[str] = []
        for record in records:
            previous_risk = record.sla.get("risk")
            previous_breached = bool(record.sla.get("breached"))
            ticket = ticket_from_record(record)
            ticket.sla = sla_service.refresh(ticket.sla)
            record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket
            if ticket.sla.risk != previous_risk or ticket.sla.breached != previous_breached:
                changed_ticket_ids.append(ticket.id)
                _audit_worker(
                    db,
                    state,
                    action="worker.sla_refresh",
                    entity_type="ticket",
                    entity_id=ticket.id,
                    market_id=market_id,
                    details={
                        "from": {"risk": previous_risk, "breached": previous_breached},
                        "to": {"risk": ticket.sla.risk, "breached": ticket.sla.breached},
                    },
                    actor=actor,
                )
        result.succeeded = len(changed_ticket_ids)
        result.details = {"changed_ticket_ids": changed_ticket_ids}
        db.commit()
        return result

    def recompute_work_queue(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        items = operations_repository.read_work_queue(db, state, market_id)
        top_item = items[0] if items else None
        result = WorkerJobResult(
            name="work_queue_recompute",
            market_id=market_id,
            processed=len(items),
            succeeded=len(items),
            details={
                "top_ticket_id": top_item.ticket.id if top_item else None,
                "top_score": top_item.score if top_item else None,
            },
        )
        _audit_worker(
            db,
            state,
            action="worker.work_queue_recompute",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details=result.details | {"items": len(items)},
            actor=actor,
        )
        db.commit()
        return result

    def rollup_analytics(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        actor: str = WORKER_ACTOR,
    ) -> WorkerJobResult:
        snapshot = operations_repository.analytics_summary(db, state, market_id)
        details = snapshot.model_dump(mode="json")
        result = WorkerJobResult(
            name="analytics_rollup",
            market_id=market_id,
            processed=1,
            succeeded=1,
            details=details,
        )
        _audit_worker(
            db,
            state,
            action="worker.analytics_rollup",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details=details,
            actor=actor,
        )
        db.commit()
        return result

    def run_once(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_ids: list[str] | None = None,
        outbound_limit: int = 50,
        actor: str = WORKER_ACTOR,
    ) -> WorkerRunSummary:
        started_at = utc_now()
        jobs: list[WorkerJobResult] = []
        for market_id in self.market_ids(db, market_ids):
            jobs.append(
                self.process_due_outbound(
                    db,
                    state,
                    market_id,
                    limit=outbound_limit,
                    actor=actor,
                )
            )
            jobs.append(self.refresh_sla_states(db, state, market_id, actor=actor))
            jobs.append(self.recompute_work_queue(db, state, market_id, actor=actor))
            jobs.append(self.rollup_analytics(db, state, market_id, actor=actor))
        return WorkerRunSummary(
            started_at=started_at.isoformat(),
            finished_at=utc_now().isoformat(),
            jobs=jobs,
        )


worker_service = BackgroundWorkerService()
