from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    analytics_rollup_from_record,
    customer_from_record,
    ticket_from_record,
)
from app.db.models import (
    AgentRecord,
    AnalyticsRollupRecord,
    CsatFeedbackRecord,
    CustomerRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.models.domain import (
    AnalyticsRollup,
    AnalyticsSnapshot,
    ChannelType,
    TicketStatus,
    TimelineEventType,
    WorkQueueItem,
    utc_now,
)
from app.services.ai import automation_service
from app.services.sla import sla_service


OPEN_STATUSES = {"open", "pending", "waiting"}
CLOSED_STATUSES = {TicketStatus.solved.value, TicketStatus.closed.value}
ACTIVE_AGENT_STATUSES = {"available", "busy", "away"}
CHAT_CHANNELS = {
    ChannelType.whatsapp.value,
    ChannelType.facebook.value,
    ChannelType.instagram.value,
    ChannelType.sms.value,
}
CUSTOMER_FACING_CHANNELS = {
    ChannelType.email.value,
    ChannelType.whatsapp.value,
    ChannelType.facebook.value,
    ChannelType.instagram.value,
    ChannelType.sms.value,
    ChannelType.voice.value,
    ChannelType.portal.value,
}
DASHBOARD_EXCLUDED_TAGS = {
    "smoke",
    "test",
    "demo",
    "production-readiness",
    "account-request",
    "internal",
    "handoff",
}
DASHBOARD_RANGE_DAYS = {"today": 1, "7d": 7, "30d": 30}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _hour_period_start() -> datetime:
    now = utc_now()
    return now.replace(minute=0, second=0, microsecond=0)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _avg_first_response_seconds(
    ticket_records: list[TicketRecord],
    first_reply_by_ticket: dict[str, datetime],
) -> float | None:
    values: list[float] = []
    for record in ticket_records:
        if record.id not in first_reply_by_ticket:
            continue
        first_reply_at = _as_utc(first_reply_by_ticket[record.id])
        created_at = _as_utc(record.created_at)
        if first_reply_at >= created_at:
            values.append((first_reply_at - created_at).total_seconds())
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _resolution_within_sla_pct(tickets: list) -> int | None:
    resolved = [ticket for ticket in tickets if ticket.status in CLOSED_STATUSES]
    if not resolved:
        return None
    within_sla = 0
    for ticket in resolved:
        met = ticket.sla_resolution_met
        if met is None:
            # Tickets resolved before the frozen outcome existed: derive from the
            # resolution moment vs the due date (resolved_at preferred over updated_at).
            resolved_at = _as_utc(ticket.resolved_at) if ticket.resolved_at else _as_utc(ticket.updated_at)
            met = not ticket.sla.breached or resolved_at <= _as_utc(ticket.sla.resolution_due_at)
        if met:
            within_sla += 1
    return round((within_sla / len(resolved)) * 100)


def _pct(part: int, whole: int) -> int:
    if whole <= 0:
        return 0
    return round((part / whole) * 100)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _dashboard_start(period: str | None, now: datetime) -> datetime | None:
    days = DASHBOARD_RANGE_DAYS.get(period or "all")
    if days is None:
        return None
    return now - timedelta(days=days)


def _within_dashboard_range(created_at: datetime, start: datetime | None) -> bool:
    if start is None:
        return True
    return _as_utc(created_at) >= _as_utc(start)


def _normal_filter(value: str | None) -> str:
    return (value or "all").strip().lower()


def _ticket_in_dashboard_scope(record: TicketRecord) -> bool:
    if record.channel not in CUSTOMER_FACING_CHANNELS:
        return False
    if record.id.startswith("ticket-"):
        return False
    tags = {str(tag).lower() for tag in (record.tags or [])}
    if tags & DASHBOARD_EXCLUDED_TAGS:
        return False
    subject = record.subject.lower()
    return "smoke" not in subject and "test" not in subject


def _filter_dashboard_records(
    records: Sequence[TicketRecord],
    *,
    start: datetime | None,
    group: str | None,
    chat: bool,
) -> list[TicketRecord]:
    group_filter = _normal_filter(group)
    return [
        record
        for record in records
        if _ticket_in_dashboard_scope(record)
        and _within_dashboard_range(record.created_at, start)
        and ((record.channel in CHAT_CHANNELS) is chat)
        and (group_filter == "all" or record.team.strip().lower() == group_filter)
    ]


def _ticket_by_id(tickets: list) -> dict[str, object]:
    return {ticket.id: ticket for ticket in tickets}


def _first_reply_by_ticket(
    db: Session,
    *,
    market_id: str,
    ticket_ids: set[str],
) -> dict[str, datetime]:
    if not ticket_ids:
        return {}
    rows = db.execute(
        select(
            TimelineEventRecord.ticket_id,
            func.min(TimelineEventRecord.created_at),
        )
        .where(
            TimelineEventRecord.market_id == market_id,
            TimelineEventRecord.type == TimelineEventType.public_reply.value,
            TimelineEventRecord.ticket_id.in_(ticket_ids),
        )
        .group_by(TimelineEventRecord.ticket_id)
    ).all()
    return {ticket_id: first_at for ticket_id, first_at in rows}


def _timeline_by_ticket(
    db: Session,
    *,
    market_id: str,
    ticket_ids: set[str],
) -> dict[str, list[TimelineEventRecord]]:
    if not ticket_ids:
        return {}
    rows = db.scalars(
        select(TimelineEventRecord)
        .where(
            TimelineEventRecord.market_id == market_id,
            TimelineEventRecord.ticket_id.in_(ticket_ids),
        )
        .order_by(TimelineEventRecord.ticket_id, TimelineEventRecord.created_at)
    ).all()
    by_ticket: dict[str, list[TimelineEventRecord]] = {}
    for row in rows:
        by_ticket.setdefault(row.ticket_id, []).append(row)
    return by_ticket


def _average_response_seconds(timeline: dict[str, list[TimelineEventRecord]]) -> float | None:
    values: list[float] = []
    for events in timeline.values():
        pending_inbound: datetime | None = None
        for event in events:
            if event.type == TimelineEventType.inbound.value and pending_inbound is None:
                pending_inbound = event.created_at
            elif event.type == TimelineEventType.public_reply.value and pending_inbound is not None:
                replied_at = _as_utc(event.created_at)
                inbound_at = _as_utc(pending_inbound)
                if replied_at >= inbound_at:
                    values.append((replied_at - inbound_at).total_seconds())
                pending_inbound = None
    return _average(values)


def _average_resolution_seconds(tickets: list) -> float | None:
    values = [
        (_as_utc(ticket.updated_at) - _as_utc(ticket.created_at)).total_seconds()
        for ticket in tickets
        if ticket.status in CLOSED_STATUSES and _as_utc(ticket.updated_at) >= _as_utc(ticket.created_at)
    ]
    return _average(values)


class OperationsRepository:
    def read_work_queue(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[WorkQueueItem]:
        records = db.scalars(
            select(TicketRecord).where(
                TicketRecord.market_id == market_id,
                TicketRecord.status.in_(OPEN_STATUSES),
            )
        ).all()
        items: list[WorkQueueItem] = []
        for record in records:
            ticket = ticket_from_record(record)
            ticket.sla = sla_service.refresh(ticket.sla)
            record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket

            customer_record = db.get(CustomerRecord, ticket.customer_id)
            if customer_record is None or customer_record.market_id != market_id:
                continue
            customer = customer_from_record(customer_record)
            state.customers[customer.id] = customer

            assignee = None
            if ticket.assignee_id:
                agent_record = db.get(AgentRecord, ticket.assignee_id)
                if agent_record is not None and market_id in agent_record.market_ids:
                    assignee = agent_from_record(agent_record)
                    state.agents[assignee.id] = assignee

            score, reasons = automation_service.score_ticket(ticket, customer)
            items.append(
                WorkQueueItem(
                    ticket=ticket,
                    customer=customer,
                    assignee=assignee,
                    score=score,
                    reasons=reasons,
                )
            )
        db.commit()
        return sorted(items, key=lambda item: (-item.score, item.ticket.created_at))

    def analytics_summary(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        period: str = "all",
        ticket_group: str | None = None,
        chat_group: str | None = None,
    ) -> AnalyticsSnapshot:
        now = utc_now()
        start = _dashboard_start(period, now)
        ticket_records = db.scalars(
            select(TicketRecord).where(TicketRecord.market_id == market_id)
        ).all()
        tickets = []
        for record in ticket_records:
            ticket = ticket_from_record(record)
            if ticket.status in OPEN_STATUSES:
                ticket.sla = sla_service.refresh(ticket.sla)
                record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket
            tickets.append(ticket)

        open_tickets = [ticket for ticket in tickets if ticket.status in OPEN_STATUSES]
        channel_volume: dict[ChannelType, int] = {}
        for ticket in tickets:
            channel_volume[ticket.channel] = channel_volume.get(ticket.channel, 0) + 1
        ticket_dashboard_records = _filter_dashboard_records(
            ticket_records,
            start=start,
            group=ticket_group,
            chat=False,
        )
        chat_dashboard_records = _filter_dashboard_records(
            ticket_records,
            start=start,
            group=chat_group,
            chat=True,
        )
        ticket_dashboard_ids = {record.id for record in ticket_dashboard_records}
        chat_dashboard_ids = {record.id for record in chat_dashboard_records}
        tickets_by_id = {ticket.id: ticket for ticket in tickets}
        ticket_dashboard_tickets = [
            tickets_by_id[record.id]
            for record in ticket_dashboard_records
            if record.id in tickets_by_id
        ]
        chat_dashboard_tickets = [
            tickets_by_id[record.id]
            for record in chat_dashboard_records
            if record.id in tickets_by_id
        ]
        ticket_open = [ticket for ticket in ticket_dashboard_tickets if ticket.status in OPEN_STATUSES]
        chat_open = [ticket for ticket in chat_dashboard_tickets if ticket.status in OPEN_STATUSES]
        performance_ticket_records = ticket_dashboard_records
        performance_ticket_ids = {record.id for record in performance_ticket_records}
        performance_tickets = ticket_dashboard_tickets

        agent_records = db.scalars(select(AgentRecord)).all()
        active_agents = [
            agent_from_record(record)
            for record in agent_records
            if market_id in record.market_ids and record.status in ACTIVE_AGENT_STATUSES
        ]
        state.agents = {
            **{key: value for key, value in state.agents.items() if market_id not in value.market_ids},
            **{agent.id: agent for agent in active_agents},
        }
        avg_occupancy = (
            round(sum(agent.occupancy for agent in active_agents) / len(active_agents))
            if active_agents
            else 0
        )
        csat_records = db.scalars(
            select(CsatFeedbackRecord).where(CsatFeedbackRecord.market_id == market_id)
        ).all()
        csat_ratings = [record.rating for record in csat_records]
        avg_csat = (
            round(sum(csat_ratings) / len(csat_ratings), 2)
            if csat_ratings
            else None
        )
        ticket_csat_records = [
            record
            for record in csat_records
            if record.ticket_id in ticket_dashboard_ids and _within_dashboard_range(record.created_at, start)
        ]
        chat_csat_records = [
            record
            for record in csat_records
            if record.ticket_id in chat_dashboard_ids and _within_dashboard_range(record.created_at, start)
        ]
        first_reply_by_ticket = _first_reply_by_ticket(
            db,
            market_id=market_id,
            ticket_ids=performance_ticket_ids,
        )
        chat_first_reply_by_ticket = _first_reply_by_ticket(
            db,
            market_id=market_id,
            ticket_ids=chat_dashboard_ids,
        )
        chat_timeline = _timeline_by_ticket(
            db,
            market_id=market_id,
            ticket_ids=chat_dashboard_ids,
        )
        avg_first_response_seconds = _avg_first_response_seconds(
            performance_ticket_records,
            first_reply_by_ticket,
        )
        resolution_within_sla_pct = _resolution_within_sla_pct(performance_tickets)
        chat_first_response_seconds = _avg_first_response_seconds(
            chat_dashboard_records,
            chat_first_reply_by_ticket,
        )
        chat_response_seconds = _average_response_seconds(chat_timeline)
        chat_resolution_seconds = _average_resolution_seconds(chat_dashboard_tickets)
        ticket_positive = sum(1 for record in ticket_csat_records if record.rating >= 4)
        ticket_neutral = sum(1 for record in ticket_csat_records if record.rating == 3)
        ticket_negative = sum(1 for record in ticket_csat_records if record.rating <= 2)
        chat_yes = sum(1 for record in chat_csat_records if record.rating >= 4)
        chat_no = sum(1 for record in chat_csat_records if record.rating <= 3)
        chat_rating_values = [record.rating for record in chat_csat_records]
        recent_ticket_ids = ticket_dashboard_ids | chat_dashboard_ids
        recent_activity = [
            {
                "id": record.id,
                "ticket_id": record.ticket_id,
                "public_id": tickets_by_id[record.ticket_id].public_id,
                "type": record.type,
                "actor": record.actor,
                "body": record.body,
                "created_at": record.created_at,
            }
            for record in db.scalars(
                select(TimelineEventRecord)
                .where(
                    TimelineEventRecord.market_id == market_id,
                    TimelineEventRecord.ticket_id.in_(recent_ticket_ids),
                )
                .order_by(TimelineEventRecord.created_at.desc())
                .limit(8)
            ).all()
            if record.ticket_id in tickets_by_id
        ] if recent_ticket_ids else []
        agents_on_chat = sum(
            1
            for agent in active_agents
            if any(skill.value in CHAT_CHANNELS for skill in agent.skills)
        )
        agents_on_tickets = sum(
            1
            for agent in active_agents
            if not agent.skills or any(skill.value not in CHAT_CHANNELS for skill in agent.skills)
        )
        db.commit()
        return AnalyticsSnapshot(
            open_tickets=len(open_tickets),
            at_risk_tickets=sum(1 for ticket in open_tickets if ticket.sla.risk == "at_risk"),
            breached_tickets=sum(1 for ticket in open_tickets if ticket.sla.breached),
            channel_volume=channel_volume,
            active_agents=len(active_agents),
            avg_occupancy=avg_occupancy,
            avg_csat=avg_csat,
            avg_first_response_seconds=avg_first_response_seconds,
            resolution_within_sla_pct=resolution_within_sla_pct,
            ticket_trends={
                "open": len(ticket_open),
                "unassigned": sum(1 for ticket in ticket_open if not ticket.assignee_id),
                "overdue": sum(1 for ticket in ticket_open if ticket.sla.breached),
                "due_today": sum(
                    1
                    for ticket in ticket_open
                    if now <= ticket.sla.resolution_due_at <= now + timedelta(days=1)
                ),
            },
            ticket_performance={
                "avg_first_response_seconds": avg_first_response_seconds,
                "resolution_within_sla_pct": resolution_within_sla_pct,
            },
            ticket_csat={
                "responses": len(ticket_csat_records),
                "positive_pct": _pct(ticket_positive, len(ticket_csat_records)),
                "neutral_pct": _pct(ticket_neutral, len(ticket_csat_records)),
                "negative_pct": _pct(ticket_negative, len(ticket_csat_records)),
            },
            chat_trends={
                "unassigned": sum(1 for ticket in chat_open if not ticket.assignee_id),
                "assigned_not_replied": sum(
                    1
                    for ticket in chat_open
                    if ticket.sla.breached or ticket.sla.risk != "on_track"
                ),
                "assigned": len(chat_open),
            },
            chat_performance={
                "first_response_seconds": chat_first_response_seconds,
                "response_seconds": chat_response_seconds,
                "resolution_seconds": chat_resolution_seconds,
                "wait_seconds": chat_first_response_seconds,
            },
            chat_csat={
                "responses": len(chat_csat_records),
                "avg_rating": _average([float(value) for value in chat_rating_values]),
                "yes_count": chat_yes,
                "no_count": chat_no,
                "yes_pct": _pct(chat_yes, len(chat_csat_records)),
                "no_pct": _pct(chat_no, len(chat_csat_records)),
            },
            agent_availability={
                "agents_on_tickets": agents_on_tickets,
                "agents_on_chat": agents_on_chat,
            },
            recent_activity=recent_activity,
        )

    def record_analytics_rollup(
        self,
        db: Session,
        *,
        market_id: str,
        snapshot: AnalyticsSnapshot,
    ) -> AnalyticsRollup:
        period_start = _hour_period_start()
        period_end = period_start + timedelta(hours=1)
        record = db.scalar(
            select(AnalyticsRollupRecord).where(
                AnalyticsRollupRecord.market_id == market_id,
                AnalyticsRollupRecord.period_start == period_start,
            )
        )
        channel_volume = {
            channel.value: count
            for channel, count in snapshot.channel_volume.items()
        }
        if record is None:
            record = AnalyticsRollupRecord(
                id=_new_id("analytics_rollup"),
                market_id=market_id,
                period_start=period_start,
                period_end=period_end,
                open_tickets=snapshot.open_tickets,
                at_risk_tickets=snapshot.at_risk_tickets,
                breached_tickets=snapshot.breached_tickets,
                active_agents=snapshot.active_agents,
                avg_occupancy=snapshot.avg_occupancy,
                avg_csat=snapshot.avg_csat,
                channel_volume=channel_volume,
            )
            db.add(record)
        else:
            record.period_end = period_end
            record.open_tickets = snapshot.open_tickets
            record.at_risk_tickets = snapshot.at_risk_tickets
            record.breached_tickets = snapshot.breached_tickets
            record.active_agents = snapshot.active_agents
            record.avg_occupancy = snapshot.avg_occupancy
            record.avg_csat = snapshot.avg_csat
            record.channel_volume = channel_volume
            record.updated_at = utc_now()
        db.flush()
        return analytics_rollup_from_record(record)

    def recent_analytics_rollups(
        self,
        db: Session,
        *,
        market_id: str,
        limit: int = 24,
    ) -> list[AnalyticsRollup]:
        records = db.scalars(
            select(AnalyticsRollupRecord)
            .where(AnalyticsRollupRecord.market_id == market_id)
            .order_by(AnalyticsRollupRecord.period_start.desc())
            .limit(limit)
        ).all()
        return [analytics_rollup_from_record(record) for record in records]


operations_repository = OperationsRepository()
