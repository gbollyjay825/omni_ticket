from fastapi.testclient import TestClient


def _customer_id(client: TestClient) -> str:
    response = client.get("/api/v1/customers")
    assert response.status_code == 200, response.text
    return response.json()[0]["id"]


def test_ticket_saved_view_filters_real_records_and_can_be_archived(client: TestClient) -> None:
    customer_id = _customer_id(client)
    created = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer_id,
            "subject": "Saved view verification",
            "description": "A real ticket for the saved view contract.",
            "channel": "email",
            "priority": "high",
            "tags": ["saved-view-verification"],
        },
    )
    assert created.status_code == 201, created.text

    view_response = client.post(
        "/api/v1/ticket-views",
        json={
            "name": "High priority verification",
            "filters": {
                "priority": "high",
                "tag": "saved-view-verification",
                "created_period": "today",
            },
            "sort_by": "created_at",
            "sort_order": "desc",
            "shared": False,
        },
    )
    assert view_response.status_code == 201, view_response.text
    view = view_response.json()
    assert view["owner_user_id"] is not None

    listed_views = client.get("/api/v1/ticket-views")
    assert listed_views.status_code == 200, listed_views.text
    assert view["id"] in {item["id"] for item in listed_views.json()}

    tickets = client.get(f"/api/v1/tickets?view_id={view['id']}")
    assert tickets.status_code == 200, tickets.text
    assert [item["id"] for item in tickets.json()] == [created.json()["id"]]
    assert tickets.headers["x-total-count"] == "1"

    archived = client.patch(
        f"/api/v1/ticket-views/{view['id']}",
        json={"active": False},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["active"] is False
    assert view["id"] not in {item["id"] for item in client.get("/api/v1/ticket-views").json()}


def test_ticket_saved_view_rejects_duplicate_names(client: TestClient) -> None:
    payload = {"name": "My active tickets", "filters": {"status": "open"}}
    assert client.post("/api/v1/ticket-views", json=payload).status_code == 201
    duplicate = client.post("/api/v1/ticket-views", json=payload)
    assert duplicate.status_code == 409
