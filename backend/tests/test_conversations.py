from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ConnectorAccountRecord
from app.db.session import get_engine
from app.services import attachments as attachment_services


def _customer_id(client: TestClient) -> str:
    response = client.get("/api/v1/customers")
    assert response.status_code == 200, response.text
    return response.json()[0]["id"]


def _create_conversation(client: TestClient, customer_id: str, *, subject: str = "Chat help") -> dict:
    response = client.post(
        "/api/v1/conversations",
        json={
            "customer_id": customer_id,
            "channel": "whatsapp",
            "subject": subject,
            "priority": "high",
            "initial_message": "I need help with my booking.",
            "initial_sender": "customer",
        },
    )
    assert response.status_code == 201, response.text
    assert response.headers["etag"] == '"1"'
    return response.json()


def test_conversation_lifecycle_is_versioned_and_market_scoped(client: TestClient) -> None:
    customer_id = _customer_id(client)
    topic_response = client.post(
        "/api/v1/conversation-topics",
        json={"name": "Booking changes", "description": "Date and route changes"},
    )
    assert topic_response.status_code == 201, topic_response.text
    topic = topic_response.json()

    conversation = _create_conversation(client, customer_id)
    conversation_id = conversation["id"]
    update = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"expected_version": 1, "topic_id": topic["id"], "subject": "Date change"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["version"] == 2
    assert update.headers["etag"] == '"2"'

    stale = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"expected_version": 1, "subject": "Stale edit"},
    )
    assert stale.status_code == 412
    assert stale.json()["detail"]["current_version"] == 2

    listed = client.get("/api/v1/conversations?status=open&channel=whatsapp&limit=10")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [conversation_id]
    assert listed.json()["has_more"] is False


def test_messages_private_notes_receipts_and_context_use_real_records(
    client: TestClient,
) -> None:
    customer_id = _customer_id(client)
    conversation = _create_conversation(client, customer_id)
    conversation_id = conversation["id"]

    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert messages.status_code == 200, messages.text
    initial_message = messages.json()["items"][0]
    assert initial_message["sender_type"] == "customer"
    assert initial_message["delivery_state"] == "received"

    receipt = client.post(
        f"/api/v1/conversations/{conversation_id}/receipts",
        json={"message_id": initial_message["id"], "receipt_type": "read"},
    )
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["receipt_type"] == "read"
    duplicate_receipt = client.post(
        f"/api/v1/conversations/{conversation_id}/receipts",
        json={"message_id": initial_message["id"], "receipt_type": "read"},
    )
    assert duplicate_receipt.status_code == 201
    assert duplicate_receipt.json()["id"] == receipt.json()["id"]

    note = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "expected_version": 1,
            "body": "Verify the fare rules before replying.",
            "visibility": "private",
            "idempotency_key": "note-1",
        },
    )
    assert note.status_code == 201, note.text
    assert note.json()["delivery_state"] == "internal"
    duplicate_note = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "expected_version": 2,
            "body": "Verify the fare rules before replying.",
            "visibility": "private",
            "idempotency_key": "note-1",
        },
    )
    assert duplicate_note.status_code == 201, duplicate_note.text
    assert duplicate_note.json()["id"] == note.json()["id"]

    conversation = client.get(f"/api/v1/conversations/{conversation_id}").json()
    reply = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "expected_version": conversation["version"],
            "body": "We are checking the fare rules now.",
            "visibility": "public",
            "idempotency_key": "reply-1",
        },
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["delivery_state"] == "failed"
    assert "outbound replies" in reply.json()["metadata"]["delivery_error"].lower()
    outbound = client.get("/api/v1/outbound/messages")
    assert outbound.status_code == 200, outbound.text
    queued_reply = next(
        item
        for item in outbound.json()
        if item["chat_message_id"] == reply.json()["id"]
    )
    assert queued_reply["ticket_id"] is None
    assert queued_reply["conversation_id"] == conversation_id
    assert queued_reply["status"] == "failed"
    assert queued_reply["payload"]["source"] == "conversation_reply"

    context = client.get(f"/api/v1/conversations/{conversation_id}/context")
    assert context.status_code == 200, context.text
    assert context.json()["customer"]["id"] == customer_id
    assert context.json()["case"]["customer_id"] == customer_id
    assert "resolve" in context.json()["allowed_actions"]


