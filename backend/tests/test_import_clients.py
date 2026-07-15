from __future__ import annotations

import base64

import httpx
import pytest

from app.importers.clients import (
    FreshchatClient,
    FreshdeskClient,
    SourceWindowExhausted,
)


def test_freshdesk_paginates_and_uses_basic_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        payload = [{"id": index} for index in range(100)] if page == 1 else [{"id": 101}]
        return httpx.Response(200, json=payload)

    client = FreshdeskClient(
        base_url="https://example.freshdesk.com",
        api_key="secret-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        contacts = list(client.iter_contacts())
    finally:
        client.close()

    assert len(contacts) == 101
    assert len(requests) == 2
    expected = base64.b64encode(b"secret-key:X").decode()
    assert requests[0].headers["Authorization"] == f"Basic {expected}"
    assert requests[0].url.path == "/api/v2/contacts"


def test_freshdesk_retries_rate_limits_using_retry_after() -> None:
    delays: list[float] = []
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json=[])

    client = FreshdeskClient(
        base_url="https://example.freshdesk.com",
        api_key="secret-key",
        transport=httpx.MockTransport(handler),
        sleeper=delays.append,
    )
    try:
        assert list(client.iter_contacts()) == []
    finally:
        client.close()

    assert attempts == 2
    assert delays == [3.0]


def test_freshdesk_refuses_a_full_result_window() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": index} for index in range(2)])

    client = FreshdeskClient(
        base_url="https://example.freshdesk.com",
        api_key="secret-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(SourceWindowExhausted, match="account export"):
            list(
                client._iter_list(
                    "/api/v2/tickets",
                    per_page=2,
                    max_pages=2,
                    strict_page_cap=True,
                )
            )
    finally:
        client.close()


def test_freshchat_requires_documented_user_criteria() -> None:
    client = FreshchatClient(
        base_url="https://example.freshchat.com",
        api_token="token",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    try:
        with pytest.raises(ValueError, match="account export"):
            list(client.iter_users(criteria={}))
    finally:
        client.close()


def test_freshchat_paginates_messages_and_uses_bearer_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "messages": [{"id": f"message-{page}"}],
                "pagination": {"current_page": page, "total_pages": 2},
            },
        )

    client = FreshchatClient(
        base_url="https://example.freshchat.com",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )
    try:
        messages = list(client.iter_messages("conversation-1"))
    finally:
        client.close()

    assert [message["id"] for message in messages] == ["message-1", "message-2"]
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert requests[0].url.path == "/v2/conversations/conversation-1/messages"
