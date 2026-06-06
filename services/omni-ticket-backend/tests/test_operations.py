from collections.abc import Callable
from datetime import datetime, timedelta
from email.message import EmailMessage
import json
import time
from urllib import parse
from urllib.request import Request
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.webhooks import sign_webhook_body
from app.core.store import store
from app.db.alerts import operational_alert_repository
from app.db.models import (
    AnalyticsRollupRecord,
    AuditEventRecord,
    CustomerRecord,
    OidcLoginStateRecord,
    OutboundMessageRecord,
    SessionRecord,
    TicketRecord,
    UserRecord,
)
from app.db.session import get_engine
from app.main import create_app
from app.models.domain import OperationalAlertSeverity, utc_now
from app.services import identity as identity_service
from app.services import inbound_adapters, outbound_adapters
from app.services.alert_delivery import AlertWebhookResponse
from app.services.worker import worker_service


def _json_body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode()


def _signed_webhook_headers(account: dict, body: bytes, delivery_id: str) -> dict[str, str]:
    timestamp = int(time.time())
    return {
        "Content-Type": "application/json",
        "X-Omni-Timestamp": str(timestamp),
        "X-Omni-Signature": sign_webhook_body(
            account_id=account["id"],
            credential_ref=account["credential_ref"],
            timestamp=timestamp,
            body=body,
        ),
        "X-Omni-Delivery": delivery_id,
    }


def _ready_connector_account(client: TestClient, provider: str = "whatsapp") -> dict:
    account = next(
        item
        for item in client.get("/api/v1/connectors/accounts").json()
        if item["provider"] == provider
    )
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={
            "status": "connected",
            "intake_enabled": True,
            "secret_configured": True,
            "webhook_verified": True,
            "credential_ref": f"vault://omni/ng/{provider}/webhook-secret",
        },
    )
    assert response.status_code == 200
    return response.json()


def _enable_oidc(monkeypatch: pytest.MonkeyPatch, *, auto_provision: bool = False) -> None:
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_provider_name", "Wakanow SSO")
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://sso.wakanow.example")
    monkeypatch.setattr(settings, "oidc_authorization_url", "https://sso.wakanow.example/authorize")
    monkeypatch.setattr(settings, "oidc_token_url", "https://sso.wakanow.example/token")
    monkeypatch.setattr(settings, "oidc_userinfo_url", "https://sso.wakanow.example/userinfo")
    monkeypatch.setattr(settings, "oidc_client_id", "omni-client")
    monkeypatch.setattr(settings, "oidc_client_secret", "omni-secret")
    monkeypatch.setattr(settings, "oidc_redirect_url", "https://omni.wakanow.com/?auth=oidc")
    monkeypatch.setattr(settings, "oidc_allowed_email_domains", ["omniticket.example.com", "wakanow.com"])
    monkeypatch.setattr(settings, "oidc_auto_provision_enabled", auto_provision)
    monkeypatch.setattr(settings, "oidc_default_market_id", "market-ng" if auto_provision else None)
    monkeypatch.setattr(settings, "oidc_default_role", "agent")
    monkeypatch.setattr(settings, "oidc_require_email_verified", True)


class FakeOidcResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeOidcResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _fake_oidc_urlopen(userinfo: dict, captured: list[dict[str, object]]):
    def fake_urlopen(request: Request, timeout: int) -> FakeOidcResponse:
        request_data = request.data
        if request_data is None:
            encoded_body = ""
        else:
            assert isinstance(request_data, bytes)
            encoded_body = request_data.decode()
        captured.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "headers": dict(request.header_items()),
                "body": parse.parse_qs(encoded_body),
            }
        )
        if request.full_url == settings.oidc_token_url:
            return FakeOidcResponse({"access_token": "oidc-access-token", "token_type": "Bearer"})
        if request.full_url == settings.oidc_userinfo_url:
            return FakeOidcResponse(userinfo)
        raise AssertionError(f"Unexpected OIDC request: {request.full_url}")

    return fake_urlopen


def test_login_returns_user_and_available_markets(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["market"]["id"] == "market-ng"


def test_auth_success_and_market_selection_are_audited() -> None:
    anonymous = TestClient(create_app())
    login_response = anonymous.post(
        "/api/v1/auth/login",
        headers={"X-Request-ID": "trace-market-login"},
        json={
            "email": "gbolahan@omniticket.example.com",
            "password": "omni-demo",
            "market_id": "market-gh",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    audit_response = anonymous.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token}", "X-Omni-Market": "market-gh"},
    )
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert any(
        event["action"] == "auth.login.success"
        and event["details"]["request_id"] == "trace-market-login"
        for event in events
    )
    assert any(
        event["action"] == "auth.market.selected"
        and event["entity_id"] == "market-gh"
        and event["details"]["request_id"] == "trace-market-login"
        for event in events
    )


def test_oidc_config_is_public_and_pending_until_provider_is_configured() -> None:
    anonymous = TestClient(create_app())

    config_response = anonymous.get("/api/v1/auth/oidc/config")
    start_response = anonymous.get("/api/v1/auth/oidc/start?market_id=market-ng")

    assert config_response.status_code == 200
    config = config_response.json()
    assert config["enabled"] is False
    assert config["login_available"] is False
    assert "OMNI_OIDC_ENABLED=true" in config["missing_settings"]
    assert start_response.status_code == 503


def test_oidc_login_links_existing_user_and_creates_market_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_oidc(monkeypatch)
    captured_requests: list[dict[str, object]] = []
    monkeypatch.setattr(
        identity_service.urlrequest,
        "urlopen",
        _fake_oidc_urlopen(
            {
                "sub": "wakanow-subject-001",
                "email": "gbolahan@omniticket.example.com",
                "name": "Gbolahan Salami",
                "email_verified": True,
            },
            captured_requests,
        ),
    )
    anonymous = TestClient(create_app())

    config_response = anonymous.get("/api/v1/auth/oidc/config")
    start_response = anonymous.get("/api/v1/auth/oidc/start?market_id=market-ng")

    assert config_response.status_code == 200
    assert config_response.json()["login_available"] is True
    assert start_response.status_code == 200
    start = start_response.json()
    parsed_authorization = parse.urlparse(start["authorization_url"])
    authorization_query = parse.parse_qs(parsed_authorization.query)
    assert parsed_authorization.netloc == "sso.wakanow.example"
    assert authorization_query["client_id"] == ["omni-client"]
    assert authorization_query["code_challenge_method"] == ["S256"]
    assert authorization_query["state"] == [start["state"]]
    assert "code_challenge" in authorization_query

    callback_response = anonymous.post(
        "/api/v1/auth/oidc/callback",
        json={"code": "auth-code-123", "state": start["state"]},
    )

    assert callback_response.status_code == 200
    body = callback_response.json()
    assert body["user"]["email"] == "gbolahan@omniticket.example.com"
    assert body["market"]["id"] == "market-ng"
    assert body["user"]["external_identity_provider"] == "https://sso.wakanow.example"
    assert body["user"]["external_subject"] == "wakanow-subject-001"
    token_request = next(item for item in captured_requests if item["url"] == settings.oidc_token_url)
    token_body = token_request["body"]
    assert isinstance(token_body, dict)
    assert token_body["code"] == ["auth-code-123"]
    assert token_body["client_secret"] == ["omni-secret"]
    assert "code_verifier" in token_body
    userinfo_request = next(item for item in captured_requests if item["url"] == settings.oidc_userinfo_url)
    userinfo_headers = userinfo_request["headers"]
    assert isinstance(userinfo_headers, dict)
    assert userinfo_headers["Authorization"] == "Bearer oidc-access-token"

    with Session(get_engine()) as session:
        user = session.scalar(select(UserRecord).where(UserRecord.email == "gbolahan@omniticket.example.com"))
        assert user is not None
        assert user.external_subject == "wakanow-subject-001"
        assert user.external_last_login_at is not None
        state_record = session.scalar(select(OidcLoginStateRecord))
        assert state_record is not None
        assert state_record.used_at is not None
        sessions = session.scalars(select(SessionRecord).where(SessionRecord.user_id == user.id)).all()
        assert sessions

    audit_response = anonymous.get(
        "/api/v1/audit",
        headers={
            "Authorization": f"Bearer {body['access_token']}",
            "X-Omni-Market": "market-ng",
        },
    )
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert any(event["action"] == "user.oidc.linked" for event in audit)
    assert any(event["action"] == "auth.oidc.login.success" for event in audit)
    assert any(
        event["action"] == "auth.login.success"
        and event["details"]["auth_method"] == "oidc"
        for event in audit
    )

    replay_response = anonymous.post(
        "/api/v1/auth/oidc/callback",
        json={"code": "auth-code-123", "state": start["state"]},
    )
    assert replay_response.status_code == 401


def test_oidc_login_rejects_unprovisioned_user_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_oidc(monkeypatch)
    captured_requests: list[dict[str, object]] = []
    monkeypatch.setattr(
        identity_service.urlrequest,
        "urlopen",
        _fake_oidc_urlopen(
            {
                "sub": "wakanow-subject-new",
                "email": "new.sso.user@wakanow.com",
                "name": "New SSO User",
                "email_verified": True,
            },
            captured_requests,
        ),
    )
    anonymous = TestClient(create_app())

    start = anonymous.get("/api/v1/auth/oidc/start?market_id=market-ng").json()
    callback_response = anonymous.post(
        "/api/v1/auth/oidc/callback",
        json={"code": "auth-code-new-user", "state": start["state"]},
    )

    assert callback_response.status_code == 403
    assert callback_response.json()["detail"] == "SSO user is not provisioned"
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(UserRecord).where(UserRecord.email == "new.sso.user@wakanow.com"))
            is None
        )


def test_failed_login_and_access_denial_are_audited(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    anonymous = TestClient(create_app())
    failed_login = anonymous.post(
        "/api/v1/auth/login",
        headers={"X-Request-ID": "trace-login-denied"},
        json={
            "email": "gbolahan@omniticket.example.com",
            "password": "wrong-password",
            "market_id": "market-ng",
        },
    )
    assert failed_login.status_code == 401

    missing_auth = anonymous.get(
        "/api/v1/work-queue",
        headers={"X-Request-ID": "trace-missing-auth"},
    )
    assert missing_auth.status_code == 401

    gh_headers = login_as("kofi.gh@omniticket.example.com", "market-gh")
    denied_market = client.get(
        "/api/v1/customers",
        headers={**gh_headers, "X-Omni-Market": "market-ng", "X-Request-ID": "trace-market-denied"},
    )
    assert denied_market.status_code == 403

    audit_response = client.get("/api/v1/audit")
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert any(
        event["action"] == "auth.login.denied"
        and event["details"]["request_id"] == "trace-login-denied"
        and event["details"]["reason"] == "invalid_credentials"
        for event in events
    )
    assert any(
        event["action"] == "auth.required"
        and event["details"]["request_id"] == "trace-missing-auth"
        for event in events
    )
    assert any(
        event["action"] == "auth.market.denied"
        and event["details"]["request_id"] == "trace-market-denied"
        and event["entity_id"] == "market-ng"
        for event in events
    )


def test_signed_token_survives_missing_session_record(client: TestClient) -> None:
    token = client.headers["Authorization"].removeprefix("Bearer ")
    with Session(get_engine()) as session:
        record = session.get(SessionRecord, token)
        assert record is not None
        session.delete(record)
        session.commit()

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "gbolahan@omniticket.example.com"


def test_tampered_signed_token_is_rejected(client: TestClient) -> None:
    token = client.headers["Authorization"].removeprefix("Bearer ")
    tampered_token = f"{token[:-1]}x"
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}", "X-Omni-Market": "market-ng"},
    )
    assert response.status_code == 401


def test_operations_require_authentication() -> None:
    unauthenticated = TestClient(create_app())
    response = unauthenticated.get("/api/v1/work-queue")
    assert response.status_code == 401


def test_login_rate_limit_blocks_repeated_attempts(client: TestClient) -> None:
    original_attempts = settings.login_rate_limit_attempts
    original_window = settings.login_rate_limit_window_seconds
    settings.login_rate_limit_attempts = 2
    settings.login_rate_limit_window_seconds = 60
    try:
        anonymous = TestClient(create_app())
        rate_limited_email = f"rate-login-{uuid4().hex}@omniticket.example.com"
        payload = {
            "email": rate_limited_email,
            "password": "wrong-password",
            "market_id": "market-ng",
        }
        assert anonymous.post("/api/v1/auth/login", json=payload).status_code == 401
        assert anonymous.post("/api/v1/auth/login", json=payload).status_code == 401
        limited = anonymous.post("/api/v1/auth/login", json=payload)
        assert limited.status_code == 429
        assert limited.json()["detail"] == "Rate limit exceeded"
        assert int(limited.headers["Retry-After"]) >= 1
    finally:
        settings.login_rate_limit_attempts = original_attempts
        settings.login_rate_limit_window_seconds = original_window


def test_market_scope_hides_other_market_customers(
    client: TestClient, login_as: Callable[..., dict[str, str]]
) -> None:
    gh_headers = login_as("kofi.gh@omniticket.example.com", "market-gh")
    gh_customers = client.get("/api/v1/customers", headers=gh_headers)
    assert gh_customers.status_code == 200
    customer_ids = {customer["id"] for customer in gh_customers.json()}
    assert "cust-ama" in customer_ids
    assert "cust-leo" not in customer_ids

    ng_ticket_from_ghana = client.get("/api/v1/tickets", headers=gh_headers)
    assert ng_ticket_from_ghana.status_code == 200
    assert all(ticket["market_id"] == "market-gh" for ticket in ng_ticket_from_ghana.json())


def test_customer_list_supports_search_sort_pagination_headers(client: TestClient) -> None:
    suffix = uuid4().hex
    search_key = f"customer-list-{suffix}"
    for name in ("Zara Search", "Ada Search"):
        response = client.post(
            "/api/v1/customers",
            json={
                "name": f"{name} {suffix}",
                "email": f"{name.lower().replace(' ', '-')}-{suffix}@example.com",
                "location": "Lagos",
                "notes": f"Production list search needle {search_key}",
                "preferred_channels": ["email"],
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/customers",
        params={
            "q": search_key,
            "sort_by": "name",
            "sort_order": "asc",
            "limit": 1,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Returned-Count"] == "1"
    assert response.headers["X-Limit"] == "1"
    assert response.headers["X-Offset"] == "0"
    assert response.headers["X-Sort"] == "name:asc"
    assert response.json()[0]["name"].startswith("Ada Search")

    next_page = client.get(
        "/api/v1/customers",
        params={
            "q": search_key,
            "sort_by": "name",
            "sort_order": "asc",
            "limit": 1,
            "offset": 1,
        },
    )
    assert next_page.status_code == 200
    assert next_page.headers["X-Total-Count"] == "2"
    assert next_page.json()[0]["name"].startswith("Zara Search")


def test_ticket_list_supports_search_filters_sort_pagination_headers(client: TestClient) -> None:
    suffix = uuid4().hex
    search_key = f"ticket-list-{suffix}"
    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Ticket List Customer {suffix}",
            "email": f"ticket-list-{suffix}@example.com",
            "preferred_channels": ["email"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    for subject in ("Zephyr itinerary change", "Atlas refund request", "Atlas baggage issue"):
        response = client.post(
            "/api/v1/tickets",
            json={
                "subject": f"{subject} {suffix}",
                "description": f"Production ticket list search needle {search_key}",
                "customer_id": customer_id,
                "channel": "email",
                "priority": "normal",
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/tickets",
        params={
            "q": "Atlas",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "normal",
            "sort_by": "subject",
            "sort_order": "asc",
            "limit": 1,
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Returned-Count"] == "1"
    assert response.headers["X-Limit"] == "1"
    assert response.headers["X-Offset"] == "0"
    assert response.headers["X-Sort"] == "subject:asc"
    assert response.json()[0]["subject"].startswith("Atlas baggage")

    second_page = client.get(
        "/api/v1/tickets",
        params={
            "q": "Atlas",
            "customer_id": customer_id,
            "sort_by": "subject",
            "sort_order": "asc",
            "limit": 1,
            "offset": 1,
        },
    )
    assert second_page.status_code == 200
    assert second_page.headers["X-Total-Count"] == "2"
    assert second_page.json()[0]["subject"].startswith("Atlas refund")


def test_ticket_fields_validate_custom_ticket_data(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    field_key = f"journey_type_{suffix}"
    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Ticket Field Customer {suffix}",
            "email": f"ticket-field-{suffix}@example.com",
            "preferred_channels": ["email"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    field = client.post(
        "/api/v1/ticket-fields",
        json={
            "key": field_key,
            "label": "Journey type",
            "field_type": "select",
            "required": True,
            "options": ["Domestic", "International"],
            "channels": ["email"],
            "position": 12,
        },
    )
    assert field.status_code == 201
    field_id = field.json()["id"]

    duplicate = client.post(
        "/api/v1/ticket-fields",
        json={
            "key": field_key,
            "label": "Duplicate journey type",
            "field_type": "text",
        },
    )
    assert duplicate.status_code == 409

    missing_required = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Missing ticket field {suffix}",
            "description": "Required field should block this email ticket.",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "normal",
        },
    )
    assert missing_required.status_code == 422
    assert "Journey type is required" in missing_required.text

    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Ticket field valid {suffix}",
            "description": "Required custom field supplied.",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "normal",
            "custom_fields": {field_key: "International"},
        },
    )
    assert ticket.status_code == 201
    ticket_body = ticket.json()
    assert ticket_body["custom_fields"][field_key] == "International"

    invalid_update = client.patch(
        f"/api/v1/tickets/{ticket_body['id']}",
        json={"custom_fields": {field_key: "Interplanetary"}},
    )
    assert invalid_update.status_code == 422

    valid_update = client.patch(
        f"/api/v1/tickets/{ticket_body['id']}",
        json={"custom_fields": {field_key: "Domestic"}},
    )
    assert valid_update.status_code == 200
    assert valid_update.json()["custom_fields"][field_key] == "Domestic"

    fields = client.get("/api/v1/ticket-fields", params={"active_only": True, "channel": "email"})
    assert fields.status_code == 200
    assert any(item["id"] == field_id for item in fields.json())

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert any(item["id"] == field_id for item in body["ticket_fields"])
    ticket_context = next(
        item for item in body["tickets"] if item["ticket"]["id"] == ticket_body["id"]
    )
    assert ticket_context["ticket"]["custom_fields"][field_key] == "Domestic"

    audit = client.get("/api/v1/audit", params={"entity_type": "ticket_field"})
    assert audit.status_code == 200
    assert any(event["action"] == "ticket_field.create" for event in audit.json())


def test_core_mutations_support_optional_etag_conflict_protection(client: TestClient) -> None:
    suffix = uuid4().hex
    company = client.post(
        "/api/v1/companies",
        json={"name": f"Concurrency Company {suffix}", "tier": "enterprise"},
    )
    assert company.status_code == 201
    company_etag = company.headers["ETag"]
    company_id = company.json()["id"]

    company_update = client.patch(
        f"/api/v1/companies/{company_id}",
        headers={"If-Match": company_etag},
        json={"health_score": 88},
    )
    assert company_update.status_code == 200
    assert company_update.headers["ETag"] != company_etag

    stale_company_update = client.patch(
        f"/api/v1/companies/{company_id}",
        headers={"If-Match": company_etag},
        json={"health_score": 70},
    )
    assert stale_company_update.status_code == 412

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Concurrency Customer {suffix}",
            "email": f"concurrency-{suffix}@example.com",
            "company_id": company_id,
            "preferred_channels": ["email"],
        },
    )
    assert customer.status_code == 201
    customer_etag = customer.headers["ETag"]
    customer_id = customer.json()["id"]

    customer_update = client.patch(
        f"/api/v1/customers/{customer_id}",
        headers={"If-Match": customer_etag},
        json={"sentiment": "positive"},
    )
    assert customer_update.status_code == 200
    assert customer_update.headers["ETag"] != customer_etag

    stale_customer_update = client.patch(
        f"/api/v1/customers/{customer_id}",
        headers={"If-Match": customer_etag},
        json={"sentiment": "frustrated"},
    )
    assert stale_customer_update.status_code == 412

    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Concurrency ticket {suffix}",
            "description": "Protect this ticket from stale browser tab overwrites.",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "normal",
        },
    )
    assert ticket.status_code == 201
    ticket_etag = ticket.headers["ETag"]
    ticket_id = ticket.json()["id"]

    ticket_update = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers={"If-Match": ticket_etag},
        json={"priority": "high"},
    )
    assert ticket_update.status_code == 200
    assert ticket_update.headers["ETag"] != ticket_etag

    stale_ticket_update = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers={"If-Match": ticket_etag},
        json={"priority": "urgent"},
    )
    assert stale_ticket_update.status_code == 412
    assert stale_ticket_update.json()["detail"] == "Resource has changed; refresh before retrying."


def test_ticket_knowledge_suggestions_rank_active_market_articles(client: TestClient) -> None:
    suffix = uuid4().hex
    article = client.post(
        "/api/v1/knowledge",
        json={
            "title": f"Duplicate payment refund recovery {suffix}",
            "status": "published",
            "language": "en",
            "channels": ["email"],
            "tags": ["payment", "refund", "recovery"],
            "body": "Use this answer when a customer reports duplicate payment, refund delay, or charge reversal.",
        },
    )
    assert article.status_code == 201
    draft = client.post(
        "/api/v1/knowledge",
        json={
            "title": f"Draft duplicate payment article {suffix}",
            "status": "draft",
            "language": "en",
            "channels": ["email"],
            "tags": ["payment", "refund"],
            "body": "Drafts should not be suggested to agents.",
        },
    )
    assert draft.status_code == 201
    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Knowledge Suggestion Customer {suffix}",
            "email": f"knowledge-suggestion-{suffix}@example.com",
            "preferred_channels": ["email"],
        },
    )
    assert customer.status_code == 201
    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Duplicate payment refund delay {suffix}",
            "description": "Customer needs refund recovery guidance after duplicate card charge.",
            "customer_id": customer.json()["id"],
            "channel": "email",
            "priority": "high",
            "tags": ["payment", "refund"],
        },
    )
    assert ticket.status_code == 201

    suggestions = client.get(f"/api/v1/tickets/{ticket.json()['id']}/knowledge-suggestions")
    assert suggestions.status_code == 200
    payload = suggestions.json()
    assert payload
    assert payload[0]["article"]["id"] == article.json()["id"]
    assert payload[0]["score"] >= 50
    assert payload[0]["reasons"]
    assert "payment" in payload[0]["matched_terms"]
    assert draft.json()["id"] not in {item["article"]["id"] for item in payload}

    context = client.get(f"/api/v1/tickets/{ticket.json()['id']}")
    assert context.status_code == 200
    assert context.json()["knowledge_suggestions"][0]["article"]["id"] == article.json()["id"]

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    ticket_context = next(
        item for item in snapshot.json()["tickets"] if item["ticket"]["id"] == ticket.json()["id"]
    )
    assert ticket_context["knowledge_suggestions"][0]["article"]["id"] == article.json()["id"]


