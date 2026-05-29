from app.core.store import InMemoryStore
from app.models.domain import AnalyticsSnapshot, ChannelType
from app.services.sla import sla_service


class AnalyticsService:
    def summary(self, state: InMemoryStore, market_id: str | None = None) -> AnalyticsSnapshot:
        tickets = [
            ticket
            for ticket in state.tickets.values()
            if market_id is None or ticket.market_id == market_id
        ]
        for ticket in tickets:
            ticket.sla = sla_service.refresh(ticket.sla)
        open_tickets = [ticket for ticket in tickets if ticket.status not in {"solved", "closed"}]
        channel_volume: dict[ChannelType, int] = {}
        for ticket in tickets:
            channel_volume[ticket.channel] = channel_volume.get(ticket.channel, 0) + 1
        active_agents = [
            agent
            for agent in state.agents.values()
            if agent.status in {"available", "busy", "away"}
            and (market_id is None or market_id in agent.market_ids)
        ]
        avg_occupancy = (
            round(sum(agent.occupancy for agent in active_agents) / len(active_agents))
            if active_agents
            else 0
        )
        return AnalyticsSnapshot(
            open_tickets=len(open_tickets),
            at_risk_tickets=sum(1 for ticket in open_tickets if ticket.sla.risk == "at_risk"),
            breached_tickets=sum(1 for ticket in open_tickets if ticket.sla.breached),
            channel_volume=channel_volume,
            active_agents=len(active_agents),
            avg_occupancy=avg_occupancy,
        )


analytics_service = AnalyticsService()
