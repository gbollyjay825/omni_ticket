import imaplib
import smtplib

from fastapi.testclient import TestClient
import pytest

from app.services import email_connection


def _save_email_settings(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/email/settings",
        json={
            "inbound_enabled": True,
            "inbound_host": "imap.gmail.test",
            "inbound_port": 993,
            "inbound_username": "omni-test@wakanow.com",
            "inbound_password": "imap-app-password",
            "inbound_mailbox": "INBOX",
            "inbound_use_ssl": True,
            "outbound_enabled": True,
            "outbound_host": "smtp.gmail.test",
            "outbound_port": 587,
            "outbound_username": "omni-test@wakanow.com",
            "outbound_password": "smtp-app-password",
            "outbound_from_email": "omni-test@wakanow.com",
            "outbound_use_starttls": True,
            "outbound_use_ssl": False,
        },
    )
    assert response.status_code == 200


def test_email_connection_test_authenticates_imap_and_smtp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _save_email_settings(client)
    events: list[tuple[object, ...]] = []

    class FakeImap:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            events.append(("imap-connect", host, port, timeout))

        def login(self, username: str, password: str) -> None:
            events.append(("imap-login", username, password))

        def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
            events.append(("imap-select", mailbox, readonly))
            return "OK", [b"0"]

        def logout(self) -> None:
            events.append(("imap-logout",))

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            events.append(("smtp-connect", host, port, timeout))

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            events.append(("smtp-close",))

        def ehlo(self) -> None:
            events.append(("smtp-ehlo",))

        def starttls(self, *, context: object) -> None:
            events.append(("smtp-starttls", context is not None))

        def login(self, username: str, password: str) -> None:
            events.append(("smtp-login", username, password))

        def noop(self) -> None:
            events.append(("smtp-noop",))

    monkeypatch.setattr(email_connection.imaplib, "IMAP4_SSL", FakeImap)
    monkeypatch.setattr(email_connection.smtplib, "SMTP", FakeSmtp)

    response = client.post("/api/v1/email/settings/test")

    assert response.status_code == 200
    result = response.json()
    assert result["inbound"]["connected"] is True
    assert result["outbound"]["connected"] is True
    assert "imap-app-password" not in response.text
    assert "smtp-app-password" not in response.text
    assert ("imap-select", "INBOX", True) in events
    assert ("smtp-login", "omni-test@wakanow.com", "smtp-app-password") in events


def test_email_connection_test_reports_provider_auth_failures(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _save_email_settings(client)

    class FailingImap:
        def __init__(self, _host: str, _port: int, timeout: int) -> None:
            self.timeout = timeout

        def login(self, _username: str, _password: str) -> None:
            raise imaplib.IMAP4.error("Application-specific password required")

        def logout(self) -> None:
            return None

    class FailingSmtp:
        def __init__(self, _host: str, _port: int, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FailingSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def starttls(self, *, context: object) -> None:
            assert context is not None

        def login(self, _username: str, _password: str) -> None:
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    monkeypatch.setattr(email_connection.imaplib, "IMAP4_SSL", FailingImap)
    monkeypatch.setattr(email_connection.smtplib, "SMTP", FailingSmtp)

    response = client.post("/api/v1/email/settings/test")

    assert response.status_code == 200
    result = response.json()
    assert result["inbound"] == {
        "configured": True,
        "connected": False,
        "detail": "Gmail requires an app password for this mailbox.",
    }
    assert result["outbound"]["connected"] is False
    assert "closed the connection" in result["outbound"]["detail"]
    assert "app password" in result["outbound"]["detail"]
