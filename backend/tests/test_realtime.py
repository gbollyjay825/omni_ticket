from fastapi.testclient import TestClient

from app.main import create_app


def test_ticket_changes_create_durable_realtime_events(client: TestClient) -> None:
    customer = client.get("/api/v1/customers").json()[0]
    created = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer["id"],
            "subject": "Realtime delivery test",
            "description": "Please keep every connected workspace synchronized.",
            "channel": "email",
        },
    )
    assert created.status_code == 201, created.text

    page = client.get("/api/v1/realtime/events?limit=100")
    assert page.status_code == 200, page.text
    events = page.json()["events"]
    ticket_events = [
        event
        for event in events
        if event["aggregate_type"] == "ticket"
        and event["aggregate_id"] == created.json()["id"]
    ]
    assert any(event["type"] == "ticket.created" for event in ticket_events)
    assert all(event["market_id"] == "market-ng" for event in events)
    assert all(event["organization_id"] == "wakanow" for event in events)

    cursor = page.json()["cursor"]
    updated = client.patch(
        f"/api/v1/tickets/{created.json()['id']}",
        json={"priority": "urgent"},
    )
    assert updated.status_code == 200, updated.text

    resumed = client.get(f"/api/v1/realtime/events?cursor={cursor}&limit=100")
    assert resumed.status_code == 200, resumed.text
    assert any(
        event["type"] == "ticket.updated"
        and event["aggregate_id"] == created.json()["id"]
        for event in resumed.json()["events"]
    )


def test_realtime_cursor_is_market_scoped(client: TestClient) -> None:
    response = client.get("/api/v1/realtime/events?cursor=event_missing")

    assert response.status_code == 409
    assert "cursor" in response.json()["detail"].lower()


def test_realtime_websocket_authenticates_and_handles_client_events(
    client: TestClient,
) -> None:
    token = client.headers["Authorization"].split(" ", 1)[1]
    ticket = client.get("/api/v1/tickets").json()[0]
    message = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()[0]
    authenticated_user = client.get("/api/v1/auth/me").json()["user"]
    with client.websocket_connect(
        "/api/v1/realtime?market_id=market-ng",
        subprotocols=["omni.realtime.v1", f"bearer.{token}"],
    ) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "realtime.ready"
        assert ready["market_id"] == "market-ng"
        assert ready["fanout"] == "database-poll"

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json()["type"] == "pong"

        websocket.send_json(
            {
                "type": "typing.updated",
                "aggregate_id": ticket["id"],
                "payload": {
                    "typing": True,
                    "user_id": "forged-user",
                    "user_name": "Forged name",
                },
            }
        )
        typing_event = websocket.receive_json()
        assert typing_event["type"] == "typing.updated"
        assert typing_event["payload"]["typing"] is True
        assert typing_event["payload"]["user_id"] == authenticated_user["id"]
        assert typing_event["payload"]["user_name"] == authenticated_user["name"]

        websocket.send_json(
            {
                "type": "message.read",
                "aggregate_id": ticket["id"],
                "payload": {
                    "message_id": message["id"],
                    "user_id": "forged-user",
                    "user_name": "Forged name",
                },
            }
        )
        read_event = websocket.receive_json()
        assert read_event["type"] == "message.read"
        assert read_event["aggregate_id"] == ticket["id"]
        assert read_event["payload"]["message_id"] == message["id"]
        assert read_event["payload"]["user_id"] == authenticated_user["id"]
        assert read_event["payload"]["user_name"] == authenticated_user["name"]

        websocket.send_json(
            {
                "type": "message.read",
                "aggregate_id": "ticket-from-another-market",
                "payload": {"message_id": message["id"]},
            }
        )
        invalid_event = websocket.receive_json()
        assert invalid_event == {
            "type": "realtime.error",
            "detail": "Conversation was not found in the active market",
        }

        websocket.send_json(
            {
                "type": "presence.updated",
                "aggregate_id": "another-user",
                "payload": {"online": True},
            }
        )
        invalid_presence = websocket.receive_json()
        assert invalid_presence == {
            "type": "realtime.error",
            "detail": "Presence can only be updated for the authenticated user",
        }


def test_realtime_websocket_accepts_browser_session_cookie() -> None:
    browser = TestClient(create_app())
    login = browser.post(
        "/api/v1/auth/browser/login",
        json={"email": "gbolahan@omniticket.example.com", "password": "omni-demo"},
    )
    assert login.status_code == 200

    with browser.websocket_connect(
        "/api/v1/realtime?market_id=market-ng",
        subprotocols=["omni.realtime.v1"],
    ) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "realtime.ready"
        assert ready["market_id"] == "market-ng"


def test_realtime_websocket_discards_ephemeral_resume_cursor(client: TestClient) -> None:
    token = client.headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(
        "/api/v1/realtime?market_id=market-ng&cursor=ephemeral_stale-browser-cursor",
        subprotocols=["omni.realtime.v1", f"bearer.{token}"],
    ) as websocket:
        ready = websocket.receive_json()

    assert ready["type"] == "realtime.ready"
    cursor = ready["cursor"]
    assert cursor is None or cursor.startswith("event_")
