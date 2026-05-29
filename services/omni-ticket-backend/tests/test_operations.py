from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import store
from app.db.models import AuditEventRecord, OutboundMessageRecord, SessionRecord, TicketRecord
from app.db.session import get_engine
from app.main import create_app
from app.models.domain import utc_now
from app.services.worker import worker_service


def test_login_returns_user_and_available_markets(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["market"]["id"] == "market-ng"


def test_signed_token_survives_missing_session_record(client: TestClient) -> None:
    token = client.headers["Authorization"].removeprefix("Bearer ")
    with Session(get_engine()) as session:
        record = session.get(SessionRecord, token)
        assert record is not None
        session.delete(record)
        session.commit()

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "gbolahan@omniticket.example.com"


def test_tampered_signed_token_is_rejected(client: TestClient) -> None:
    token = client.headers["Authorization"].removeprefix("Bearer ")
    tampered_token = f"{token[:-1]}x"
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}", "X-Omni-Market": "market-ng"},
    )
    assert response.status_code == 401


def test_operations_require_authentication() -> None:
    unauthenticated = TestClient(create_app())
    response = unauthenticated.get("/api/v1/work-queue")
    assert response.status_code == 401


def test_market_scope_hides_other_market_customers(
    client: TestClient, login_as: Callable[[str, str], dict[str, str]]
) -> None:
    gh_headers = login_as("kofi.gh@omniticket.example.com", "market-gh")
    gh_customers = client.get("/api/v1/customers", headers=gh_headers)
    assert gh_customers.status_code == 200
    customer_ids = {customer["id"] for customer in gh_customers.json()}
    assert "cust-ama" in customer_ids
    assert "cust-leo" not in customer_ids

    ng_ticket_from_ghana = client.get("/api/v1/tickets", headers=gh_headers)
    assert ng_ticket_from_ghana.status_code == 200
    assert all(ticket["market_id"] == "market-gh" for ticket in ng_ticket_from_ghana.json())


def test_seeded_work_queue_has_ai_ranked_items(client: TestClient) -> None:
    response = client.get("/api/v1/work-queue")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2
    assert items[0]["score"] >= items[-1]["score"]
    assert "ticket" in items[0]
    assert "customer" in items[0]