def test_ticket_response_macros_are_ranked_and_usage_tracked(client: TestClient) -> None:
    suffix = uuid4().hex
    macro = client.post(
        "/api/v1/macros",
        json={
            "name": f"Duplicate payment refund macro {suffix}",
            "body": (
                "Thanks for reporting the duplicate payment. I am checking the refund and reversal "
                "timeline now, and I will keep this ticket open until the charge is resolved."
            ),
            "language": "en",
            "channels": ["email"],
            "tags": ["payment", "refund", "recovery"],
            "shortcut": "/refund-recovery",
        },
    )
    assert macro.status_code == 201
    inactive = client.post(
        "/api/v1/macros",
        json={
            "name": f"Inactive duplicate payment macro {suffix}",
            "body": "Inactive macros should not be suggested.",
            "channels": ["email"],
            "tags": ["payment", "refund"],
            "active": False,
        },
    )
    assert inactive.status_code == 201

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Macro Suggestion Customer {suffix}",
            "email": f"macro-suggestion-{suffix}@example.com",
            "preferred_channels": ["email"],
        },
    )
    assert customer.status_code == 201
    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Duplicate payment refund delay {suffix}",
            "description": "Customer needs a refund recovery reply after a duplicate card charge.",
            "customer_id": customer.json()["id"],
            "channel": "email",
            "priority": "high",
            "tags": ["payment", "refund"],
        },
    )
    assert ticket.status_code == 201

    suggestions = client.get(f"/api/v1/tickets/{ticket.json()['id']}/macro-suggestions")
    assert suggestions.status_code == 200
    payload = suggestions.json()
    assert payload
    assert payload[0]["macro"]["id"] == macro.json()["id"]
    assert payload[0]["score"] >= 50
    assert payload[0]["reasons"]
    assert "payment" in payload[0]["matched_terms"]
    assert inactive.json()["id"] not in {item["macro"]["id"] for item in payload}

    context = client.get(f"/api/v1/tickets/{ticket.json()['id']}")
    assert context.status_code == 200
    assert context.json()["macro_suggestions"][0]["macro"]["id"] == macro.json()["id"]

    macro_list = client.get("/api/v1/macros?active_only=true&channel=email&query=refund")
    assert macro_list.status_code == 200
    assert any(item["id"] == macro.json()["id"] for item in macro_list.json())
    assert inactive.json()["id"] not in {item["id"] for item in macro_list.json()}

    use = client.post(f"/api/v1/macros/{macro.json()['id']}/use?ticket_id={ticket.json()['id']}")
    assert use.status_code == 200
    assert use.json()["usage_count"] == 1
    assert use.json()["last_used_at"] is not None

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert any(item["id"] == macro.json()["id"] for item in body["macros"])
    ticket_context = next(
        item for item in body["tickets"] if item["ticket"]["id"] == ticket.json()["id"]
    )
    assert ticket_context["macro_suggestions"][0]["macro"]["id"] == macro.json()["id"]

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "response_macro.create" for event in audit)
    assert any(event["action"] == "response_macro.use" for event in audit)


def test_ticket_duplicate_suggestions_and_merge_close_source(client: TestClient) -> None:
    suffix = uuid4().hex
    booking_reference = f"WK-{suffix[:10]}"
    customer = client.post(
        "/api/v1/customers",
        json={
            "name": f"Duplicate Merge Customer {suffix}",
            "email": f"duplicate-merge-{suffix}@example.com",
            "preferred_channels": ["email", "portal"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    target = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Refund delay after duplicate card charge {suffix}",
            "description": "Customer needs refund recovery after a duplicate payment authorization.",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "high",
            "tags": ["payment", "refund"],
            "custom_fields": {
                "booking_reference": booking_reference,
                "issue_category": "Refund",
            },
        },
    )
    assert target.status_code == 201
    source = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Duplicate payment refund follow up {suffix}",
            "description": "The same customer sent another note about the same duplicate card charge.",
            "customer_id": customer_id,
            "channel": "email",
            "priority": "normal",
            "tags": ["payment", "charge"],
            "custom_fields": {
                "booking_reference": booking_reference,
                "issue_category": "Refund",
            },
        },
    )
    assert source.status_code == 201
    source_attachment = client.post(
        f"/api/v1/tickets/{source.json()['id']}/attachments/binary?filename=duplicate-proof.txt",
        content=b"duplicate proof",
        headers={"content-type": "text/plain"},
    )
    assert source_attachment.status_code == 201

    suggestions = client.get(f"/api/v1/tickets/{target.json()['id']}/duplicate-suggestions")
    assert suggestions.status_code == 200
    suggestion_payload = suggestions.json()
    assert suggestion_payload
    assert suggestion_payload[0]["ticket"]["id"] == source.json()["id"]
    assert suggestion_payload[0]["score"] >= 70
    assert "Same customer" in suggestion_payload[0]["reasons"]
    assert "Matching booking or transaction reference" in suggestion_payload[0]["reasons"]
    assert booking_reference.lower() in suggestion_payload[0]["matched_terms"]

    context = client.get(f"/api/v1/tickets/{target.json()['id']}")
    assert context.status_code == 200
    assert context.json()["duplicate_suggestions"][0]["ticket"]["id"] == source.json()["id"]

    merge = client.post(
        f"/api/v1/tickets/{target.json()['id']}/merge",
        json={
            "source_ticket_id": source.json()["id"],
            "reason": "Same customer, reference, and duplicate payment issue.",
            "actor": "agent-amara",
            "close_source": True,
        },
    )
    assert merge.status_code == 200
    body = merge.json()
    assert body["target_ticket"]["id"] == target.json()["id"]
    assert source.json()["id"] in body["target_ticket"]["custom_fields"]["merged_source_ticket_ids"]
    assert source.json()["public_id"] in body["target_ticket"]["custom_fields"]["merged_source_public_ids"]
    assert body["source_ticket"]["status"] == "closed"
    assert body["source_ticket"]["custom_fields"]["merged_into_ticket_id"] == target.json()["id"]
    assert body["source_ticket"]["custom_fields"]["merged_into_public_id"] == target.json()["public_id"]
    assert body["target_timeline_event"]["metadata"]["source_ticket_id"] == source.json()["id"]
    assert body["source_timeline_event"]["metadata"]["target_ticket_id"] == target.json()["id"]
    assert "duplicate-proof.txt" in body["target_timeline_event"]["body"]
    assert body["audit_event_id"]

    after_merge_suggestions = client.get(
        f"/api/v1/tickets/{target.json()['id']}/duplicate-suggestions"
    )
    assert after_merge_suggestions.status_code == 200
    assert source.json()["id"] not in {
        item["ticket"]["id"] for item in after_merge_suggestions.json()
    }

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "ticket.merge"
        and event["details"]["source_ticket_id"] == source.json()["id"]
        and event["details"]["target_ticket_id"] == target.json()["id"]
        for event in audit
    )


def test_admin_manages_support_groups_and_group_rename_retargets_work(client: TestClient) -> None:
    created_ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate payment needs ownership",
            "description": "Customer reports a duplicate payment and needs refund recovery.",
            "customer_id": "cust-leo",
            "channel": "email",
            "tags": ["payment"],
        },
    )
    assert created_ticket.status_code == 201
    ticket = created_ticket.json()
    assert ticket["team"] == "Billing Support"

    groups = client.get("/api/v1/support-groups")
    assert groups.status_code == 200
    billing_group = next(item for item in groups.json() if item["name"] == "Billing Support")
    assert billing_group["member_count"] >= 1
    assert billing_group["open_ticket_count"] >= 1
    assert billing_group["team_email"] == "billing-support@omniticket.example.com"

    created = client.post(
        "/api/v1/support-groups",
        json={
            "name": "Refund Desk",
            "description": "Specialist queue for refund investigations.",
            "team_email": "refunds@wakanow.com",
            "channels": ["email", "portal"],
            "skills": ["refunds", "payments", "refunds"],
        },
    )
    assert created.status_code == 201
    assert created.json()["team_email"] == "refunds@wakanow.com"
    assert created.json()["skills"] == ["refunds", "payments"]

    duplicate = client.post(
        "/api/v1/support-groups",
        json={
            "name": "Billing Support",
            "description": "Duplicate should not be accepted",
        },
    )
    assert duplicate.status_code == 409

    note = client.post(
        f"/api/v1/tickets/{ticket['id']}/timeline",
        json={
            "type": "internal_note",
            "channel": "internal",
            "actor": "agent-amara",
            "body": "Customer sent proof of duplicate card charge and refund deadline.",
            "public": False,
        },
    )
    assert note.status_code == 200
    clean_upload = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/binary?filename=refund-proof.txt",
        content=b"refund proof bytes",
        headers={"content-type": "text/plain"},
    )
    assert clean_upload.status_code == 201
    clean_attachment = clean_upload.json()
    assert clean_attachment["scan_status"] == "clean"
    blocked_upload = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/binary?filename=unsafe-proof.exe",
        content=b"unsafe bytes",
        headers={"content-type": "application/x-msdownload"},
    )
    assert blocked_upload.status_code == 201
    assert blocked_upload.json()["scan_status"] == "blocked"

    handoff = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Billing Support",
            "requested_by": "agent-amara",
            "reason": "Billing owner must confirm the recovery path.",
            "due_minutes": 45,
            "checklist": ["Accept billing ownership"],
        },
    )
    assert handoff.status_code == 201
    handoff_body = handoff.json()
    assert handoff_body["linked_ticket_id"]
    linked_context = client.get(f"/api/v1/tickets/{handoff_body['linked_ticket_id']}")
    assert linked_context.status_code == 200
    linked_ticket = linked_context.json()["ticket"]
    assert linked_ticket["channel"] == "internal"
    assert linked_ticket["team"] == "Billing Support"
    assert linked_ticket["customer_id"] == ticket["customer_id"]
    assert linked_ticket["custom_fields"]["linked_ticket_type"] == "handoff_child"
    assert linked_ticket["custom_fields"]["source_ticket_id"] == ticket["id"]
    assert linked_ticket["custom_fields"]["handoff_id"] == handoff_body["id"]
    assert "duplicate card charge" in linked_ticket["description"]
    assert "refund-proof.txt" in linked_ticket["description"]
    assert "/download/signed?token=" in linked_ticket["description"]

    linked_timeline = client.get(f"/api/v1/tickets/{linked_ticket['id']}/timeline").json()
    assert any(
        event["metadata"].get("source_ticket_id") == ticket["id"]
        and event["metadata"].get("handoff_id") == handoff_body["id"]
        for event in linked_timeline
    )

    outbound_messages = client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}")
    assert outbound_messages.status_code == 200
    handoff_forward = next(
        item
        for item in outbound_messages.json()
        if item["payload"].get("source") == "handoff_forward"
    )
    assert handoff_forward["provider"] == "email"
    assert handoff_forward["status"] == "queued"
    assert handoff_forward["payload"]["to_email"] == "billing-support@omniticket.example.com"
    assert handoff_forward["payload"]["handoff_id"] == handoff_body["id"]
    assert handoff_forward["payload"]["source_ticket_id"] == ticket["id"]
    assert handoff_forward["payload"]["source_ticket_public_id"] == ticket["public_id"]
    assert handoff_forward["payload"]["linked_ticket_id"] == linked_ticket["id"]
    assert handoff_forward["payload"]["linked_ticket_public_id"] == linked_ticket["public_id"]
    assert handoff_forward["payload"]["reply_target"] == "linked_ticket"
    assert handoff_forward["payload"]["reply_target_ticket_id"] == linked_ticket["id"]
    assert linked_ticket["public_id"] in handoff_forward["payload"]["subject"]
    assert "Customer" in handoff_forward["body"]
    assert "Recent comments and notes" in handoff_forward["body"]
    assert "duplicate card charge" in handoff_forward["body"]
    assert "refund-proof.txt" in handoff_forward["body"]
    assert "unsafe-proof.exe" in handoff_forward["body"]
    assert handoff_forward["body"].count("/download/signed?token=") == 1
    signed_url = next(
        part
        for part in handoff_forward["body"].split()
        if part.startswith("https://omni.wakanow.com/api/v1/")
        and "/download/signed?token=" in part
    )
    parsed_signed_url = parse.urlparse(signed_url)
    signed_path = f"{parsed_signed_url.path}?{parsed_signed_url.query}"
    signed_download = TestClient(create_app()).get(signed_path)
    assert signed_download.status_code == 200
    assert signed_download.content == b"refund proof bytes"

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()
    handoff_event = next(event for event in timeline if event["type"] == "handoff_requested")
    assert handoff_event["metadata"]["handoff_forward_status"] == "queued"
    assert handoff_event["metadata"]["handoff_forward_to"] == "billing-support@omniticket.example.com"
    assert handoff_event["metadata"]["linked_ticket_id"] == linked_ticket["id"]
    assert handoff_event["metadata"]["linked_ticket_public_id"] == linked_ticket["public_id"]
    assert handoff_event["metadata"]["handoff_forward_reply_target"] == "linked_ticket"
    assert handoff_event["metadata"]["handoff_forward_reply_target_ticket_id"] == linked_ticket["id"]

    renamed = client.patch(
        f"/api/v1/support-groups/{billing_group['id']}",
        json={
            "name": "Payment Recovery",
            "skills": ["payments", "refunds", "payments"],
            "channels": ["email", "portal"],
        },
    )
    assert renamed.status_code == 200
    renamed_body = renamed.json()
    assert renamed_body["name"] == "Payment Recovery"
    assert renamed_body["skills"] == ["payments", "refunds"]
    assert renamed_body["member_count"] >= 1
    assert renamed_body["open_ticket_count"] >= 1

    assert any(
        item["team"] == "Payment Recovery"
        for item in client.get("/api/v1/agents").json()
    )
    assert client.get("/api/v1/tickets?team=Billing%20Support").json() == []
    assert any(
        item["id"] == ticket["id"]
        for item in client.get("/api/v1/tickets?team=Payment%20Recovery").json()
    )
    renamed_handoff = next(
        item
        for item in client.get("/api/v1/handoffs").json()
        if item["id"] == handoff_body["id"]
    )
    assert renamed_handoff["from_team"] == "Payment Recovery"
    assert renamed_handoff["to_team"] == "Payment Recovery"
    assert renamed_handoff["linked_ticket_id"] == linked_ticket["id"]

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == billing_group["id"] for item in snapshot.json()["support_groups"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "support_group.create" for event in audit)
    assert any(event["action"] == "support_group.update" for event in audit)
    assert any(event["action"] == "handoff.linked_ticket.create" for event in audit)
    assert any(event["action"] == "handoff.forward.queue" for event in audit)
    assert any(
        event["action"] == "attachment.handoff_link.create"
        and event["entity_id"] == clean_attachment["id"]
        and event["details"]["handoff_id"] == handoff_body["id"]
        for event in audit
    )


def test_handoff_forward_email_reply_threads_to_linked_ticket(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[EmailMessage] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(settings, "email_smtp_host", "smtp.thread.wakanow.test")
    monkeypatch.setattr(settings, "email_smtp_port", 2525)
    monkeypatch.setattr(settings, "email_smtp_username", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_password", "smtp-secret")
    monkeypatch.setattr(settings, "email_smtp_from_email", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_use_starttls", True)
    monkeypatch.setattr(settings, "email_smtp_use_ssl", False)
    monkeypatch.setattr(outbound_adapters.smtplib, "SMTP", FakeSmtp)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Refund team email thread",
            "description": "Customer needs the refund team to validate a duplicate charge.",
            "customer_id": "cust-leo",
            "channel": "email",
            "tags": ["refund"],
        },
    )
    assert ticket_response.status_code == 201
    source_ticket = ticket_response.json()
    note = client.post(
        f"/api/v1/tickets/{source_ticket['id']}/timeline",
        json={
            "type": "internal_note",
            "channel": "internal",
            "actor": "agent-amara",
            "body": "Refund evidence and customer notes are ready for the team.",
            "public": False,
        },
    )
    assert note.status_code == 200

    handoff = client.post(
        f"/api/v1/tickets/{source_ticket['id']}/handoffs",
        json={
            "to_team": "Billing Support",
            "requested_by": "agent-amara",
            "reason": "Team must validate refund ownership by email.",
            "due_minutes": 30,
            "checklist": ["Validate refund owner"],
        },
    )
    assert handoff.status_code == 201
    handoff_body = handoff.json()
    linked_ticket_id = handoff_body["linked_ticket_id"]
    linked_ticket = client.get(f"/api/v1/tickets/{linked_ticket_id}").json()["ticket"]

    forward = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={source_ticket['id']}").json()
        if message["payload"].get("source") == "handoff_forward"
    )
    sent = client.post(
        f"/api/v1/outbound/messages/{forward['id']}/retry",
        json={"reason": "Thread smoke"},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent_messages
    sent_message = sent_messages[0]
    assert sent_message["To"] == "billing-support@omniticket.example.com"
    assert sent_message["X-Omni-Handoff-ID"] == handoff_body["id"]
    assert sent_message["X-Omni-Source-Ticket-ID"] == source_ticket["id"]
    assert sent_message["X-Omni-Linked-Ticket-ID"] == linked_ticket_id
    assert sent_message["X-Omni-Linked-Ticket-Public-ID"] == linked_ticket["public_id"]
    assert sent_message["X-Omni-Reply-Target"] == "linked_ticket"
    assert sent_message["X-Omni-Reply-Target-Ticket-ID"] == linked_ticket_id
    assert linked_ticket["public_id"] in sent_message["Subject"]

    ticket_count_before = len(client.get("/api/v1/tickets").json())
    external_id = f"team-reply-{uuid4().hex}"
    threaded_reply = client.post(
        "/api/v1/connectors/inbound",
        json={
            "provider": "email",
            "external_id": external_id,
            "customer_name": "Billing Support",
            "customer_email": "billing-support@omniticket.example.com",
            "subject": f"Re: {sent_message['Subject']}",
            "body": "Billing confirms the refund can proceed after finance validation.",
            "handle": "billing-support@omniticket.example.com",
            "metadata": {
                "in_reply_to": sent_message["Message-ID"],
                "references": sent_message["Message-ID"],
            },
        },
    )

    assert threaded_reply.status_code == 201
    threaded_body = threaded_reply.json()
    assert threaded_body["deduplicated"] is False
    assert threaded_body["threaded"] is True
    assert threaded_body["ticket"]["id"] == linked_ticket_id
    assert "team-replied" in threaded_body["ticket"]["tags"]
    assert len(client.get("/api/v1/tickets").json()) == ticket_count_before

    connector_event = threaded_body["connector_event"]
    assert connector_event["status"] == "thread-appended"
    assert connector_event["payload"]["thread_match"]["thread_match"] == "outbound_email_reference"
    assert connector_event["payload"]["thread_match"]["handoff_id"] == handoff_body["id"]

    linked_timeline = client.get(f"/api/v1/tickets/{linked_ticket_id}/timeline").json()
    reply_event = next(event for event in linked_timeline if event["metadata"].get("external_id") == external_id)
    assert reply_event["type"] == "inbound"
    assert reply_event["public"] is False
    assert reply_event["metadata"]["threaded"] is True
    assert "refund can proceed" in reply_event["body"]

    source_timeline = client.get(f"/api/v1/tickets/{source_ticket['id']}/timeline").json()
    assert any(
        event["metadata"].get("source") == "handoff_forward_reply"
        and event["metadata"].get("linked_ticket_id") == linked_ticket_id
        for event in source_timeline
    )
    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "connector.thread_append"
        and event["entity_id"] == connector_event["id"]
        for event in audit
    )


def test_global_search_returns_market_scoped_operational_records(client: TestClient) -> None:
    group = client.post(
        "/api/v1/support-groups",
        json={
            "name": "Refund Intelligence",
            "description": "Handles refund anomalies and payment reversals.",
            "team_email": "refund-intel@wakanow.com",
            "channels": ["email"],
            "skills": ["refunds"],
        },
    )
    assert group.status_code == 201
    created = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Refund Intelligence search case",
            "description": "Search should find this refund anomaly ticket and requester.",
            "customer_id": "cust-leo",
            "channel": "email",
            "tags": ["refund-intelligence"],
        },
    )
    assert created.status_code == 201
    ticket = created.json()

    response = client.get("/api/v1/search?q=refund-intel&limit=10")

    assert response.status_code == 200
    results = response.json()
    result_types = {item["type"] for item in results}
    assert {"ticket", "support_group"} <= result_types
    assert any(item["entity_id"] == ticket["id"] for item in results)
    assert any(item["entity_id"] == group.json()["id"] for item in results)
    assert all(item["metadata"] for item in results)


