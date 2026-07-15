from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEventRecord, CustomerRecord, OutboundMessageRecord, TicketRecord
from app.db.session import get_engine
from app.main import create_app


def test_public_portal_lists_only_active_markets() -> None:
    public_client = TestClient(create_app())

    response = public_client.get("/api/v1/portal/markets")

    assert response.status_code == 200
    markets = response.json()
    assert {market["code"] for market in markets} == {"gh", "ng", "uk"}
    assert all({"code", "name", "default_locale"} <= set(market) for market in markets)


def test_public_portal_configuration_exposes_only_customer_safe_branding() -> None:
    public_client = TestClient(create_app())

    response = public_client.get("/api/v1/portal/ng/config")

    assert response.status_code == 200
    config = response.json()
    assert config["market_id"] == "market-ng"
    assert config["market_code"] == "ng"
    assert config["market_name"] == "Nigeria"
    assert config["support_email"]
    assert config["public_brand_name"]
    assert "credentials" not in config
    assert "ai_work_queue_automation_enabled" not in config


def test_public_portal_configuration_rejects_unknown_market() -> None:
    public_client = TestClient(create_app())

    response = public_client.get("/api/v1/portal/unknown/config")

    assert response.status_code == 404


def test_widget_conversation_uses_signed_session_and_real_chat_ticket(
    client: TestClient,
) -> None:
    enabled = client.patch(
        "/api/v1/widget-settings",
        json={
            "enabled": True,
            "display_name": "Talk to Wakanow",
            "welcome_message": "How can we help?",
            "collect_email": True,
        },
    )
    assert enabled.status_code == 200
    public_client = TestClient(create_app())

    config = public_client.get("/api/v1/widget/ng/config")
    assert config.status_code == 200
    assert config.json()["enabled"] is True
    assert config.json()["display_name"] == "Talk to Wakanow"
    assert config.json()["availability"] in {
        "online",
        "outside_business_hours",
        "paused",
    }

    created = public_client.post(
        "/api/v1/widget/ng/conversations",
        json={
            "name": "Widget Customer",
            "email": "widget-customer@example.com",
            "message": "I need help with a duplicate payment on my booking.",
            "subject": "Duplicate payment in web chat",
        },
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["public_id"].startswith("OMNI-")
    assert conversation["access_token"].startswith("ow1.")
    assert conversation["messages"][0]["channel"] == "chat"

    ticket = client.get(f"/api/v1/tickets/{conversation['ticket_id']}").json()["ticket"]
    assert ticket["channel"] == "chat"
    assert "web-widget" in ticket["tags"]

    unauthorized = public_client.get(
        f"/api/v1/widget/ng/conversations/{conversation['public_id']}"
    )
    assert unauthorized.status_code == 401

    headers = {"Authorization": f"Widget {conversation['access_token']}"}
    viewed = public_client.get(
        f"/api/v1/widget/ng/conversations/{conversation['public_id']}",
        headers=headers,
    )
    assert viewed.status_code == 200
    assert viewed.json()["access_token"] is None

    client.patch(f"/api/v1/tickets/{conversation['ticket_id']}", json={"status": "solved"})
    replied = public_client.post(
        f"/api/v1/widget/ng/conversations/{conversation['public_id']}/messages",
        headers=headers,
        json={"body": "The charge is still present. Please reopen this conversation."},
    )
    assert replied.status_code == 201, replied.text
    assert replied.json()["status"] == "open"
    assert any("Please reopen" in message["body"] for message in replied.json()["messages"])

    with Session(get_engine()) as db:
        audit = db.scalar(
            select(AuditEventRecord).where(
                AuditEventRecord.entity_id == conversation["ticket_id"],
                AuditEventRecord.action == "ticket.web_widget_reply",
            )
        )
        assert audit is not None
        assert audit.actor == "customer-widget"


def test_widget_supports_anonymous_conversation_when_email_collection_is_disabled(
    client: TestClient,
) -> None:
    client.patch(
        "/api/v1/widget-settings",
        json={"enabled": True, "collect_email": False},
    )
    public_client = TestClient(create_app())

    created = public_client.post(
        "/api/v1/widget/ng/conversations",
        json={
            "name": "Anonymous visitor",
            "visitor_id": "visitor-browser-session-1",
            "message": "Can someone explain the change fee for this itinerary?",
        },
    )

    assert created.status_code == 201, created.text
    ticket_id = created.json()["ticket_id"]
    with Session(get_engine()) as db:
        ticket = db.get(TicketRecord, ticket_id)
        assert ticket is not None
        customer = db.get(CustomerRecord, ticket.customer_id)
        assert customer is not None
        assert customer.email.startswith("widget-")
        assert customer.email.endswith("@example.com")
        outbound = db.scalar(
            select(OutboundMessageRecord).where(OutboundMessageRecord.ticket_id == ticket_id)
        )
        assert outbound is None


def test_widget_rejects_new_conversation_when_disabled() -> None:
    public_client = TestClient(create_app())

    response = public_client.post(
        "/api/v1/widget/ng/conversations",
        json={
            "name": "Disabled Widget Visitor",
            "email": "disabled-widget@example.com",
            "message": "This should not create a support conversation.",
        },
    )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"].lower()