def test_work_queue_override_updates_ticket_and_persists(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/work-queue/{ticket['id']}/override",
        json={
            "reason": "Supervisor moved this issue to the payments desk for manual review.",
            "priority": "urgent",
            "status": "pending",
            "assignee_id": "agent-mateo",
            "recommended_action": "Call the acquirer and send a manual payment status update.",
            "tags": ["manual-override", "payments-escalation"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "urgent"
    assert body["status"] == "pending"
    assert body["assignee_id"] == "agent-mateo"
    assert body["team"] == "Social Care"
    assert body["recommended_action"] == "Call the acquirer and send a manual payment status update."
    assert body["tags"] == ["manual-override", "payments-escalation"]

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline")
    assert timeline.status_code == 200
    assert any(
        event["metadata"].get("reason") == "Supervisor moved this issue to the payments desk for manual review."
        for event in timeline.json()
    )

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200
    assert any(event["action"] == "work_queue.override" for event in audit.json())

    store.seed()

    persisted = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert persisted.status_code == 200
    context = persisted.json()
    assert context["ticket"]["priority"] == "urgent"
    assert context["ticket"]["assignee_id"] == "agent-mateo"
    assert context["ticket"]["recommended_action"] == "Call the acquirer and send a manual payment status update."


def test_work_queue_override_requires_mutation_fields(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/work-queue/{ticket['id']}/override",
        json={"reason": "No-op override request."},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "At least one override field is required"


def test_create_ticket_runs_ai_routing_by_default(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Public WhatsApp complaint about duplicate payment",
            "description": "Customer is angry about a duplicate payment and wants escalation.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
            "tags": ["vip"],
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is not None
    assert ticket["priority"] == "urgent"
    assert "ai-routed" in ticket["tags"]
    assert "payment-risk" in ticket["tags"]

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert context["ai_decisions"]
    assert any(event["type"] == "ai_decision" for event in context["timeline"])


def test_ai_routing_can_be_disabled_in_settings(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings",
        json={"ai_work_queue_automation_enabled": False},
    )
    assert settings.status_code == 200
    assert settings.json()["ai_work_queue_automation_enabled"] is False

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp user cannot confirm payment reference",
            "description": "Customer needs manual help but no AI routing should run.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is None
    assert "ai-routed" not in ticket["tags"]


def test_ai_routing_setting_is_database_backed(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings/ai-work-queue-automation",
        json={"enabled": False},
    )
    assert settings.status_code == 200

    store.seed()

    persisted = client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["ai_work_queue_automation_enabled"] is False

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp customer angry about payment hold",
            "description": "This should stay manual because the persisted setting is disabled.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is None
    assert "ai-routed" not in ticket["tags"]


def test_reply_creates_timeline_and_outbound_queue_message(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    account = next(
        item
        for item in client.get("/api/v1/connectors/accounts").json()
        if item["provider"] == ticket["channel"]
    )
    client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": f"vault://omni/ng/{ticket['channel']}",
        },
    )
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": ticket["channel"],
            "actor": "agent-amara",
            "body": "We have your request and will update you shortly.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["type"] == "public_reply"
    assert response.json()["metadata"]["delivery_status"] == "sent"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(event["direction"] == "outbound" and event["status"] == "sent" for event in connector_events)

    outbound_messages = client.get("/api/v1/outbound/messages").json()
    assert any(
        message["ticket_id"] == ticket["id"]
        and message["status"] == "sent"
        and message["attempts"] == 1
        for message in outbound_messages
    )

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert context["outbound_messages"]
    assert any(
        event["type"] == "connector_receipt"
        and event["metadata"]["delivery_status"] == "sent"
        for event in context["timeline"]
    )


def test_failed_outbound_message_can_be_retried_after_connector_is_enabled(
    client: TestClient,
) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "We are checking this in WhatsApp.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "failed"

    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )
    assert failed_message["status"] == "failed"
    assert failed_message["last_error"]

    whatsapp_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "whatsapp"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{whatsapp_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
        },
    )

    retry = client.post(
        f"/api/v1/outbound/messages/{failed_message['id']}/retry",
        json={"reason": "Credentials connected"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "sent"
    assert retry.json()["attempts"] == 2


def test_worker_processes_due_outbound_retries_after_connector_is_enabled(
    client: TestClient,
) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Worker should retry this WhatsApp reply.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "failed"
    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )

    with Session(get_engine()) as session:
        message_record = session.get(OutboundMessageRecord, failed_message["id"])
        assert message_record is not None
        message_record.next_attempt_at = utc_now() - timedelta(minutes=1)
        session.commit()

    whatsapp_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "whatsapp"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{whatsapp_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
        },
    )

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"])

    outbound_job = next(job for job in summary.jobs if job.name == "outbound_retry")
    assert outbound_job.processed == 1
    assert outbound_job.succeeded == 1

    messages = client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
    retried = next(message for message in messages if message["id"] == failed_message["id"])
    assert retried["status"] == "sent"
    assert retried["attempts"] == 2

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "worker.outbound_batch" for event in audit)


def test_worker_dead_letters_due_outbound_after_max_attempts(client: TestClient) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "This should become a dead-letter after the worker retry.",
            "public": True,
        },
    )
    assert response.status_code == 200
    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )

    with Session(get_engine()) as session:
        message_record = session.get(OutboundMessageRecord, failed_message["id"])
        assert message_record is not None
        message_record.attempts = message_record.max_attempts - 1
        message_record.next_attempt_at = utc_now() - timedelta(minutes=1)
        session.commit()

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"])

    outbound_job = next(job for job in summary.jobs if job.name == "outbound_retry")
    assert outbound_job.processed == 1
    assert outbound_job.dead_lettered == 1

    messages = client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
    dead_lettered = next(message for message in messages if message["id"] == failed_message["id"])
    assert dead_lettered["status"] == "dead_lettered"
    assert dead_lettered["next_attempt_at"] is None

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "outbound.dead_lettered" for event in audit)