def test_admin_manages_sla_policies_and_ticket_creation_uses_active_match(
    client: TestClient,
) -> None:
    def parse_test_datetime(value: str):
        return datetime.fromisoformat(value).replace(tzinfo=None)

    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/sla-policies",
        json={
            "name": f"Urgent API policy {suffix}",
            "priority": "urgent",
            "channels": ["api", "api"],
            "first_response_minutes": 7,
            "resolution_minutes": 77,
            "business_hours": "24x7",
            "active": True,
            "position": 1,
        },
    )
    assert created.status_code == 201
    policy = created.json()
    assert policy["channels"] == ["api"]

    policies = client.get("/api/v1/sla-policies")
    assert policies.status_code == 200
    assert any(item["id"] == policy["id"] for item in policies.json())

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Urgent partner API refund",
            "description": "Partner API reports an urgent duplicate payment refund issue.",
            "customer_id": "cust-leo",
            "channel": "api",
            "priority": "urgent",
            "tags": ["partner-api"],
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    created_at = parse_test_datetime(ticket["created_at"])
    first_due = parse_test_datetime(ticket["sla"]["first_response_due_at"])
    resolution_due = parse_test_datetime(ticket["sla"]["resolution_due_at"])
    assert timedelta(minutes=6, seconds=30) <= first_due - created_at <= timedelta(
        minutes=7,
        seconds=30,
    )
    assert timedelta(minutes=76, seconds=30) <= resolution_due - created_at <= timedelta(
        minutes=77,
        seconds=30,
    )

    updated = client.patch(
        f"/api/v1/sla-policies/{policy['id']}",
        json={"active": False, "first_response_minutes": 11},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["first_response_minutes"] == 11

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == policy["id"] for item in snapshot.json()["sla_policies"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "sla_policy.create" for event in audit)
    assert any(event["action"] == "sla_policy.update" for event in audit)


def test_admin_manages_business_hours(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/business-hours",
        json={"name": f"Lagos hours {suffix}", "timezone": "Africa/Lagos", "active": True},
    )
    assert created.status_code == 201
    calendar = created.json()
    # A new calendar gets a default Mon-Fri 09:00-17:00 schedule (no dummy/empty content).
    assert len(calendar["days"]) == 7
    assert sum(1 for day in calendar["days"] if day["enabled"]) == 5

    listing = client.get("/api/v1/business-hours")
    assert listing.status_code == 200
    assert any(item["id"] == calendar["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/business-hours/{calendar['id']}",
        json={
            "active": False,
            "timezone": "Europe/London",
            "days": [{"day": "Monday", "enabled": True, "open": "08:00", "close": "18:00"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["timezone"] == "Europe/London"
    assert updated.json()["days"][0]["open"] == "08:00"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == calendar["id"] for item in snapshot.json()["business_hours"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "business_hours.create" for event in audit)
    assert any(event["action"] == "business_hours.update" for event in audit)


def test_admin_manages_ticket_templates(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/ticket-templates",
        json={
            "name": f"Refund template {suffix}",
            "subject": "Refund request",
            "description": "Confirm booking reference and refund reason.",
            "priority": "high",
            "channel": "email",
            "group": "Refund Desk",
            "tags": ["refund", "refund"],
        },
    )
    assert created.status_code == 201
    template = created.json()
    assert template["priority"] == "high"
    assert template["tags"] == ["refund"]  # de-duplicated

    listing = client.get("/api/v1/ticket-templates")
    assert listing.status_code == 200
    assert any(item["id"] == template["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/ticket-templates/{template['id']}",
        json={"active": False, "subject": "Updated refund subject"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["subject"] == "Updated refund subject"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == template["id"] for item in snapshot.json()["ticket_templates"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "ticket_template.create" for event in audit)
    assert any(event["action"] == "ticket_template.update" for event in audit)


def test_admin_manages_tags(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/tags",
        json={"name": f"escalated-{suffix}", "color": "#e25555", "description": "Escalated cases"},
    )
    assert created.status_code == 201
    tag = created.json()
    assert tag["color"] == "#e25555"

    duplicate = client.post("/api/v1/tags", json={"name": f"escalated-{suffix}"})
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/tags")
    assert listing.status_code == 200
    assert any(item["id"] == tag["id"] for item in listing.json())

    updated = client.patch(f"/api/v1/tags/{tag['id']}", json={"active": False, "color": "#2f6fed"})
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["color"] == "#2f6fed"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == tag["id"] for item in snapshot.json()["tags"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "tag.create" for event in audit)
    assert any(event["action"] == "tag.update" for event in audit)


def test_admin_manages_csat_surveys(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/csat-surveys",
        json={
            "name": f"Post-resolution {suffix}",
            "question": "How did we do?",
            "scale": 5,
            "channels": ["email", "email", "portal"],
        },
    )
    assert created.status_code == 201
    survey = created.json()
    assert survey["channels"] == ["email", "portal"]  # de-duplicated

    listing = client.get("/api/v1/csat-surveys")
    assert listing.status_code == 200
    assert any(item["id"] == survey["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/csat-surveys/{survey['id']}",
        json={"active": False, "scale": 4},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["scale"] == 4

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == survey["id"] for item in snapshot.json()["csat_surveys"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "csat_survey.create" for event in audit)
    assert any(event["action"] == "csat_survey.update" for event in audit)


def test_admin_manages_email_notifications(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/email-notifications",
        json={
            "name": f"Resolved notice {suffix}",
            "event": "ticket_resolved",
            "recipients": ["requester", "requester"],
            "subject": "Resolved",
            "body": "Your ticket is resolved.",
        },
    )
    assert created.status_code == 201
    notification = created.json()
    assert notification["recipients"] == ["requester"]  # de-duplicated
    assert notification["event"] == "ticket_resolved"

    listing = client.get("/api/v1/email-notifications")
    assert listing.status_code == 200
    assert any(item["id"] == notification["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/email-notifications/{notification['id']}",
        json={"active": False, "subject": "Updated subject"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["subject"] == "Updated subject"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == notification["id"] for item in snapshot.json()["email_notifications"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "email_notification.create" for event in audit)
    assert any(event["action"] == "email_notification.update" for event in audit)


def test_admin_manages_scenario_automations(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/scenario-automations",
        json={
            "name": f"Refund flow {suffix}",
            "description": "Tag and route refunds",
            "actions": [
                {"type": "add_tag", "value": "refund"},
                {"type": "set_priority", "value": "high"},
                {"type": "", "value": "ignored"},
            ],
        },
    )
    assert created.status_code == 201
    scenario = created.json()
    assert len(scenario["actions"]) == 2  # blank-type action dropped
    assert scenario["actions"][0]["type"] == "add_tag"

    listing = client.get("/api/v1/scenario-automations")
    assert listing.status_code == 200
    assert any(item["id"] == scenario["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/scenario-automations/{scenario['id']}",
        json={"active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == scenario["id"] for item in snapshot.json()["scenario_automations"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "scenario_automation.create" for event in audit)
    assert any(event["action"] == "scenario_automation.update" for event in audit)


def test_admin_manages_custom_field_definitions(client: TestClient) -> None:
    suffix = uuid4().hex[:6]
    created = client.post(
        "/api/v1/custom-fields",
        json={
            "entity": "contact",
            "key": f"tier_{suffix}",
            "label": "Tier",
            "field_type": "select",
            "options": ["Gold", "Gold", "Silver"],
        },
    )
    assert created.status_code == 201
    field = created.json()
    assert field["entity"] == "contact"
    assert field["options"] == ["Gold", "Silver"]  # de-duplicated

    # select fields require options
    bad = client.post(
        "/api/v1/custom-fields",
        json={"entity": "company", "key": f"bad_{suffix}", "label": "Bad", "field_type": "select"},
    )
    assert bad.status_code == 422

    filtered = client.get("/api/v1/custom-fields", params={"entity": "contact"})
    assert filtered.status_code == 200
    assert all(item["entity"] == "contact" for item in filtered.json())
    assert any(item["id"] == field["id"] for item in filtered.json())

    updated = client.patch(
        f"/api/v1/custom-fields/{field['id']}",
        json={"active": False, "label": "Loyalty tier"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["label"] == "Loyalty tier"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(
        item["id"] == field["id"] for item in snapshot.json()["custom_field_definitions"]
    )

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "custom_field.create" for event in audit)
    assert any(event["action"] == "custom_field.update" for event in audit)


def test_admin_manages_custom_objects(client: TestClient) -> None:
    suffix = uuid4().hex[:6]
    created = client.post(
        "/api/v1/custom-objects",
        json={
            "key": f"loyalty_{suffix}",
            "name": "Loyalty account",
            "description": "Frequent-flyer account",
            "fields": [
                {"key": "membership_id", "label": "Membership ID", "field_type": "text", "required": True},
                {"key": "tier", "label": "Tier", "field_type": "select", "options": ["Blue", "Gold"]},
                {"key": "tier", "label": "Dup", "field_type": "text"},
            ],
        },
    )
    assert created.status_code == 201
    obj = created.json()
    assert len(obj["fields"]) == 2  # duplicate field key dropped
    assert obj["fields"][1]["options"] == ["Blue", "Gold"]

    duplicate = client.post(
        "/api/v1/custom-objects",
        json={"key": f"loyalty_{suffix}", "name": "Dup"},
    )
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/custom-objects")
    assert listing.status_code == 200
    assert any(item["id"] == obj["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/custom-objects/{obj['id']}",
        json={"active": False, "name": "Loyalty programme"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["name"] == "Loyalty programme"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == obj["id"] for item in snapshot.json()["custom_objects"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "custom_object.create" for event in audit)
    assert any(event["action"] == "custom_object.update" for event in audit)


def test_admin_manages_products(client: TestClient) -> None:
    suffix = uuid4().hex[:6]
    created = client.post(
        "/api/v1/products",
        json={"name": f"Wakanow Tours {suffix}", "code": "TOURS", "description": "Guided tours"},
    )
    assert created.status_code == 201
    product = created.json()
    assert product["code"] == "TOURS"

    duplicate = client.post("/api/v1/products", json={"name": f"Wakanow Tours {suffix}"})
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/products")
    assert listing.status_code == 200
    assert any(item["id"] == product["id"] for item in listing.json())

    updated = client.patch(f"/api/v1/products/{product['id']}", json={"active": False})
    assert updated.status_code == 200
    assert updated.json()["active"] is False

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == product["id"] for item in snapshot.json()["products"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "product.create" for event in audit)
    assert any(event["action"] == "product.update" for event in audit)


def test_role_policy_blocks_agent_from_admin_and_supervisor_controls(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    temporary_password = "Nia-temp-2026"
    created = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Nia Agent",
            "email": "nia.agent@omniticket.example.com",
            "temporary_password": temporary_password,
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert created.status_code == 201
    agent_headers = login_as("nia.agent@omniticket.example.com", "market-ng", temporary_password)

    assert client.get("/api/v1/tickets", headers=agent_headers).status_code == 200
    assert client.get("/api/v1/work-queue", headers=agent_headers).status_code == 200
    assert client.get("/api/v1/audit", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/alerts", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/alerts/deliveries", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/alerts/delivery-config", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/inbound/provider-config", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/outbound/provider-config", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/production/account-requests", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/production/readiness-checklist", headers=agent_headers).status_code == 403
    assert client.post("/api/v1/production/account-requests/email", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/production/account-references", headers=agent_headers).status_code == 403
    assert client.post(
        "/api/v1/production/account-references",
        json={
            "provider": "sms",
            "area": "SMS provider",
            "account_name": "Blocked SMS account",
        },
        headers=agent_headers,
    ).status_code == 403
    assert client.get("/api/v1/csat/feedback", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/platform/readiness", headers=agent_headers).status_code == 403
    assert client.patch(
        "/api/v1/settings",
        json={"public_brand_name": "Blocked"},
        headers=agent_headers,
    ).status_code == 403
    assert client.post(
        "/api/v1/automation-rules",
        json={
            "name": "Blocked rule",
            "trigger": "always",
            "action": "assign escalation",
        },
        headers=agent_headers,
    ).status_code == 403

    ticket = client.get("/api/v1/tickets", headers=agent_headers).json()[0]
    assert client.post(
        f"/api/v1/work-queue/{ticket['id']}/override",
        json={"reason": "Agent should not override the queue.", "priority": "urgent"},
        headers=agent_headers,
    ).status_code == 403

    with Session(get_engine()) as session:
        alert = operational_alert_repository.upsert_alert(
            session,
            market_id="market-ng",
            severity=OperationalAlertSeverity.critical,
            source="test",
            entity_type="worker",
            entity_id="worker-test",
            dedupe_key="test:snapshot-alert-visibility",
            title="Supervisor-only alert",
            message="Agents should not see operational control alerts in snapshots.",
            details={},
            actor="pytest",
        )
        session.commit()

    agent_snapshot = client.get("/api/v1/frontend/snapshot", headers=agent_headers)
    assert agent_snapshot.status_code == 200
    assert agent_snapshot.json()["operational_alerts"] == []
    assert agent_snapshot.json()["alert_deliveries"] == []
    assert agent_snapshot.json()["alert_delivery_config"]["webhook_configured"] is False
    assert agent_snapshot.json()["inbound_provider_config"] == []
    assert agent_snapshot.json()["outbound_provider_config"] == []

    admin_snapshot = client.get("/api/v1/frontend/snapshot")
    assert admin_snapshot.status_code == 200
    assert any(item["id"] == alert.id for item in admin_snapshot.json()["operational_alerts"])
    assert admin_snapshot.json()["inbound_provider_config"]
    assert admin_snapshot.json()["outbound_provider_config"]


def test_role_policy_allows_agent_ticket_work_but_keeps_auditor_read_only(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    auditor_password = "Ada-temp-2026"
    auditor = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Ada Auditor",
            "email": "ada.auditor@omniticket.example.com",
            "temporary_password": auditor_password,
            "role": "auditor",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert auditor.status_code == 201
    agent_password = "Ola-temp-2026"
    agent = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Ola Agent",
            "email": "ola.agent@omniticket.example.com",
            "temporary_password": agent_password,
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert agent.status_code == 201

    agent_headers = login_as("ola.agent@omniticket.example.com", "market-ng", agent_password)
    ticket = client.get("/api/v1/tickets", headers=agent_headers).json()[0]
    reply = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": ticket["channel"],
            "actor": "ola.agent@omniticket.example.com",
            "body": "I am checking this now.",
            "public": False,
        },
        headers=agent_headers,
    )
    assert reply.status_code == 200

    auditor_headers = login_as("ada.auditor@omniticket.example.com", "market-ng", auditor_password)
    assert client.get("/api/v1/tickets", headers=auditor_headers).status_code == 200
    assert client.get("/api/v1/audit", headers=auditor_headers).status_code == 200
    assert client.get("/api/v1/auth/users", headers=auditor_headers).status_code == 403
    assert client.post(
        "/api/v1/tickets",
        json={
            "subject": "Auditor should not create tickets",
            "description": "Read-only role enforcement.",
            "customer_id": "cust-leo",
            "channel": "email",
        },
        headers=auditor_headers,
    ).status_code == 403


def test_role_policy_limits_setup_to_admins_and_supervisor_tools_to_supervisors(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    supervisor_headers = login_as("amara.ng@omniticket.example.com", "market-ng")
    assert client.get("/api/v1/auth/users", headers=supervisor_headers).status_code == 200
    assert client.get("/api/v1/audit", headers=supervisor_headers).status_code == 200
    assert client.get("/api/v1/platform/readiness", headers=supervisor_headers).status_code == 200
    assert client.patch(
        "/api/v1/channels/channel-email",
        json={"queued": 41},
        headers=supervisor_headers,
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/users",
        json={
            "name": "Blocked Supervisor Create",
            "email": "blocked.supervisor@omniticket.example.com",
            "temporary_password": "Blocked-temp-2026",
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
        headers=supervisor_headers,
    ).status_code == 403
    assert client.patch(
        "/api/v1/settings",
        json={"public_brand_name": "Supervisor blocked"},
        headers=supervisor_headers,
    ).status_code == 403
    account = client.get("/api/v1/connectors/accounts").json()[0]
    assert client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"status": "connected"},
        headers=supervisor_headers,
    ).status_code == 403


def test_role_policy_allows_service_account_operations_but_blocks_setup_and_audit(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    service_password = "Svc-temp-2026"
    service_account = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Queue Worker",
            "email": "queue.worker@omniticket.example.com",
            "temporary_password": service_password,
            "role": "service_account",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert service_account.status_code == 201

    service_headers = login_as(
        "queue.worker@omniticket.example.com",
        "market-ng",
        service_password,
    )
    ticket = client.get("/api/v1/tickets", headers=service_headers).json()[0]
    reply = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": ticket["channel"],
            "actor": "queue.worker@omniticket.example.com",
            "body": "Automated follow-up queued for manual review.",
            "public": False,
        },
        headers=service_headers,
    )
    assert reply.status_code == 200
    assert client.get("/api/v1/audit", headers=service_headers).status_code == 403
    assert client.get("/api/v1/auth/users", headers=service_headers).status_code == 403
    assert client.patch(
        "/api/v1/settings",
        json={"public_brand_name": "Service account blocked"},
        headers=service_headers,
    ).status_code == 403


def test_user_passwords_are_hashed_and_admin_can_reset_temporary_password(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    created = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Password Managed",
            "email": "password.managed@omniticket.example.com",
            "temporary_password": "First-temp-2026",
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert created.status_code == 201
    user = created.json()
    assert user["password_reset_required"] is True

    with Session(get_engine()) as session:
        record = session.get(UserRecord, user["id"])
        assert record is not None
        assert record.password_hash is not None
        assert record.password_hash != "First-temp-2026"

    denied = client.post(
        "/api/v1/auth/login",
        json={
            "email": "password.managed@omniticket.example.com",
            "password": "omni-demo",
            "market_id": "market-ng",
        },
    )
    assert denied.status_code == 401
    login_as("password.managed@omniticket.example.com", "market-ng", "First-temp-2026")

    reset = client.patch(
        f"/api/v1/auth/users/{user['id']}",
        json={"temporary_password": "Second-temp-2026"},
    )
    assert reset.status_code == 200
    assert reset.json()["password_reset_required"] is True
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "password.managed@omniticket.example.com",
                "password": "First-temp-2026",
                "market_id": "market-ng",
            },
        ).status_code
        == 401
    )
    login_as("password.managed@omniticket.example.com", "market-ng", "Second-temp-2026")


def test_user_can_change_password_and_clear_reset_requirement(client: TestClient) -> None:
    created = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Password Change",
            "email": "password.change@omniticket.example.com",
            "temporary_password": "Temp-change-2026",
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert created.status_code == 201

    anonymous = TestClient(create_app())
    login = anonymous.post(
        "/api/v1/auth/login",
        json={
            "email": "password.change@omniticket.example.com",
            "password": "Temp-change-2026",
            "market_id": "market-ng",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Omni-Market": "market-ng"}
    changed = anonymous.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": "Temp-change-2026", "new_password": "Permanent-2026"},
    )
    assert changed.status_code == 204
    assert (
        anonymous.post(
            "/api/v1/auth/login",
            json={
                "email": "password.change@omniticket.example.com",
                "password": "Temp-change-2026",
                "market_id": "market-ng",
            },
        ).status_code
        == 401
    )
    relogin = anonymous.post(
        "/api/v1/auth/login",
        json={
            "email": "password.change@omniticket.example.com",
            "password": "Permanent-2026",
            "market_id": "market-ng",
        },
    )
    assert relogin.status_code == 200
    assert relogin.json()["user"]["password_reset_required"] is False


def test_seeded_work_queue_has_ai_ranked_items(client: TestClient) -> None:
    response = client.get("/api/v1/work-queue")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2
    assert items[0]["score"] >= items[-1]["score"]
    assert "ticket" in items[0]
    assert "customer" in items[0]


def test_work_queue_override_updates_ticket_and_persists(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/work-queue/{ticket['id']}/override",
        json={
            "reason": "Supervisor moved this issue to the payments desk for manual review.",
            "priority": "urgent",
            "status": "pending",
            "assignee_id": "agent-mateo",
            "recommended_action": "Call the acquirer and send a manual payment status update.",
            "tags": ["manual-override", "payments-escalation"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "urgent"
    assert body["status"] == "pending"
    assert body["assignee_id"] == "agent-mateo"
    assert body["team"] == "Social Care"
    assert body["recommended_action"] == "Call the acquirer and send a manual payment status update."
    assert body["tags"] == ["manual-override", "payments-escalation"]

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline")
    assert timeline.status_code == 200
    assert any(
        event["metadata"].get("reason") == "Supervisor moved this issue to the payments desk for manual review."
        for event in timeline.json()
    )

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200
    assert any(event["action"] == "work_queue.override" for event in audit.json())

    store.seed()

    persisted = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert persisted.status_code == 200
    context = persisted.json()
    assert context["ticket"]["priority"] == "urgent"
    assert context["ticket"]["assignee_id"] == "agent-mateo"
    assert context["ticket"]["recommended_action"] == "Call the acquirer and send a manual payment status update."


def test_work_queue_override_requires_mutation_fields(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/work-queue/{ticket['id']}/override",
        json={"reason": "No-op override request."},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "At least one override field is required"


def test_supervisor_recommendations_rank_blocked_handoff_and_snapshot_access(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    customer = client.get("/api/v1/customers").json()[0]
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer["id"],
            "subject": "Urgent refund handoff needs manager intervention",
            "description": "Customer has waited through two payment reviews.",
            "channel": "email",
            "priority": "urgent",
            "tags": ["refund", "sla"],
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    handoff_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Billing Operations",
            "requested_by": "Support desk",
            "reason": "Payment capture needs manual review before customer promise can be met.",
            "due_minutes": 20,
            "checklist": ["Confirm payment capture", "Send customer update"],
        },
    )
    assert handoff_response.status_code == 201
    handoff = handoff_response.json()
    blocked = client.patch(
        f"/api/v1/handoffs/{handoff['id']}",
        json={"blocker": "Waiting for acquirer reference from finance."},
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    recommendations_response = client.get("/api/v1/operations/recommendations")
    assert recommendations_response.status_code == 200
    recommendations = recommendations_response.json()
    blocker = next(
        item
        for item in recommendations
        if item["handoff_id"] == handoff["id"] and item["category"] == "handoff_blocker"
    )
    assert blocker["ticket_id"] == ticket["id"]
    assert blocker["support_group"] == "Billing Operations"
    assert blocker["priority_score"] >= 80
    assert "customer" in blocker["action"].lower()
    assert any("Blocker:" in reason for reason in blocker["reasons"])

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(
        item["handoff_id"] == handoff["id"]
        for item in snapshot.json()["supervisor_recommendations"]
    )

    created = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Recommendation Agent",
            "email": "recommendation.agent@omniticket.example.com",
            "temporary_password": "Agent-temp-2026",
            "role": "agent",
            "market_ids": ["market-ng"],
            "default_market_id": "market-ng",
        },
    )
    assert created.status_code == 201
    agent_headers = login_as(
        "recommendation.agent@omniticket.example.com",
        password="Agent-temp-2026",
    )
    assert client.get("/api/v1/operations/recommendations", headers=agent_headers).status_code == 403
    agent_snapshot = client.get("/api/v1/frontend/snapshot", headers=agent_headers)
    assert agent_snapshot.status_code == 200
    assert agent_snapshot.json()["supervisor_recommendations"] == []


def test_create_ticket_runs_ai_routing_by_default(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Public WhatsApp complaint about duplicate payment",
            "description": "Customer is angry about a duplicate payment and wants escalation.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
            "tags": ["vip"],
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is not None
    assert ticket["priority"] == "urgent"
    assert "ai-routed" in ticket["tags"]
    assert "payment-risk" in ticket["tags"]

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert context["ai_decisions"]
    assert any(event["type"] == "ai_decision" for event in context["timeline"])


def test_ai_routing_can_be_disabled_in_settings(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings",
        json={"ai_work_queue_automation_enabled": False},
    )
    assert settings.status_code == 200
    assert settings.json()["ai_work_queue_automation_enabled"] is False

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp user cannot update profile contact",
            "description": "Customer needs manual help but no AI routing should run.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is None
    assert "ai-routed" not in ticket["tags"]


def test_automation_rules_route_social_complaints_without_ai(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings",
        json={"ai_work_queue_automation_enabled": False},
    )
    assert settings.status_code == 200

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Public Facebook complaint about missed delivery",
            "description": (
                "Customer is angry after a failed delivery and posted the complaint publicly."
            ),
            "customer_id": "cust-sofia",
            "channel": "facebook",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["priority"] == "urgent"
    assert ticket["assignee_id"] == "agent-mateo"
    assert ticket["team"] == "Social Care"
    assert "ai-routed" not in ticket["tags"]
    assert "automation-rule" in ticket["tags"]
    assert "rule:rule-social-risk" in ticket["tags"]
    task_labels = {task["label"] for task in ticket["tasks"]}
    assert "Reply in the private social thread" in task_labels
    assert "Notify supervisor if the blocker remains open" in task_labels

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert not context["ai_decisions"]
    assert any(
        event["metadata"].get("rule_id") == "rule-social-risk"
        for event in context["timeline"]
    )

    rules = client.get("/api/v1/automation-rules").json()
    social_rule = next(rule for rule in rules if rule["id"] == "rule-social-risk")
    assert social_rule["last_fired_at"] is not None

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200
    assert any(
        event["action"] == "automation_rule.fire"
        and event["entity_id"] == "rule-social-risk"
        and event["details"]["ticket_id"] == ticket["id"]
        for event in audit.json()
    )


def test_automation_rules_attach_payment_checklist_without_ai(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings",
        json={"ai_work_queue_automation_enabled": False},
    )
    assert settings.status_code == 200

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate payment after WhatsApp checkout",
            "description": "Customer says the card was charged twice and needs billing help.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] == "agent-amara"
    assert ticket["team"] == "Billing Support"
    assert "ai-routed" not in ticket["tags"]
    assert "rule:rule-payment-risk" in ticket["tags"]
    task_labels = {task["label"] for task in ticket["tasks"]}
    assert "Confirm duplicate transaction reference" in task_labels
    assert "Validate payment gateway status" in task_labels
    assert "Send customer reversal timeline" in task_labels


def test_ai_routing_setting_is_database_backed(client: TestClient) -> None:
    settings = client.patch(
        "/api/v1/settings/ai-work-queue-automation",
        json={"enabled": False},
    )
    assert settings.status_code == 200

    store.seed()

    persisted = client.get("/api/v1/settings")
    assert persisted.status_code == 200
    assert persisted.json()["ai_work_queue_automation_enabled"] is False

    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp customer needs a profile update",
            "description": "This should stay manual because the persisted setting is disabled.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["assignee_id"] is None
    assert "ai-routed" not in ticket["tags"]


def test_reply_creates_timeline_and_outbound_queue_message(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    account = next(
        item
        for item in client.get("/api/v1/connectors/accounts").json()
        if item["provider"] == ticket["channel"]
    )
    client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": f"vault://omni/ng/{ticket['channel']}",
        },
    )
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": ticket["channel"],
            "actor": "agent-amara",
            "body": "We have your request and will update you shortly.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["type"] == "public_reply"
    assert response.json()["metadata"]["delivery_status"] == "sent"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(event["direction"] == "outbound" and event["status"] == "sent" for event in connector_events)

    outbound_messages = client.get("/api/v1/outbound/messages").json()
    assert any(
        message["ticket_id"] == ticket["id"]
        and message["status"] == "sent"
        and message["attempts"] == 1
        for message in outbound_messages
    )

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert context["outbound_messages"]
    assert any(
        event["type"] == "connector_receipt"
        and event["metadata"]["delivery_status"] == "sent"
        for event in context["timeline"]
    )


def test_attachment_metadata_is_scanned_and_added_to_ticket_timeline(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        json={
            "filename": "customer-payment-screenshot.png",
            "content_type": "image/png",
            "size_bytes": 248_000,
        },
    )
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["ticket_id"] == ticket["id"]
    assert attachment["scan_status"] == "clean"
    assert attachment["storage_key"].startswith(f"attachment://market-ng/{ticket['id']}/")

    attachments = client.get(f"/api/v1/tickets/{ticket['id']}/attachments")
    assert attachments.status_code == 200
    assert any(item["id"] == attachment["id"] for item in attachments.json())

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(item["id"] == attachment["id"] for item in context["attachments"])
    assert any(
        event["type"] == "attachment_added"
        and event["metadata"]["attachment_id"] == attachment["id"]
        and event["metadata"]["scan_status"] == "clean"
        for event in context["timeline"]
    )
    assert any(
        event["action"] == "attachment.create" and event["entity_id"] == attachment["id"]
        for event in client.get("/api/v1/audit").json()
    )


def test_dangerous_attachment_metadata_is_blocked(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        json={
            "filename": "customer-details.exe",
            "content_type": "application/x-msdownload",
            "size_bytes": 128_000,
        },
    )
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["scan_status"] == "blocked"
    assert "not allowed" in attachment["scan_result"]

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()
    assert any(
        event["type"] == "attachment_added"
        and event["metadata"]["scan_status"] == "blocked"
        for event in timeline
    )


def test_binary_attachment_upload_can_be_downloaded_after_clean_scan(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/binary?filename=proof-note.txt",
        content=b"customer proof bytes",
        headers={"content-type": "text/plain"},
    )
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["filename"] == "proof-note.txt"
    assert attachment["scan_status"] == "clean"
    assert attachment["size_bytes"] == len(b"customer proof bytes")
    assert attachment["storage_key"].startswith("local:")

    download = client.get(
        f"/api/v1/tickets/{ticket['id']}/attachments/{attachment['id']}/download"
    )
    assert download.status_code == 200
    assert download.content == b"customer proof bytes"
    assert download.headers["content-type"].startswith("text/plain")


def test_blocked_binary_attachment_cannot_be_downloaded(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/binary?filename=malware.exe",
        content=b"blocked bytes",
        headers={"content-type": "application/x-msdownload"},
    )
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["scan_status"] == "blocked"

    download = client.get(
        f"/api/v1/tickets/{ticket['id']}/attachments/{attachment['id']}/download"
    )
    assert download.status_code == 403


def test_clean_attachment_can_use_signed_download_link(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    upload = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/binary?filename=signed-proof.txt",
        content=b"signed proof bytes",
        headers={"content-type": "text/plain"},
    )
    assert upload.status_code == 201
    attachment = upload.json()

    link = client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments/{attachment['id']}/download-link"
    )
    assert link.status_code == 200
    assert "/download/signed?token=" in link.json()["url"]

    public_download = TestClient(create_app()).get(link.json()["url"])
    assert public_download.status_code == 200
    assert public_download.content == b"signed proof bytes"
    assert public_download.headers["cache-control"] == "no-store"
    assert public_download.headers["x-content-type-options"] == "nosniff"

    tampered = TestClient(create_app()).get(f"{link.json()['url']}x")
    assert tampered.status_code == 401

    audit = client.get("/api/v1/audit").json()
    link_events = [
        event
        for event in audit
        if event["action"] == "attachment.download_link.create"
        and event["entity_id"] == attachment["id"]
    ]
    download_events = [
        event
        for event in audit
        if event["action"] == "attachment.download"
        and event["entity_id"] == attachment["id"]
    ]
    assert link_events
    assert download_events
    link_details = link_events[0]["details"]
    download_details = download_events[0]["details"]
    assert link_details["token_id"] != "legacy"
    assert download_details["token_id"] == link_details["token_id"]
    assert download_details["created_by"] == link_events[0]["actor"]

    wrong_ticket_download = TestClient(create_app()).get(
        link.json()["url"].replace(f"/tickets/{ticket['id']}/", "/tickets/not-this-ticket/")
    )
    assert wrong_ticket_download.status_code == 401


def test_failed_outbound_message_can_be_retried_after_connector_is_enabled(
    client: TestClient,
) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "We are checking this in WhatsApp.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "failed"

    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )
    assert failed_message["status"] == "failed"
    assert failed_message["last_error"]

    whatsapp_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "whatsapp"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{whatsapp_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
        },
    )

    retry = client.post(
        f"/api/v1/outbound/messages/{failed_message['id']}/retry",
        json={"reason": "Credentials connected"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "sent"
    assert retry.json()["attempts"] == 2


def test_email_outbound_uses_configured_smtp_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[EmailMessage] = []
    smtp_events: list[tuple[object, ...]] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            smtp_events.append(("connect", host, port, timeout))

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            smtp_events.append(("close",))

        def starttls(self) -> None:
            smtp_events.append(("starttls",))

        def login(self, username: str, password: str) -> None:
            smtp_events.append(("login", username, password))

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(settings, "email_smtp_host", "smtp.wakanow.test")
    monkeypatch.setattr(settings, "email_smtp_port", 2525)
    monkeypatch.setattr(settings, "email_smtp_username", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_password", "smtp-secret")
    monkeypatch.setattr(settings, "email_smtp_from_email", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_use_starttls", True)
    monkeypatch.setattr(settings, "email_smtp_use_ssl", False)
    monkeypatch.setattr(settings, "email_smtp_timeout_seconds", 9)
    monkeypatch.setattr(outbound_adapters.smtplib, "SMTP", FakeSmtp)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Email customer needs itinerary resend",
            "description": "Customer is asking for the latest itinerary by email.",
            "customer_id": "cust-leo",
            "channel": "email",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "email",
            "actor": "agent-amara",
            "body": "SMTP adapter should send this customer reply.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert smtp_events[:3] == [
        ("connect", "smtp.wakanow.test", 2525, 9),
        ("starttls",),
        ("login", "jimb@wakanow.com", "smtp-secret"),
    ]
    assert sent_messages
    sent_message = sent_messages[0]
    assert sent_message["From"] == "jimb@wakanow.com"
    assert sent_message["To"]
    assert "SMTP adapter should send this customer reply." in sent_message.get_content()

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "email"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "smtp"
    assert outbound_message["payload"]["external_id"].startswith("<")

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    email_config = next(config for config in provider_config if config["provider"] == "email")
    assert email_config["live_delivery"] is True
    assert email_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "smtp"
        for event in audit
    )


def test_email_reply_threads_to_existing_ticket_and_reopens(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[EmailMessage] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(settings, "email_smtp_host", "smtp.thread.wakanow.test")
    monkeypatch.setattr(settings, "email_smtp_port", 2525)
    monkeypatch.setattr(settings, "email_smtp_username", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_password", "smtp-secret")
    monkeypatch.setattr(settings, "email_smtp_from_email", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_smtp_use_starttls", True)
    monkeypatch.setattr(settings, "email_smtp_use_ssl", False)
    monkeypatch.setattr(outbound_adapters.smtplib, "SMTP", FakeSmtp)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Customer email thread reopen",
            "description": "Customer needs a fresh itinerary confirmation.",
            "customer_id": "cust-leo",
            "channel": "email",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    customer = client.get(f"/api/v1/tickets/{ticket['id']}").json()["customer"]
    outbound_reply = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "email",
            "actor": "agent-amara",
            "body": "Please reply here if the itinerary still looks wrong.",
            "public": True,
        },
    )
    assert outbound_reply.status_code == 200
    assert outbound_reply.json()["metadata"]["delivery_status"] == "sent"
    assert sent_messages
    sent_message = sent_messages[0]
    assert sent_message["Message-ID"]

    waiting = client.patch(f"/api/v1/tickets/{ticket['id']}", json={"status": "waiting"})
    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting"

    ticket_count_before = len(client.get("/api/v1/tickets").json())
    external_id = f"customer-reply-{uuid4().hex}"
    threaded_reply = client.post(
        "/api/v1/connectors/inbound",
        json={
            "provider": "email",
            "external_id": external_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "subject": f"Re: {sent_message['Subject']}",
            "body": "I am replying in the same thread. The itinerary still needs correction.",
            "handle": customer["email"],
            "metadata": {
                "in_reply_to": sent_message["Message-ID"],
                "references": sent_message["Message-ID"],
            },
        },
    )

    assert threaded_reply.status_code == 201
    threaded_body = threaded_reply.json()
    assert threaded_body["deduplicated"] is False
    assert threaded_body["threaded"] is True
    assert threaded_body["ticket"]["id"] == ticket["id"]
    assert threaded_body["ticket"]["status"] == "open"
    assert "customer-replied" in threaded_body["ticket"]["tags"]
    assert "thread-reply" in threaded_body["ticket"]["tags"]
    assert "team-replied" not in threaded_body["ticket"]["tags"]
    assert len(client.get("/api/v1/tickets").json()) == ticket_count_before

    connector_event = threaded_body["connector_event"]
    assert connector_event["status"] == "thread-appended"
    assert connector_event["payload"]["thread_match"]["thread_match"] == "outbound_email_reference"

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()
    reply_event = next(event for event in timeline if event["metadata"].get("external_id") == external_id)
    assert reply_event["type"] == "inbound"
    assert reply_event["public"] is True
    assert reply_event["metadata"]["threaded"] is True
    assert "same thread" in reply_event["body"]

    status_event = next(
        event
        for event in timeline
        if event["type"] == "status_change"
        and event["metadata"].get("connector_event_id") == connector_event["id"]
    )
    assert status_event["public"] is False
    assert status_event["metadata"]["previous_status"] == "waiting"
    assert status_event["metadata"]["new_status"] == "open"
    assert status_event["metadata"]["threaded"] is True

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "connector.thread_append"
        and event["entity_id"] == connector_event["id"]
        and event["details"]["previous_status"] == "waiting"
        and event["details"]["new_status"] == "open"
        for event in audit
    )


def test_email_settings_can_be_saved_and_used_by_imap_and_smtp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex
    response = client.patch(
        "/api/v1/email/settings",
        json={
            "inbound_enabled": True,
            "inbound_host": "imap.settings.wakanow.test",
            "inbound_port": 1993,
            "inbound_username": "jimb@wakanow.com",
            "inbound_password": "imap-settings-secret",
            "inbound_mailbox": "Support",
            "inbound_use_ssl": True,
            "inbound_mark_seen": True,
            "outbound_enabled": True,
            "outbound_host": "smtp.settings.wakanow.test",
            "outbound_port": 1587,
            "outbound_username": "jimb@wakanow.com",
            "outbound_password": "smtp-settings-secret",
            "outbound_from_email": "jimb@wakanow.com",
            "outbound_use_starttls": True,
            "outbound_use_ssl": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "inbound_password" not in body
    assert "outbound_password" not in body
    assert body["inbound_password_configured"] is True
    assert body["outbound_password_configured"] is True

    inbound_config = client.get("/api/v1/inbound/provider-config").json()
    email_inbound = next(item for item in inbound_config if item["provider"] == "email")
    assert email_inbound["live_intake"] is True
    assert email_inbound["missing_settings"] == []

    outbound_config = client.get("/api/v1/outbound/provider-config").json()
    email_outbound = next(item for item in outbound_config if item["provider"] == "email")
    assert email_outbound["live_delivery"] is True
    assert email_outbound["missing_settings"] == []

    email_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "email"
    )
    assert email_account["status"] == "connected"
    assert email_account["credential_ref"] == "settings://email/market-ng"
    assert email_account["secret_configured"] is True

    sent_messages: list[EmailMessage] = []
    smtp_events: list[tuple[object, ...]] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            smtp_events.append(("connect", host, port, timeout))

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            smtp_events.append(("close",))

        def starttls(self) -> None:
            smtp_events.append(("starttls",))

        def login(self, username: str, password: str) -> None:
            smtp_events.append(("login", username, password))

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(outbound_adapters.smtplib, "SMTP", FakeSmtp)
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": f"Saved SMTP settings smoke {suffix}",
            "description": "Customer should receive an email from saved setup settings.",
            "customer_id": "cust-leo",
            "channel": "email",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "email",
            "actor": "agent-amara",
            "body": "Saved SMTP settings should send this reply.",
            "public": True,
        },
    )
    assert reply.status_code == 200
    assert reply.json()["metadata"]["delivery_status"] == "sent"
    assert smtp_events[:3] == [
        ("connect", "smtp.settings.wakanow.test", 1587, settings.email_smtp_timeout_seconds),
        ("starttls",),
        ("login", "jimb@wakanow.com", "smtp-settings-secret"),
    ]
    assert sent_messages[0]["From"] == "jimb@wakanow.com"

    inbound_email = EmailMessage()
    inbound_email["From"] = "Inbound Settings Customer <settings.customer@example.com>"
    inbound_email["To"] = "jimb@wakanow.com"
    inbound_email["Subject"] = f"Saved IMAP settings smoke {suffix}"
    inbound_email["Message-ID"] = f"<settings-imap-{suffix}@example.com>"
    inbound_email.set_content("Please check that saved IMAP settings are used.")
    raw_message = inbound_email.as_bytes()
    imap_events: list[tuple[object, ...]] = []

    class FakeImap:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            imap_events.append(("connect", host, port, timeout))

        def login(self, username: str, password: str) -> None:
            imap_events.append(("login", username, password))

        def select(self, mailbox: str) -> None:
            imap_events.append(("select", mailbox))

        def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
            imap_events.append(("uid", command, *args))
            if command == "search":
                return "OK", [b"201"]
            if command == "fetch":
                return "OK", [(b"201 RFC822", raw_message)]
            if command == "store":
                return "OK", []
            raise AssertionError(f"Unexpected IMAP command: {command}")

        def logout(self) -> None:
            imap_events.append(("logout",))

    monkeypatch.setattr(inbound_adapters.imaplib, "IMAP4_SSL", FakeImap)
    with Session(get_engine()) as session:
        job = worker_service.sync_inbound_email(session, store, "market-ng", limit=10)

    assert job.succeeded == 1
    assert imap_events[:4] == [
        ("connect", "imap.settings.wakanow.test", 1993, settings.email_imap_timeout_seconds),
        ("login", "jimb@wakanow.com", "imap-settings-secret"),
        ("select", "Support"),
        ("uid", "search", None, "UNSEEN"),
    ]
    assert ("uid", "store", "201", "+FLAGS", "(\\Seen)") in imap_events

    audit = client.get("/api/v1/audit").json()
    email_audit = next(
        event for event in audit if event["action"] == "email_provider_settings.update"
    )
    assert "inbound_password" not in email_audit["details"]
    assert "outbound_password" not in email_audit["details"]


def test_integration_credentials_settings_mask_secrets_and_drive_sms_delivery(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeSmsResponse:
        def __enter__(self) -> "FakeSmsResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return 202

        def read(self) -> bytes:
            return json.dumps({"message_id": "sms-settings-provider-100"}).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeSmsResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        sent_requests.append(
            {
                "url": request.full_url,
                "auth": request.get_header("Authorization"),
                "timeout": timeout,
                "body": json.loads(request_data.decode()),
            }
        )
        return FakeSmsResponse()

    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    response = client.patch(
        "/api/v1/integration-credentials/settings",
        json={
            "ai_provider": "rules",
            "anthropic_api_key": "anthropic-settings-secret",
            "anthropic_api_base_url": "https://api.anthropic.test",
            "anthropic_model": "claude-settings-test",
            "alert_webhook_url": "https://alerts.wakanow.test/omni",
            "alert_webhook_secret": "alert-settings-secret",
            "alert_delivery_min_severity": "critical",
            "sms_http_endpoint": "https://sms.settings.wakanow.test/messages",
            "sms_http_auth_token": "sms-settings-secret",
            "sms_http_from": "Wakanow",
            "sms_http_auth_header": "Authorization",
            "sms_http_auth_scheme": "Bearer",
            "sms_http_delivery_callback_url": "https://omni.wakanow.test/sms/callback",
            "voice_http_endpoint": "https://voice.settings.wakanow.test/calls",
            "voice_http_auth_token": "voice-settings-secret",
            "voice_http_from": "+23410000000",
            "whatsapp_cloud_api_base_url": "https://graph.facebook.test/v25.0",
            "whatsapp_phone_number_id": "wa-phone-100",
            "whatsapp_access_token": "whatsapp-settings-secret",
            "facebook_graph_api_base_url": "https://graph.facebook.test/v25.0",
            "facebook_page_id": "fb-page-100",
            "facebook_page_access_token": "facebook-settings-secret",
            "instagram_graph_api_base_url": "https://graph.instagram.test/v25.0",
            "instagram_business_account_id": "ig-business-100",
            "instagram_access_token": "instagram-settings-secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    for secret_key in (
        "anthropic_api_key",
        "alert_webhook_secret",
        "sms_http_auth_token",
        "voice_http_auth_token",
        "whatsapp_access_token",
        "facebook_page_access_token",
        "instagram_access_token",
    ):
        assert secret_key not in body
    assert body["anthropic_api_key_configured"] is True
    assert body["alert_webhook_secret_configured"] is True
    assert body["sms_http_auth_token_configured"] is True
    assert body["voice_http_auth_token_configured"] is True
    assert body["whatsapp_access_token_configured"] is True
    assert body["facebook_page_access_token_configured"] is True
    assert body["instagram_access_token_configured"] is True

    alert_config = client.get("/api/v1/alerts/delivery-config").json()
    assert alert_config["webhook_configured"] is True
    assert alert_config["min_severity"] == "critical"

    accounts = client.get("/api/v1/connectors/accounts").json()
    for provider in ("sms", "voice", "whatsapp", "facebook", "instagram"):
        account = next(item for item in accounts if item["provider"] == provider)
        assert account["status"] == "connected"
        assert account["secret_configured"] is True
        assert account["webhook_verified"] is True
        assert account["credential_ref"] == f"settings://{provider}/market-ng"

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    assert next(config for config in provider_config if config["provider"] == "sms")[
        "live_delivery"
    ] is True

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "SMS settings customer needs update",
            "description": "Customer wants text confirmation.",
            "customer_id": "cust-leo",
            "channel": "sms",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "sms",
            "actor": "agent-amara",
            "body": "Your booking update has been sent.",
            "public": True,
        },
    )

    assert reply_response.status_code == 200
    assert reply_response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://sms.settings.wakanow.test/messages"
    assert sent_request["auth"] == "Bearer sms-settings-secret"
    assert sent_request["timeout"] == settings.sms_http_timeout_seconds
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["from"] == "Wakanow"
    assert sent_body["callback_url"] == "https://omni.wakanow.test/sms/callback"

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "sms"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "http-sms"
    assert outbound_message["payload"]["external_id"] == "sms-settings-provider-100"

    audit = client.get("/api/v1/audit").json()
    credential_audit = next(
        event for event in audit if event["action"] == "integration_credentials.update"
    )
    assert "sms_http_auth_token" not in credential_audit["details"]
    assert "anthropic_api_key" not in credential_audit["details"]


def test_sms_outbound_uses_configured_http_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeSmsResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self.payload = payload

        def __enter__(self) -> "FakeSmsResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return self.status_code

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeSmsResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        body = json.loads(request_data.decode())
        sent_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "auth": request.get_header("Authorization"),
                "idempotency": request.get_header("X-Omni-Idempotency-Key"),
                "body": body,
            }
        )
        return FakeSmsResponse(202, {"message_id": "sms-provider-100", "status": "queued"})

    monkeypatch.setattr(settings, "sms_http_endpoint", "https://sms.wakanow.test/messages")
    monkeypatch.setattr(settings, "sms_http_auth_token", "sms-secret")
    monkeypatch.setattr(settings, "sms_http_from", "Wakanow")
    monkeypatch.setattr(settings, "sms_http_auth_header", "Authorization")
    monkeypatch.setattr(settings, "sms_http_auth_scheme", "Bearer")
    monkeypatch.setattr(settings, "sms_http_timeout_seconds", 7)
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    sms_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "sms"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{sms_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/sms-http",
        },
    )

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "SMS customer needs booking update",
            "description": "Customer asked for a text update on payment confirmation.",
            "customer_id": "cust-leo",
            "channel": "sms",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "sms",
            "actor": "agent-amara",
            "body": "Your payment has been confirmed and your booking is active.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://sms.wakanow.test/messages"
    assert sent_request["timeout"] == 7
    assert sent_request["auth"] == "Bearer sms-secret"
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["to"] == "+2348012345678"
    assert sent_body["from"] == "Wakanow"
    assert sent_body["body"] == "Your payment has been confirmed and your booking is active."
    assert sent_body["ticket_id"] == ticket["id"]

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "sms"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "http-sms"
    assert outbound_message["payload"]["external_id"] == "sms-provider-100"
    assert outbound_message["payload"]["provider_payload"]["status_code"] == 202

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    sms_config = next(config for config in provider_config if config["provider"] == "sms")
    assert sms_config["live_delivery"] is True
    assert sms_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "http-sms"
        for event in audit
    )


def test_whatsapp_outbound_uses_configured_cloud_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeWhatsAppResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self.payload = payload

        def __enter__(self) -> "FakeWhatsAppResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return self.status_code

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeWhatsAppResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        body = json.loads(request_data.decode())
        sent_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "auth": request.get_header("Authorization"),
                "idempotency": request.get_header("X-Omni-Idempotency-Key"),
                "body": body,
            }
        )
        return FakeWhatsAppResponse(
            200,
            {
                "messaging_product": "whatsapp",
                "contacts": [{"input": "2348012345678", "wa_id": "2348012345678"}],
                "messages": [{"id": "wamid.TEST-CLOUD-100"}],
            },
        )

    monkeypatch.setattr(settings, "whatsapp_cloud_api_base_url", "https://graph.facebook.com/v25.0")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "whatsapp_access_token", "wa-secret")
    monkeypatch.setattr(settings, "whatsapp_preview_urls", False)
    monkeypatch.setattr(settings, "whatsapp_timeout_seconds", 6)
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    whatsapp_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "whatsapp"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{whatsapp_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp-cloud",
        },
    )

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp customer needs booking update",
            "description": "Customer asked for a WhatsApp update on payment confirmation.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Your payment has been confirmed and your booking is active.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://graph.facebook.com/v25.0/1234567890/messages"
    assert sent_request["timeout"] == 6
    assert sent_request["auth"] == "Bearer wa-secret"
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["messaging_product"] == "whatsapp"
    assert sent_body["recipient_type"] == "individual"
    assert sent_body["to"] == "2348012345678"
    assert sent_body["type"] == "text"
    assert sent_body["text"]["body"] == "Your payment has been confirmed and your booking is active."
    assert sent_body["text"]["preview_url"] is False

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "whatsapp"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "whatsapp-cloud"
    assert outbound_message["payload"]["external_id"] == "wamid.TEST-CLOUD-100"
    assert outbound_message["payload"]["provider_payload"]["status_code"] == 200

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    whatsapp_config = next(config for config in provider_config if config["provider"] == "whatsapp")
    assert whatsapp_config["live_delivery"] is True
    assert whatsapp_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "whatsapp-cloud"
        for event in audit
    )


def test_facebook_outbound_uses_configured_messenger_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeFacebookResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self.payload = payload

        def __enter__(self) -> "FakeFacebookResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return self.status_code

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeFacebookResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        body = json.loads(request_data.decode())
        sent_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "auth": request.get_header("Authorization"),
                "idempotency": request.get_header("X-Omni-Idempotency-Key"),
                "body": body,
            }
        )
        return FakeFacebookResponse(
            200,
            {
                "recipient_id": "sofia.grant",
                "message_id": "m_FACEBOOK-CLOUD-100",
            },
        )

    monkeypatch.setattr(settings, "facebook_graph_api_base_url", "https://graph.facebook.com/v25.0")
    monkeypatch.setattr(settings, "facebook_page_id", "page-100")
    monkeypatch.setattr(settings, "facebook_page_access_token", "fb-secret")
    monkeypatch.setattr(settings, "facebook_messaging_type", "RESPONSE")
    monkeypatch.setattr(settings, "facebook_timeout_seconds", 5)
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    facebook_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "facebook"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{facebook_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/facebook-messenger",
        },
    )

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Facebook customer needs delivery update",
            "description": "Customer moved from page complaint into Messenger.",
            "customer_id": "cust-sofia",
            "channel": "facebook",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "facebook",
            "actor": "agent-mateo",
            "body": "Thanks for the details. We are checking the delivery status now.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://graph.facebook.com/v25.0/page-100/messages"
    assert sent_request["timeout"] == 5
    assert sent_request["auth"] == "Bearer fb-secret"
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["recipient"] == {"id": "sofia.grant"}
    assert sent_body["messaging_type"] == "RESPONSE"
    assert sent_body["message"]["text"] == "Thanks for the details. We are checking the delivery status now."

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "facebook"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "facebook-messenger"
    assert outbound_message["payload"]["external_id"] == "m_FACEBOOK-CLOUD-100"
    assert outbound_message["payload"]["provider_payload"]["status_code"] == 200

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    facebook_config = next(config for config in provider_config if config["provider"] == "facebook")
    assert facebook_config["live_delivery"] is True
    assert facebook_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "facebook-messenger"
        for event in audit
    )


def test_instagram_outbound_uses_configured_dm_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeInstagramResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self.payload = payload

        def __enter__(self) -> "FakeInstagramResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return self.status_code

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeInstagramResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        body = json.loads(request_data.decode())
        sent_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "auth": request.get_header("Authorization"),
                "idempotency": request.get_header("X-Omni-Idempotency-Key"),
                "body": body,
            }
        )
        return FakeInstagramResponse(
            200,
            {
                "recipient_id": "igsid-sofia-100",
                "message_id": "m_INSTAGRAM-DM-100",
            },
        )

    monkeypatch.setattr(settings, "instagram_graph_api_base_url", "https://graph.instagram.com/v25.0")
    monkeypatch.setattr(settings, "instagram_business_account_id", "ig-business-100")
    monkeypatch.setattr(settings, "instagram_access_token", "ig-secret")
    monkeypatch.setattr(settings, "instagram_timeout_seconds", 6)
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    instagram_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "instagram"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{instagram_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/instagram-dm",
        },
    )
    customer_response = client.post(
        "/api/v1/customers",
        json={
            "name": "Sofia Instagram",
            "email": "sofia.instagram@example.com",
            "preferred_channels": ["instagram"],
            "contact_points": [
                {"channel": "instagram", "value": "ig:igsid-sofia-100", "verified": True}
            ],
        },
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Instagram customer needs delivery update",
            "description": "Customer sent the details by Instagram DM.",
            "customer_id": customer["id"],
            "channel": "instagram",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "instagram",
            "actor": "agent-mateo",
            "body": "Thanks for the DM. We are checking the delivery status now.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://graph.instagram.com/v25.0/ig-business-100/messages"
    assert sent_request["timeout"] == 6
    assert sent_request["auth"] == "Bearer ig-secret"
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["recipient"] == {"id": "igsid-sofia-100"}
    assert sent_body["message"]["text"] == "Thanks for the DM. We are checking the delivery status now."

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "instagram"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "instagram-dm"
    assert outbound_message["payload"]["external_id"] == "m_INSTAGRAM-DM-100"
    assert outbound_message["payload"]["provider_payload"]["status_code"] == 200

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    instagram_config = next(config for config in provider_config if config["provider"] == "instagram")
    assert instagram_config["live_delivery"] is True
    assert instagram_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "instagram-dm"
        for event in audit
    )


def test_signed_sms_webhook_ingests_inbound_text_and_updates_readiness(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="sms")
    payload = {
        "event_type": "inbound_message",
        "message_id": f"sms-inbound-{uuid4().hex}",
        "from": "+2348011112222",
        "text": "Please confirm my refund status by text.",
    }
    body = _json_body(payload)

    response = TestClient(create_app()).post(
        "/api/v1/webhooks/sms/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "sms-inbound-delivery-1"),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "sms"
    assert ticket["subject"] == "SMS from +2348011112222"
    assert "connector-intake" in ticket["tags"]
    connector_payload = result["connector_event"]["payload"]
    assert connector_payload["metadata"]["sms_event_kind"] == "inbound"
    assert connector_payload["metadata"]["webhook_signature_verified"] is True

    customer = next(
        item
        for item in client.get("/api/v1/customers").json()
        if item["id"] == ticket["customer_id"]
    )
    assert customer["email"].startswith("sms-2348011112222@")
    assert any(point["channel"] == "sms" and point["value"] == "+2348011112222" for point in customer["contact_points"])

    provider_config = client.get("/api/v1/inbound/provider-config").json()
    sms_config = next(config for config in provider_config if config["provider"] == "sms")
    assert sms_config["live_intake"] is True
    assert sms_config["missing_settings"] == []


def test_signed_sms_webhook_updates_outbound_delivery_receipt(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="sms")
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"outbound_enabled": True},
    )
    assert response.status_code == 200
    account = response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "SMS delivery receipt test",
            "description": "Customer asked for a text update.",
            "customer_id": "cust-leo",
            "channel": "sms",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "sms",
            "actor": "agent-amara",
            "body": "Your refund update has been sent by SMS.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200
    assert reply_response.json()["metadata"]["delivery_status"] == "sent"
    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "sms"
    )

    receipt_payload = {
        "event_type": "delivery_receipt",
        "outbound_message_id": outbound_message["id"],
        "message_id": "sms-provider-delivered-100",
        "status": "delivered",
    }
    body = _json_body(receipt_payload)
    receipt = TestClient(create_app()).post(
        "/api/v1/webhooks/sms/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "sms-receipt-delivered-1"),
    )

    assert receipt.status_code == 201
    result = receipt.json()
    assert result["deduplicated"] is False
    assert result["receipt"]["status"] == "delivered"
    assert result["outbound_message"]["status"] == "sent"
    assert result["outbound_message"]["payload"]["delivery_receipt"]["normalized_status"] == "delivered"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(
        event["provider"] == "sms"
        and event["status"] == "delivery-receipt"
        and event["payload"]["metadata"]["webhook_delivery_id"] == "sms-receipt-delivered-1"
        for event in connector_events
    )
    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(
        event["type"] == "connector_receipt"
        and "delivery receipt reported delivered" in event["body"]
        for event in context["timeline"]
    )
    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.delivery_receipt"
        and event["entity_id"] == outbound_message["id"]
        for event in audit
    )

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/sms/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "sms-receipt-delivered-1"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True


def test_signed_whatsapp_webhook_ingests_meta_inbound_message_and_updates_readiness(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="whatsapp")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-100",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "2348000000000",
                                "phone_number_id": "1234567890",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Ada Tester"},
                                    "wa_id": "2348011112222",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "2348011112222",
                                    "id": f"wamid.INBOUND-{uuid4().hex}",
                                    "timestamp": "1717344000",
                                    "text": {
                                        "body": "Please confirm my refund status on WhatsApp.",
                                    },
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(payload)

    response = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "whatsapp-inbound-delivery-1"),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "whatsapp"
    assert ticket["subject"] == "WhatsApp from Ada Tester"
    assert "connector-intake" in ticket["tags"]
    connector_payload = result["connector_event"]["payload"]
    assert connector_payload["metadata"]["whatsapp_event_kind"] == "inbound"
    assert connector_payload["metadata"]["whatsapp_phone_number_id"] == "1234567890"
    assert connector_payload["metadata"]["webhook_signature_verified"] is True

    customer = next(
        item
        for item in client.get("/api/v1/customers").json()
        if item["id"] == ticket["customer_id"]
    )
    assert customer["email"].startswith("whatsapp-2348011112222@")
    assert any(
        point["channel"] == "whatsapp" and point["value"] == "2348011112222"
        for point in customer["contact_points"]
    )

    provider_config = client.get("/api/v1/inbound/provider-config").json()
    whatsapp_config = next(config for config in provider_config if config["provider"] == "whatsapp")
    assert whatsapp_config["live_intake"] is True
    assert whatsapp_config["missing_settings"] == []


def test_signed_whatsapp_webhook_updates_cloud_delivery_receipt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeWhatsAppResponse:
        def __enter__(self) -> "FakeWhatsAppResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return json.dumps({"messages": [{"id": "wamid.RECEIPT-100"}]}).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeWhatsAppResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        sent_requests.append(json.loads(request_data.decode()))
        return FakeWhatsAppResponse()

    monkeypatch.setattr(settings, "whatsapp_cloud_api_base_url", "https://graph.facebook.com/v25.0")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "whatsapp_access_token", "wa-secret")
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    account = _ready_connector_account(client, provider="whatsapp")
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"outbound_enabled": True},
    )
    assert response.status_code == 200
    account = response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp delivery receipt test",
            "description": "Customer asked for a WhatsApp update.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Your refund update has been sent on WhatsApp.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200
    assert sent_requests
    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "whatsapp"
    )
    assert outbound_message["payload"]["external_id"] == "wamid.RECEIPT-100"

    receipt_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-100",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "1234567890"},
                            "statuses": [
                                {
                                    "id": "wamid.RECEIPT-100",
                                    "status": "delivered",
                                    "timestamp": "1717344060",
                                    "recipient_id": "2348012345678",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(receipt_payload)
    receipt = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "whatsapp-receipt-delivered-1"),
    )

    assert receipt.status_code == 201
    result = receipt.json()
    assert result["deduplicated"] is False
    assert result["receipt"]["status"] == "delivered"
    assert result["receipt"]["provider_message_id"] == "wamid.RECEIPT-100"
    assert result["outbound_message"]["status"] == "sent"
    assert result["outbound_message"]["payload"]["delivery_receipt"]["normalized_status"] == "delivered"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(
        event["provider"] == "whatsapp"
        and event["status"] == "delivery-receipt"
        and event["payload"]["metadata"]["webhook_delivery_id"] == "whatsapp-receipt-delivered-1"
        for event in connector_events
    )
    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(
        event["type"] == "connector_receipt"
        and "delivery receipt reported delivered" in event["body"]
        for event in context["timeline"]
    )

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "whatsapp-receipt-delivered-1"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True


