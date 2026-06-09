from fastapi.testclient import TestClient


def _pick_two_tickets(tickets: list[dict]) -> tuple[str, list[str]]:
    """Prefer two tickets from the same customer; fall back to any two."""
    by_customer: dict[str, list[dict]] = {}
    for ticket in tickets:
        by_customer.setdefault(ticket["customer_id"], []).append(ticket)
    pair = next((group for group in by_customer.values() if len(group) >= 2), tickets[:2])
    return pair[0]["customer_id"], [pair[0]["id"], pair[1]["id"]]


def test_case_groups_tickets_and_supports_attach_detach(client: TestClient) -> None:
    tickets = client.get("/api/v1/tickets").json()
    assert len(tickets) >= 2
    customer_id, ticket_ids = _pick_two_tickets(tickets)

    created = client.post(
        "/api/v1/cases",
        json={
            "customer_id": customer_id,
            "title": "Duplicate charge follow-up",
            "summary": "Customer reached out on multiple channels about the same charge.",
            "ticket_ids": ticket_ids,
        },
    )
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["public_id"].startswith("CASE-")
    assert case["ticket_count"] == 2
    assert set(case["ticket_ids"]) == set(ticket_ids)
    assert len(case["channels"]) >= 1
    case_id = case["id"]

    # Each grouped ticket now references the case.
    refreshed = {ticket["id"]: ticket for ticket in client.get("/api/v1/tickets").json()}
    assert refreshed[ticket_ids[0]]["case_id"] == case_id
    assert refreshed[ticket_ids[1]]["case_id"] == case_id

    # List + detail.
    assert any(item["id"] == case_id for item in client.get("/api/v1/cases").json())
    assert client.get(f"/api/v1/cases/{case_id}").json()["ticket_count"] == 2

    # Detach one ticket.
    detached = client.delete(f"/api/v1/cases/{case_id}/tickets/{ticket_ids[0]}")
    assert detached.status_code == 200, detached.text
    assert detached.json()["ticket_count"] == 1
    after_detach = {ticket["id"]: ticket for ticket in client.get("/api/v1/tickets").json()}
    assert after_detach[ticket_ids[0]]["case_id"] is None

    # Re-attach it.
    attached = client.post(
        f"/api/v1/cases/{case_id}/tickets", json={"ticket_id": ticket_ids[0]}
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["ticket_count"] == 2

    # Update status.
    updated = client.patch(f"/api/v1/cases/{case_id}", json={"status": "resolved"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "resolved"


def test_case_and_ticket_case_id_appear_in_snapshot(client: TestClient) -> None:
    tickets = client.get("/api/v1/tickets").json()
    customer_id = tickets[0]["customer_id"]
    case = client.post(
        "/api/v1/cases",
        json={
            "customer_id": customer_id,
            "title": "Snapshot case",
            "ticket_ids": [tickets[0]["id"]],
        },
    ).json()

    snapshot = client.get("/api/v1/frontend/snapshot").json()
    assert "cases" in snapshot
    assert any(item["id"] == case["id"] for item in snapshot["cases"])

    def ticket_of(item: dict) -> dict:
        return item.get("ticket", item)

    assert any(ticket_of(item).get("case_id") == case["id"] for item in snapshot["tickets"])


def test_case_404_for_unknown_id(client: TestClient) -> None:
    assert client.get("/api/v1/cases/case_does_not_exist").status_code == 404
