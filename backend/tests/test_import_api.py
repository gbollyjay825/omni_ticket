from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.imports import import_repository
from app.db.models import ImportReconciliationRecord
from app.db.session import get_engine
from app.models.domain import utc_now


def _completed_import_run(*, provider: str, mode: str) -> None:
    with Session(get_engine()) as db:
        run = import_repository.begin_run(
            db,
            market_id="market-ng",
            provider=provider,
            mode=mode,
            dry_run=False,
            started_by="migration-test",
        )
        import_repository.finish_run(
            run,
            status="completed",
            statistics={"records": {"created": 3}},
        )
        db.commit()


def _record_source_manifest(client: TestClient, provider: str, entities: list[str]) -> None:
    response = client.post(
        "/api/v1/imports/reconciliation/manifests",
        json={
            "provider": provider,
            "source_snapshot_at": utc_now().isoformat(),
            "entities": [
                {
                    "entity_type": entity_type,
                    "source_count": 1,
                    "source_checksum": f"sha256:{provider}:{entity_type}",
                    "sample_size": 1,
                    "sample_failures": 0,
                    "missing_attachments": 0,
                }
                for entity_type in entities
            ],
        },
    )
    assert response.status_code == 200, response.text


def test_admin_can_read_import_runs_and_reconciliation(client: TestClient) -> None:
    with Session(get_engine()) as db:
        run = import_repository.begin_run(
            db,
            market_id="market-ng",
            provider="freshdesk",
            mode="incremental",
            dry_run=True,
            started_by="test",
            source_cursor={"updated_since": "2026-07-01T00:00:00Z"},
        )
        import_repository.set_mapping(
            db,
            market_id="market-ng",
            provider="freshdesk",
            entity_type="ticket",
            external_id="42",
            internal_id="ticket-42",
            source_updated_at=None,
            payload_hash="abc",
        )
        import_repository.finish_run(
            run,
            status="completed",
            statistics={"tickets": {"created": 1}},
            next_cursor={"updated_since": "2026-07-02T00:00:00Z"},
        )
        db.commit()
        run_id = run.id

    runs = client.get("/api/v1/imports/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["id"] == run_id
    assert runs.json()[0]["dry_run"] is True

    detail = client.get(f"/api/v1/imports/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["statistics"]["tickets"]["created"] == 1

    reconciliation = client.get("/api/v1/imports/reconciliation")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["providers"]["freshdesk"]["ticket"] == 1


def test_agent_cannot_read_import_control_plane(
    client: TestClient,
    login_as,
) -> None:
    response = client.get(
        "/api/v1/imports/runs",
        headers=login_as("amara.ng@omniticket.example.com"),
    )
    assert response.status_code == 403


def test_cutover_is_blocked_without_source_reconciliation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/cutover/approve",
        json={"reason": "Migration lead approved the production route."},
    )

    assert response.status_code == 422
    assert "every reconciliation check" in response.text.lower()


def test_reconciliation_manifest_and_cutover_decision_are_audited(
    client: TestClient,
) -> None:
    required = {
        "freshdesk": ["contact", "ticket", "conversation"],
        "freshchat": ["user", "conversation", "message"],
    }
    with Session(get_engine()) as db:
        for provider, entity_types in required.items():
            for entity_type in entity_types:
                import_repository.set_mapping(
                    db,
                    market_id="market-ng",
                    provider=provider,
                    entity_type=entity_type,
                    external_id=f"{provider}-{entity_type}-1",
                    internal_id=f"omni-{provider}-{entity_type}-1",
                    source_updated_at=None,
                    payload_hash=f"hash-{provider}-{entity_type}",
                )
        db.commit()

    for provider, entity_types in required.items():
        _completed_import_run(provider=provider, mode="full_export")
        _completed_import_run(provider=provider, mode="incremental")
        _record_source_manifest(client, provider, entity_types)
    _record_source_manifest(client, "freshdesk", required["freshdesk"])

    with Session(get_engine()) as db:
        freshdesk_snapshots = db.query(ImportReconciliationRecord).filter_by(
            market_id="market-ng",
            provider="freshdesk",
        ).count()
        assert freshdesk_snapshots == 6

    reconciliation = client.get("/api/v1/imports/reconciliation")
    assert reconciliation.status_code == 200, reconciliation.text
    body = reconciliation.json()
    assert body["readiness"]["ready"] is True
    assert body["provider_results"]["freshdesk"]["verified"] is True
    assert body["provider_results"]["freshchat"]["verified"] is True
    assert body["source_manifests"]["freshdesk"]["ticket"]["source_count"] == 1

    approved = client.post(
        "/api/v1/imports/cutover/approve",
        json={"reason": "All migration evidence was reviewed by the cutover lead."},
    )
    assert approved.status_code == 200, approved.text
    decision = approved.json()["cutover"]
    assert decision["status"] == "approved"
    assert decision["rollback_active"] is True
    assert decision["snapshot_current"] is True

    revoked = client.post(
        "/api/v1/imports/cutover/revoke",
        json={"reason": "Routing rollback drill completed before broad release."},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["cutover"]["status"] == "revoked"

    actions = [event["action"] for event in client.get("/api/v1/audit").json()]
    assert "import.reconciliation.recorded" in actions
    assert "import.cutover.approved" in actions
    assert "import.cutover.revoked" in actions


def test_reconciliation_rejects_invalid_sample_counts(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/reconciliation/manifests",
        json={
            "provider": "freshdesk",
            "source_snapshot_at": utc_now().isoformat(),
            "entities": [
                {
                    "entity_type": "ticket",
                    "source_count": 5,
                    "sample_size": 1,
                    "sample_failures": 2,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "sample failures" in response.text.lower()


def test_reconciliation_rejects_timezone_free_snapshot(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/reconciliation/manifests",
        json={
            "provider": "freshchat",
            "source_snapshot_at": "2026-07-14T04:00:00",
            "entities": [
                {
                    "entity_type": "message",
                    "source_count": 0,
                    "source_checksum": "sha256:empty",
                    "sample_size": 1,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "timezone" in response.text.lower()