def test_signed_facebook_webhook_ingests_meta_message_and_updates_readiness(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="facebook")
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page-100",
                "time": 1717344000,
                "messaging": [
                    {
                        "sender": {"id": "psid-sofia-100"},
                        "recipient": {"id": "page-100"},
                        "timestamp": 1717344000,
                        "message": {
                            "mid": f"m_FACEBOOK-INBOUND-{uuid4().hex}",
                            "text": "Please confirm the missed delivery details in Messenger.",
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(payload)

    response = TestClient(create_app()).post(
        "/api/v1/webhooks/facebook/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "facebook-inbound-delivery-1"),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "facebook"
    assert ticket["subject"] == "Facebook Messenger from psid-sofia-100"
    assert "connector-intake" in ticket["tags"]
    connector_payload = result["connector_event"]["payload"]
    assert connector_payload["metadata"]["facebook_event_kind"] == "inbound"
    assert connector_payload["metadata"]["facebook_page_id"] == "page-100"
    assert connector_payload["metadata"]["webhook_signature_verified"] is True

    customer = next(
        item
        for item in client.get("/api/v1/customers").json()
        if item["id"] == ticket["customer_id"]
    )
    assert customer["email"].startswith("facebook-psidsofia100@")
    assert any(
        point["channel"] == "facebook" and point["value"] == "psid-sofia-100"
        for point in customer["contact_points"]
    )

    provider_config = client.get("/api/v1/inbound/provider-config").json()
    facebook_config = next(config for config in provider_config if config["provider"] == "facebook")
    assert facebook_config["live_intake"] is True
    assert facebook_config["missing_settings"] == []


def test_signed_facebook_webhook_updates_delivery_receipt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeFacebookResponse:
        def __enter__(self) -> "FakeFacebookResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return json.dumps(
                {
                    "recipient_id": "sofia.grant",
                    "message_id": "m_FACEBOOK-RECEIPT-100",
                }
            ).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeFacebookResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        sent_requests.append(json.loads(request_data.decode()))
        return FakeFacebookResponse()

    monkeypatch.setattr(settings, "facebook_graph_api_base_url", "https://graph.facebook.com/v25.0")
    monkeypatch.setattr(settings, "facebook_page_id", "page-100")
    monkeypatch.setattr(settings, "facebook_page_access_token", "fb-secret")
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    account = _ready_connector_account(client, provider="facebook")
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"outbound_enabled": True},
    )
    assert response.status_code == 200
    account = response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Facebook delivery receipt test",
            "description": "Customer is waiting for a Messenger update.",
            "customer_id": "cust-sofia",
            "channel": "facebook",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "facebook",
            "actor": "agent-mateo",
            "body": "Your Messenger update has been sent.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200
    assert sent_requests
    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "facebook"
    )
    assert outbound_message["payload"]["external_id"] == "m_FACEBOOK-RECEIPT-100"

    receipt_payload = {
        "object": "page",
        "entry": [
            {
                "id": "page-100",
                "time": 1717344060,
                "messaging": [
                    {
                        "sender": {"id": "psid-sofia-100"},
                        "recipient": {"id": "page-100"},
                        "timestamp": 1717344060,
                        "delivery": {
                            "mids": ["m_FACEBOOK-RECEIPT-100"],
                            "watermark": 1717344060,
                            "seq": 37,
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(receipt_payload)
    receipt = TestClient(create_app()).post(
        "/api/v1/webhooks/facebook/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "facebook-receipt-delivered-1"),
    )

    assert receipt.status_code == 201
    result = receipt.json()
    assert result["deduplicated"] is False
    assert result["receipt"]["status"] == "delivered"
    assert result["receipt"]["provider_message_id"] == "m_FACEBOOK-RECEIPT-100"
    assert result["outbound_message"]["status"] == "sent"
    assert result["outbound_message"]["payload"]["delivery_receipt"]["normalized_status"] == "delivered"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(
        event["provider"] == "facebook"
        and event["status"] == "delivery-receipt"
        and event["payload"]["metadata"]["webhook_delivery_id"] == "facebook-receipt-delivered-1"
        for event in connector_events
    )
    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(
        event["type"] == "connector_receipt"
        and "delivery receipt reported delivered" in event["body"]
        for event in context["timeline"]
    )

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/facebook/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "facebook-receipt-delivered-1"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True


def test_signed_instagram_webhook_ingests_meta_message_and_updates_readiness(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="instagram")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "ig-business-100",
                "time": 1717344000,
                "messaging": [
                    {
                        "sender": {"id": "igsid-sofia-100"},
                        "recipient": {"id": "ig-business-100"},
                        "timestamp": 1717344000,
                        "message": {
                            "mid": f"m_INSTAGRAM-INBOUND-{uuid4().hex}",
                            "text": "Please confirm the missed delivery details in Instagram DM.",
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(payload)

    response = TestClient(create_app()).post(
        "/api/v1/webhooks/instagram/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "instagram-inbound-delivery-1"),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "instagram"
    assert ticket["subject"] == "Instagram DM from igsid-sofia-100"
    assert "connector-intake" in ticket["tags"]
    connector_payload = result["connector_event"]["payload"]
    assert connector_payload["metadata"]["instagram_event_kind"] == "inbound"
    assert connector_payload["metadata"]["instagram_business_account_id"] == "ig-business-100"
    assert connector_payload["metadata"]["webhook_signature_verified"] is True

    customer = next(
        item
        for item in client.get("/api/v1/customers").json()
        if item["id"] == ticket["customer_id"]
    )
    assert customer["email"].startswith("instagram-igsidsofia100@")
    assert any(
        point["channel"] == "instagram" and point["value"] == "igsid-sofia-100"
        for point in customer["contact_points"]
    )

    provider_config = client.get("/api/v1/inbound/provider-config").json()
    instagram_config = next(config for config in provider_config if config["provider"] == "instagram")
    assert instagram_config["live_intake"] is True
    assert instagram_config["missing_settings"] == []


def test_signed_instagram_webhook_updates_delivery_receipt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeInstagramResponse:
        def __enter__(self) -> "FakeInstagramResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return json.dumps(
                {
                    "recipient_id": "igsid-sofia-100",
                    "message_id": "m_INSTAGRAM-RECEIPT-100",
                }
            ).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeInstagramResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        sent_requests.append(json.loads(request_data.decode()))
        return FakeInstagramResponse()

    monkeypatch.setattr(settings, "instagram_graph_api_base_url", "https://graph.instagram.com/v25.0")
    monkeypatch.setattr(settings, "instagram_business_account_id", "ig-business-100")
    monkeypatch.setattr(settings, "instagram_access_token", "ig-secret")
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    account = _ready_connector_account(client, provider="instagram")
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"outbound_enabled": True},
    )
    assert response.status_code == 200
    account = response.json()
    customer_response = client.post(
        "/api/v1/customers",
        json={
            "name": "Sofia Instagram",
            "email": "sofia.instagram.receipt@example.com",
            "preferred_channels": ["instagram"],
            "contact_points": [
                {"channel": "instagram", "value": "ig:igsid-sofia-100", "verified": True}
            ],
        },
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Instagram delivery receipt test",
            "description": "Customer is waiting for an Instagram DM update.",
            "customer_id": customer["id"],
            "channel": "instagram",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "instagram",
            "actor": "agent-mateo",
            "body": "Your Instagram DM update has been sent.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200
    assert sent_requests
    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "instagram"
    )
    assert outbound_message["payload"]["external_id"] == "m_INSTAGRAM-RECEIPT-100"

    receipt_payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "ig-business-100",
                "time": 1717344060,
                "messaging": [
                    {
                        "sender": {"id": "igsid-sofia-100"},
                        "recipient": {"id": "ig-business-100"},
                        "timestamp": 1717344060,
                        "read": {
                            "mid": "m_INSTAGRAM-RECEIPT-100",
                            "watermark": 1717344060,
                        },
                    }
                ],
            }
        ],
    }
    body = _json_body(receipt_payload)
    receipt = TestClient(create_app()).post(
        "/api/v1/webhooks/instagram/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "instagram-receipt-read-1"),
    )

    assert receipt.status_code == 201
    result = receipt.json()
    assert result["deduplicated"] is False
    assert result["receipt"]["status"] == "read"
    assert result["receipt"]["provider_message_id"] == "m_INSTAGRAM-RECEIPT-100"
    assert result["outbound_message"]["status"] == "sent"
    assert result["outbound_message"]["payload"]["delivery_receipt"]["normalized_status"] == "read"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(
        event["provider"] == "instagram"
        and event["status"] == "delivery-receipt"
        and event["payload"]["metadata"]["webhook_delivery_id"] == "instagram-receipt-read-1"
        for event in connector_events
    )
    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(
        event["type"] == "connector_receipt"
        and "delivery receipt reported read" in event["body"]
        for event in context["timeline"]
    )

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/instagram/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "instagram-receipt-read-1"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True


def test_voice_outbound_uses_configured_http_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeVoiceResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self.payload = payload

        def __enter__(self) -> "FakeVoiceResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return self.status_code

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeVoiceResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        body = json.loads(request_data.decode())
        sent_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "auth": request.headers.get("X-voice-token")
                or request.headers.get("X-Voice-Token"),
                "idempotency": request.get_header("X-Omni-Idempotency-Key"),
                "body": body,
            }
        )
        return FakeVoiceResponse(
            202,
            {
                "call_id": "call_VOICE-HTTP-100",
                "status": "queued",
            },
        )

    monkeypatch.setattr(settings, "voice_http_endpoint", "https://voice.example.test/callbacks")
    monkeypatch.setattr(settings, "voice_http_auth_token", "voice-secret")
    monkeypatch.setattr(settings, "voice_http_from", "+2348000000000")
    monkeypatch.setattr(settings, "voice_http_auth_header", "X-Voice-Token")
    monkeypatch.setattr(settings, "voice_http_auth_scheme", "Token")
    monkeypatch.setattr(settings, "voice_http_status_callback_url", "https://omni.example.test/webhooks/voice/ng")
    monkeypatch.setattr(settings, "voice_http_timeout_seconds", 7)
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    voice_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "voice"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{voice_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/voice-provider",
        },
    )
    customer_response = client.post(
        "/api/v1/customers",
        json={
            "name": "Priya Voice",
            "email": "priya.voice@example.com",
            "preferred_channels": ["voice"],
            "contact_points": [
                {"channel": "voice", "value": "voice:+13125550108", "verified": True}
            ],
        },
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "VIP renewal callback requested",
            "description": "Customer requested a callback before procurement meeting.",
            "customer_id": customer["id"],
            "channel": "voice",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "voice",
            "actor": "agent-zoe",
            "body": "Please call this customer back before 15:00 and use the renewal script.",
            "public": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "sent"
    assert sent_requests
    sent_request = sent_requests[0]
    assert sent_request["url"] == "https://voice.example.test/callbacks"
    assert sent_request["timeout"] == 7
    assert sent_request["auth"] == "Token voice-secret"
    sent_body = sent_request["body"]
    assert isinstance(sent_body, dict)
    assert sent_body["action"] == "callback_request"
    assert sent_body["to"] == "+13125550108"
    assert sent_body["from"] == "+2348000000000"
    assert sent_body["body"] == "Please call this customer back before 15:00 and use the renewal script."
    assert sent_body["status_callback_url"] == "https://omni.example.test/webhooks/voice/ng"
    assert sent_body["metadata"]["actor"] == "agent-zoe"

    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "voice"
    )
    assert outbound_message["status"] == "sent"
    assert outbound_message["payload"]["adapter"] == "http-voice"
    assert outbound_message["payload"]["external_id"] == "call_VOICE-HTTP-100"
    assert outbound_message["payload"]["provider_payload"]["status_code"] == 202

    provider_config = client.get("/api/v1/outbound/provider-config").json()
    voice_config = next(config for config in provider_config if config["provider"] == "voice")
    assert voice_config["live_delivery"] is True
    assert voice_config["missing_settings"] == []

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "outbound.sent"
        and event["details"].get("adapter") == "http-voice"
        for event in audit
    )


