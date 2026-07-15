from fastapi.testclient import TestClient


def _pick_two_tickets(tickets: list[dict]) -> tuple[str, list[str]]:
    """Prefer two tickets from the same customer; fall back to any two."""
    by_customer: dict[str, list[dict]] = {}
    for ticket in tickets:
        by_customer.setdefault(ticket["customer_id"], []).append(ticket)
    pair = next((group for group in by_customer.values() if len(group) >= 2), tickets[:2])
    return pair[0]["customer_id"], [pair[0]["id"], pair[1]["id"]]


def _pick_cross_customer_tickets(tickets: list[dict]) -> tuple[dict, dict]:
    first = tickets[0]
    other = next(
        (ticket for ticket in tickets if ticket["customer_id"] != first["customer_id"]), None
    )
    assert other is not None, "case tests need tickets from at least two customers"
    return first, other


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

    # A case cannot close while any child ticket is active.
    blocked = client.patch(f"/api/v1/cases/{case_id}", json={"status": "resolved"})
    assert blocked.status_code == 422, blocked.text
    for ticket_id in ticket_ids:
        solved = client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "solved"})
        assert solved.status_code == 200, solved.text

    # Update status after all child work is resolved.
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


def test_case_rejects_tickets_from_a_different_customer(client: TestClient) -> None:
    tickets = client.get("/api/v1/tickets").json()
    first, other = _pick_cross_customer_tickets(tickets)

    created = client.post(
        "/api/v1/cases",
        json={
            "customer_id": first["customer_id"],
            "title": "Wrong customer guard",
            "ticket_ids": [first["id"], other["id"]],
        },
    )
    assert created.status_code == 400, created.text
    assert "different customer" in created.json()["detail"]

    case = client.post(
        "/api/v1/cases",
        json={
            "customer_id": first["customer_id"],
            "title": "Single customer case",
            "ticket_ids": [first["id"]],
        },
    ).json()
    attached = client.post(f"/api/v1/cases/{case['id']}/tickets", json={"ticket_id": other["id"]})
    assert attached.status_code == 400, attached.text
    assert "different customer" in attached.json()["detail"]


def test_case_404_for_unknown_id(client: TestClient) -> None:
    assert client.get("/api/v1/cases/case_does_not_exist").status_code == 404


def test_new_tickets_reuse_one_active_case_per_customer_and_market(client: TestClient) -> None:
    customer = client.get("/api/v1/customers").json()[0]

    first = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer["id"],
            "subject": "Payment review",
            "description": "Please review my payment.",
            "channel": "email",
        },
    )
    second = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer["id"],
            "subject": "More payment evidence",
            "description": "I have attached another receipt.",
            "channel": "whatsapp",
        },
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["case_id"]
    assert second.json()["case_id"] == first.json()["case_id"]

    active_cases = [
        case
        for case in client.get("/api/v1/cases").json()
        if case["customer_id"] == customer["id"] and case["status"] == "open"
    ]
    assert len(active_cases) == 1
    assert {first.json()["id"], second.json()["id"]} <= set(active_cases[0]["ticket_ids"])