def test_worker_refreshes_sla_and_recomputes_operational_views(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    past = utc_now() - timedelta(hours=1)
    with Session(get_engine()) as session:
        record = session.get(TicketRecord, ticket["id"])
        assert record is not None
        record.sla = {
            **record.sla,
            "first_response_due_at": past.isoformat(),
            "resolution_due_at": past.isoformat(),
            "risk": "on_track",
            "breached": False,
        }
        session.commit()

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"], outbound_limit=0)

    sla_job = next(job for job in summary.jobs if job.name == "sla_refresh")
    queue_job = next(job for job in summary.jobs if job.name == "work_queue_recompute")
    analytics_job = next(job for job in summary.jobs if job.name == "analytics_rollup")
    assert sla_job.succeeded >= 1
    assert ticket["id"] in sla_job.details["changed_ticket_ids"]
    assert queue_job.processed >= 1
    assert analytics_job.details["open_tickets"] >= 1

    with Session(get_engine()) as session:
        refreshed = session.get(TicketRecord, ticket["id"])
        assert refreshed is not None
        assert refreshed.sla["risk"] == "breached"
        assert refreshed.sla["breached"] is True
        actions = set(
            session.scalars(
                select(AuditEventRecord.action).where(AuditEventRecord.actor == "omni-worker")
            )
        )
    assert {
        "worker.sla_refresh",
        "worker.work_queue_recompute",
        "worker.analytics_rollup",
    } <= actions


def test_handoff_lifecycle_writes_back_to_ticket_timeline(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    create_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Fulfillment",
            "requested_by": "agent-mateo",
            "reason": "Need delivery confirmation before customer update.",
            "due_minutes": 45,
            "checklist": ["Confirm warehouse state", "Return ETA"],
        },
    )
    assert create_response.status_code == 201
    handoff = create_response.json()
    assert handoff["status"] == "requested"

    update_response = client.patch(
        f"/api/v1/handoffs/{handoff['id']}",
        json={"status": "accepted"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "accepted"

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()
    assert any(event["type"] == "handoff_requested" for event in timeline)
    assert any(event["metadata"].get("handoff_id") == handoff["id"] for event in timeline)


def test_ticket_timeline_and_handoff_are_database_first_after_runtime_reset(
    client: TestClient,
) -> None:
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp restart persistence check",
            "description": "Customer expects this ticket, timeline, and handoff to survive restart.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    handoff_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Payments",
            "requested_by": "agent-amara",
            "reason": "Confirm payment processor state after restart.",
            "checklist": ["Check processor", "Return answer"],
        },
    )
    assert handoff_response.status_code == 201
    handoff_id = handoff_response.json()["id"]

    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Restart-safe reply.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200

    store.seed()

    context = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert context.status_code == 200
    body = context.json()
    assert body["ticket"]["id"] == ticket["id"]
    assert any(event["type"] == "inbound" for event in body["timeline"])
    assert any(event["type"] == "public_reply" for event in body["timeline"])
    assert any(handoff["id"] == handoff_id for handoff in body["handoffs"])

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline")
    assert timeline.status_code == 200
    assert any(event["type"] == "public_reply" for event in timeline.json())

    connector_events = client.get("/api/v1/connectors/events")
    assert connector_events.status_code == 200
    assert any(event["ticket_id"] == ticket["id"] for event in connector_events.json())


def test_ticket_task_toggle_is_database_backed(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    task = ticket["tasks"][0]

    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={
            "task_item_id": task["id"],
            "task_item_complete": True,
        },
    )
    assert response.status_code == 200
    updated_ticket = response.json()
    assert any(item["id"] == task["id"] and item["complete"] is True for item in updated_ticket["tasks"])

    store.seed()

    persisted = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert persisted.status_code == 200
    persisted_ticket = persisted.json()["ticket"]
    assert any(item["id"] == task["id"] and item["complete"] is True for item in persisted_ticket["tasks"])


