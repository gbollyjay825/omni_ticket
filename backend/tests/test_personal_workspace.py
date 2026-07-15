from fastapi.testclient import TestClient


def test_personal_tasks_are_server_owned_and_user_scoped(client: TestClient) -> None:
    created = client.post("/api/v1/me/tasks", json={"label": "Review overdue queue"})
    assert created.status_code == 201, created.text
    assert created.json()["completed"] is False

    workspace = client.get("/api/v1/me/workspace")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["tasks"] == [created.json()]

    updated = client.patch(
        f"/api/v1/me/tasks/{created.json()['id']}",
        json={"completed": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["completed"] is True

    deleted = client.delete(f"/api/v1/me/tasks/{created.json()['id']}")
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/v1/me/workspace").json()["tasks"] == []


def test_ticket_watch_is_idempotent_and_persists_in_workspace(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]

    assert client.put(f"/api/v1/tickets/{ticket['id']}/watch").status_code == 204
    assert client.put(f"/api/v1/tickets/{ticket['id']}/watch").status_code == 204
    assert client.get("/api/v1/me/workspace").json()["watched_ticket_ids"] == [ticket["id"]]

    assert client.delete(f"/api/v1/tickets/{ticket['id']}/watch").status_code == 204
    assert client.get("/api/v1/me/workspace").json()["watched_ticket_ids"] == []


def test_time_entries_are_persisted_and_auditable_ticket_records(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    created = client.post(
        f"/api/v1/tickets/{ticket['id']}/time-entries",
        json={"minutes": 18, "note": "Reviewed payment evidence", "billable": False},
    )
    assert created.status_code == 201, created.text
    assert created.json()["minutes"] == 18
    assert created.json()["agent"] == "Gbolahan Salami"

    entries = client.get(f"/api/v1/tickets/{ticket['id']}/time-entries")
    assert entries.status_code == 200, entries.text
    assert entries.json() == [created.json()]

    deleted = client.delete(
        f"/api/v1/tickets/{ticket['id']}/time-entries/{created.json()['id']}"
    )
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/tickets/{ticket['id']}/time-entries").json() == []
