from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.integration_credentials import integration_credential_settings_repository
from app.db.session import get_engine


def _agent_payload(name: str = "Booking support agent", *, auto_send: bool = False) -> dict:
    return {
        "name": name,
        "description": "Answers booking questions and hands complex cases to an operator.",
        "instructions": (
            "Use approved knowledge only. Ask for the booking reference, explain the next step, "
            "and hand off whenever identity or payment status is uncertain."
        ),
        "channels": ["email", "whatsapp"],
        "languages": ["en"],
        "handoff_team": "General Support",
        "confidence_threshold": 82,
        "auto_send": auto_send,
    }


def _configure_anthropic_for_nigeria() -> None:
    with Session(get_engine()) as db:
        record = integration_credential_settings_repository.get_or_create(
            db,
            market_id="market-ng",
        )
        record.ai_provider = "anthropic"
        record.anthropic_api_key = "test-anthropic-key"
        record.anthropic_model = "claude-test-model"
        db.commit()


def test_ai_agent_draft_is_durable_and_activation_requires_provider(client: TestClient) -> None:
    readiness = client.get("/api/v1/ai/readiness")
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["provider"] == "Anthropic"
    assert readiness.json()["configured"] is False
    assert "not configured" in readiness.json()["detail"].lower()

    created = client.post("/api/v1/ai/agents", json=_agent_payload())
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["status"] == "draft"
    assert agent["channels"] == ["email", "whatsapp"]

    listed = client.get("/api/v1/ai/agents")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [agent["id"]]

    activation = client.patch(
        f"/api/v1/ai/agents/{agent['id']}",
        json={"status": "active"},
    )
    assert activation.status_code == 409
    assert "anthropic" in activation.text.lower()

    auto_send_policy = client.patch(
        "/api/v1/ai/policy",
        json={"can_send_customer_messages": True},
    )
    assert auto_send_policy.status_code == 409


def test_ai_agent_activation_and_policy_are_guarded_and_audited(client: TestClient) -> None:
    _configure_anthropic_for_nigeria()

    policy = client.patch(
        "/api/v1/ai/policy",
        json={"automation_enabled": True, "can_send_customer_messages": True},
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["configured"] is True
    assert policy.json()["model"] == "claude-test-model"
    assert policy.json()["can_send_customer_messages"] is True

    created = client.post(
        "/api/v1/ai/agents",
        json=_agent_payload("Auto booking agent", auto_send=True),
    )
    assert created.status_code == 201, created.text
    agent = created.json()

    activated = client.patch(
        f"/api/v1/ai/agents/{agent['id']}",
        json={"status": "active"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert activated.json()["auto_send"] is True

    readiness = client.get("/api/v1/ai/readiness")
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["active_agents"] == 1

    disable_auto_send = client.patch(
        "/api/v1/ai/policy",
        json={"can_send_customer_messages": False},
    )
    assert disable_auto_send.status_code == 409
    assert "pause" in disable_auto_send.text.lower()

    disable_automation = client.patch(
        "/api/v1/ai/policy",
        json={"automation_enabled": False},
    )
    assert disable_automation.status_code == 409
    assert "pause" in disable_automation.text.lower()

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200, audit.text
    actions = {event["action"] for event in audit.json()}
    assert "ai_policy.update" in actions
    assert "ai_agent.create" in actions
    assert "ai_agent.update" in actions


def test_ai_studio_is_market_scoped_and_requires_admin_for_changes(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    created = client.post("/api/v1/ai/agents", json=_agent_payload("Nigeria draft"))
    assert created.status_code == 201, created.text

    gh_headers = login_as("kofi.gh@omniticket.example.com", market_id="market-gh")
    gh_list = client.get("/api/v1/ai/agents", headers=gh_headers)
    assert gh_list.status_code == 200, gh_list.text
    assert gh_list.json() == []

    forbidden = client.post(
        "/api/v1/ai/agents",
        headers=gh_headers,
        json=_agent_payload("Agent cannot create"),
    )
    assert forbidden.status_code == 403

    policy_forbidden = client.patch(
        "/api/v1/ai/policy",
        headers=gh_headers,
        json={"automation_enabled": False},
    )
    assert policy_forbidden.status_code == 403


def test_ai_decisions_are_real_market_scoped_records(client: TestClient) -> None:
    response = client.get("/api/v1/ai/decisions", params={"limit": 10})
    assert response.status_code == 200, response.text
    decisions = response.json()
    assert all(decision["ticket_id"] for decision in decisions)
    assert all(decision["ticket_number"].startswith("OMNI-") for decision in decisions)
    assert all(isinstance(decision["confidence"], int) for decision in decisions)