def test_connector_ingest_creates_ticket_and_deduplicates(client: TestClient) -> None:
    payload = {
        "provider": "instagram",
        "external_id": "ig-msg-123",
        "customer_name": "Nia Brooks",
        "customer_email": "nia@example.com",
        "subject": "Instagram DM about missed order",
        "body": "I posted publicly because my order delivery was missed.",
        "handle": "@niabrooks",
    }
    first = client.post("/api/v1/connectors/inbound", json=payload)
    assert first.status_code == 201
    assert first.json()["deduplicated"] is False
    ticket = first.json()["ticket"]
    assert ticket["channel"] == "instagram"
    assert "reputation-risk" in ticket["tags"]

    second = client.post("/api/v1/connectors/inbound", json=payload)
    assert second.status_code == 201
    assert second.json()["deduplicated"] is True
    assert second.json()["ticket"]["id"] == ticket["id"]


def test_connector_ingest_is_database_first_after_runtime_reset(client: TestClient) -> None:
    external_id = f"wa-msg-{uuid4().hex}"
    payload = {
        "provider": "whatsapp",
        "external_id": external_id,
        "customer_name": "Mira Patel",
        "customer_email": f"mira-{uuid4().hex}@example.com",
        "subject": "WhatsApp complaint after callback",
        "body": "I need support to fix this payment issue before my promise time expires.",
        "handle": "+2348000000000",
    }
    first = client.post("/api/v1/connectors/inbound", json=payload)
    assert first.status_code == 201
    body = first.json()
    assert body["deduplicated"] is False
    ticket_id = body["ticket"]["id"]
    connector_event_id = body["connector_event"]["id"]

    store.seed()

    events = client.get("/api/v1/connectors/events")
    assert events.status_code == 200
    assert any(event["id"] == connector_event_id for event in events.json())

    context = client.get(f"/api/v1/tickets/{ticket_id}")
    assert context.status_code == 200
    assert context.json()["ticket"]["id"] == ticket_id
    assert any(event["type"] == "connector_receipt" for event in context.json()["timeline"])

    duplicate = client.post("/api/v1/connectors/inbound", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True
    assert duplicate.json()["ticket"]["id"] == ticket_id


def test_management_surfaces_are_available(client: TestClient) -> None:
    assert client.get("/api/v1/channels").status_code == 200
    assert client.get("/api/v1/agents").status_code == 200
    assert client.get("/api/v1/customers").status_code == 200
    assert client.get("/api/v1/companies").status_code == 200
    assert client.get("/api/v1/knowledge").status_code == 200
    assert client.get("/api/v1/automation-rules").status_code == 200
    assert client.get("/api/v1/analytics/summary").status_code == 200
    assert client.get("/api/v1/analytics/overview").status_code == 200
    assert client.get("/api/v1/connectors/providers").status_code == 200
    assert client.get("/api/v1/connectors/accounts").status_code == 200
    assert client.get("/api/v1/connector-accounts").status_code == 200
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/api/v1/tracker").status_code == 200
    assert client.get("/api/v1/frontend/snapshot").status_code == 200
    readiness = client.get("/api/v1/platform/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["required_tables_present"] is True


def test_customer_company_knowledge_and_rule_management(client: TestClient) -> None:
    company = client.post(
        "/api/v1/companies",
        json={"name": "Northstar Ops", "tier": "enterprise", "account_value": 2500},
    )
    assert company.status_code == 201
    company_id = company.json()["id"]

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": "Ada James",
            "email": "ada@example.com",
            "company_id": company_id,
            "preferred_channels": ["whatsapp", "email"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    updated_customer = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"sentiment": "frustrated", "tags": ["vip", "renewal"]},
    )
    assert updated_customer.status_code == 200
    assert updated_customer.json()["sentiment"] == "frustrated"

    article = client.post(
        "/api/v1/knowledge",
        json={
            "title": "WhatsApp escalation reply",
            "status": "draft",
            "channels": ["whatsapp"],
            "tags": ["escalation"],
            "body": "Acknowledge, confirm owner, and set a promise time.",
        },
    )
    assert article.status_code == 201

    rule = client.post(
        "/api/v1/automation-rules",
        json={
            "name": "VIP WhatsApp escalation",
            "enabled": True,
            "trigger": "customer tags contains vip and channel is whatsapp",
            "action": "assign escalations and raise priority",
        },
    )
    assert rule.status_code == 201
    updated_rule = client.patch(
        f"/api/v1/automation-rules/{rule.json()['id']}",
        json={"enabled": False},
    )
    assert updated_rule.status_code == 200
    assert updated_rule.json()["enabled"] is False


def test_customer_company_records_survive_store_reset_and_can_open_ticket(
    client: TestClient,
) -> None:
    suffix = uuid4().hex
    company = client.post(
        "/api/v1/companies",
        json={"name": f"Durable Company {suffix}", "tier": "enterprise"},
    )
    assert company.status_code == 201
    company_id = company.json()["id"]

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": "Durable Customer",
            "email": f"durable-{suffix}@example.com",
            "company_id": company_id,
            "preferred_channels": ["whatsapp"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    store.seed()

    customers = client.get("/api/v1/customers")
    assert customers.status_code == 200
    assert any(item["id"] == customer_id for item in customers.json())

    companies = client.get("/api/v1/companies")
    assert companies.status_code == 200
    assert any(item["id"] == company_id for item in companies.json())

    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp customer needs persistent account help",
            "description": "Ticket should be created after customer data is rehydrated from DB.",
            "customer_id": customer_id,
            "channel": "whatsapp",
        },
    )
    assert ticket.status_code == 201
    assert ticket.json()["customer_id"] == customer_id