def test_signed_voice_webhook_ingests_call_log_and_updates_readiness(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client, provider="voice")
    payload = {
        "event_type": "callback_request",
        "call_id": f"call_VOICE-INBOUND-{uuid4().hex}",
        "from": "+13125550108",
        "caller_name": "Priya Voice",
        "summary": "Customer requested a renewal callback before procurement review.",
        "duration_seconds": 42,
    }
    body = _json_body(payload)

    response = TestClient(create_app()).post(
        "/api/v1/webhooks/voice/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "voice-inbound-delivery-1"),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "voice"
    assert ticket["subject"] == "Voice callback request from Priya Voice"
    assert "connector-intake" in ticket["tags"]
    connector_payload = result["connector_event"]["payload"]
    assert connector_payload["metadata"]["voice_event_kind"] == "inbound"
    assert connector_payload["metadata"]["voice_event_type"] == "callback_request"
    assert connector_payload["metadata"]["webhook_signature_verified"] is True

    customer = next(
        item
        for item in client.get("/api/v1/customers").json()
        if item["id"] == ticket["customer_id"]
    )
    assert customer["email"].startswith("voice-13125550108@")
    assert any(
        point["channel"] == "voice" and point["value"] == "+13125550108"
        for point in customer["contact_points"]
    )

    provider_config = client.get("/api/v1/inbound/provider-config").json()
    voice_config = next(config for config in provider_config if config["provider"] == "voice")
    assert voice_config["live_intake"] is True
    assert voice_config["missing_settings"] == []


def test_signed_voice_webhook_updates_call_status_receipt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_requests: list[dict[str, object]] = []

    class FakeVoiceResponse:
        def __enter__(self) -> "FakeVoiceResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getcode(self) -> int:
            return 202

        def read(self) -> bytes:
            return json.dumps(
                {
                    "call_id": "call_VOICE-RECEIPT-100",
                    "status": "queued",
                }
            ).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeVoiceResponse:
        request_data = request.data
        assert isinstance(request_data, bytes)
        sent_requests.append(json.loads(request_data.decode()))
        return FakeVoiceResponse()

    monkeypatch.setattr(settings, "voice_http_endpoint", "https://voice.example.test/callbacks")
    monkeypatch.setattr(settings, "voice_http_auth_token", "voice-secret")
    monkeypatch.setattr(settings, "voice_http_from", "+2348000000000")
    monkeypatch.setattr(outbound_adapters.urlrequest, "urlopen", fake_urlopen)

    account = _ready_connector_account(client, provider="voice")
    response = client.patch(
        f"/api/v1/connectors/accounts/{account['id']}",
        json={"outbound_enabled": True},
    )
    assert response.status_code == 200
    account = response.json()
    customer_response = client.post(
        "/api/v1/customers",
        json={
            "name": "Priya Voice",
            "email": "priya.voice.receipt@example.com",
            "preferred_channels": ["voice"],
            "contact_points": [
                {"channel": "voice", "value": "voice:+13125550108", "verified": True}
            ],
        },
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Voice delivery receipt test",
            "description": "Customer is waiting for a callback.",
            "customer_id": customer["id"],
            "channel": "voice",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "voice",
            "actor": "agent-zoe",
            "body": "Please call this customer back now.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200
    assert sent_requests
    outbound_message = next(
        message
        for message in client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
        if message["provider"] == "voice"
    )
    assert outbound_message["payload"]["external_id"] == "call_VOICE-RECEIPT-100"

    receipt_payload = {
        "event_type": "call_status",
        "call_id": "call_VOICE-RECEIPT-100",
        "status": "completed",
        "duration_seconds": 96,
    }
    body = _json_body(receipt_payload)
    receipt = TestClient(create_app()).post(
        "/api/v1/webhooks/voice/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "voice-receipt-completed-1"),
    )

    assert receipt.status_code == 201
    result = receipt.json()
    assert result["deduplicated"] is False
    assert result["receipt"]["status"] == "delivered"
    assert result["receipt"]["provider_message_id"] == "call_VOICE-RECEIPT-100"
    assert result["outbound_message"]["status"] == "sent"
    assert result["outbound_message"]["payload"]["delivery_receipt"]["normalized_status"] == "delivered"

    connector_events = client.get("/api/v1/connectors/events").json()
    assert any(
        event["provider"] == "voice"
        and event["status"] == "delivery-receipt"
        and event["payload"]["metadata"]["webhook_delivery_id"] == "voice-receipt-completed-1"
        for event in connector_events
    )
    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(
        event["type"] == "connector_receipt"
        and "delivery receipt reported delivered" in event["body"]
        for event in context["timeline"]
    )

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/voice/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "voice-receipt-completed-1"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True


def test_email_inbound_sync_uses_configured_imap_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = EmailMessage()
    email["From"] = "Ada Customer <ada.customer@example.com>"
    email["To"] = "jimb@wakanow.com"
    email["Subject"] = "Inbound itinerary question"
    email["Message-ID"] = "<wakanow-itinerary-100@example.com>"
    email.set_content("Please resend my itinerary and confirm the latest travel date.")
    email.add_attachment(
        b"passport proof bytes",
        maintype="text",
        subtype="plain",
        filename="passport-proof.txt",
    )
    email.add_attachment(
        b"unsafe email bytes",
        maintype="application",
        subtype="x-msdownload",
        filename="unsafe-email.exe",
    )
    raw_message = email.as_bytes()
    imap_events: list[tuple[object, ...]] = []

    class FakeImap:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            imap_events.append(("connect", host, port, timeout))

        def login(self, username: str, password: str) -> None:
            imap_events.append(("login", username, password))

        def select(self, mailbox: str) -> None:
            imap_events.append(("select", mailbox))

        def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
            imap_events.append(("uid", command, *args))
            if command == "search":
                return "OK", [b"101"]
            if command == "fetch":
                return "OK", [(b"101 RFC822", raw_message)]
            if command == "store":
                return "OK", []
            raise AssertionError(f"Unexpected IMAP command: {command}")

        def logout(self) -> None:
            imap_events.append(("logout",))

    monkeypatch.setattr(settings, "email_imap_poll_enabled", True)
    monkeypatch.setattr(settings, "email_imap_host", "imap.wakanow.test")
    monkeypatch.setattr(settings, "email_imap_port", 993)
    monkeypatch.setattr(settings, "email_imap_username", "jimb@wakanow.com")
    monkeypatch.setattr(settings, "email_imap_password", "imap-secret")
    monkeypatch.setattr(settings, "email_imap_mailbox", "INBOX")
    monkeypatch.setattr(settings, "email_imap_use_ssl", True)
    monkeypatch.setattr(settings, "email_imap_timeout_seconds", 7)
    monkeypatch.setattr(settings, "email_imap_mark_seen", True)
    monkeypatch.setattr(inbound_adapters.imaplib, "IMAP4_SSL", FakeImap)

    config = client.get("/api/v1/inbound/provider-config").json()
    email_config = next(item for item in config if item["provider"] == "email")
    assert email_config["live_intake"] is True
    assert email_config["missing_settings"] == []

    with Session(get_engine()) as session:
        job = worker_service.sync_inbound_email(session, store, "market-ng", limit=10)

    assert job.processed == 1
    assert job.succeeded == 1
    assert job.failed == 0
    assert job.details["message_ids"] == ["<wakanow-itinerary-100@example.com>"]
    assert job.details["attachments_saved"] == 1
    assert job.details["attachments_blocked"] == 1
    assert job.details["attachments_skipped"] == 0
    assert len(job.details["attachment_ids"]) == 2
    assert imap_events[:4] == [
        ("connect", "imap.wakanow.test", 993, 7),
        ("login", "jimb@wakanow.com", "imap-secret"),
        ("select", "INBOX"),
        ("uid", "search", None, "UNSEEN"),
    ]
    assert ("uid", "store", "101", "+FLAGS", "(\\Seen)") in imap_events

    tickets = client.get("/api/v1/tickets").json()
    ticket = next(item for item in tickets if item["subject"] == "Inbound itinerary question")
    assert ticket["channel"] == "email"
    attachments = client.get(f"/api/v1/tickets/{ticket['id']}/attachments").json()
    clean_attachment = next(item for item in attachments if item["filename"] == "passport-proof.txt")
    blocked_attachment = next(item for item in attachments if item["filename"] == "unsafe-email.exe")
    assert clean_attachment["scan_status"] == "clean"
    assert clean_attachment["storage_key"].startswith("local:")
    assert blocked_attachment["scan_status"] == "blocked"
    assert blocked_attachment["storage_key"].startswith("blocked:")
    clean_download = client.get(
        f"/api/v1/tickets/{ticket['id']}/attachments/{clean_attachment['id']}/download"
    )
    assert clean_download.status_code == 200
    assert clean_download.content == b"passport proof bytes"
    blocked_download = client.get(
        f"/api/v1/tickets/{ticket['id']}/attachments/{blocked_attachment['id']}/download"
    )
    assert blocked_download.status_code == 403

    events = client.get("/api/v1/connectors/events").json()
    connector_event = next(
        item for item in events if item["external_id"] == "<wakanow-itinerary-100@example.com>"
    )
    assert connector_event["provider"] == "email"
    assert connector_event["ticket_id"] == ticket["id"]
    assert connector_event["payload"]["metadata"]["imap_uid"] == "101"
    assert connector_event["payload"]["metadata"]["attachments"] == [
        {
            "filename": "passport-proof.txt",
            "content_type": "text/plain",
            "size_bytes": len(b"passport proof bytes"),
        },
        {
            "filename": "unsafe-email.exe",
            "content_type": "application/x-msdownload",
            "size_bytes": len(b"unsafe email bytes"),
        },
    ]

    account = next(
        item
        for item in client.get("/api/v1/connectors/accounts").json()
        if item["provider"] == "email"
    )
    assert account["last_sync_at"] is not None
    assert account["last_error"] is None

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "connector.ingest" for event in audit)
    assert any(
        event["action"] == "attachment.create"
        and event["entity_id"] == clean_attachment["id"]
        and event["actor"] == "email-inbound:<wakanow-itinerary-100@example.com>"
        for event in audit
    )
    assert any(event["action"] == "worker.email_inbound_sync" for event in audit)

    with Session(get_engine()) as session:
        duplicate = worker_service.sync_inbound_email(session, store, "market-ng", limit=10)

    assert duplicate.processed == 1
    assert duplicate.succeeded == 1
    assert duplicate.details["deduplicated"] == 1
    assert duplicate.details["attachment_ids"] == []
    assert len(client.get(f"/api/v1/tickets/{ticket['id']}/attachments").json()) == len(attachments)
    assert len(
        [
            item
            for item in client.get("/api/v1/connectors/events").json()
            if item["external_id"] == "<wakanow-itinerary-100@example.com>"
        ]
    ) == 1


def test_worker_processes_due_outbound_retries_after_connector_is_enabled(
    client: TestClient,
) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Worker should retry this WhatsApp reply.",
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["delivery_status"] == "failed"
    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )

    with Session(get_engine()) as session:
        message_record = session.get(OutboundMessageRecord, failed_message["id"])
        assert message_record is not None
        message_record.next_attempt_at = utc_now() - timedelta(minutes=1)
        session.commit()

    whatsapp_account = next(
        account
        for account in client.get("/api/v1/connectors/accounts").json()
        if account["provider"] == "whatsapp"
    )
    client.patch(
        f"/api/v1/connectors/accounts/{whatsapp_account['id']}",
        json={
            "status": "connected",
            "outbound_enabled": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
        },
    )

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"])

    outbound_job = next(job for job in summary.jobs if job.name == "outbound_retry")
    assert outbound_job.processed == 1
    assert outbound_job.succeeded == 1

    messages = client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
    retried = next(message for message in messages if message["id"] == failed_message["id"])
    assert retried["status"] == "sent"
    assert retried["attempts"] == 2

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "worker.outbound_batch" for event in audit)


