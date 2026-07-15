from __future__ import annotations

import base64
import hashlib
import hmac
from secrets import token_bytes
from time import time
from urllib.parse import quote


TOTP_DIGITS = 6
TOTP_PERIOD_SECONDS = 30


def generate_totp_secret() -> str:
    return base64.b32encode(token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    normalized = secret.replace(" ", "").upper()
    padding = "=" * (-len(normalized) % 8)
    return base64.b32decode(f"{normalized}{padding}")


def _hotp(secret: str, counter: int) -> str:
    digest = hmac.new(
        _decode_secret(secret),
        counter.to_bytes(8, "big"),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(value % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def current_totp_code(secret: str, *, at_time: int | None = None) -> str:
    timestamp = int(time() if at_time is None else at_time)
    return _hotp(secret, timestamp // TOTP_PERIOD_SECONDS)


def verify_totp_code(
    secret: str,
    code: str,
    *,
    at_time: int | None = None,
    window: int = 1,
) -> bool:
    normalized_code = "".join(character for character in code if character.isdigit())
    if len(normalized_code) != TOTP_DIGITS:
        return False
    timestamp = int(time() if at_time is None else at_time)
    counter = timestamp // TOTP_PERIOD_SECONDS
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret, counter + offset), normalized_code):
            return True
    return False


def otpauth_uri(*, issuer: str, account_name: str, secret: str) -> str:
    label = f"{issuer}:{account_name}"
    return (
        f"otpauth://totp/{quote(label)}"
        f"?secret={quote(secret)}"
        f"&issuer={quote(issuer)}"
        f"&algorithm=SHA1"
        f"&digits={TOTP_DIGITS}"
        f"&period={TOTP_PERIOD_SECONDS}"
    )