def test_management_records_are_database_first_after_runtime_reset(client: TestClient) -> None:
    channel = client.get("/api/v1/channels").json()[0]
    channel_update = client.patch(
        f"/api/v1/channels/{channel['id']}",
        json={"health": "paused", "queued": 44},
    )
    assert channel_update.status_code == 200

    agent = client.get("/api/v1/agents").json()[0]
    agent_update = client.patch(
        f"/api/v1/agents/{agent['id']}/status",
        json={"status": "away"},
    )
    assert agent_update.status_code == 200

    article = client.post(
        "/api/v1/knowledge",
        json={
            "title": "Runtime reset article",
            "status": "draft",
            "channels": ["whatsapp"],
            "tags": ["reset-proof"],
            "body": "This article should survive runtime reset.",
        },
    )
    assert article.status_code == 201
    article_id = article.json()["id"]

    rule = client.post(
        "/api/v1/automation-rules",
        json={
            "name": "Runtime reset rule",
            "enabled": True,
            "trigger": "channel is whatsapp",
            "action": "raise priority",
        },
    )
    assert rule.status_code == 201
    rule_id = rule.json()["id"]

    store.seed()

    channels = client.get("/api/v1/channels").json()
    assert any(item["id"] == channel["id"] and item["health"] == "paused" for item in channels)
    agents = client.get("/api/v1/agents").json()
    assert any(item["id"] == agent["id"] and item["status"] == "away" for item in agents)
    articles = client.get("/api/v1/knowledge").json()
    assert any(item["id"] == article_id for item in articles)
    rules = client.get("/api/v1/automation-rules").json()
    assert any(item["id"] == rule_id for item in rules)