def test_worker_dead_letters_due_outbound_after_max_attempts(client: TestClient) -> None:
    ticket = next(item for item in client.get("/api/v1/tickets").json() if item["channel"] == "whatsapp")
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "This should become a dead-letter after the worker retry.",
            "public": True,
        },
    )
    assert response.status_code == 200
    failed_message = next(
        message
        for message in client.get("/api/v1/outbound/messages").json()
        if message["ticket_id"] == ticket["id"]
    )

    with Session(get_engine()) as session:
        message_record = session.get(OutboundMessageRecord, failed_message["id"])
        assert message_record is not None
        message_record.attempts = message_record.max_attempts - 1
        message_record.next_attempt_at = utc_now() - timedelta(minutes=1)
        session.commit()

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"])

    outbound_job = next(job for job in summary.jobs if job.name == "outbound_retry")
    assert outbound_job.processed == 1
    assert outbound_job.dead_lettered == 1

    messages = client.get(f"/api/v1/outbound/messages?ticket_id={ticket['id']}").json()
    dead_lettered = next(message for message in messages if message["id"] == failed_message["id"])
    assert dead_lettered["status"] == "dead_lettered"
    assert dead_lettered["next_attempt_at"] is None

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "outbound.dead_lettered" for event in audit)

    alerts = client.get("/api/v1/alerts").json()
    alert = next(
        item
        for item in alerts
        if item["entity_type"] == "outbound_message" and item["entity_id"] == failed_message["id"]
    )
    assert alert["severity"] == "critical"
    assert alert["status"] == "open"
    assert alert["details"]["provider"] == "whatsapp"
    assert alert["occurrence_count"] == 1

    resolved = client.patch(
        f"/api/v1/alerts/{alert['id']}",
        json={"status": "resolved", "note": "Connector owner notified."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_by"] == "gbolahan@omniticket.example.com"
    assert all(item["id"] != alert["id"] for item in client.get("/api/v1/alerts").json())
    resolved_alerts = client.get("/api/v1/alerts?include_resolved=true").json()
    assert any(item["id"] == alert["id"] for item in resolved_alerts)


def test_worker_delivers_operational_alerts_to_configured_webhook(
    client: TestClient,
    monkeypatch,
) -> None:
    sent_payloads: list[dict] = []

    class FakeAlertSender:
        def send(self, payload: dict) -> AlertWebhookResponse:
            sent_payloads.append(payload)
            return AlertWebhookResponse(status_code=202, body="accepted")

    monkeypatch.setattr(settings, "alert_webhook_url", "https://alerts.example.test/omni")
    monkeypatch.setattr(settings, "alert_delivery_min_severity", "warning")
    monkeypatch.setattr(settings, "alert_delivery_max_attempts", 3)

    with Session(get_engine()) as session:
        alert = operational_alert_repository.upsert_alert(
            session,
            market_id="market-ng",
            severity=OperationalAlertSeverity.critical,
            source="pytest",
            entity_type="worker",
            entity_id="alert-delivery-test",
            dedupe_key="pytest:alert-delivery-test",
            title="Alert delivery test",
            message="This alert should be delivered through the configured webhook.",
            details={"scope": "test"},
            actor="pytest",
        )
        session.commit()

    with Session(get_engine()) as session:
        job = worker_service.dispatch_alert_deliveries(
            session,
            store,
            "market-ng",
            sender=FakeAlertSender(),
        )

    assert job.name == "alert_delivery"
    assert job.processed == 1
    assert job.succeeded == 1
    assert job.failed == 0
    assert sent_payloads[0]["alert"]["id"] == alert.id
    assert sent_payloads[0]["alert"]["severity"] == "critical"

    deliveries = client.get("/api/v1/alerts/deliveries?include_sent=true").json()
    delivery = next(item for item in deliveries if item["alert_id"] == alert.id)
    assert delivery["status"] == "sent"
    assert delivery["attempts"] == 1
    assert delivery["destination_name"] == "operations_webhook"

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "alert_delivery.sent"
        and event["details"]["alert_id"] == alert.id
        for event in audit
    )


def test_worker_refreshes_sla_and_recomputes_operational_views(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    past = utc_now() - timedelta(hours=1)
    with Session(get_engine()) as session:
        record = session.get(TicketRecord, ticket["id"])
        assert record is not None
        record.sla = {
            **record.sla,
            "first_response_due_at": past.isoformat(),
            "resolution_due_at": past.isoformat(),
            "risk": "on_track",
            "breached": False,
        }
        session.commit()

    with Session(get_engine()) as session:
        summary = worker_service.run_once(session, store, market_ids=["market-ng"], outbound_limit=0)

    sla_job = next(job for job in summary.jobs if job.name == "sla_refresh")
    queue_job = next(job for job in summary.jobs if job.name == "work_queue_recompute")
    analytics_job = next(job for job in summary.jobs if job.name == "analytics_rollup")
    assert sla_job.succeeded >= 1
    assert ticket["id"] in sla_job.details["changed_ticket_ids"]
    assert queue_job.processed >= 1
    assert analytics_job.details["open_tickets"] >= 1
    assert analytics_job.details["rollup_id"].startswith("analytics_rollup_")

    with Session(get_engine()) as session:
        refreshed = session.get(TicketRecord, ticket["id"])
        assert refreshed is not None
        assert refreshed.sla["risk"] == "breached"
        assert refreshed.sla["breached"] is True
        rollup = session.get(AnalyticsRollupRecord, analytics_job.details["rollup_id"])
        assert rollup is not None
        assert rollup.market_id == "market-ng"
        assert rollup.open_tickets >= 1
        assert rollup.channel_volume
        actions = set(
            session.scalars(
                select(AuditEventRecord.action).where(AuditEventRecord.actor == "omni-worker")
            )
        )
    assert {
        "worker.sla_refresh",
        "worker.work_queue_recompute",
        "worker.analytics_rollup",
    } <= actions

    rollups = client.get("/api/v1/analytics/rollups").json()
    assert any(item["id"] == analytics_job.details["rollup_id"] for item in rollups)


def test_worker_emits_supervisor_notification_once_per_risk_state(client: TestClient) -> None:
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Instagram complaint needs supervisor visibility",
            "description": "Customer reported a public billing complaint and wants an update now.",
            "customer_id": "cust-leo",
            "channel": "instagram",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    past = utc_now() - timedelta(hours=1)

    with Session(get_engine()) as session:
        record = session.get(TicketRecord, ticket["id"])
        assert record is not None
        record.priority = "high"
        record.sla = {
            **record.sla,
            "first_response_due_at": past.isoformat(),
            "resolution_due_at": past.isoformat(),
            "risk": "on_track",
            "breached": False,
        }
        session.commit()

    with Session(get_engine()) as session:
        first_summary = worker_service.run_once(session, store, market_ids=["market-ng"], outbound_limit=0)

    sla_job = next(job for job in first_summary.jobs if job.name == "sla_refresh")
    assert ticket["id"] in sla_job.details["notified_ticket_ids"]

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline")
    assert timeline.status_code == 200
    assert any(
        event["actor"] == "omni-worker"
        and event["type"] == "internal_note"
        and event["body"].startswith("Supervisor notification:")
        for event in timeline.json()
    )

    audit = client.get("/api/v1/audit").json()
    notifications = [
        event
        for event in audit
        if event["action"] == "worker.supervisor_notification" and event["entity_id"] == ticket["id"]
    ]
    assert len(notifications) == 1
    assert notifications[0]["details"]["risk"] == "breached"

    alerts = client.get("/api/v1/alerts").json()
    sla_alert = next(
        item
        for item in alerts
        if item["source"] == "sla_worker" and item["entity_id"] == ticket["id"]
    )
    assert sla_alert["severity"] == "critical"
    assert sla_alert["details"]["public_id"] == ticket["public_id"]

    with Session(get_engine()) as session:
        second_summary = worker_service.run_once(session, store, market_ids=["market-ng"], outbound_limit=0)

    repeat_sla_job = next(job for job in second_summary.jobs if job.name == "sla_refresh")
    assert ticket["id"] not in repeat_sla_job.details["notified_ticket_ids"]


def test_handoff_lifecycle_writes_back_to_ticket_timeline(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    create_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Fulfillment",
            "requested_by": "agent-mateo",
            "reason": "Need delivery confirmation before customer update.",
            "due_minutes": 45,
            "checklist": ["Confirm warehouse state", "Return ETA"],
        },
    )
    assert create_response.status_code == 201
    handoff = create_response.json()
    assert handoff["status"] == "requested"

    accepted_due_at = "2026-05-30T12:00:00Z"
    update_response = client.patch(
        f"/api/v1/handoffs/{handoff['id']}",
        json={"status": "accepted", "due_at": accepted_due_at},
    )
    assert update_response.status_code == 200
    accepted = update_response.json()
    assert accepted["status"] == "accepted"
    assert accepted["due_at"].startswith("2026-05-30T12:00:00")

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline").json()
    assert any(event["type"] == "handoff_requested" for event in timeline)
    assert any(
        event["type"] == "handoff_accepted"
        and event["metadata"].get("handoff_id") == handoff["id"]
        and event["metadata"].get("status_was") == "requested"
        for event in timeline
    )


def test_handoff_blocker_and_checklist_updates_persist(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    create_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Payments",
            "requested_by": "agent-amara",
            "reason": "Need processor confirmation.",
            "due_minutes": 60,
            "checklist": ["Check processor state"],
        },
    )
    assert create_response.status_code == 201
    handoff = create_response.json()
    checklist_item_id = handoff["checklist"][0]["id"]

    blocked_response = client.patch(
        f"/api/v1/handoffs/{handoff['id']}",
        json={
            "blocker": "Waiting for gateway callback",
            "checklist_item_id": checklist_item_id,
            "checklist_item_complete": True,
        },
    )
    assert blocked_response.status_code == 200
    blocked = blocked_response.json()
    assert blocked["status"] == "blocked"
    assert blocked["blocker"] == "Waiting for gateway callback"
    assert blocked["checklist"][0]["complete"] is True

    store.seed()

    persisted_handoffs = client.get("/api/v1/handoffs")
    assert persisted_handoffs.status_code == 200
    persisted = next(item for item in persisted_handoffs.json() if item["id"] == handoff["id"])
    assert persisted["status"] == "blocked"
    assert persisted["blocker"] == "Waiting for gateway callback"
    assert persisted["checklist"][0]["complete"] is True


