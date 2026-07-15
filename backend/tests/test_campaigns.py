from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.integration_credentials import integration_credential_settings_repository
from app.db.models import (
    CampaignDeliveryRecord,
    CampaignRecord,
    ConnectorAccountRecord,
    CustomerRecord,
    TicketRecord,
)
from app.db.session import get_engine
from app.models.domain import ChannelType
from app.services.campaign_delivery import (
    CampaignDeliveryTransport,
    CampaignSendRequest,
    CampaignSendResult,
)
from app.services.campaigns import campaign_service


def _campaign_payload(name: str = "Lagos travel update") -> dict:
    return {
        "name": name,
        "channel": "whatsapp",
        "message_body": "Your booking support team is available if your itinerary changed.",
        "audience": {"include_all": True, "tags_any": []},
    }


class RecordingCampaignTransport(CampaignDeliveryTransport):
    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.requests: list[CampaignSendRequest] = []

    def send(self, request, credentials):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if not self.succeed:
            return CampaignSendResult(
                succeeded=False,
                adapter="test-campaign",
                error="Provider timeout",
            )
        return CampaignSendResult(
            succeeded=True,
            adapter="test-campaign",
            external_id=f"provider-{request.delivery_id}",
            payload={"accepted": True},
        )


def _configure_sms_campaign_delivery() -> str:
    with Session(get_engine()) as db:
        account = db.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == "market-ng",
                ConnectorAccountRecord.provider == "sms",
            )
        )
        assert account is not None
        account.status = "connected"
        account.outbound_enabled = True
        account.secret_configured = True
        credentials = integration_credential_settings_repository.get_or_create(
            db,
            market_id="market-ng",
        )
        credentials.sms_http_endpoint = "https://sms.example.test/messages"
        credentials.sms_http_auth_token = "test-token"
        credentials.sms_http_from = "WAKANOW"
        customer = db.scalar(
            select(CustomerRecord)
            .where(CustomerRecord.market_id == "market-ng")
            .order_by(CustomerRecord.id.asc())
        )
        assert customer is not None
        customer.contact_points = [
            *(customer.contact_points or []),
            {"channel": "sms", "value": "+234 800 000 0100", "verified": True},
        ]
        db.commit()
        return customer.id


def test_campaign_draft_lifecycle_is_market_scoped_and_audited(client: TestClient) -> None:
    created = client.post("/api/v1/campaigns", json=_campaign_payload())
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["market_id"] == "market-ng"
    assert campaign["status"] == "draft"
    assert isinstance(campaign["estimated_recipients"], int)
    assert campaign["provider"]["channel"] == "whatsapp"
    assert isinstance(campaign["provider"]["configured"], bool)

    listed = client.get("/api/v1/campaigns")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [campaign["id"]]

    paused = client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={"status": "paused"},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"

    resumed = client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={"status": "draft"},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "draft"

    duplicate = client.post("/api/v1/campaigns", json=_campaign_payload())
    assert duplicate.status_code == 409

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200, audit.text
    actions = [event["action"] for event in audit.json() if event["entity_id"] == campaign["id"]]
    assert "campaign.create" in actions
    assert "campaign.update" in actions


def test_campaign_requires_an_explicit_audience(client: TestClient) -> None:
    payload = _campaign_payload("No audience")
    payload["audience"] = {"include_all": False, "tags_any": []}

    response = client.post("/api/v1/campaigns", json=payload)

    assert response.status_code == 422
    assert "audience" in response.text.lower()


def test_campaign_rbac_and_market_isolation(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    created = client.post("/api/v1/campaigns", json=_campaign_payload("Nigeria only"))
    assert created.status_code == 201, created.text

    gh_headers = login_as("kofi.gh@omniticket.example.com", market_id="market-gh")
    gh_list = client.get("/api/v1/campaigns", headers=gh_headers)
    assert gh_list.status_code == 200, gh_list.text
    assert gh_list.json() == []

    forbidden = client.post(
        "/api/v1/campaigns",
        headers=gh_headers,
        json=_campaign_payload("Agent cannot create"),
    )
    assert forbidden.status_code == 403


def test_campaign_readiness_is_factual_for_every_supported_channel(client: TestClient) -> None:
    response = client.get("/api/v1/campaigns/readiness")

    assert response.status_code == 200, response.text
    readiness = response.json()
    assert {item["channel"] for item in readiness} == {
        "whatsapp",
        "sms",
        "facebook",
        "instagram",
    }
    assert all(item["detail"] for item in readiness)


def test_campaign_launch_dispatch_and_receipt_are_durable_without_tickets(
    client: TestClient,
) -> None:
    customer_id = _configure_sms_campaign_delivery()
    consent = client.put(
        "/api/v1/campaigns/consents",
        json={
            "customer_id": customer_id,
            "channel": "sms",
            "status": "opted_in",
            "source": "booking checkout",
            "evidence": "Customer selected SMS travel updates.",
        },
    )
    assert consent.status_code == 200, consent.text
    with Session(get_engine()) as db:
        tickets_before = db.scalar(select(func.count(TicketRecord.id)))

    payload = _campaign_payload("Consent-backed SMS update")
    payload["channel"] = "sms"
    created = client.post("/api/v1/campaigns", json=payload)
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    launched = client.post(f"/api/v1/campaigns/{campaign_id}/launch")
    assert launched.status_code == 200, launched.text
    body = launched.json()
    assert body["created_deliveries"] == 1
    assert body["campaign"]["status"] == "running"
    assert body["campaign"]["consented_recipients"] == 1
    assert body["campaign"]["delivery_summary"]["queued"] == 1

    relaunched = client.post(f"/api/v1/campaigns/{campaign_id}/launch")
    assert relaunched.status_code == 200, relaunched.text
    assert relaunched.json()["created_deliveries"] == 0
    assert relaunched.json()["existing_deliveries"] == 1

    deliveries = client.get(f"/api/v1/campaigns/{campaign_id}/deliveries")
    assert deliveries.status_code == 200, deliveries.text
    delivery = deliveries.json()[0]
    assert delivery["status"] == "queued"
    assert delivery["recipient"].startswith("+234")
    assert " " not in delivery["recipient"]

    transport = RecordingCampaignTransport()
    with Session(get_engine()) as db:
        result = campaign_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test-worker",
            transport=transport,
        )
        assert result.sent_ids == [delivery["id"]]
        assert len(transport.requests) == 1
        campaign = db.get(CampaignRecord, campaign_id)
        assert campaign is not None
        assert campaign.status == "completed"
        tickets_after = db.scalar(select(func.count(TicketRecord.id)))
        assert tickets_after == tickets_before
        receipt = campaign_service.record_delivery_receipt(
            db,
            market_id="market-ng",
            provider=ChannelType.sms,
            status_label="delivered",
            provider_message_id=f"provider-{delivery['id']}",
            campaign_delivery_id=None,
            idempotency_key=None,
            delivery_id="sms-receipt-100",
            raw_payload={"status": "delivered"},
        )
        assert receipt is not None
        assert receipt.status == "delivered"
        db.commit()

    audit = client.get("/api/v1/audit").json()
    delivery_actions = [
        event["action"] for event in audit if event["entity_id"] == delivery["id"]
    ]
    assert "campaign.delivery.sent" in delivery_actions
    assert "campaign.delivery.receipt" in delivery_actions