def test_analytics_and_work_queue_are_database_first_after_runtime_reset(
    client: TestClient,
) -> None:
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp urgent operations queue check",
            "description": "Customer is angry about a public payment issue and needs escalation.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket_id = ticket_response.json()["id"]

    store.seed()

    queue = client.get("/api/v1/work-queue")
    assert queue.status_code == 200
    assert any(item["ticket"]["id"] == ticket_id for item in queue.json())

    analytics = client.get("/api/v1/analytics/summary")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["open_tickets"] >= 1
    assert body["channel_volume"]["whatsapp"] >= 1


def test_connector_accounts_are_market_scoped_and_database_backed(
    client: TestClient,
    login_as: Callable[[str, str], dict[str, str]],
) -> None:
    accounts = client.get("/api/v1/connectors/accounts")
    assert accounts.status_code == 200
    body = accounts.json()
    assert {account["provider"] for account in body} >= {
        "email",
        "whatsapp",
        "facebook",
        "instagram",
        "sms",
        "voice",
    }
    assert all(account["market_id"] == "market-ng" for account in body)

    whatsapp = next(account for account in body if account["provider"] == "whatsapp")
    update = client.patch(
        f"/api/v1/connectors/accounts/{whatsapp['id']}",
        json={
            "status": "connected",
            "webhook_verified": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
            "outbound_enabled": True,
        },
    )
    assert update.status_code == 200
    assert update.json()["status"] == "connected"
    assert update.json()["credential_ref"] == "vault://omni/ng/whatsapp"

    store.seed()

    persisted = client.get("/api/v1/connectors/accounts").json()
    assert any(
        account["id"] == whatsapp["id"]
        and account["status"] == "connected"
        and account["webhook_verified"] is True
        for account in persisted
    )

    gh_headers = login_as("kofi.gh@omniticket.example.com", "market-gh")
    gh_accounts = client.get("/api/v1/connectors/accounts", headers=gh_headers)
    assert gh_accounts.status_code == 200
    assert gh_accounts.json()
    assert all(account["market_id"] == "market-gh" for account in gh_accounts.json())
    assert not any(account["id"] == whatsapp["id"] for account in gh_accounts.json())


def test_admin_can_create_and_manage_market_users(client: TestClient) -> None:
    create = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Ops Reviewer",
            "email": "ops.reviewer@example.com",
            "role": "agent",
            "market_ids": ["market-ng", "market-gh"],
            "default_market_id": "market-ng",
        },
    )
    assert create.status_code == 201
    user = create.json()
    assert user["email"] == "ops.reviewer@example.com"
    assert user["role"] == "agent"
    assert user["market_ids"] == ["market-ng", "market-gh"]

    update = client.patch(
        f"/api/v1/auth/users/{user['id']}",
        json={"role": "supervisor", "active": False, "default_market_id": "market-gh"},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["role"] == "supervisor"
    assert updated["active"] is False
    assert updated["default_market_id"] == "market-gh"

    users = client.get("/api/v1/auth/users")
    assert users.status_code == 200
    assert any(item["id"] == user["id"] for item in users.json())

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == user["id"] for item in snapshot.json()["users"])


def test_frontend_compatibility_endpoints_update_state(client: TestClient) -> None:
    channel = client.get("/api/v1/channels").json()[0]
    channel_update = client.patch(
        f"/api/v1/channels/{channel['id']}",
        json={"health": "paused", "queued": 41},
    )
    assert channel_update.status_code == 200
    assert channel_update.json()["health"] == "paused"
    assert channel_update.json()["queued"] == 41

    agent = client.get("/api/v1/agents").json()[0]
    agent_update = client.patch(
        f"/api/v1/agents/{agent['id']}/status",
        json={"status": "away"},
    )
    assert agent_update.status_code == 200
    assert agent_update.json()["status"] == "away"

    settings_update = client.patch(
        "/api/v1/settings/ai-work-queue-automation",
        json={"enabled": False},
    )
    assert settings_update.status_code == 200
    assert settings_update.json()["ai_work_queue_automation_enabled"] is False

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["settings"]["ai_work_queue_automation_enabled"] is False
    assert body["channels"]
    assert body["tickets"]
    assert body["analytics"]["open_tickets"] >= 1
