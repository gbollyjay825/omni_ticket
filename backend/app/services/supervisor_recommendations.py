from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import agent_from_record, ticket_from_record
from app.db.models import AgentRecord, HandoffRecord, SupportGroupRecord, TicketRecord
from app.models.domain import OperationalAlertSeverity, SupervisorRecommendation
from app.services.sla import sla_service


OPEN_TICKET_STATUSES = {"open", "pending", "waiting"}
ACTIVE_HANDOFF_STATUSES = {"requested", "accepted", "in-progress", "blocked"}
PRESSURE_RISK_STATES = {"at_risk", "breached"}
PRIORITY_WEIGHT = {"urgent": 18, "high": 12, "medium": 6, "normal": 4, "low": 0}


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _severity_for_score(score: int, breached: bool = False) -> OperationalAlertSeverity:
    if breached or score >= 92:
        return OperationalAlertSeverity.critical
    if score >= 64:
        return OperationalAlertSeverity.warning
    return OperationalAlertSeverity.info


class SupervisorRecommendationService:
    def list_recommendations(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int = 8,
    ) -> list[SupervisorRecommendation]:
        now = datetime.now(timezone.utc)
        recommendations: list[SupervisorRecommendation] = []
        ticket_records = db.scalars(
            select(TicketRecord).where(
                TicketRecord.market_id == market_id,
                TicketRecord.status.in_(OPEN_TICKET_STATUSES),
            )
        ).all()
        open_tickets: dict[str, TicketRecord] = {}
        for record in ticket_records:
            ticket = ticket_from_record(record)
            ticket.sla = sla_service.refresh(ticket.sla)
            record.sla = ticket.sla.model_dump(mode="json")
            state.tickets[ticket.id] = ticket
            open_tickets[record.id] = record

        handoffs = db.scalars(
            select(HandoffRecord).where(
                HandoffRecord.market_id == market_id,
                HandoffRecord.status.in_(ACTIVE_HANDOFF_STATUSES),
            )
        ).all()
        recommendations.extend(self._handoff_recommendations(market_id, handoffs, open_tickets, now))

        agents = [
            agent_from_record(record)
            for record in db.scalars(select(AgentRecord)).all()
            if market_id in record.market_ids
        ]
        state.agents.update({agent.id: agent for agent in agents})
        groups = db.scalars(
            select(SupportGroupRecord).where(
                SupportGroupRecord.market_id == market_id,
                SupportGroupRecord.active.is_(True),
            )
        ).all()
        recommendations.extend(self._queue_pressure_recommendations(market_id, ticket_records, groups, agents))
        recommendations.extend(self._reassignment_recommendations(market_id, ticket_records, agents))

        db.commit()
        return sorted(
            recommendations,
            key=lambda item: (-item.priority_score, item.category, item.title),
        )[:limit]

    def _handoff_recommendations(
        self,
        market_id: str,
        handoffs: Sequence[HandoffRecord],
        open_tickets: dict[str, TicketRecord],
        now: datetime,
    ) -> list[SupervisorRecommendation]:
        recommendations: list[SupervisorRecommendation] = []
        for handoff in handoffs:
            ticket = open_tickets.get(handoff.ticket_id)
            if ticket is None:
                continue
            due_at = _aware(handoff.due_at)
            minutes_to_due = int((due_at - now).total_seconds() // 60)
            sla = ticket.sla or {}
            breached = bool(sla.get("breached"))
            sla_risk = str(sla.get("risk") or "on_track")
            priority_score = 42 + PRIORITY_WEIGHT.get(ticket.priority, 4)
            reasons = [f"{handoff.to_team} owns the next step", f"{ticket.priority} priority"]
            if sla_risk in PRESSURE_RISK_STATES:
                priority_score += 18
                reasons.append(f"SLA {sla_risk.replace('_', ' ')}")
            if breached:
                priority_score += 18
            if handoff.status == "blocked":
                priority_score += 22
                if handoff.blocker:
                    reasons.append(f"Blocker: {handoff.blocker[:96]}")
                recommendations.append(
                    SupervisorRecommendation(
                        id=f"handoff-blocker:{handoff.id}",
                        market_id=market_id,
                        title=f"Unblock {handoff.to_team} handoff",
                        summary=f"{ticket.public_id} is blocked while the ticket is {sla_risk.replace('_', ' ')}.",
                        action=(
                            f"Ask the {handoff.to_team} lead for a blocker decision, assign an owner, "
                            "and send the customer a promise update."
                        ),
                        severity=_severity_for_score(priority_score, breached),
                        category="handoff_blocker",
                        priority_score=min(priority_score, 100),
                        ticket_id=ticket.id,
                        handoff_id=handoff.id,
                        support_group=handoff.to_team,
                        reasons=reasons,
                    )
                )
                continue

            if minutes_to_due <= 90:
                if minutes_to_due <= 0:
                    priority_score += 20
                    due_text = f"{abs(minutes_to_due)}m overdue"
                else:
                    priority_score += 12
                    due_text = f"due in {minutes_to_due}m"
                reasons.append(due_text)
                recommendations.append(
                    SupervisorRecommendation(
                        id=f"handoff-due:{handoff.id}",
                        market_id=market_id,
                        title=f"Push {handoff.to_team} handoff before SLA slips",
                        summary=f"{ticket.public_id} handoff is {due_text}.",
                        action=(
                            f"Confirm {handoff.to_team} capacity, update the handoff due time if needed, "
                            "and keep the ticket owner accountable for the customer update."
                        ),
                        severity=_severity_for_score(priority_score, breached),
                        category="handoff_due",
                        priority_score=min(priority_score, 100),
                        ticket_id=ticket.id,
                        handoff_id=handoff.id,
                        support_group=handoff.to_team,
                        reasons=reasons,
                    )
                )
        return recommendations

    def _queue_pressure_recommendations(
        self,
        market_id: str,
        tickets: Sequence[TicketRecord],
        groups: Sequence[SupportGroupRecord],
        agents: list,
    ) -> list[SupervisorRecommendation]:
        if not tickets:
            return []
        open_by_team: dict[str, list[TicketRecord]] = defaultdict(list)
        risk_by_team: dict[str, list[TicketRecord]] = defaultdict(list)
        for ticket in tickets:
            open_by_team[ticket.team].append(ticket)
            sla = ticket.sla or {}
            if sla.get("risk") in PRESSURE_RISK_STATES or sla.get("breached"):
                risk_by_team[ticket.team].append(ticket)

        agent_capacity_by_team: dict[str, int] = defaultdict(int)
        available_agents_by_team: dict[str, int] = defaultdict(int)
        for agent in agents:
            agent_capacity_by_team[agent.team] += max(agent.capacity, 1)
            if agent.status in {"available", "busy"} and agent.occupancy < 85:
                available_agents_by_team[agent.team] += 1

        recommendations: list[SupervisorRecommendation] = []
        active_group_names = {group.name for group in groups}
        for team, team_tickets in open_by_team.items():
            if active_group_names and team not in active_group_names:
                continue
            risk_count = len(risk_by_team[team])
            if risk_count == 0 and len(team_tickets) < 4:
                continue
            capacity = max(agent_capacity_by_team.get(team, 0), 1)
            pressure_ratio = len(team_tickets) / capacity
            if risk_count == 0 and pressure_ratio < 1.2:
                continue
            score = min(100, 48 + risk_count * 10 + int(max(pressure_ratio - 1, 0) * 18))
            reasons = [
                f"{len(team_tickets)} open ticket(s)",
                f"{risk_count} SLA risk ticket(s)",
                f"{available_agents_by_team.get(team, 0)} lower-load agent(s)",
            ]
            recommendations.append(
                SupervisorRecommendation(
                    id=f"queue-pressure:{market_id}:{team.lower().replace(' ', '-')}",
                    market_id=market_id,
                    title=f"Balance {team} queue pressure",
                    summary=f"{team} has {len(team_tickets)} open ticket(s) with {risk_count} SLA risk item(s).",
                    action=(
                        "Move the highest-risk work to an available skilled agent or borrow capacity from "
                        "a neighbouring support group before the queue breaches."
                    ),
                    severity=_severity_for_score(score, risk_count >= 3),
                    category="queue_pressure",
                    priority_score=score,
                    support_group=team,
                    reasons=reasons,
                )
            )
        return recommendations

    def _reassignment_recommendations(
        self,
        market_id: str,
        tickets: Sequence[TicketRecord],
        agents: list,
    ) -> list[SupervisorRecommendation]:
        agent_by_id = {agent.id: agent for agent in agents}
        relief_agents = [
            agent
            for agent in agents
            if agent.status == "available" and agent.occupancy <= 55
        ]
        if not relief_agents:
            return []

        candidates = []
        for ticket in tickets:
            sla = ticket.sla or {}
            if sla.get("risk") not in PRESSURE_RISK_STATES and not sla.get("breached"):
                continue
            owner = agent_by_id.get(ticket.assignee_id or "")
            if owner is None or owner.occupancy < 90:
                continue
            replacement = self._best_reassignment_agent(ticket, relief_agents)
            if replacement is None:
                continue
            score = min(
                100,
                58
                + PRIORITY_WEIGHT.get(ticket.priority, 4)
                + (18 if sla.get("breached") else 10)
                + max(owner.occupancy - replacement.occupancy, 0) // 4,
            )
            candidates.append(
                SupervisorRecommendation(
                    id=f"reassign:{ticket.id}:{replacement.id}",
                    market_id=market_id,
                    title=f"Reassign {ticket.public_id} to protect SLA",
                    summary=(
                        f"{owner.name} is at {owner.occupancy}% occupancy while "
                        f"{replacement.name} has matching capacity at {replacement.occupancy}%."
                    ),
                    action=(
                        f"Move ownership to {replacement.name}, keep {owner.name} as watcher if needed, "
                        "and ask the new owner to send the next public update."
                    ),
                    severity=_severity_for_score(score, bool(sla.get("breached"))),
                    category="reassignment",
                    priority_score=score,
                    ticket_id=ticket.id,
                    support_group=ticket.team,
                    owner_id=replacement.id,
                    reasons=[
                        f"SLA {str(sla.get('risk') or 'on track').replace('_', ' ')}",
                        f"Current owner {owner.occupancy}% occupied",
                        f"Candidate {replacement.occupancy}% occupied",
                    ],
                )
            )
        return candidates[:3]

    def _best_reassignment_agent(self, ticket: TicketRecord, agents: list):
        channel = str(ticket.channel)
        matching = [
            agent
            for agent in agents
            if channel in [skill.value if hasattr(skill, "value") else str(skill) for skill in agent.skills]
        ]
        pool = matching or agents
        return min(pool, key=lambda agent: (agent.occupancy, -agent.capacity, agent.name), default=None)


supervisor_recommendation_service = SupervisorRecommendationService()
