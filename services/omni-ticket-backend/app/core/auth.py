from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from app.core.config import settings


TOKEN_PREFIX = "ot2"


@dataclass(frozen=True)
class TokenPayload:
    user_id: str
    expires_at: datetime


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _from_base36(value: str) -> int:
    return int(value, 36)


def _b64_encode(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _b64_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")


def _signature(payload: str) -> str:
    digest = hmac.new(
        settings.session_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def create_session_token(user_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes)
    user_part = _b64_encode(user_id)
    expiry_part = _base36(int(expires_at.timestamp()))
    nonce = token_urlsafe(8)
    payload = f"{user_part}.{expiry_part}.{nonce}"
    return f"{TOKEN_PREFIX}.{payload}.{_signature(payload)}", expires_at


def parse_session_token(token: str) -> TokenPayload | None:
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != TOKEN_PREFIX:
        return None
    _, user_part, expiry_part, nonce, provided_signature = parts
    payload = f"{user_part}.{expiry_part}.{nonce}"
    if not hmac.compare_digest(_signature(payload), provided_signature):
        return None
    try:
        user_id = _b64_decode(user_part)
        expires_at = datetime.fromtimestamp(_from_base36(expiry_part), tz=timezone.utc)
    except (ValueError, UnicodeDecodeError):
        return None
    return TokenPayload(user_id=user_id, expires_at=expires_at)
