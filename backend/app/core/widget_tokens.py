from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

from app.core.config import settings


@dataclass(frozen=True)
class WidgetTokenPayload:
    market_id: str
    ticket_id: str
    customer_id: str
    expires_at: datetime


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signature(payload: str) -> str:
    return hmac.new(
        settings.session_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_widget_token(
    *,
    market_id: str,
    ticket_id: str,
    customer_id: str,
    ttl_days: int = 7,
) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    payload = _encode(
        json.dumps(
            {
                "market_id": market_id,
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "expires_at": int(expires_at.timestamp()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    return f"ow1.{payload}.{_signature(payload)}", expires_at


def parse_widget_token(token: str) -> WidgetTokenPayload | None:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "ow1":
        return None
    payload, signature = parts[1:]
    if not hmac.compare_digest(_signature(payload), signature):
        return None
    try:
        document = json.loads(_decode(payload))
        expires_at = datetime.fromtimestamp(int(document["expires_at"]), tz=timezone.utc)
        market_id = str(document["market_id"])
        ticket_id = str(document["ticket_id"])
        customer_id = str(document["customer_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return WidgetTokenPayload(
        market_id=market_id,
        ticket_id=ticket_id,
        customer_id=customer_id,
        expires_at=expires_at,
    )
