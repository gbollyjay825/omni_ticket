from datetime import datetime, timezone
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_admin, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.core.auth import create_session_token
from app.core.config import settings
from app.core.mfa import generate_totp_secret, otpauth_uri, verify_totp_code
from app.core.passwords import hash_password, validate_password_strength, verify_password
from app.core.permissions import effective_permissions_for
from app.core.rate_limit import (
    RateLimitExceeded,
    raise_rate_limit_exceeded,
)
from app.db.audit import write_audit_event
from app.db.mappers import market_from_record, user_from_record
from app.db.models import MarketRecord, OidcLoginStateRecord, SessionRecord, UserRecord
from app.db.rate_limit import database_rate_limiter
from app.db.session import get_db
from app.db.sso_settings import sso_provider_settings_repository
from app.models.domain import (
    AuthSession,
    ChangePasswordRequest,
    ConfirmMfaRequest,
    CreateUserRequest,
    DisableMfaRequest,
    LoginRequest,
    Market,
    MfaEnrollmentResponse,
    OidcCallbackRequest,
    OidcProviderConfig,
    OidcStartResponse,
    Permission,
    UpdateUserRequest,
    User,
    UserRole,
    utc_now,
)
from app.services import identity as identity_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _assigned_markets(db: Session, market_ids: list[str]) -> list[Market]:
    records = db.scalars(select(MarketRecord).where(MarketRecord.id.in_(market_ids))).all()
    records_by_id = {record.id: record for record in records}
    return [market_from_record(records_by_id[market_id]) for market_id in market_ids if market_id in records_by_id]


def _normalize_market_assignment(
    db: Session,
    market_ids: list[str] | None,
    default_market_id: str | None,
) -> tuple[list[str], str]:
    normalized_market_ids = list(dict.fromkeys(market_ids or []))
    if not normalized_market_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one market is required")
    records = db.scalars(select(MarketRecord).where(MarketRecord.id.in_(normalized_market_ids))).all()
    active_market_ids = {record.id for record in records if record.active}
    missing = [market_id for market_id in normalized_market_ids if market_id not in active_market_ids]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown or inactive market: {missing[0]}",
        )
    resolved_default_market_id = default_market_id or normalized_market_ids[0]
    if resolved_default_market_id not in normalized_market_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Default market must be one of the assigned markets",
        )
    return normalized_market_ids, resolved_default_market_id


def _auth_session_for_user(
    db: Session,
    *,
    user_record: UserRecord,
    market_record: MarketRecord,
    auth_method: str,
    explicit_market_selection: bool,
) -> AuthSession:
    token, expires_at = create_session_token(user_record.id)
    now = utc_now()
    user_record.last_login_at = now
    if auth_method == "oidc":
        user_record.external_last_login_at = now
    db.add(SessionRecord(token=token, user_id=user_record.id, expires_at=expires_at))
    write_audit_event(
        db,
        actor=user_record.id,
        action="auth.login.success",
        entity_type="auth_session",
        entity_id=user_record.id,
        market_id=market_record.id,
        details={
            "email": user_record.email,
            "selected_market_id": market_record.id,
            "explicit_market_selection": explicit_market_selection,
            "auth_method": auth_method,
        },
    )
    if explicit_market_selection:
        write_audit_event(
            db,
            actor=user_record.id,
            action="auth.market.selected",
            entity_type="market",
            entity_id=market_record.id,
            market_id=market_record.id,
            details={
                "email": user_record.email,
                "selected_market_id": market_record.id,
                "auth_method": auth_method,
            },
        )
    db.commit()
    db.refresh(user_record)
    return AuthSession(
        access_token=token,
        user=user_from_record(user_record),
        market=market_from_record(market_record),
        available_markets=_assigned_markets(db, user_record.market_ids),
    )


def _oidc_provider_key(config: identity_service.ResolvedOidcConfig | None = None) -> str:
    cfg = config or identity_service.ResolvedOidcConfig.from_env()
    return cfg.provider_key


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _require_oidc_login_available(
    config: identity_service.ResolvedOidcConfig | None = None,
) -> OidcProviderConfig:
    provider_config = identity_service.oidc_provider_config(config)
    if not provider_config.login_available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Enterprise SSO is not configured.",
        )
    return provider_config