def test_ticket_timeline_and_handoff_are_database_first_after_runtime_reset(
    client: TestClient,
) -> None:
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp restart persistence check",
            "description": "Customer expects this ticket, timeline, and handoff to survive restart.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    handoff_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/handoffs",
        json={
            "to_team": "Payments",
            "requested_by": "agent-amara",
            "reason": "Confirm payment processor state after restart.",
            "checklist": ["Check processor", "Return answer"],
        },
    )
    assert handoff_response.status_code == 201
    handoff_id = handoff_response.json()["id"]

    reply_response = client.post(
        f"/api/v1/tickets/{ticket['id']}/reply",
        json={
            "channel": "whatsapp",
            "actor": "agent-amara",
            "body": "Restart-safe reply.",
            "public": True,
        },
    )
    assert reply_response.status_code == 200

    store.seed()

    context = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert context.status_code == 200
    body = context.json()
    assert body["ticket"]["id"] == ticket["id"]
    assert any(event["type"] == "inbound" for event in body["timeline"])
    assert any(event["type"] == "public_reply" for event in body["timeline"])
    assert any(handoff["id"] == handoff_id for handoff in body["handoffs"])

    timeline = client.get(f"/api/v1/tickets/{ticket['id']}/timeline")
    assert timeline.status_code == 200
    assert any(event["type"] == "public_reply" for event in timeline.json())

    connector_events = client.get("/api/v1/connectors/events")
    assert connector_events.status_code == 200
    assert any(event["ticket_id"] == ticket["id"] for event in connector_events.json())


def test_ticket_task_toggle_is_database_backed(client: TestClient) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    task = ticket["tasks"][0]

    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={
            "task_item_id": task["id"],
            "task_item_complete": True,
        },
    )
    assert response.status_code == 200
    updated_ticket = response.json()
    assert any(item["id"] == task["id"] and item["complete"] is True for item in updated_ticket["tasks"])

    store.seed()

    persisted = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert persisted.status_code == 200
    persisted_ticket = persisted.json()["ticket"]
    assert any(item["id"] == task["id"] and item["complete"] is True for item in persisted_ticket["tasks"])


def test_connector_ingest_creates_ticket_and_deduplicates(client: TestClient) -> None:
    payload = {
        "provider": "instagram",
        "external_id": "ig-msg-123",
        "customer_name": "Nia Brooks",
        "customer_email": "nia@example.com",
        "subject": "Instagram DM about missed order",
        "body": "I posted publicly because my order delivery was missed.",
        "handle": "@niabrooks",
    }
    first = client.post("/api/v1/connectors/inbound", json=payload)
    assert first.status_code == 201
    assert first.json()["deduplicated"] is False
    ticket = first.json()["ticket"]
    assert ticket["channel"] == "instagram"
    assert "reputation-risk" in ticket["tags"]

    second = client.post("/api/v1/connectors/inbound", json=payload)
    assert second.status_code == 201
    assert second.json()["deduplicated"] is True
    assert second.json()["ticket"]["id"] == ticket["id"]


def test_connector_ingest_is_database_first_after_runtime_reset(client: TestClient) -> None:
    external_id = f"wa-msg-{uuid4().hex}"
    payload = {
        "provider": "whatsapp",
        "external_id": external_id,
        "customer_name": "Mira Patel",
        "customer_email": f"mira-{uuid4().hex}@example.com",
        "subject": "WhatsApp complaint after callback",
        "body": "I need support to fix this payment issue before my promise time expires.",
        "handle": "+2348000000000",
    }
    first = client.post("/api/v1/connectors/inbound", json=payload)
    assert first.status_code == 201
    body = first.json()
    assert body["deduplicated"] is False
    ticket_id = body["ticket"]["id"]
    connector_event_id = body["connector_event"]["id"]

    store.seed()

    events = client.get("/api/v1/connectors/events")
    assert events.status_code == 200
    assert any(event["id"] == connector_event_id for event in events.json())

    context = client.get(f"/api/v1/tickets/{ticket_id}")
    assert context.status_code == 200
    assert context.json()["ticket"]["id"] == ticket_id
    assert any(event["type"] == "connector_receipt" for event in context.json()["timeline"])

    duplicate = client.post("/api/v1/connectors/inbound", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True
    assert duplicate.json()["ticket"]["id"] == ticket_id


def test_authenticated_connector_ingest_is_rate_limited(client: TestClient) -> None:
    original_attempts = settings.connector_inbound_rate_limit_attempts
    original_window = settings.connector_inbound_rate_limit_window_seconds
    settings.connector_inbound_rate_limit_attempts = 1
    settings.connector_inbound_rate_limit_window_seconds = 60
    try:
        first = client.post(
            "/api/v1/connectors/inbound",
            json={
                "provider": "whatsapp",
                "external_id": f"rate-auth-{uuid4().hex}",
                "customer_name": "Rate Limited Auth",
                "customer_email": f"rate-auth-{uuid4().hex}@example.com",
                "subject": "First authenticated connector event",
                "body": "This first event should pass.",
            },
        )
        assert first.status_code == 201
        limited = client.post(
            "/api/v1/connectors/inbound",
            json={
                "provider": "whatsapp",
                "external_id": f"rate-auth-{uuid4().hex}",
                "customer_name": "Rate Limited Auth",
                "customer_email": f"rate-auth-{uuid4().hex}@example.com",
                "subject": "Second authenticated connector event",
                "body": "This second event should be rate limited.",
            },
        )
        assert limited.status_code == 429
        assert limited.json()["detail"] == "Rate limit exceeded"
    finally:
        settings.connector_inbound_rate_limit_attempts = original_attempts
        settings.connector_inbound_rate_limit_window_seconds = original_window


def test_signed_webhook_ingests_without_agent_session(client: TestClient) -> None:
    account = _ready_connector_account(client)
    payload = {
        "external_id": f"wa-signed-{uuid4().hex}",
        "customer_name": "Signed Webhook Customer",
        "customer_email": f"signed-{uuid4().hex}@example.com",
        "subject": "Signed WhatsApp webhook payment complaint",
        "body": "Customer is angry about a duplicate payment from WhatsApp.",
        "handle": "+2348111111111",
    }
    body = _json_body(payload)
    response = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=body,
        headers=_signed_webhook_headers(account, body, "delivery-signed-1"),
    )
    assert response.status_code == 201
    result = response.json()
    assert result["deduplicated"] is False
    ticket = result["ticket"]
    assert ticket["channel"] == "whatsapp"
    assert ticket["team"] == "Billing Support"
    assert "connector-intake" in ticket["tags"]
    assert result["connector_event"]["payload"]["metadata"]["webhook_signature_verified"] is True
    assert result["connector_event"]["payload"]["metadata"]["webhook_delivery_id"] == "delivery-signed-1"

    context = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert context.status_code == 200
    assert any(
        event["type"] == "connector_receipt"
        and event["metadata"]["external_id"] == payload["external_id"]
        for event in context.json()["timeline"]
    )


def test_signed_webhook_rejects_invalid_signature_and_tracks_failure(client: TestClient) -> None:
    account = _ready_connector_account(client)
    payload = {
        "external_id": f"wa-invalid-{uuid4().hex}",
        "customer_name": "Invalid Signature",
        "customer_email": f"invalid-{uuid4().hex}@example.com",
        "subject": "Invalid signature should fail",
        "body": "This event should never become a ticket.",
    }
    body = _json_body(payload)
    response = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Omni-Timestamp": str(int(time.time())),
            "X-Omni-Signature": "sha256=bad",
            "X-Omni-Delivery": "delivery-invalid",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"

    updated_account = next(
        item
        for item in client.get("/api/v1/connectors/accounts").json()
        if item["id"] == account["id"]
    )
    assert updated_account["failure_count"] == 1
    assert updated_account["last_error"] == "Invalid webhook signature"
    assert not any(
        event["external_id"] == payload["external_id"]
        for event in client.get("/api/v1/connectors/events").json()
    )


def test_signed_webhook_is_rate_limited_before_ticket_creation(client: TestClient) -> None:
    account = _ready_connector_account(client)
    original_attempts = settings.webhook_rate_limit_attempts
    original_window = settings.webhook_rate_limit_window_seconds
    settings.webhook_rate_limit_attempts = 1
    settings.webhook_rate_limit_window_seconds = 60
    try:
        first_payload = {
            "external_id": f"wa-rate-{uuid4().hex}",
            "customer_name": "Webhook Rate One",
            "customer_email": f"webhook-rate-one-{uuid4().hex}@example.com",
            "subject": "First signed webhook",
            "body": "The first signed webhook should pass.",
        }
        first_body = _json_body(first_payload)
        first = TestClient(create_app()).post(
            "/api/v1/webhooks/whatsapp/ng",
            content=first_body,
            headers=_signed_webhook_headers(account, first_body, "delivery-rate-1"),
        )
        assert first.status_code == 201

        second_payload = {
            "external_id": f"wa-rate-{uuid4().hex}",
            "customer_name": "Webhook Rate Two",
            "customer_email": f"webhook-rate-two-{uuid4().hex}@example.com",
            "subject": "Second signed webhook",
            "body": "The second signed webhook should be limited.",
        }
        second_body = _json_body(second_payload)
        limited = TestClient(create_app()).post(
            "/api/v1/webhooks/whatsapp/ng",
            content=second_body,
            headers=_signed_webhook_headers(account, second_body, "delivery-rate-2"),
        )
        assert limited.status_code == 429
        assert limited.json()["detail"] == "Rate limit exceeded"
        assert not any(
            event["external_id"] == second_payload["external_id"]
            for event in client.get("/api/v1/connectors/events").json()
        )
    finally:
        settings.webhook_rate_limit_attempts = original_attempts
        settings.webhook_rate_limit_window_seconds = original_window


def test_signed_webhook_blocks_replayed_delivery_id_with_new_event(
    client: TestClient,
) -> None:
    account = _ready_connector_account(client)
    first_payload = {
        "external_id": f"wa-replay-{uuid4().hex}",
        "customer_name": "Replay Customer",
        "customer_email": f"replay-{uuid4().hex}@example.com",
        "subject": "Original signed delivery",
        "body": "Original delivery should create one ticket.",
    }
    first_body = _json_body(first_payload)
    delivery_id = "delivery-replay-1"
    first = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=first_body,
        headers=_signed_webhook_headers(account, first_body, delivery_id),
    )
    assert first.status_code == 201

    duplicate = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=first_body,
        headers=_signed_webhook_headers(account, first_body, delivery_id),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["deduplicated"] is True
    assert duplicate.json()["ticket"]["id"] == first.json()["ticket"]["id"]

    replay_payload = {**first_payload, "external_id": f"wa-replay-mutated-{uuid4().hex}"}
    replay_body = _json_body(replay_payload)
    replay = TestClient(create_app()).post(
        "/api/v1/webhooks/whatsapp/ng",
        content=replay_body,
        headers=_signed_webhook_headers(account, replay_body, delivery_id),
    )
    assert replay.status_code == 409
    assert replay.json()["detail"] == "Webhook delivery id was already processed"


def test_public_portal_answers_expose_only_customer_safe_knowledge() -> None:
    public_client = TestClient(create_app())

    response = public_client.get("/api/v1/portal/ng/answers?q=duplicate%20payment")

    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == "market-ng"
    assert body["market_code"] == "ng"
    assert body["suggestions"]
    assert any("payment" in suggestion["title"].lower() for suggestion in body["suggestions"])
    assert {"article_id", "title", "body", "score", "reasons", "matched_terms", "updated_at"} <= set(
        body["suggestions"][0]
    )
    assert "status" not in body["suggestions"][0]
    assert any(field["key"] == "booking_reference" for field in body["ticket_fields"])


def test_public_portal_ticket_submission_creates_normal_ticket(client: TestClient) -> None:
    public_client = TestClient(create_app())
    email = f"portal-{uuid4().hex}@example.com"

    response = public_client.post(
        "/api/v1/portal/ng/tickets",
        json={
            "name": "Portal Customer",
            "email": email,
            "phone": "+2348000000000",
            "subject": "Duplicate payment after booking",
            "description": "I paid twice for the same booking and need help reversing one charge.",
            "custom_fields": {
                "booking_reference": "WAK-PORTAL-100",
                "issue_category": "Payment",
                "trip_stage": "Pre-trip",
            },
            "search_query": "duplicate payment reversal",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["public_id"].startswith("OMNI-")
    assert body["status"] == "open"
    assert body["article_suggestions"]

    ticket_context = client.get(f"/api/v1/tickets/{body['ticket_id']}")
    assert ticket_context.status_code == 200
    ticket = ticket_context.json()["ticket"]
    assert ticket["channel"] == "portal"
    assert ticket["customer_id"]
    assert ticket["custom_fields"]["booking_reference"] == "WAK-PORTAL-100"
    assert "portal" in ticket["tags"]
    assert any(event["actor"] == "Portal Customer" for event in ticket_context.json()["timeline"])

    with Session(get_engine()) as db:
        customer = db.scalar(
            select(CustomerRecord).where(
                CustomerRecord.market_id == "market-ng",
                CustomerRecord.email == email,
            )
        )
        assert customer is not None
        assert "portal" in customer.preferred_channels
        assert any(point["channel"] == "portal" for point in customer.contact_points)
        audit = db.scalar(
            select(AuditEventRecord).where(
                AuditEventRecord.entity_id == body["ticket_id"],
                AuditEventRecord.action == "ticket.create",
            )
        )
        assert audit is not None
        assert audit.actor == "customer-portal"
        assert audit.details["source"] == "portal"


def test_public_portal_ticket_attachment_upload_is_customer_safe(client: TestClient) -> None:
    public_client = TestClient(create_app())
    email = f"portal-attachment-{uuid4().hex}@example.com"
    created = public_client.post(
        "/api/v1/portal/ng/tickets",
        json={
            "name": "Portal Attachment Customer",
            "email": email,
            "subject": "Refund proof upload",
            "description": "I need to upload proof of the duplicate payment.",
            "custom_fields": {"issue_category": "Payment"},
        },
    )
    assert created.status_code == 201
    ticket = created.json()

    clean = public_client.post(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}/attachments?email={email}&filename=payment-proof.txt",
        content=b"portal payment proof",
        headers={"content-type": "text/plain"},
    )
    assert clean.status_code == 201
    clean_body = clean.json()
    assert clean_body["filename"] == "payment-proof.txt"
    assert clean_body["scan_status"] == "clean"
    assert "storage_key" not in clean_body

    blocked = public_client.post(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}/attachments?email={email}&filename=unsafe-portal.exe",
        content=b"unsafe bytes",
        headers={"content-type": "application/x-msdownload"},
    )
    assert blocked.status_code == 201
    blocked_body = blocked.json()
    assert blocked_body["filename"] == "unsafe-portal.exe"
    assert blocked_body["scan_status"] == "blocked"
    assert "storage_key" not in blocked_body

    wrong_email = public_client.post(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}/attachments?email=someone-else@example.com&filename=wrong.txt",
        content=b"wrong customer",
        headers={"content-type": "text/plain"},
    )
    assert wrong_email.status_code == 404

    detail = public_client.get(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}?email={email}"
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert [item["filename"] for item in detail_body["attachments"]] == [
        "payment-proof.txt",
        "unsafe-portal.exe",
    ]
    assert any("Attachment received: payment-proof.txt." in event["body"] for event in detail_body["timeline"])

    attachments = client.get(f"/api/v1/tickets/{ticket['ticket_id']}/attachments").json()
    clean_attachment = next(item for item in attachments if item["id"] == clean_body["id"])
    blocked_attachment = next(item for item in attachments if item["id"] == blocked_body["id"])
    assert clean_attachment["uploaded_by"] == f"customer-portal:{email}"
    assert clean_attachment["storage_key"].startswith("local:")
    assert blocked_attachment["storage_key"].startswith("blocked:")

    clean_download = client.get(
        f"/api/v1/tickets/{ticket['ticket_id']}/attachments/{clean_body['id']}/download"
    )
    assert clean_download.status_code == 200
    assert clean_download.content == b"portal payment proof"
    blocked_download = client.get(
        f"/api/v1/tickets/{ticket['ticket_id']}/attachments/{blocked_body['id']}/download"
    )
    assert blocked_download.status_code == 403

    audit = client.get("/api/v1/audit").json()
    assert any(
        event["action"] == "attachment.create"
        and event["entity_id"] == clean_body["id"]
        and event["actor"] == f"customer-portal:{email}"
        for event in audit
    )


def test_public_portal_ticket_status_lookup_is_customer_safe(client: TestClient) -> None:
    public_client = TestClient(create_app())
    email = f"portal-status-{uuid4().hex}@example.com"
    created = public_client.post(
        "/api/v1/portal/ng/tickets",
        json={
            "name": "Portal Status Customer",
            "email": email,
            "subject": "Need booking status",
            "description": "I need to know whether my booking confirmation has been issued.",
            "custom_fields": {"booking_reference": "WAK-STATUS-100"},
        },
    )
    assert created.status_code == 201
    ticket = created.json()

    status_response = public_client.get(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}?email={email}"
    )

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["ticket_id"] == ticket["ticket_id"]
    assert body["public_id"] == ticket["public_id"]
    assert body["customer_status"] == "Support is reviewing your request"
    assert body["reply_allowed"] is True
    assert body["timeline"]
    assert all(event["body"] for event in body["timeline"])
    assert "assignee" not in body
    assert "customer" not in body

    wrong_email = public_client.get(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}?email=someone-else@example.com"
    )
    assert wrong_email.status_code == 404