def test_public_conversation_reply_uses_configured_outbound_adapter(
    client: TestClient,
) -> None:
    customer_id = _customer_id(client)
    conversation = _create_conversation(client, customer_id)
    with Session(get_engine()) as session:
        account = session.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == "market-ng",
                ConnectorAccountRecord.provider == "whatsapp",
            )
        )
        assert account is not None
        account.status = "mocked"
        account.outbound_enabled = True
        account.secret_configured = True
        session.commit()

    reply = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "expected_version": conversation["version"],
            "body": "Your booking is confirmed.",
            "visibility": "public",
            "idempotency_key": "reply-local-provider",
        },
    )

    assert reply.status_code == 201, reply.text
    assert reply.json()["delivery_state"] == "sent"
    assert reply.json()["provider_message_id"].startswith("local-dev:")
    assert reply.json()["metadata"]["delivery_status"] == "sent"


def test_conversation_attachments_are_scanned_stored_linked_and_audited(
    client: TestClient,
    tmp_path,
    monkeypatch,
) -> None:
    storage = attachment_services.LocalAttachmentStorage(str(tmp_path / "attachments"))
    monkeypatch.setattr(attachment_services, "attachment_storage", storage)
    customer_id = _customer_id(client)
    conversation = _create_conversation(client, customer_id)

    upload = client.post(
        f"/api/v1/conversations/{conversation['id']}/attachments/binary",
        params={"filename": "booking-confirmation.txt"},
        content=b"Booking confirmed for WAK-2026.",
        headers={"Content-Type": "text/plain"},
    )

    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    assert attachment["scan_status"] == "clean"
    assert attachment["lifecycle_status"] == "active"
    assert attachment["storage_provider"] == "local"
    assert attachment["retained_until"] is not None

    reply = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "expected_version": conversation["version"],
            "body": "Your booking confirmation is attached.",
            "visibility": "public",
            "content": {"attachment_ids": [attachment["id"]]},
            "idempotency_key": "reply-with-attachment",
        },
    )
    assert reply.status_code == 201, reply.text
    context = client.get(
        f"/api/v1/conversations/{conversation['id']}/context"
    ).json()
    linked_attachment = next(
        item for item in context["attachments"] if item["id"] == attachment["id"]
    )
    assert linked_attachment["message_id"] == reply.json()["id"]

    outbound = client.get("/api/v1/outbound/messages").json()
    outbound_reply = next(
        item for item in outbound if item["chat_message_id"] == reply.json()["id"]
    )
    assert outbound_reply["payload"]["attachment_ids"] == [attachment["id"]]

    download = client.get(
        f"/api/v1/conversations/{conversation['id']}/attachments/"
        f"{attachment['id']}/download"
    )
    assert download.status_code == 200
    assert download.content == b"Booking confirmed for WAK-2026."
    link = client.post(
        f"/api/v1/conversations/{conversation['id']}/attachments/"
        f"{attachment['id']}/download-link"
    )
    assert link.status_code == 200, link.text
    signed_download = TestClient(client.app).get(link.json()["url"])
    assert signed_download.status_code == 200
    assert signed_download.content == download.content

    deleted = client.request(
        "DELETE",
        f"/api/v1/conversations/{conversation['id']}/attachments/{attachment['id']}",
        json={"reason": "Retention test", "purge_storage": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["lifecycle_status"] == "purged"
    assert deleted.json()["purged_at"] is not None
    assert client.get(
        f"/api/v1/conversations/{conversation['id']}/attachments/"
        f"{attachment['id']}/download"
    ).status_code == 403


def test_conversation_attachment_blocks_dangerous_file_types(
    client: TestClient,
    tmp_path,
    monkeypatch,
) -> None:
    storage = attachment_services.LocalAttachmentStorage(str(tmp_path / "attachments"))
    monkeypatch.setattr(attachment_services, "attachment_storage", storage)
    conversation = _create_conversation(client, _customer_id(client))

    upload = client.post(
        f"/api/v1/conversations/{conversation['id']}/attachments/binary",
        params={"filename": "payload.exe"},
        content=b"not-an-executable",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert upload.status_code == 201, upload.text
    assert upload.json()["scan_status"] == "blocked"
    assert "not allowed" in upload.json()["scan_result"].lower()
    assert client.get(
        f"/api/v1/conversations/{conversation['id']}/attachments/"
        f"{upload.json()['id']}/download"
    ).status_code == 403


def test_assignment_status_saved_views_flags_and_one_active_case(client: TestClient) -> None:
    customer_id = _customer_id(client)
    first = _create_conversation(client, customer_id, subject="First inquiry")
    second = _create_conversation(client, customer_id, subject="Second inquiry")
    first_context = client.get(f"/api/v1/conversations/{first['id']}/context").json()
    second_context = client.get(f"/api/v1/conversations/{second['id']}/context").json()
    assert first_context["case"]["id"] == second_context["case"]["id"]

    groups = client.get("/api/v1/support-groups").json()
    assignment = client.post(
        f"/api/v1/conversations/{first['id']}/assignment",
        json={
            "expected_version": first["version"],
            "group_id": groups[0]["id"],
            "reason": "Route by booking skill",
        },
    )
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()["assigned_group_id"] == groups[0]["id"]

    intelli_assignment = client.post(
        f"/api/v1/conversations/{second['id']}/intelli-assign",
        json={"expected_version": second["version"]},
    )
    assert intelli_assignment.status_code == 200, intelli_assignment.text
    assert intelli_assignment.json()["assignee_id"] is not None
    intelli_context = client.get(
        f"/api/v1/conversations/{second['id']}/context"
    ).json()
    assert any(
        "selected least-loaded operator" in item["reason"]
        for item in intelli_context["assignments"]
    )

    resolved = client.post(
        f"/api/v1/conversations/{first['id']}/resolve",
        json={"expected_version": assignment.json()["version"], "reason": "Answered"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    reopened = client.post(
        f"/api/v1/conversations/{first['id']}/reopen",
        json={"expected_version": resolved.json()["version"], "reason": "Customer replied"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"
    assert reopened.json()["reopened_at"] is not None

    view = client.post(
        "/api/v1/conversation-views",
        json={"name": "My WhatsApp", "filters": {"channel": "whatsapp"}},
    )
    assert view.status_code == 201, view.text
    filtered = client.get(f"/api/v1/conversations?view_id={view.json()['id']}")
    assert filtered.status_code == 200
    assert len(filtered.json()["items"]) == 2

    before = client.get("/api/v1/features")
    assert before.status_code == 200
    assert all(item["available"] is False for item in before.json())
    enabled = client.put(
        "/api/v1/features/omnichat_parity",
        json={"enabled": True, "allowed_roles": ["admin"], "allowed_user_ids": []},
    )
    assert enabled.status_code == 200, enabled.text
    after = client.get("/api/v1/features").json()
    capability = next(item for item in after if item["key"] == "omnichat_parity")
    assert capability["available"] is True


def test_ticket_workspace_is_consolidated_and_version_aware(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets?limit=1").json()[0]
    workspace = client.get(f"/api/v1/tickets/{ticket['id']}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    assert payload["ticket"]["version"] >= 1
    assert payload["customer"]["id"] == ticket["customer_id"]
    assert isinstance(payload["timeline"], list)
    assert isinstance(payload["time_entries"], list)
    assert isinstance(payload["suggestions"]["knowledge"], list)
    assert "reply" in payload["allowed_actions"]

    current = payload["ticket"]
    updated = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={"expected_version": current["version"], "priority": "high"},
    )
    assert updated.status_code == 200, updated.text
    stale = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={"expected_version": current["version"], "priority": "low"},
    )
    assert stale.status_code == 412
