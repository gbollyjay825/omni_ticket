from fastapi import HTTPException, status

from app.core.store import InMemoryStore
from app.models.domain import (
    ConnectorDirection,
    ConnectorInboundRequest,
    ContactPoint,
    CreateTicketRequest,
    Customer,
)
from app.services.tickets import ticket_service


class ConnectorService:
    def ingest(
        self,
        state: InMemoryStore,
        request: ConnectorInboundRequest,
        market_id: str,
        *,
        ai_enabled: bool | None = None,
    ) -> dict:
        existing = [
            event
            for event in state.connector_events.values()
            if event.external_id == request.external_id and event.provider == request.provider
            and event.market_id == market_id
        ]
        if existing:
            ticket_id = existing[0].ticket_id
            ticket = state.tickets.get(ticket_id or "")
            if ticket is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Connector event was seen before but ticket is unavailable",
                )
            return {"deduplicated": True, "ticket": ticket, "connector_event": existing[0]}

        customer = next(
            (
                customer
                for customer in state.customers.values()
                if customer.email == request.customer_email and customer.market_id == market_id
            ),
            None,
        )
        if customer is None:
            customer = Customer(
                id=state.next_id("customer"),
                market_id=market_id,
                name=request.customer_name,
                email=request.customer_email,
                preferred_channels=[request.provider],
                contact_points=[
                    ContactPoint(
                        channel=request.provider,
                        value=request.handle or str(request.customer_email),
                    )
                ],
            )
            state.customers[customer.id] = customer
            state.audit_event(
                actor="connector-service",
                action="customer.create_from_connector",
                entity_type="customer",
                entity_id=customer.id,
                market_id=market_id,
                details={"provider": request.provider.value},
            )

        ticket = ticket_service.create_ticket(
            state,
            CreateTicketRequest(
                subject=request.subject,
                description=request.body,
                customer_id=customer.id,
                channel=request.provider,
                external_id=request.external_id,
                tags=["connector-intake"],
            ),
            market_id,
            ai_enabled=ai_enabled,
        )
        event = state.record_connector_event(
            market_id=market_id,
            provider=request.provider,
            direction=ConnectorDirection.inbound,
            external_id=request.external_id,
            ticket_id=ticket.id,
            status="ticket-created",
            payload=request.model_dump(mode="json"),
        )
        return {"deduplicated": False, "ticket": ticket, "connector_event": event}


connector_service = ConnectorService()
