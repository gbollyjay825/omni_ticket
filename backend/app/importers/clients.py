from collections.abc import Callable, Iterator, Mapping
from email.utils import parsedate_to_datetime
import time
from typing import Any
from urllib.parse import urlparse

import httpx


class FreshworksApiError(RuntimeError):
    pass


class SourceWindowExhausted(FreshworksApiError):
    """Raised when an API result cap could hide additional source records."""


def _normalized_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Freshworks base URL must be an absolute HTTPS URL")
    return base_url


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), 60.0)
        except ValueError:
            try:
                reset_at = parsedate_to_datetime(retry_after)
                return min(max(reset_at.timestamp() - time.time(), 0.0), 60.0)
            except (TypeError, ValueError, OverflowError):
                pass
    return min(float(2**attempt), 30.0)


class _FreshworksClient:
    def __init__(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout_seconds: float = 30,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = _normalized_base_url(base_url)
        self.max_retries = max(0, max_retries)
        self.sleeper = sleeper
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json", **dict(headers or {})},
            auth=auth,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "_FreshworksClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, path: str, *, params: Mapping[str, Any] | None = None) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise FreshworksApiError(f"Freshworks request failed: {exc}") from exc
                self.sleeper(min(float(2**attempt), 30.0))
                continue
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt >= self.max_retries:
                break
            self.sleeper(_retry_delay(response, attempt))
        if response is None:
            raise FreshworksApiError("Freshworks request did not produce a response")
        if response.is_redirect:
            raise FreshworksApiError(
                f"Freshworks API returned an unexpected redirect ({response.status_code})"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            request_id = response.headers.get("X-Request-ID") or response.headers.get(
                "X-Freshworks-Request-ID", ""
            )
            suffix = f" request_id={request_id}" if request_id else ""
            raise FreshworksApiError(
                f"Freshworks API returned {response.status_code} for {path}.{suffix}"
            ) from exc
        return response

    def _json(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        response = self._get(path, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise FreshworksApiError(f"Freshworks API returned invalid JSON for {path}") from exc


class FreshdeskClient(_FreshworksClient):
    def __init__(self, *, api_key: str, **kwargs: Any) -> None:
        if not api_key.strip():
            raise ValueError("Freshdesk API key is required")
        super().__init__(auth=(api_key.strip(), "X"), **kwargs)

    def _iter_list(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 10_000,
        strict_page_cap: bool = False,
    ) -> Iterator[dict[str, Any]]:
        base_params = dict(params or {})
        for page in range(1, max_pages + 1):
            response = self._get(
                path,
                params={**base_params, "page": page, "per_page": per_page},
            )
            try:
                payload = response.json()
            except ValueError as exc:
                raise FreshworksApiError(
                    f"Freshdesk returned invalid JSON for {path} page {page}"
                ) from exc
            if not isinstance(payload, list):
                raise FreshworksApiError(f"Freshdesk returned a non-list payload for {path}")
            for item in payload:
                if isinstance(item, dict):
                    yield dict(item)
            if len(payload) < per_page:
                return
            if page == max_pages:
                if strict_page_cap:
                    raise SourceWindowExhausted(
                        f"Freshdesk {path} filled its {max_pages * per_page:,}-record API window; "
                        "use a full account export before incremental sync"
                    )
                raise FreshworksApiError(
                    f"Freshdesk pagination exceeded the configured {max_pages}-page safety limit"
                )

    def iter_contacts(self, *, updated_since: str | None = None) -> Iterator[dict[str, Any]]:
        params = {"updated_since": updated_since} if updated_since else None
        yield from self._iter_list("/api/v2/contacts", params=params)

    def get_contact(self, contact_id: object) -> dict[str, Any]:
        payload = self._json(f"/api/v2/contacts/{contact_id}")
        if not isinstance(payload, dict):
            raise FreshworksApiError("Freshdesk returned an invalid contact payload")
        return dict(payload)

    def iter_companies(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_list("/api/v2/companies")

    def iter_agents(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_list("/api/v2/agents")

    def iter_groups(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_list("/api/v2/groups")

    def iter_products(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_list("/api/v2/products")

    def iter_tickets(self, *, updated_since: str) -> Iterator[dict[str, Any]]:
        yield from self._iter_list(
            "/api/v2/tickets",
            params={
                "updated_since": updated_since,
                "include": "description",
                "order_by": "updated_at",
                "order_type": "asc",
            },
            max_pages=300,
            strict_page_cap=True,
        )

    def iter_ticket_conversations(self, ticket_id: object) -> Iterator[dict[str, Any]]:
        yield from self._iter_list(f"/api/v2/tickets/{ticket_id}/conversations")


class FreshchatClient(_FreshworksClient):
    def __init__(self, *, api_token: str, **kwargs: Any) -> None:
        if not api_token.strip():
            raise ValueError("Freshchat API token is required")
        super().__init__(headers={"Authorization": f"Bearer {api_token.strip()}"}, **kwargs)

    def _iter_collection(
        self,
        path: str,
        *,
        collection_key: str,
        params: Mapping[str, Any] | None = None,
        items_per_page: int = 100,
    ) -> Iterator[dict[str, Any]]:
        base_params = dict(params or {})
        page = 1
        while True:
            payload = self._json(
                path,
                params={
                    **base_params,
                    "page": page,
                    "items_per_page": items_per_page,
                },
            )
            if not isinstance(payload, dict):
                raise FreshworksApiError(f"Freshchat returned a non-object payload for {path}")
            items = payload.get(collection_key, [])
            if not isinstance(items, list):
                raise FreshworksApiError(
                    f"Freshchat payload for {path} has no {collection_key} list"
                )
            for item in items:
                if isinstance(item, dict):
                    yield dict(item)
            pagination = payload.get("pagination")
            pagination_data: dict[str, Any] | None = (
                dict(pagination) if isinstance(pagination, dict) else None
            )
            total_pages = int(pagination_data.get("total_pages", page)) if pagination_data else page
            if page >= total_pages or (pagination_data is None and len(items) < items_per_page):
                return
            page += 1

    def iter_users(self, *, criteria: Mapping[str, str]) -> Iterator[dict[str, Any]]:
        allowed = {"first_name", "last_name", "email", "reference_id", "phone_no"}
        query = {key: value for key, value in criteria.items() if key in allowed and value.strip()}
        if not query:
            raise ValueError(
                "Freshchat requires at least one documented user search criterion; "
                "use an account export for tenant-wide discovery"
            )
        yield from self._iter_collection("/v2/users", collection_key="users", params=query)

    def list_user_conversations(self, user_id: str) -> list[str]:
        payload = self._json(f"/v2/users/{user_id}/conversations")
        if not isinstance(payload, dict) or not isinstance(payload.get("conversations"), list):
            raise FreshworksApiError("Freshchat returned an invalid user conversations payload")
        return [
            str(item["id"])
            for item in payload["conversations"]
            if isinstance(item, dict) and item.get("id")
        ]

    def get_user(self, user_id: str) -> dict[str, Any]:
        payload = self._json(f"/v2/users/{user_id}")
        if not isinstance(payload, dict):
            raise FreshworksApiError("Freshchat returned an invalid user payload")
        return dict(payload)

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        payload = self._json(f"/v2/conversations/{conversation_id}")
        if not isinstance(payload, dict):
            raise FreshworksApiError("Freshchat returned an invalid conversation payload")
        return dict(payload)

    def iter_messages(
        self,
        conversation_id: str,
        *,
        from_time: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        params = {"from_time": from_time} if from_time else None
        yield from self._iter_collection(
            f"/v2/conversations/{conversation_id}/messages",
            collection_key="messages",
            params=params,
            items_per_page=50,
        )

    def iter_agents(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_collection("/v2/agents", collection_key="agents")

    def iter_groups(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_collection("/v2/groups", collection_key="groups")

    def iter_channels(self) -> Iterator[dict[str, Any]]:
        yield from self._iter_collection("/v2/channels", collection_key="channels")
