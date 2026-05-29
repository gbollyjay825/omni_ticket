from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import parse_session_token
from app.core.observability import current_request_id
from app.db.audit import write_audit_event
from app.db.mappers import market_from_record, user_from_record
from app.db.models import MarketRecord, SessionRecord, UserRecord
from app.db.session import get_db
from app.models.domain import Market, User


@dataclass(frozen=True)
class RequestContext:
    user: User
    market: Market
    request_id: str | None = None

    @property
    def market_id(self) -> str:
        return self.market.id


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    normalized = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return normalized <= now


def _deny(
    db: Session,
    *,
    status_code: int,
    detail: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict,
) -> NoReturn:
    write_audit_event(
        db,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details={"detail": detail, **details},
        commit=True,
    )
    raise HTTPException(status_code, detail=detail)


def require_context(
    authorization: str | None = Header(default=None),
    market_header: str | None = Header(default=None, alias="X-Omni-Market"),
    db: Session = Depends(get_db),
) -> RequestContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            actor="anonymous",
            action="auth.required",
            entity_type="request",
            entity_id="protected-api",
            market_id=None,
            details={"reason": "missing_bearer_token"},
        )
    token = authorization.split(" ", 1)[1].strip()
    session_record = db.get(SessionRecord, token)
    now = datetime.now(timezone.utc)
    if session_record is not None and session_record.revoked_at is not None:
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
            actor=session_record.user_id,
            action="auth.session.denied",
            entity_type="auth_session",
            entity_id=session_record.user_id,
            market_id=None,
            details={"reason": "revoked_session"},
        )
    if session_record is not None and _is_expired(session_record.expires_at, now):
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
            actor=session_record.user_id,
            action="auth.session.denied",
            entity_type="auth_session",
            entity_id=session_record.user_id,
            market_id=None,
            details={"reason": "expired_session"},
        )

    token_payload = parse_session_token(token) if session_record is None else None
    if session_record is None and token_payload is None:
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
            actor="anonymous",
            action="auth.session.denied",
            entity_type="auth_session",
            entity_id="provided-token",
            market_id=None,
            details={"reason": "invalid_token"},
        )
    if token_payload is not None and _is_expired(token_payload.expires_at, now):
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
            actor=token_payload.user_id,
            action="auth.session.denied",
            entity_type="auth_session",
            entity_id=token_payload.user_id,
            market_id=None,
            details={"reason": "expired_signed_token"},
        )

    if session_record is not None:
        user_id = session_record.user_id
    else:
        assert token_payload is not None
        user_id = token_payload.user_id
    user_record = db.get(UserRecord, user_id)
    if user_record is None:
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
            actor=user_id,
            action="auth.session.denied",
            entity_type="user",
            entity_id=user_id,
            market_id=None,
            details={"reason": "missing_user"},
        )
    user = user_from_record(user_record)
    if not user.active:
        _deny(
            db,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
            actor=user.id,
            action="auth.session.denied",
            entity_type="user",
            entity_id=user.id,
            market_id=user.default_market_id,
            details={"reason": "inactive_user"},
        )

    market_id = market_header or user.default_market_id
    if market_id not in user.market_ids:
        _deny(
            db,
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to this market",
            actor=user.id,
            action="auth.market.denied",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details={"assigned_market_ids": user.market_ids},
        )

    market_record = db.scalar(select(MarketRecord).where(MarketRecord.id == market_id))
    if market_record is None:
        _deny(
            db,
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found",
            actor=user.id,
            action="auth.market.denied",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details={"reason": "market_not_found"},
        )
    market = market_from_record(market_record)
    if not market.active:
        _deny(
            db,
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found",
            actor=user.id,
            action="auth.market.denied",
            entity_type="market",
            entity_id=market_id,
            market_id=market_id,
            details={"reason": "inactive_market"},
        )
    return RequestContext(user=user, market=market, request_id=current_request_id())
