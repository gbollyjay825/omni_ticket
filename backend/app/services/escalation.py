from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import company_from_record, customer_from_record, timeline_event_from_record
from app.db.models import AuditEventRecord, CompanyRecord, CustomerRecord, TicketRecord, TimelineEventRecord
from app.models.domain import ChannelType, Priority, Ticket, TimelineEventType, utc_now


class EscalationService:
    def notification_payload(
        self,
        db: Session,
        ticket: Ticket,
        *,
        state: InMemoryStore,
    ) -> dict | None:
        if ticket.sla.risk not in {"at_risk", "breached"}:
            return None

        customer_record = db.get(CustomerRecord, ticket.customer_id)
        customer_tier = "standard"
        customer_name = "Customer"
        if customer_record is not None and customer_record.market_id == ticket.market_id:
            customer = customer_from_record(customer_record)
            state.customers[customer.id] = customer
            customer_name = customer.name
            if customer.company_id:
                company_record = db.get(CompanyRecord, customer.company_id)
                if company_record is not None and company_record.market_id == ticket.market_id:
                    company = company_from_record(company_record)
                    state.companies[company.id] = company
                    customer_tier = company.tier

        should_notify = (
            ticket.sla.breached
            or ticket.priority in {Priority.urgent, Priority.high}
            or ticket.channel in {ChannelType.facebook, ChannelType.instagram}
            or customer_tier in {"enterprise", "vip"}
        )
        if not should_notify:
            return None

        reasons: list[str] = [ticket.sla.risk.replace("_", " ")]
        if ticket.priority in {Priority.urgent, Priority.high}:
            reasons.append(f"{ticket.priority.value} priority")
        if ticket.channel in {ChannelType.facebook, ChannelType.instagram}:
            reasons.append("public social channel")
        if customer_tier in {"enterprise", "vip"}:
            reasons.append(f"{customer_tier} customer tier")

        return {
            "risk": ticket.sla.risk,
            "channel": ticket.channel.value,
            "priority": ticket.priority.value,
            "queue": ticket.team,
            "customer_tier": customer_tier,
            "customer_name": customer_name,
            "reasons": reasons,
        }

    def notification_message(self, ticket: Ticket, payload: dict) -> str:
        return (
            f"Supervisor notification: {ticket.public_id} for {payload['customer_name']} is "
            f"{payload['risk'].replace('_', ' ')} in {payload['queue']} via {payload['channel']} "
            f"({', '.join(payload['reasons'])})."
        )

    def already_notified(
        self,
        db: Session,
        ticket_id: str,
        *,
        market_id: str,
        risk: str,
    ) -> bool:
        for event in db.scalars(
            select(AuditEventRecord).where(
                AuditEventRecord.market_id == market_id,
                AuditEventRecord.entity_type == "ticket",
                AuditEventRecord.entity_id == ticket_id,
                AuditEventRecord.action == "worker.supervisor_notification",
            )
        ):
            if event.details.get("risk") == risk:
                return True
        return False

    def append_notification_timeline(
        self,
        db: Session,
        state: InMemoryStore,
        ticket_record: TicketRecord,
        *,
        actor: str,
        body: str,
        metadata: dict,
    ) -> None:
        ticket_record.updated_at = utc_now()
        record = TimelineEventRecord(
            id=f"event_{uuid4().hex}",
            market_id=ticket_record.market_id,
            ticket_id=ticket_record.id,
            type=TimelineEventType.internal_note.value,
            channel=ChannelType.internal.value,
            actor=actor,
            body=body,
            public=False,
            event_metadata=metadata,
        )
        db.add(record)
        db.flush()
        state.timeline.setdefault(ticket_record.id, []).append(timeline_event_from_record(record))


escalation_service = EscalationService()