def test_public_portal_customer_reply_reopens_ticket(client: TestClient) -> None:
    public_client = TestClient(create_app())
    email = f"portal-reply-{uuid4().hex}@example.com"
    created = public_client.post(
        "/api/v1/portal/ng/tickets",
        json={
            "name": "Portal Reply Customer",
            "email": email,
            "subject": "Refund follow-up",
            "description": "I need help checking a refund that is still pending.",
            "custom_fields": {"issue_category": "Refund"},
        },
    )
    assert created.status_code == 201
    ticket = created.json()
    solved = client.patch(f"/api/v1/tickets/{ticket['ticket_id']}", json={"status": "solved"})
    assert solved.status_code == 200
    assert solved.json()["status"] == "solved"

    reply = public_client.post(
        f"/api/v1/portal/ng/tickets/{ticket['public_id']}/reply",
        json={
            "email": email,
            "body": "This is still unresolved. Please reopen and check the refund reference.",
        },
    )

    assert reply.status_code == 201
    body = reply.json()
    assert body["status"] == "open"
    assert body["customer_status"] == "Support is reviewing your request"
    assert any("Please reopen" in event["body"] for event in body["timeline"])
    assert all(event["type"] != "status_change" for event in body["timeline"])

    ticket_context = client.get(f"/api/v1/tickets/{ticket['ticket_id']}")
    assert ticket_context.status_code == 200
    assert ticket_context.json()["ticket"]["status"] == "open"
    assert "customer-replied" in ticket_context.json()["ticket"]["tags"]

    with Session(get_engine()) as db:
        audit = db.scalar(
            select(AuditEventRecord).where(
                AuditEventRecord.entity_id == ticket["ticket_id"],
                AuditEventRecord.action == "ticket.portal_reply",
            )
        )
        assert audit is not None
        assert audit.actor == "customer-portal"
        assert audit.details["previous_status"] == "solved"
        assert audit.details["new_status"] == "open"


def test_public_portal_answers_are_rate_limited() -> None:
    original_attempts = settings.portal_rate_limit_attempts
    original_window = settings.portal_rate_limit_window_seconds
    settings.portal_rate_limit_attempts = 1
    settings.portal_rate_limit_window_seconds = 60
    public_client = TestClient(create_app())
    try:
        first = public_client.get("/api/v1/portal/ng/answers?q=payment")
        assert first.status_code == 200
        limited = public_client.get("/api/v1/portal/ng/answers?q=refund")
        assert limited.status_code == 429
        assert limited.json()["detail"] == "Rate limit exceeded"
    finally:
        settings.portal_rate_limit_attempts = original_attempts
        settings.portal_rate_limit_window_seconds = original_window


def test_management_surfaces_are_available(client: TestClient) -> None:
    assert client.get("/api/v1/channels").status_code == 200
    assert client.get("/api/v1/agents").status_code == 200
    assert client.get("/api/v1/customers").status_code == 200
    assert client.get("/api/v1/companies").status_code == 200
    assert client.get("/api/v1/knowledge").status_code == 200
    assert client.get("/api/v1/automation-rules").status_code == 200
    assert client.get("/api/v1/analytics/summary").status_code == 200
    assert client.get("/api/v1/analytics/overview").status_code == 200
    assert client.get("/api/v1/analytics/rollups").status_code == 200
    assert client.get("/api/v1/csat/feedback").status_code == 200
    assert client.get("/api/v1/inbound/provider-config").status_code == 200
    assert client.get("/api/v1/production/account-requests").status_code == 200
    assert client.get("/api/v1/production/readiness-checklist").status_code == 200
    assert client.get("/api/v1/production/account-references").status_code == 200
    assert client.get("/api/v1/production/account-references/docs").status_code == 200
    assert client.get("/api/v1/connectors/providers").status_code == 200
    assert client.get("/api/v1/connectors/accounts").status_code == 200
    assert client.get("/api/v1/connector-accounts").status_code == 200
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/api/v1/tracker").status_code == 200
    assert client.get("/api/v1/frontend/snapshot").status_code == 200
    readiness = client.get("/api/v1/platform/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["required_tables_present"] is True


def test_production_account_request_pack_is_sanitized_and_actionable(client: TestClient) -> None:
    response = client.get(
        "/api/v1/production/account-requests",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omni.wakanow.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recipient_email"] == "gbolahans@wakanow.com"
    assert body["market_id"] == "market-ng"
    assert body["total_items"] >= 10
    assert body["missing_items"] >= 1
    assert "Omni Ticket production account requests - NG" == body["subject"]
    assert body["mailto_url"].startswith("mailto:gbolahans%40wakanow.com")
    assert "Do not email raw passwords" in body["body"]
    assert "https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng" in body["body"]
    assert "https://omni.wakanow.com/api/v1/auth/oidc/callback" in body["body"]
    assert "omni-demo" not in body["body"]

    items = {item["id"]: item for item in body["items"]}
    assert items["email"]["setup_location"] == "Setup -> Connectors -> Email setup"
    assert "IMAP host" in items["email"]["missing_settings"]
    assert "SMTP host" in items["email"]["missing_settings"]
    assert items["whatsapp"]["callback_urls"] == [
        "https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng"
    ]
    assert items["identity-oidc"]["callback_urls"] == [
        "https://omni.wakanow.com/api/v1/auth/oidc/callback"
    ]
    assert items["attachment-storage"]["status"] == "missing"
    assert items["observability"]["status"] == "missing"


def test_production_account_request_email_is_queued_idempotently(client: TestClient) -> None:
    response = client.post(
        "/api/v1/production/account-requests/email",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omni.wakanow.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["already_queued"] is False
    assert body["ticket_id"]
    assert body["ticket_public_id"].startswith("OMNI-")
    assert body["pack"]["recipient_email"] == "gbolahans@wakanow.com"
    assert "Do not email raw passwords" in body["pack"]["body"]
    assert "omni-demo" not in body["pack"]["body"]

    outbound = body["outbound_message"]
    assert outbound["provider"] == "email"
    assert outbound["status"] == "queued"
    assert outbound["ticket_id"] == body["ticket_id"]
    assert outbound["payload"]["source"] == "production_account_request"
    assert outbound["payload"]["to_email"] == "gbolahans@wakanow.com"
    assert outbound["payload"]["subject"] == body["pack"]["subject"]
    assert outbound["payload"]["missing_items"] == body["pack"]["missing_items"]
    assert "pack_signature" in outbound["payload"]

    ticket_context = client.get(f"/api/v1/tickets/{body['ticket_id']}")
    assert ticket_context.status_code == 200
    ticket = ticket_context.json()["ticket"]
    assert ticket["team"] == "Setup"
    assert ticket["channel"] == "internal"
    assert ticket["custom_fields"]["recipient_email"] == "gbolahans@wakanow.com"

    duplicate = client.post(
        "/api/v1/production/account-requests/email",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omni.wakanow.com"},
    )
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert duplicate_body["already_queued"] is True
    assert duplicate_body["outbound_message"]["id"] == outbound["id"]
    assert duplicate_body["ticket_id"] == body["ticket_id"]

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "production.account_request.ticket.create" for event in audit)
    assert any(event["action"] == "production.account_request.email.queue" for event in audit)


def test_production_account_references_track_non_secret_provider_details(client: TestClient) -> None:
    created = client.post(
        "/api/v1/production/account-references",
        json={
            "provider": "WhatsApp",
            "area": "WhatsApp Business channel",
            "account_name": "Wakanow NG WhatsApp Business",
            "account_identifier": "phone-number-id-12345",
            "status": "provisioned",
            "owner_email": "owner@wakanow.com",
            "credential_reference": "vault://omni/ng/whatsapp/access-token",
            "docs_reference": "API_DOCS.md#external-accounts-needed",
            "callback_urls": [
                "https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng",
                "https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng",
            ],
            "notes": "Non-secret account metadata only.",
        },
    )
    assert created.status_code == 201
    reference = created.json()
    assert reference["provider"] == "whatsapp"
    assert reference["status"] == "provisioned"
    assert reference["owner_email"] == "owner@wakanow.com"
    assert reference["credential_reference"] == "vault://omni/ng/whatsapp/access-token"
    assert reference["callback_urls"] == ["https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng"]
    assert "access-token-secret" not in json.dumps(reference)

    duplicate = client.post(
        "/api/v1/production/account-references",
        json={
            "provider": "whatsapp",
            "area": "WhatsApp Business channel",
            "account_name": "Wakanow NG WhatsApp Business",
        },
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/production/account-references/{reference['id']}",
        json={
            "status": "connected",
            "docs_reference": "API_DOCS.md#whatsapp-business",
            "notes": "Connected in provider dashboard; secret remains in vault.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "connected"
    assert updated.json()["docs_reference"] == "API_DOCS.md#whatsapp-business"

    listed = client.get("/api/v1/production/account-references?provider=whatsapp")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [reference["id"]]

    docs = client.get("/api/v1/production/account-references/docs")
    assert docs.status_code == 200
    markdown = docs.json()["markdown"]
    assert "Wakanow NG WhatsApp Business" in markdown
    assert "vault://omni/ng/whatsapp/access-token" in markdown
    assert "API_DOCS.md#whatsapp-business" in markdown
    assert "access-token-secret" not in markdown

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "production_account_reference.create" for event in audit)
    assert any(event["action"] == "production_account_reference.update" for event in audit)


def test_production_readiness_checklist_uses_live_evidence(client: TestClient) -> None:
    queued = client.post(
        "/api/v1/production/account-requests/email",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omni.wakanow.com"},
    )
    assert queued.status_code == 200

    reference = client.post(
        "/api/v1/production/account-references",
        json={
            "provider": "whatsapp",
            "area": "WhatsApp Business channel",
            "account_name": "Wakanow NG WhatsApp Business",
            "account_identifier": "phone-number-id-12345",
            "status": "provisioned",
            "owner_email": "owner@wakanow.com",
            "credential_reference": "vault://omni/ng/whatsapp/access-token",
            "docs_reference": "API_DOCS.md#external-accounts-needed",
            "callback_urls": ["https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng"],
            "notes": "Non-secret account metadata only.",
        },
    )
    assert reference.status_code == 201

    response = client.get(
        "/api/v1/production/readiness-checklist",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omni.wakanow.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == "market-ng"
    assert body["total_items"] >= 10
    assert body["blocked_items"] >= 1
    assert body["overall_status"] in {"blocked", "action_required"}

    items = {item["id"]: item for item in body["items"]}
    assert items["account-request-email"]["status"] == "ready"
    assert queued.json()["outbound_message"]["id"] in " ".join(items["account-request-email"]["evidence"])
    assert items["account-reference-tracking"]["status"] == "ready"
    assert "Provisioned or connected: 1" in items["account-reference-tracking"]["evidence"]
    assert items["account-reference-secret-hygiene"]["status"] == "ready"
    assert items["provider-whatsapp"]["status"] == "blocked"
    assert "https://omni.wakanow.com/api/v1/webhooks/whatsapp/ng" in queued.json()["pack"]["body"]
    assert "omni-demo" not in json.dumps(body)


def test_customer_company_knowledge_and_rule_management(client: TestClient) -> None:
    company = client.post(
        "/api/v1/companies",
        json={"name": "Northstar Ops", "tier": "enterprise", "account_value": 2500},
    )
    assert company.status_code == 201
    company_id = company.json()["id"]

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": "Ada James",
            "email": "ada@example.com",
            "company_id": company_id,
            "preferred_channels": ["whatsapp", "email"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    updated_customer = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"sentiment": "frustrated", "tags": ["vip", "renewal"]},
    )
    assert updated_customer.status_code == 200
    assert updated_customer.json()["sentiment"] == "frustrated"

    article = client.post(
        "/api/v1/knowledge",
        json={
            "title": "WhatsApp escalation reply",
            "status": "draft",
            "channels": ["whatsapp"],
            "tags": ["escalation"],
            "body": "Acknowledge, confirm owner, and set a promise time.",
        },
    )
    assert article.status_code == 201
    assert article.json()["submitted_for_review_at"] is None
    assert article.json()["approved_at"] is None

    review_article = client.patch(
        f"/api/v1/knowledge/{article.json()['id']}",
        json={"status": "in_review"},
    )
    assert review_article.status_code == 200
    assert review_article.json()["status"] == "in_review"
    assert review_article.json()["submitted_for_review_at"] is not None
    assert review_article.json()["approved_at"] is None

    approved_article = client.patch(
        f"/api/v1/knowledge/{article.json()['id']}",
        json={"status": "approved"},
    )
    assert approved_article.status_code == 200
    assert approved_article.json()["status"] == "approved"
    assert approved_article.json()["approved_at"] is not None
    assert approved_article.json()["approved_by"] == "user-gbolahan"

    reset_article = client.patch(
        f"/api/v1/knowledge/{article.json()['id']}",
        json={"status": "draft"},
    )
    assert reset_article.status_code == 200
    assert reset_article.json()["status"] == "draft"
    assert reset_article.json()["submitted_for_review_at"] is None
    assert reset_article.json()["approved_at"] is None
    assert reset_article.json()["approved_by"] is None

    rule = client.post(
        "/api/v1/automation-rules",
        json={
            "name": "VIP WhatsApp escalation",
            "enabled": True,
            "trigger": "customer tags contains vip and channel is whatsapp",
            "action": "assign escalations and raise priority",
        },
    )
    assert rule.status_code == 201
    updated_rule = client.patch(
        f"/api/v1/automation-rules/{rule.json()['id']}",
        json={"enabled": False},
    )
    assert updated_rule.status_code == 200
    assert updated_rule.json()["enabled"] is False


def test_customer_company_records_survive_store_reset_and_can_open_ticket(
    client: TestClient,
) -> None:
    suffix = uuid4().hex
    company = client.post(
        "/api/v1/companies",
        json={"name": f"Durable Company {suffix}", "tier": "enterprise"},
    )
    assert company.status_code == 201
    company_id = company.json()["id"]

    customer = client.post(
        "/api/v1/customers",
        json={
            "name": "Durable Customer",
            "email": f"durable-{suffix}@example.com",
            "company_id": company_id,
            "preferred_channels": ["whatsapp"],
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    store.seed()

    customers = client.get("/api/v1/customers")
    assert customers.status_code == 200
    assert any(item["id"] == customer_id for item in customers.json())

    companies = client.get("/api/v1/companies")
    assert companies.status_code == 200
    assert any(item["id"] == company_id for item in companies.json())

    ticket = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp customer needs persistent account help",
            "description": "Ticket should be created after customer data is rehydrated from DB.",
            "customer_id": customer_id,
            "channel": "whatsapp",
        },
    )
    assert ticket.status_code == 201
    assert ticket.json()["customer_id"] == customer_id


def test_management_records_are_database_first_after_runtime_reset(client: TestClient) -> None:
    channel = client.get("/api/v1/channels").json()[0]
    channel_update = client.patch(
        f"/api/v1/channels/{channel['id']}",
        json={"health": "paused", "queued": 44},
    )
    assert channel_update.status_code == 200

    agent = client.get("/api/v1/agents").json()[0]
    agent_update = client.patch(
        f"/api/v1/agents/{agent['id']}/status",
        json={"status": "away"},
    )
    assert agent_update.status_code == 200

    article = client.post(
        "/api/v1/knowledge",
        json={
            "title": "Runtime reset article",
            "status": "draft",
            "channels": ["whatsapp"],
            "tags": ["reset-proof"],
            "body": "This article should survive runtime reset.",
        },
    )
    assert article.status_code == 201
    article_id = article.json()["id"]

    rule = client.post(
        "/api/v1/automation-rules",
        json={
            "name": "Runtime reset rule",
            "enabled": True,
            "trigger": "channel is whatsapp",
            "action": "raise priority",
        },
    )
    assert rule.status_code == 201
    rule_id = rule.json()["id"]

    store.seed()

    channels = client.get("/api/v1/channels").json()
    assert any(item["id"] == channel["id"] and item["health"] == "paused" for item in channels)
    agents = client.get("/api/v1/agents").json()
    assert any(item["id"] == agent["id"] and item["status"] == "away" for item in agents)
    articles = client.get("/api/v1/knowledge").json()
    assert any(item["id"] == article_id for item in articles)
    rules = client.get("/api/v1/automation-rules").json()
    assert any(item["id"] == rule_id for item in rules)


def test_analytics_and_work_queue_are_database_first_after_runtime_reset(
    client: TestClient,
) -> None:
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "WhatsApp urgent operations queue check",
            "description": "Customer is angry about a public payment issue and needs escalation.",
            "customer_id": "cust-leo",
            "channel": "whatsapp",
        },
    )
    assert ticket_response.status_code == 201
    ticket_id = ticket_response.json()["id"]

    store.seed()

    queue = client.get("/api/v1/work-queue")
    assert queue.status_code == 200
    assert any(item["ticket"]["id"] == ticket_id for item in queue.json())

    analytics = client.get("/api/v1/analytics/summary")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["open_tickets"] >= 1
    assert body["channel_volume"]["whatsapp"] >= 1


def test_csat_feedback_persists_and_feeds_analytics(
    client: TestClient,
) -> None:
    ticket = client.get("/api/v1/tickets").json()[0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/csat",
        json={
            "rating": 5,
            "comment": "The support owner solved this quickly.",
            "source": "customer_survey",
            "submitted_by": "customer@example.com",
        },
    )
    assert response.status_code == 200
    feedback = response.json()
    assert feedback["ticket_id"] == ticket["id"]
    assert feedback["rating"] == 5
    assert feedback["comment"] == "The support owner solved this quickly."

    context = client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert any(item["id"] == feedback["id"] for item in context["csat_feedback"])
    assert any(
        event["metadata"].get("csat_feedback_id") == feedback["id"]
        for event in context["timeline"]
    )

    feedback_list = client.get("/api/v1/csat/feedback").json()
    assert any(item["id"] == feedback["id"] for item in feedback_list)

    analytics = client.get("/api/v1/analytics/summary").json()
    assert analytics["avg_csat"] == 5

    with Session(get_engine()) as session:
        analytics_job = worker_service.rollup_analytics(session, store, "market-ng")
    assert analytics_job.details["avg_csat"] == 5

    rollups = client.get("/api/v1/analytics/rollups").json()
    assert any(item["avg_csat"] == 5 for item in rollups)

    update = client.post(
        f"/api/v1/tickets/{ticket['id']}/csat",
        json={
            "rating": 3,
            "comment": "The final update was slower than expected.",
            "source": "agent_recorded",
        },
    )
    assert update.status_code == 200
    assert update.json()["id"] == feedback["id"]
    assert update.json()["rating"] == 3
    assert len(client.get(f"/api/v1/csat/feedback?ticket_id={ticket['id']}").json()) == 1
    assert client.get("/api/v1/analytics/summary").json()["avg_csat"] == 3

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "csat.create" for event in audit)
    assert any(event["action"] == "csat.update" for event in audit)


def test_connector_accounts_are_market_scoped_and_database_backed(
    client: TestClient,
    login_as: Callable[[str, str], dict[str, str]],
) -> None:
    accounts = client.get("/api/v1/connectors/accounts")
    assert accounts.status_code == 200
    body = accounts.json()
    assert {account["provider"] for account in body} >= {
        "email",
        "whatsapp",
        "facebook",
        "instagram",
        "sms",
        "voice",
        "portal",
        "api",
    }
    assert all(account["market_id"] == "market-ng" for account in body)

    portal = next(account for account in body if account["provider"] == "portal")
    api_account = next(account for account in body if account["provider"] == "api")
    assert portal["account_identifier"] == "NG customer portal pending"
    assert portal["outbound_enabled"] is True
    assert api_account["account_identifier"] == "NG partner API pending"
    assert api_account["outbound_enabled"] is True

    whatsapp = next(account for account in body if account["provider"] == "whatsapp")
    update = client.patch(
        f"/api/v1/connectors/accounts/{whatsapp['id']}",
        json={
            "status": "connected",
            "webhook_verified": True,
            "secret_configured": True,
            "credential_ref": "vault://omni/ng/whatsapp",
            "outbound_enabled": True,
        },
    )
    assert update.status_code == 200
    assert update.json()["status"] == "connected"
    assert update.json()["credential_ref"] == "vault://omni/ng/whatsapp"

    store.seed()

    persisted = client.get("/api/v1/connectors/accounts").json()
    assert any(
        account["id"] == whatsapp["id"]
        and account["status"] == "connected"
        and account["webhook_verified"] is True
        for account in persisted
    )

    gh_headers = login_as("kofi.gh@omniticket.example.com", "market-gh")
    gh_accounts = client.get("/api/v1/connectors/accounts", headers=gh_headers)
    assert gh_accounts.status_code == 200
    assert gh_accounts.json()
    assert all(account["market_id"] == "market-gh" for account in gh_accounts.json())
    assert not any(account["id"] == whatsapp["id"] for account in gh_accounts.json())


def test_admin_can_create_and_manage_market_users(client: TestClient) -> None:
    create = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Ops Reviewer",
            "email": "ops.reviewer@example.com",
            "temporary_password": "Reviewer-temp-2026",
            "role": "agent",
            "market_ids": ["market-ng", "market-gh"],
            "default_market_id": "market-ng",
        },
    )
    assert create.status_code == 201
    user = create.json()
    assert user["email"] == "ops.reviewer@example.com"
    assert user["role"] == "agent"
    assert user["market_ids"] == ["market-ng", "market-gh"]
    assert user["password_reset_required"] is True

    update = client.patch(
        f"/api/v1/auth/users/{user['id']}",
        json={"role": "supervisor", "active": False, "default_market_id": "market-gh"},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["role"] == "supervisor"
    assert updated["active"] is False
    assert updated["default_market_id"] == "market-gh"

    users = client.get("/api/v1/auth/users")
    assert users.status_code == 200
    assert any(item["id"] == user["id"] for item in users.json())

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == user["id"] for item in snapshot.json()["users"])


def test_frontend_compatibility_endpoints_update_state(client: TestClient) -> None:
    channel = client.get("/api/v1/channels").json()[0]
    channel_update = client.patch(
        f"/api/v1/channels/{channel['id']}",
        json={"health": "paused", "queued": 41},
    )
    assert channel_update.status_code == 200
    assert channel_update.json()["health"] == "paused"
    assert channel_update.json()["queued"] == 41

    agent = client.get("/api/v1/agents").json()[0]
    agent_update = client.patch(
        f"/api/v1/agents/{agent['id']}/status",
        json={"status": "away"},
    )
    assert agent_update.status_code == 200
    assert agent_update.json()["status"] == "away"

    settings_update = client.patch(
        "/api/v1/settings/ai-work-queue-automation",
        json={"enabled": False},
    )
    assert settings_update.status_code == 200
    assert settings_update.json()["ai_work_queue_automation_enabled"] is False

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["settings"]["ai_work_queue_automation_enabled"] is False
    assert body["channels"]
    assert body["tickets"]
    assert body["analytics"]["open_tickets"] >= 1
