import json
import logging
import re

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_observability_headers_are_added() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert re.fullmatch(r"req_[a-f0-9]{32}", response.headers["X-Request-ID"])
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_request_observability_preserves_safe_request_id() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health", headers={"X-Request-ID": "case-OMNI-1001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "case-OMNI-1001"


def test_request_observability_logs_json_access_record(caplog) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(create_app())
    with caplog.at_level(logging.INFO, logger="omni_ticket.access"):
        response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-1001"})

    assert response.status_code == 200
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "http.request"
    assert payload["request_id"] == "trace-1001"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] >= 0
