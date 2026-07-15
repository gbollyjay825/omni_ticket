from collections.abc import Callable

from fastapi.testclient import TestClient


def _segment_payload(name: str = "Payment recovery") -> dict:
    return {
        "name": name,
        "description": "Customers who need payment recovery support.",
        "rules": {
            "include_all": False,
            "tags_any": ["payment-risk"],
            "tags_all": [],
            "preferred_channels_any": [],
            "sentiments": [],
            "company_ids": [],
        },
    }


def test_segment_lifecycle_uses_real_market_customers_and_is_audited(
    client: TestClient,
) -> None:
    customers = client.get("/api/v1/customers").json()
    expected_payment_risk = sum(
        1 for customer in customers if "payment-risk" in customer["tags"]
    )

    created = client.post("/api/v1/segments", json=_segment_payload())
    assert created.status_code == 201, created.text
    segment = created.json()
    assert segment["market_id"] == "market-ng"
    assert segment["member_count"] == expected_payment_risk
    assert segment["rules"]["tags_any"] == ["payment-risk"]
    assert segment["active"] is True

    listed = client.get("/api/v1/segments")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [segment["id"]]

    updated = client.patch(
        f"/api/v1/segments/{segment['id']}",
        json={
            "name": "Angry customers",
            "active": False,
            "rules": {
                "include_all": False,
                "tags_any": [],
                "tags_all": [],
                "preferred_channels_any": [],
                "sentiments": ["angry"],
                "company_ids": [],
            },
        },
    )
    assert updated.status_code == 200, updated.text
    expected_angry = sum(1 for customer in customers if customer["sentiment"] == "angry")
    assert updated.json()["member_count"] == expected_angry
    assert updated.json()["active"] is False

    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200, audit.text
    actions = [
        event["action"]
        for event in audit.json()
        if event["entity_id"] == segment["id"]
    ]
    assert "segment.create" in actions
    assert "segment.update" in actions


def test_segment_requires_explicit_rules_and_unique_market_name(client: TestClient) -> None:
    invalid = _segment_payload("No rules")
    invalid["rules"]["tags_any"] = []
    response = client.post("/api/v1/segments", json=invalid)
    assert response.status_code == 422

    first = client.post("/api/v1/segments", json=_segment_payload("VIP care"))
    assert first.status_code == 201, first.text
    duplicate = client.post("/api/v1/segments", json=_segment_payload("VIP care"))
    assert duplicate.status_code == 409


def test_segment_include_all_and_market_isolation(
    client: TestClient,
    login_as: Callable[..., dict[str, str]],
) -> None:
    ng_customers = client.get("/api/v1/customers").json()
    include_all = _segment_payload("All Nigeria contacts")
    include_all["rules"] = {
        "include_all": True,
        "tags_any": [],
        "tags_all": [],
        "preferred_channels_any": [],
        "sentiments": [],
        "company_ids": [],
    }
    created = client.post("/api/v1/segments", json=include_all)
    assert created.status_code == 201, created.text
    assert created.json()["member_count"] == len(ng_customers)

    gh_headers = login_as("kofi.gh@omniticket.example.com", market_id="market-gh")
    gh_list = client.get("/api/v1/segments", headers=gh_headers)
    assert gh_list.status_code == 200, gh_list.text
    assert gh_list.json() == []

    forbidden = client.post(
        "/api/v1/segments",
        headers=gh_headers,
        json=_segment_payload("Agent cannot create"),
    )
    assert forbidden.status_code == 403