@router.post("/login", response_model=AuthSession)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthSession:
    try:
        database_rate_limiter.check(
            db,
            f"auth-login:{str(request.email).lower()}",
            limit=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        write_audit_event(
            db,
            actor=str(request.email).lower(),
            action="auth.login.rate_limited",
            entity_type="auth",
            entity_id=str(request.email).lower(),
            market_id=request.market_id,
            details={"email": str(request.email).lower(), "requested_market_id": request.market_id},
            commit=True,
        )
        raise_rate_limit_exceeded(exc)

    user_record = db.scalar(
        select(UserRecord).where(UserRecord.email == str(request.email).lower())
    )
    if (
        user_record is None
        or not user_record.active
        or not verify_password(request.password, user_record.password_hash)
    ):
        reason = "inactive_user" if user_record is not None and not user_record.active else "invalid_credentials"
        write_audit_event(
            db,
            actor=str(request.email).lower(),
            action="auth.login.denied",
            entity_type="auth",
            entity_id=str(request.email).lower(),
            market_id=request.market_id or (user_record.default_market_id if user_record else None),
            details={
                "email": str(request.email).lower(),
                "reason": reason,
                "requested_market_id": request.market_id,
            },
            commit=True,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = user_from_record(user_record)
    market_id = request.market_id or user.default_market_id
    if market_id not in user.market_ids:
        write_audit_event(
            db,
            actor=user.id,
            action="auth.market.denied",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details={"email": str(request.email).lower(), "assigned_market_ids": user.market_ids},
            commit=True,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not assigned to this market")

    market_record = db.get(MarketRecord, market_id)
    if market_record is None or not market_record.active:
        write_audit_event(
            db,
            actor=user.id,
            action="auth.login.denied",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details={"email": str(request.email).lower(), "reason": "market_not_found_or_inactive"},
            commit=True,
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")

    if user_record.mfa_enabled:
        if not request.mfa_code:
            write_audit_event(
                db,
                actor=user.id,
                action="auth.mfa.required",
                entity_type="user",
                entity_id=user.id,
                market_id=market_id,
                details={"email": user_record.email, "selected_market_id": market_id},
                commit=True,
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="MFA code required")
        if not user_record.mfa_secret or not verify_totp_code(
            user_record.mfa_secret,
            request.mfa_code,
        ):
            write_audit_event(
                db,
                actor=user.id,
                action="auth.mfa.denied",
                entity_type="user",
                entity_id=user.id,
                market_id=market_id,
                details={
                    "email": user_record.email,
                    "selected_market_id": market_id,
                    "reason": "invalid_mfa_code",
                },
                commit=True,
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
        user_record.mfa_last_verified_at = utc_now()
        write_audit_event(
            db,
            actor=user.id,
            action="auth.mfa.verified",
            entity_type="user",
            entity_id=user.id,
            market_id=market_id,
            details={"email": user_record.email, "selected_market_id": market_id},
        )

    return _auth_session_for_user(
        db,
        user_record=user_record,
        market_record=market_record,
        auth_method="password",
        explicit_market_selection=request.market_id is not None,
    )


@router.get("/oidc/config", response_model=OidcProviderConfig)
def read_oidc_provider_config(db: Session = Depends(get_db)) -> OidcProviderConfig:
    return identity_service.oidc_provider_config(sso_provider_settings_repository.resolve(db))


@router.get("/oidc/start", response_model=OidcStartResponse)
def start_oidc_login(
    market_id: str = Query(..., min_length=1),
    return_to: str | None = Query(None, max_length=500),
    db: Session = Depends(get_db),
) -> OidcStartResponse:
    oidc_config = sso_provider_settings_repository.resolve(db)
    _require_oidc_login_available(oidc_config)
    market_record = db.get(MarketRecord, market_id)
    if market_record is None or not market_record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
    expires_at = identity_service.oidc_state_expires_at()
    state_id = f"oidc_state_{uuid4().hex}"
    code_verifier, code_challenge = identity_service.generate_pkce_pair()
    nonce = token_urlsafe(24)
    state = identity_service.create_oidc_state_token(state_id, expires_at)
    db.add(
        OidcLoginStateRecord(
            id=state_id,
            state_hash=identity_service.oidc_state_hash(state),
            market_id=market_id,
            return_to=return_to,
            code_verifier=code_verifier,
            nonce=nonce,
            expires_at=expires_at,
        )
    )
    write_audit_event(
        db,
        actor="oidc",
        action="auth.oidc.start",
        entity_type="market",
        entity_id=market_id,
        market_id=market_id,
        details={
            "provider": _oidc_provider_key(oidc_config),
            "return_to_configured": bool(return_to),
        },
    )
    db.commit()
    return OidcStartResponse(
        authorization_url=identity_service.build_authorization_url(
            state=state,
            code_challenge=code_challenge,
            nonce=nonce,
            config=oidc_config,
        ),
        state=state,
        expires_at=expires_at,
    )


@router.post("/oidc/callback", response_model=AuthSession)
def complete_oidc_login(
    request: OidcCallbackRequest,
    db: Session = Depends(get_db),
) -> AuthSession:
    oidc_config = sso_provider_settings_repository.resolve(db)
    _require_oidc_login_available(oidc_config)
    parsed_state = identity_service.parse_oidc_state_token(request.state)
    if parsed_state is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SSO state")
    state_record = db.scalar(
        select(OidcLoginStateRecord).where(
            OidcLoginStateRecord.state_hash == identity_service.oidc_state_hash(request.state)
        )
    )
    if state_record is None or state_record.id != parsed_state.state_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SSO state")
    if state_record.used_at is not None or _as_utc(state_record.expires_at) <= utc_now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SSO state")
    market_record = db.get(MarketRecord, state_record.market_id)
    if market_record is None or not market_record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")

    state_record.used_at = utc_now()
    try:
        userinfo = identity_service.exchange_code_for_userinfo(
            code=request.code,
            code_verifier=state_record.code_verifier,
            config=oidc_config,
        )
    except Exception as exc:
        write_audit_event(
            db,
            actor="oidc",
            action="auth.oidc.denied",
            entity_type="market",
            entity_id=state_record.market_id,
            market_id=state_record.market_id,
            details={"provider": _oidc_provider_key(oidc_config), "reason": "provider_exchange_failed"},
            commit=True,
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Enterprise SSO provider exchange failed.",
        ) from exc

    if oidc_config.require_email_verified and userinfo.email_verified is not True:
        write_audit_event(
            db,
            actor=userinfo.email,
            action="auth.oidc.denied",
            entity_type="user",
            entity_id=userinfo.email,
            market_id=state_record.market_id,
            details={"provider": _oidc_provider_key(oidc_config), "reason": "email_not_verified"},
            commit=True,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="SSO email is not verified")

    allowed_domains = identity_service.normalized_allowed_domains(oidc_config)
    email_domain = userinfo.email.rsplit("@", 1)[-1]
    if allowed_domains and email_domain not in allowed_domains:
        write_audit_event(
            db,
            actor=userinfo.email,
            action="auth.oidc.denied",
            entity_type="user",
            entity_id=userinfo.email,
            market_id=state_record.market_id,
            details={
                "provider": _oidc_provider_key(oidc_config),
                "reason": "email_domain_not_allowed",
                "email_domain": email_domain,
            },
            commit=True,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="SSO email domain is not allowed")

    provider_key = _oidc_provider_key(oidc_config)
    user_record = db.scalar(
        select(UserRecord).where(
            UserRecord.external_identity_provider == provider_key,
            UserRecord.external_subject == userinfo.subject,
        )
    )
    if user_record is None:
        user_record = db.scalar(select(UserRecord).where(UserRecord.email == userinfo.email))

    if user_record is None:
        if not oidc_config.auto_provision_enabled:
            write_audit_event(
                db,
                actor=userinfo.email,
                action="auth.oidc.denied",
                entity_type="user",
                entity_id=userinfo.email,
                market_id=state_record.market_id,
                details={"provider": provider_key, "reason": "user_not_provisioned"},
                commit=True,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="SSO user is not provisioned")
        default_market_id = oidc_config.default_market_id or state_record.market_id
        default_market = db.get(MarketRecord, default_market_id)
        if default_market is None or not default_market.active:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="SSO default market is not active")
        market_ids = list(dict.fromkeys([default_market_id, state_record.market_id]))
        user_record = UserRecord(
            id=f"user_{uuid4().hex}",
            name=userinfo.name,
            email=userinfo.email,
            password_hash=None,
            password_reset_required=False,
            role=UserRole(oidc_config.default_role).value,
            default_market_id=default_market_id,
            market_ids=market_ids,
            active=True,
            external_identity_provider=provider_key,
            external_subject=userinfo.subject,
            external_last_login_at=utc_now(),
        )
        db.add(user_record)
        write_audit_event(
            db,
            actor="oidc",
            action="user.oidc.provisioned",
            entity_type="user",
            entity_id=user_record.id,
            market_id=state_record.market_id,
            details={
                "provider": provider_key,
                "email": userinfo.email,
                "market_ids": market_ids,
                "role": user_record.role,
            },
        )
    else:
        if not user_record.active:
            write_audit_event(
                db,
                actor=userinfo.email,
                action="auth.oidc.denied",
                entity_type="user",
                entity_id=user_record.id,
                market_id=state_record.market_id,
                details={"provider": provider_key, "reason": "inactive_user"},
                commit=True,
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="SSO user is inactive")
        if user_record.external_subject and (
            user_record.external_identity_provider != provider_key
            or user_record.external_subject != userinfo.subject
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="SSO identity is linked to another subject")
        if not user_record.external_subject:
            user_record.external_identity_provider = provider_key
            user_record.external_subject = userinfo.subject
            write_audit_event(
                db,
                actor="oidc",
                action="user.oidc.linked",
                entity_type="user",
                entity_id=user_record.id,
                market_id=state_record.market_id,
                details={"provider": provider_key, "email": userinfo.email},
            )

    if state_record.market_id not in user_record.market_ids:
        write_audit_event(
            db,
            actor=user_record.id,
            action="auth.market.denied",
            entity_type="market",
            entity_id=state_record.market_id,
            market_id=state_record.market_id,
            details={
                "email": user_record.email,
                "assigned_market_ids": user_record.market_ids,
                "auth_method": "oidc",
            },
            commit=True,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not assigned to this market")

    write_audit_event(
        db,
        actor=user_record.id,
        action="auth.oidc.login.success",
        entity_type="user",
        entity_id=user_record.id,
        market_id=state_record.market_id,
        details={"provider": provider_key, "email": user_record.email},
    )
    return _auth_session_for_user(
        db,
        user_record=user_record,
        market_record=market_record,
        auth_method="oidc",
        explicit_market_selection=True,
    )


@router.get("/me")
def me(context: RequestContext = Depends(require_context)) -> dict:
    return {"user": context.user, "market": context.market}


@router.get("/markets", response_model=list[Market])
def my_markets(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[Market]:
    return _assigned_markets(db, context.user.market_ids)


@router.get("/users", response_model=list[User])
def list_users(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[User]:
    require_supervisor(context)
    records = db.scalars(select(UserRecord)).all()
    return [
        user_from_record(record)
        for record in records
        if context.market_id in record.market_ids or context.user.role == UserRole.admin
    ]


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(
    request: CreateUserRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> User:
    require_admin(context)
    duplicate = db.scalar(select(UserRecord).where(UserRecord.email == str(request.email).lower()))
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="User already exists")
    market_ids, default_market_id = _normalize_market_assignment(
        db,
        request.market_ids or [context.market_id],
        request.default_market_id,
    )
    validate_password_strength(request.temporary_password, user_email=str(request.email).lower())
    record = UserRecord(
        id=f"user_{uuid4().hex}",
        name=request.name.strip(),
        email=str(request.email).lower(),
        password_hash=hash_password(request.temporary_password),
        password_reset_required=True,
        role=request.role.value,
        default_market_id=default_market_id,
        market_ids=market_ids,
        active=request.active,
        permission_profile=request.permission_profile.value,
        permission_overrides=request.permission_overrides.model_dump(mode="json"),
    )
    db.add(record)
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.create",
        entity_type="user",
        entity_id=record.id,
        market_id=context.market_id,
        details={
            "email": record.email,
            "role": record.role,
            "market_ids": market_ids,
            "permission_profile": record.permission_profile,
            "temporary_password_set": True,
        },
    )
    db.commit()
    db.refresh(record)
    return user_from_record(record)


@router.patch("/users/{user_id}", response_model=User)
def update_user(
    user_id: str,
    request: UpdateUserRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> User:
    require_admin(context)
    record = db.get(UserRecord, user_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    patch = request.model_dump(exclude_unset=True, mode="json")
    audit_details = {key: value for key, value in patch.items() if key != "temporary_password"}
    if request.active is False and record.id == context.user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself")
    if request.email is not None:
        duplicate = db.scalar(
            select(UserRecord).where(
                UserRecord.email == str(request.email).lower(),
                UserRecord.id != user_id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="User already exists")
        record.email = str(request.email).lower()
    if request.temporary_password is not None:
        validate_password_strength(request.temporary_password, user_email=record.email)
        record.password_hash = hash_password(request.temporary_password)
        record.password_reset_required = True
        record.mfa_enabled = False
        record.mfa_pending_secret = None
        record.mfa_secret = None
        record.mfa_confirmed_at = None
        record.mfa_last_verified_at = None
        audit_details["temporary_password_set"] = True
        audit_details["mfa_reset"] = True
    if request.name is not None:
        record.name = request.name.strip()
    if request.role is not None:
        record.role = request.role.value
    if request.permission_profile is not None:
        record.permission_profile = request.permission_profile.value
    if request.permission_overrides is not None:
        record.permission_overrides = request.permission_overrides.model_dump(mode="json")
    if request.market_ids is not None or request.default_market_id is not None:
        market_ids, default_market_id = _normalize_market_assignment(
            db,
            request.market_ids if request.market_ids is not None else record.market_ids,
            request.default_market_id if request.default_market_id is not None else record.default_market_id,
        )
        record.market_ids = market_ids
        record.default_market_id = default_market_id
    if request.active is not None:
        record.active = request.active
    if record.id == context.user.id and Permission.setup_manage not in effective_permissions_for(
        record.role,
        record.permission_profile,
        record.permission_overrides,
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own setup access",
        )
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.update",
        entity_type="user",
        entity_id=record.id,
        market_id=context.market_id,
        details=audit_details,
    )
    db.commit()
    db.refresh(record)
    return user_from_record(record)


@router.post("/mfa/enroll", response_model=MfaEnrollmentResponse)
def enroll_mfa(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> MfaEnrollmentResponse:
    if context.user.role == UserRole.service_account:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Service accounts cannot enroll MFA")
    record = db.get(UserRecord, context.user.id)
    if record is None or not record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    secret = generate_totp_secret()
    record.mfa_pending_secret = secret
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.mfa.enroll.started",
        entity_type="user",
        entity_id=context.user.id,
        market_id=context.market_id,
        details={"enabled": record.mfa_enabled},
    )
    db.commit()
    return MfaEnrollmentResponse(
        secret=secret,
        otpauth_uri=otpauth_uri(
            issuer="Omni Ticket",
            account_name=record.email,
            secret=secret,
        ),
    )


@router.post("/mfa/confirm", response_model=User)
def confirm_mfa(
    request: ConfirmMfaRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> User:
    record = db.get(UserRecord, context.user.id)
    if record is None or not record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if not record.mfa_pending_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No pending MFA enrollment")
    if not verify_totp_code(record.mfa_pending_secret, request.code):
        write_audit_event(
            db,
            actor=context.user.id,
            action="user.mfa.confirm.denied",
            entity_type="user",
            entity_id=context.user.id,
            market_id=context.market_id,
            details={"reason": "invalid_mfa_code"},
            commit=True,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    now = utc_now()
    record.mfa_secret = record.mfa_pending_secret
    record.mfa_pending_secret = None
    record.mfa_enabled = True
    record.mfa_confirmed_at = now
    record.mfa_last_verified_at = now
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.mfa.enabled",
        entity_type="user",
        entity_id=context.user.id,
        market_id=context.market_id,
        details={"enabled": True},
    )
    db.commit()
    db.refresh(record)
    return user_from_record(record)


@router.post("/mfa/disable", response_model=User)
def disable_mfa(
    request: DisableMfaRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> User:
    record = db.get(UserRecord, context.user.id)
    if record is None or not record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(request.current_password, record.password_hash):
        write_audit_event(
            db,
            actor=context.user.id,
            action="user.mfa.disable.denied",
            entity_type="user",
            entity_id=context.user.id,
            market_id=context.market_id,
            details={"reason": "current_password_invalid"},
            commit=True,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    if record.mfa_enabled:
        if not request.code or not record.mfa_secret or not verify_totp_code(
            record.mfa_secret,
            request.code,
        ):
            write_audit_event(
                db,
                actor=context.user.id,
                action="user.mfa.disable.denied",
                entity_type="user",
                entity_id=context.user.id,
                market_id=context.market_id,
                details={"reason": "invalid_mfa_code"},
                commit=True,
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    record.mfa_enabled = False
    record.mfa_pending_secret = None
    record.mfa_secret = None
    record.mfa_confirmed_at = None
    record.mfa_last_verified_at = None
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.mfa.disabled",
        entity_type="user",
        entity_id=context.user.id,
        market_id=context.market_id,
        details={"enabled": False},
    )
    db.commit()
    db.refresh(record)
    return user_from_record(record)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: ChangePasswordRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> None:
    record = db.get(UserRecord, context.user.id)
    if record is None or not record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(request.current_password, record.password_hash):
        write_audit_event(
            db,
            actor=context.user.id,
            action="user.password.change.denied",
            entity_type="user",
            entity_id=context.user.id,
            market_id=context.market_id,
            details={"reason": "current_password_invalid"},
            commit=True,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    validate_password_strength(request.new_password, user_email=record.email)
    record.password_hash = hash_password(request.new_password)
    record.password_reset_required = False
    write_audit_event(
        db,
        actor=context.user.id,
        action="user.password.change",
        entity_type="user",
        entity_id=context.user.id,
        market_id=context.market_id,
        details={"reset_required_cleared": True},
    )
    db.commit()
