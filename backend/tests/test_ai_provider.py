import json
from typing import Any

from app.core.config import settings
from app.core.store import store
from app.services import ai as ai_service


class FakeAnthropicResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeAnthropicResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _ticket_and_customer():
    ticket = next(iter(store.tickets.values()))
    customer = store.customers[ticket.customer_id]
    return ticket, customer


def test_anthropic_guidance_reads_gitignored_key_file(
    monkeypatch,
    tmp_path,
) -> None:
    key_file = tmp_path / "AI_Key"
    key_file.write_text("sk-ant-test-value\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    def fake_urlopen(request, timeout: int) -> FakeAnthropicResponse:
        body = json.loads((request.data or b"{}").decode("utf-8"))
        calls.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "body": body,
                "api_key": next(
                    (
                        value
                        for key, value in request.headers.items()
                        if key.lower() == "x-api-key"
                    ),
                    None,
                ),
            }
        )
        return FakeAnthropicResponse(
            {
                "model": "claude-test-model",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "summary": "Customer needs urgent payment support.",
                                "recommended_action": "Validate the payment reference and set a clear update time.",
                                "confidence": 0.91,
                            }
                        ),
                    }
                ],
            }
        )

    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key_file", str(key_file))
    monkeypatch.setattr(settings, "anthropic_api_base_url", "https://api.anthropic.test")
    monkeypatch.setattr(settings, "anthropic_model", "claude-test")
    monkeypatch.setattr(settings, "anthropic_timeout_seconds", 3)
    monkeypatch.setattr(ai_service.urlrequest, "urlopen", fake_urlopen)

    ticket, customer = _ticket_and_customer()
    guidance = ai_service.automation_service.generate_guidance(ticket, customer)

    assert guidance.summary == "Customer needs urgent payment support."
    assert guidance.recommended_action == "Validate the payment reference and set a clear update time."
    assert guidance.confidence == 0.91
    assert guidance.model_version == "claude-test-model"
    assert guidance.input_reference == f"anthropic:{ticket.id}"
    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.anthropic.test/v1/messages"
    assert calls[0]["timeout"] == 3
    assert calls[0]["api_key"] == "sk-ant-test-value"
    assert calls[0]["body"]["model"] == "claude-test"
    assert calls[0]["body"]["messages"][0]["role"] == "user"


def test_ai_guidance_falls_back_when_anthropic_key_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise AssertionError("Anthropic should not be called without a key")

    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key_file", str(tmp_path / "missing_AI_Key"))
    monkeypatch.setattr(ai_service.urlrequest, "urlopen", fail_urlopen)

    ticket, customer = _ticket_and_customer()
    guidance = ai_service.automation_service.generate_guidance(ticket, customer)

    assert guidance.model_version == "rules-v1"
    assert guidance.input_reference == "rules:fallback"
    assert customer.name in guidance.summary
    assert guidance.recommended_action
