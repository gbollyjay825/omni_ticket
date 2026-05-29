from app.core.store import InMemoryStore
from app.models.domain import (
    Agent,
    AiDecision,
    ChannelType,
    Customer,
    Priority,
    Sentiment,
    Ticket,
    WorkQueueItem,
    utc_now,
)
from app.services.sla import sla_service


NEGATIVE_TERMS = {
    "angry",
    "terrible",
    "failed",
    "breach",
    "complaint",
    "escalate",
    "refund",
    "duplicate",
    "missed",
    "delay",
    "public",
}

URGENT_TERMS = {"breach", "public", "angry", "escalate", "failed", "fraud", "legal"}
PAYMENT_TERMS = {"payment", "invoice", "billing", "duplicate", "refund", "charge"}
DELIVERY_TERMS = {"delivery", "order", "shipment", "fulfillment"}


class WorkQueueAutomationService:
    def classify_priority(self, text: str, requested_priority: Priority | None) -> Priority:
        if requested_priority:
            return requested_priority
        normalized = text.lower()
        if any(term in normalized for term in URGENT_TERMS):
            return Priority.urgent
        if any(term in normalized for term in PAYMENT_TERMS | DELIVERY_TERMS):
            return Priority.high
        return Priority.normal

    def classify_sentiment(self, text: str) -> Sentiment:
        normalized = text.lower()
        hits = sum(1 for term in NEGATIVE_TERMS if term in normalized)
        if hits >= 3:
            return Sentiment.angry
        if hits >= 1:
            return Sentiment.frustrated
        return Sentiment.neutral

    def classify_tags(self, text: str, channel: ChannelType, incoming_tags: list[str]) -> list[str]:
        normalized = text.lower()
        tags = set(incoming_tags)
        tags.add(channel.value)
        if any(term in normalized for term in PAYMENT_TERMS):
            tags.add("payment-risk")
        if any(term in normalized for term in DELIVERY_TERMS):
            tags.add("delivery")
        if channel in {ChannelType.facebook, ChannelType.instagram} or "public" in normalized:
            tags.add("reputation-risk")
        return sorted(tags)

    def choose_agent(self, store: InMemoryStore, channel: ChannelType, market_id: str) -> Agent | None:
        candidates = [
            agent
            for agent in store.agents.values()
            if agent.status != "offline" and market_id in agent.market_ids and channel in agent.skills
        ]
        if not candidates:
            candidates = [
                agent
                for agent in store.agents.values()
                if agent.status != "offline" and market_id in agent.market_ids
            ]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda agent: (
                0 if agent.status == "available" else 1,
                agent.occupancy,
                -agent.capacity,
                agent.name,
            ),
        )[0]

    def recommended_action(self, ticket: Ticket, customer: Customer) -> str:
        if ticket.channel in {ChannelType.facebook, ChannelType.instagram}:
            return "Move private details into direct chat, acknowledge publicly, and update fulfillment."
        if "payment-risk" in ticket.tags:
            return "Confirm transaction reference, validate gateway state, and send the reversal timeline."
        if ticket.priority == Priority.urgent:
            return "Acknowledge within the SLA window and notify a supervisor if the blocker remains open."
        return f"Reply on {ticket.channel.value} with the next clear owner and promise time."

    def summary(self, ticket: Ticket, customer: Customer) -> str:
        return (
            f"{customer.name} has a {ticket.priority.value} {ticket.channel.value} issue "
            f"with {ticket.sentiment.value} sentiment and {ticket.sla.risk.replace('_', ' ')} SLA state."
        )

    def score_ticket(self, ticket: Ticket, customer: Customer) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        priority_scores = {
            Priority.urgent: 45,
            Priority.high: 32,
            Priority.normal: 18,
            Priority.low: 8,
        }
        sentiment_scores = {
            Sentiment.angry: 25,
            Sentiment.frustrated: 18,
            Sentiment.neutral: 6,
            Sentiment.positive: 0,
        }
        score += priority_scores[ticket.priority]
        score += sentiment_scores[ticket.sentiment]
        if ticket.sla.breached:
            score += 40
            reasons.append("SLA breached")
        elif ticket.sla.risk == "at_risk":
            score += 20
            reasons.append("SLA at risk")
        if "reputation-risk" in ticket.tags:
            score += 16
            reasons.append("Public reputation risk")
        if customer.company_id:
            company = customer.company_id
            if company:
                score += 4
        reasons.append(f"{ticket.priority.value} priority")
        reasons.append(f"{ticket.sentiment.value} sentiment")
        return score, reasons

    def queue(self, store: InMemoryStore, market_id: str | None = None) -> list[WorkQueueItem]:
        items: list[WorkQueueItem] = []
        for ticket in store.tickets.values():
            if market_id and ticket.market_id != market_id:
                continue
            if ticket.status in {"solved", "closed"}:
                continue
            ticket.sla = sla_service.refresh(ticket.sla)
            customer = store.customers[ticket.customer_id]
            score, reasons = self.score_ticket(ticket, customer)
            assignee = store.agents.get(ticket.assignee_id or "")
            items.append(
                WorkQueueItem(
                    ticket=ticket,
                    customer=customer,
                    assignee=assignee,
                    score=score,
                    reasons=reasons,
                )
            )
        return sorted(items, key=lambda item: (-item.score, item.ticket.created_at))

    def make_decision(self, ticket: Ticket) -> AiDecision:
        return AiDecision(
            id=f"ai-{ticket.id}",
            ticket_id=ticket.id,
            created_at=utc_now(),
            decision_type="work_queue_routing",
            confidence=0.87,
            summary=(
                f"Routed {ticket.public_id} to {ticket.team} as "
                f"{ticket.priority.value} priority from {ticket.channel.value}."
            ),
        )


automation_service = WorkQueueAutomationService()
