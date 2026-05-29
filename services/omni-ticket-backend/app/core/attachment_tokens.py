import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from app.core.config import settings


TOKEN_PREFIX = "otatt"


@dataclass(frozen=True)
class AttachmentTokenPayload:
    market_id: str
    ticket_id: str
    attachment_id: str
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


def create_attachment_download_token(
    *,
    market_id: str,
    ticket_id: str,
    attachment_id: str,
) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.attachment_download_ttl_minutes
    )
    payload = ".".join(
        [
            _b64_encode(market_id),
            _b64_encode(ticket_id),
            _b64_encode(attachment_id),
            _base36(int(expires_at.timestamp())),
        ]
    )
    return f"{TOKEN_PREFIX}.{payload}.{_signature(payload)}", expires_at


def parse_attachment_download_token(token: str) -> AttachmentTokenPayload | None:
    parts = token.split(".")
    if len(parts) != 6 or parts[0] != TOKEN_PREFIX:
        return None
    _, market_part, ticket_part, attachment_part, expiry_part, provided_signature = parts
    payload = ".".join([market_part, ticket_part, attachment_part, expiry_part])
    if not hmac.compare_digest(_signature(payload), provided_signature):
        return None
    try:
        parsed = AttachmentTokenPayload(
            market_id=_b64_decode(market_part),
            ticket_id=_b64_decode(ticket_part),
            attachment_id=_b64_decode(attachment_part),
            expires_at=datetime.fromtimestamp(_from_base36(expiry_part), tz=timezone.utc),
        )
    except (ValueError, UnicodeDecodeError):
        return None
    if parsed.expires_at <= datetime.now(timezone.utc):
        return None
    return parsed