def test_campaign_delivery_is_suppressed_when_consent_is_withdrawn(client: TestClient) -> None:
    customer_id = _configure_sms_campaign_delivery()
    opt_in = {
        "customer_id": customer_id,
        "channel": "sms",
        "status": "opted_in",
        "source": "profile preferences",
        "evidence": "SMS enabled",
    }
    assert client.put("/api/v1/campaigns/consents", json=opt_in).status_code == 200
    payload = _campaign_payload("Consent withdrawal")
    payload["channel"] = "sms"
    campaign = client.post("/api/v1/campaigns", json=payload).json()
    launched = client.post(f"/api/v1/campaigns/{campaign['id']}/launch")
    assert launched.status_code == 200, launched.text
    opt_out = {**opt_in, "status": "opted_out", "evidence": "STOP received"}
    assert client.put("/api/v1/campaigns/consents", json=opt_out).status_code == 200

    transport = RecordingCampaignTransport()
    with Session(get_engine()) as db:
        result = campaign_service.dispatch_due(
            db,
            market_id="market-ng",
            actor="test-worker",
            transport=transport,
        )
        assert len(result.suppressed_ids) == 1
        assert transport.requests == []
        delivery = db.get(CampaignDeliveryRecord, result.suppressed_ids[0])
        assert delivery is not None
        assert delivery.status == "suppressed"
        assert "withdrawn" in (delivery.last_error or "").lower()


def test_campaign_launch_requires_explicit_consent(client: TestClient) -> None:
    _configure_sms_campaign_delivery()
    payload = _campaign_payload("No inferred consent")
    payload["channel"] = "sms"
    campaign = client.post("/api/v1/campaigns", json=payload).json()

    launched = client.post(f"/api/v1/campaigns/{campaign['id']}/launch")

    assert launched.status_code == 422, launched.text
    assert "consented" in launched.text.lower()


def test_campaign_receipt_matches_only_identifiers_present_in_webhook(
    client: TestClient,
) -> None:
    customer_id = _configure_sms_campaign_delivery()
    assert (
        client.put(
            "/api/v1/campaigns/consents",
            json={
                "customer_id": customer_id,
                "channel": "sms",
                "status": "opted_in",
                "source": "profile preferences",
                "evidence": "SMS enabled",
            },
        ).status_code
        == 200
    )
    delivery_ids: list[str] = []
    idempotency_keys: list[str] = []
    for name in ("First queued campaign", "Second queued campaign"):
        payload = _campaign_payload(name)
        payload["channel"] = "sms"
        campaign = client.post("/api/v1/campaigns", json=payload).json()
        assert client.post(f"/api/v1/campaigns/{campaign['id']}/launch").status_code == 200
        delivery = client.get(f"/api/v1/campaigns/{campaign['id']}/deliveries").json()[0]
        delivery_ids.append(delivery["id"])
        idempotency_keys.append(delivery["idempotency_key"])

    with Session(get_engine()) as db:
        receipt = campaign_service.record_delivery_receipt(
            db,
            market_id="market-ng",
            provider=ChannelType.sms,
            status_label="delivered",
            provider_message_id=None,
            campaign_delivery_id=None,
            idempotency_key=idempotency_keys[1],
            delivery_id="sms-idempotency-receipt",
            raw_payload={"status": "delivered"},
        )
        assert receipt is not None
        assert receipt.id == delivery_ids[1]
        first = db.get(CampaignDeliveryRecord, delivery_ids[0])
        assert first is not None
        assert first.status == "queued"
