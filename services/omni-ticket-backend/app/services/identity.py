from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any
from urllib import parse
from urllib import request as urlrequest

from app.core.config import settings
from app.models.domain import OidcProviderConfig, UserRole


STATE_PREFIX = "oidc2"


@dataclass(frozen=True)
class OidcStatePayload:
    state_id: str
    expires_at: datetime


@dataclass(frozen=True)
class OidcTokenResponse:
    access_token: str
    id_token: str | None
    token_type: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class OidcUserInfo:
    subject: str
    email: str
    name: str
    email_verified: bool | None
    raw: dict[str, Any]


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


def _required_settings() -> dict[str, str | None]:
    return {
        "OMNI_OIDC_AUTHORIZATION_URL": settings.oidc_authorization_url,
        "OMNI_OIDC_TOKEN_URL": settings.oidc_token_url,
        "OMNI_OIDC_USERINFO_URL": settings.oidc_userinfo_url,
        "OMNI_OIDC_CLIENT_ID": settings.oidc_client_id,
        "OMNI_OIDC_CLIENT_SECRET": settings.oidc_client_secret,
        "OMNI_OIDC_REDIRECT_URL": settings.oidc_redirect_url,
    }


def normalized_allowed_domains() -> list[str]:
    return [
        value.strip().lower().removeprefix("@")
        for value in settings.oidc_allowed_email_domains
        if value.strip()
    ]


def oidc_provider_config() -> OidcProviderConfig:
    required = _required_settings()
    missing = [field_name for field_name, field_value in required.items() if not field_value]
    configured = settings.oidc_enabled and not missing
    return OidcProviderConfig(
        provider_name=settings.oidc_provider_name,
        enabled=settings.oidc_enabled,
        configured=configured,
        login_available=configured,
        authorization_endpoint_configured=bool(settings.oidc_authorization_url),
        token_endpoint_configured=bool(settings.oidc_token_url),
        userinfo_endpoint_configured=bool(settings.oidc_userinfo_url),
        redirect_url_configured=bool(settings.oidc_redirect_url),
        client_configured=bool(settings.oidc_client_id and settings.oidc_client_secret),
        auto_provision_enabled=settings.oidc_auto_provision_enabled,
        default_role=UserRole(settings.oidc_default_role),
        default_market_id=settings.oidc_default_market_id,
        allowed_email_domains=normalized_allowed_domains(),
        required_settings=list(required),
        missing_settings=missing if settings.oidc_enabled else ["OMNI_OIDC_ENABLED=true", *missing],
        notes=(
            f"{settings.oidc_provider_name} login is available."
            if configured
            else "Enterprise SSO remains pending until the OIDC provider, client, redirect, and secret are configured."
        ),
    )


def oidc_state_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.oidc_state_ttl_minutes)


def create_oidc_state_token(state_id: str, expires_at: datetime) -> str:
    state_part = _b64_encode(state_id)
    expiry_part = _base36(int(expires_at.timestamp()))
    payload = f"{state_part}.{expiry_part}"
    return f"{STATE_PREFIX}.{payload}.{_signature(payload)}"


def parse_oidc_state_token(state: str) -> OidcStatePayload | None:
    parts = state.split(".")
    if len(parts) != 4 or parts[0] != STATE_PREFIX:
        return None
    _, state_part, expiry_part, provided_signature = parts
    payload = f"{state_part}.{expiry_part}"
    if not hmac.compare_digest(_signature(payload), provided_signature):
        return None
    try:
        state_id = _b64_decode(state_part)
        expires_at = datetime.fromtimestamp(_from_base36(expiry_part), tz=timezone.utc)
    except (ValueError, UnicodeDecodeError):
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return OidcStatePayload(state_id=state_id, expires_at=expires_at)


def oidc_state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def generate_pkce_pair() -> tuple[str, str]:
    verifier = token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorization_url(
    *,
    state: str,
    code_challenge: str,
    nonce: str,
) -> str:
    if not settings.oidc_authorization_url or not settings.oidc_client_id or not settings.oidc_redirect_url:
        raise ValueError("OIDC authorization settings are incomplete.")
    query = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_url,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    separator = "&" if "?" in settings.oidc_authorization_url else "?"
    return f"{settings.oidc_authorization_url}{separator}{parse.urlencode(query)}"


def _read_json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise ValueError("OIDC provider returned an invalid JSON response.")
    return data


def exchange_code_for_userinfo(*, code: str, code_verifier: str) -> OidcUserInfo:
    token = _exchange_code_for_token(code=code, code_verifier=code_verifier)
    return _fetch_userinfo(token.access_token)


def _exchange_code_for_token(*, code: str, code_verifier: str) -> OidcTokenResponse:
    if (
        not settings.oidc_token_url
        or not settings.oidc_client_id
        or not settings.oidc_client_secret
        or not settings.oidc_redirect_url
    ):
        raise ValueError("OIDC token settings are incomplete.")
    body = parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oidc_redirect_url,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")
    request = urlrequest.Request(
        settings.oidc_token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlrequest.urlopen(request, timeout=settings.oidc_http_timeout_seconds) as response:
        payload = _read_json_response(response)
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("OIDC provider did not return an access token.")
    return OidcTokenResponse(
        access_token=access_token,
        id_token=str(payload["id_token"]) if payload.get("id_token") else None,
        token_type=str(payload.get("token_type") or "Bearer"),
        raw=payload,
    )


def _fetch_userinfo(access_token: str) -> OidcUserInfo:
    if not settings.oidc_userinfo_url:
        raise ValueError("OIDC userinfo settings are incomplete.")
    request = urlrequest.Request(
        settings.oidc_userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlrequest.urlopen(request, timeout=settings.oidc_http_timeout_seconds) as response:
        payload = _read_json_response(response)
    subject = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    if not subject:
        raise ValueError("OIDC userinfo response did not include a subject.")
    if not email:
        raise ValueError("OIDC userinfo response did not include an email.")
    email_verified_value = payload.get("email_verified")
    email_verified = (
        None
        if email_verified_value is None
        else str(email_verified_value).strip().lower() in {"1", "true", "yes"}
    )
    name = str(payload.get("name") or payload.get("preferred_username") or email.split("@", 1)[0]).strip()
    return OidcUserInfo(
        subject=subject,
        email=email,
        name=name or email,
        email_verified=email_verified,
        raw=payload,
    )
