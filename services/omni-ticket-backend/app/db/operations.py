from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
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
)
from app.models.domain import AnalyticsRollup, AnalyticsSnapshot, ChannelType, WorkQueueItem, utc_now
from app.services.ai import automation_service
from app.services.sla import sla_service


OPEN_STATUSES = {"open", "pending", "waiting"}
ACTIVE_AGENT_STATUSES = {"available", "busy", "away"}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _hour_period_start() -> datetime:
    now = utc_now()
    return now.replace(minute=0, second=0, microsecond=0)


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
    ) -> AnalyticsSnapshot:
        ticket_records = db.scalars(
            select(TicketRecord).where(TicketRecord.market_id == market_id)
        ).all()
        tickets = []
        for record in ticket_records:
            ticket = ticket_from_record(record)
            ticket.sla = sla_service.refresh(ticket.sla)
            record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket
            tickets.append(ticket)

        open_tickets = [ticket for ticket in tickets if ticket.status in OPEN_STATUSES]
        channel_volume: dict[ChannelType, int] = {}
        for ticket in tickets:
            channel_volume[ticket.channel] = channel_volume.get(ticket.channel, 0) + 1

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
        csat_ratings = list(
            db.scalars(
                select(CsatFeedbackRecord.rating).where(CsatFeedbackRecord.market_id == market_id)
            )
        )
        avg_csat = (
            round(sum(csat_ratings) / len(csat_ratings), 2)
            if csat_ratings
            else None
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
