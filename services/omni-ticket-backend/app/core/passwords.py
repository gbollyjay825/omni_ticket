from __future__ import annotations

import base64
import hashlib
import hmac
from secrets import token_bytes


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 210_000
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    salt = token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )
    salt_part = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_part = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{ALGORITHM}${ITERATIONS}${salt_part}${digest_part}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations_part, salt_part, digest_part = password_hash.split("$", 3)
        iterations = int(iterations_part)
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    padding = "=" * (-len(salt_part) % 4)
    digest_padding = "=" * (-len(digest_part) % 4)
    try:
        salt = base64.urlsafe_b64decode(f"{salt_part}{padding}")
        expected = base64.urlsafe_b64decode(f"{digest_part}{digest_padding}")
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def validate_password_strength(password: str, *, user_email: str | None = None) -> None:
    from fastapi import HTTPException, status

    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if user_email and user_email.split("@", 1)[0].lower() in password.lower():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password cannot contain the user's email name.",
        )
