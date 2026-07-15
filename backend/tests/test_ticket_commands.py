from fastapi.testclient import TestClient


def _first_ticket(client: TestClient) -> dict:
    response = client.get("/api/v1/tickets", params={"limit": 1})
    assert response.status_code == 200
    return response.json()[0]


def test_ticket_child_task_is_persisted_in_workspace(client: TestClient) -> None:
    ticket = _first_ticket(client)

    created = client.post(
        f"/api/v1/tickets/{ticket['id']}/tasks",
        json={
            "expected_version": ticket["version"],
            "label": "Confirm refund approval",
        },
    )

    assert created.status_code == 201
    created_ticket = created.json()
    assert created_ticket["version"] > ticket["version"]
    assert created_ticket["tasks"][-1]["label"] == "Confirm refund approval"
    assert created_ticket["tasks"][-1]["complete"] is False

    workspace = client.get(f"/api/v1/tickets/{ticket['id']}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["tasks"] == created_ticket["tasks"]
    assert any(
        event["metadata"].get("task_id") == created_ticket["tasks"][-1]["id"]
        for event in workspace.json()["timeline"]
    )


def test_ticket_commands_reject_a_stale_version(client: TestClient) -> None:
    ticket = _first_ticket(client)
    updated = client.post(
        f"/api/v1/tickets/{ticket['id']}/tasks",
        json={"expected_version": ticket["version"], "label": "First task"},
    )
    assert updated.status_code == 201

    stale = client.post(
        f"/api/v1/tickets/{ticket['id']}/tasks",
        json={"expected_version": ticket["version"], "label": "Stale task"},
    )

    assert stale.status_code == 412
    assert stale.json()["detail"]["current_version"] == updated.json()["version"]


def test_ticket_forward_uses_the_durable_email_queue(client: TestClient) -> None:
    ticket = _first_ticket(client)

    forwarded = client.post(
        f"/api/v1/tickets/{ticket['id']}/forward",
        json={
            "expected_version": ticket["version"],
            "to_email": "operations@wakanow.com",
            "subject": f"Fwd: {ticket['subject']}",
            "body": "Please review this customer request.",
            "idempotency_key": f"forward-test-{ticket['id']}",
        },
    )

    assert forwarded.status_code == 200
    event = forwarded.json()
    assert event["type"] == "forwarded"
    assert event["public"] is False
    assert event["metadata"]["to_email"] == "operations@wakanow.com"

    messages = client.get(
        "/api/v1/outbound/messages",
        params={"ticket_id": ticket["id"]},
    )
    assert messages.status_code == 200
    outbound = next(
        item for item in messages.json() if item["payload"].get("source") == "ticket_forward"
    )
    assert outbound["provider"] == "email"
    assert outbound["payload"]["to_email"] == "operations@wakanow.com"
    assert outbound["payload"]["subject"] == f"Fwd: {ticket['subject']}"
    assert outbound["status"] in {"queued", "sent", "failed", "retrying"}
