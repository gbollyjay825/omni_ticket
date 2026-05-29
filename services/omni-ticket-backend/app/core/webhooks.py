import hashlib
import hmac
import time
from dataclasses import dataclass

from app.core.config import settings


SIGNATURE_HEADER = "x-omni-signature"
TIMESTAMP_HEADER = "x-omni-timestamp"
DELIVERY_HEADER = "x-omni-delivery"


@dataclass(frozen=True)
class WebhookVerification:
    delivery_id: str | None
    timestamp: int
    signature: str


def webhook_secret(account_id: str, credential_ref: str | None) -> bytes:
    material = f"{settings.session_secret}:{account_id}:{credential_ref or 'no-credential-ref'}"
    return material.encode()


def sign_webhook_body(
    *,
    account_id: str,
    credential_ref: str | None,
    timestamp: int,
    body: bytes,
) -> str:
    payload = str(timestamp).encode() + b"." + body
    signature = hmac.new(webhook_secret(account_id, credential_ref), payload, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def verify_webhook_signature(
    *,
    account_id: str,
    credential_ref: str | None,
    body: bytes,
    headers: dict[str, str],
    now: int | None = None,
) -> WebhookVerification:
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    timestamp_value = normalized_headers.get(TIMESTAMP_HEADER)
    signature = normalized_headers.get(SIGNATURE_HEADER)
    if not timestamp_value or not signature:
        raise ValueError("Missing webhook signature headers")
    try:
        timestamp = int(timestamp_value)
    except ValueError as exc:
        raise ValueError("Invalid webhook timestamp") from exc

    current_time = now or int(time.time())
    if abs(current_time - timestamp) > settings.webhook_signature_tolerance_seconds:
        raise ValueError("Webhook timestamp is outside the allowed replay window")

    expected_signature = sign_webhook_body(
        account_id=account_id,
        credential_ref=credential_ref,
        timestamp=timestamp,
        body=body,
    )
    if not hmac.compare_digest(expected_signature, signature):
        raise ValueError("Invalid webhook signature")

    return WebhookVerification(
        delivery_id=normalized_headers.get(DELIVERY_HEADER),
        timestamp=timestamp,
        signature=signature,
    )
