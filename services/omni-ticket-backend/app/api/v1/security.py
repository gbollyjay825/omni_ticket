from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import parse_session_token
from app.core.observability import current_request_id
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


def require_context(
    authorization: str | None = Header(default=None),
    market_header: str | None = Header(default=None, alias="X-Omni-Market"),
    db: Session = Depends(get_db),
) -> RequestContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    session_record = db.get(SessionRecord, token)
    now = datetime.now(timezone.utc)
    if session_record is not None and session_record.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if session_record is not None and _is_expired(session_record.expires_at, now):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    token_payload = parse_session_token(token) if session_record is None else None
    if session_record is None and token_payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if token_payload is not None and _is_expired(token_payload.expires_at, now):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if session_record is not None:
        user_id = session_record.user_id
    else:
        assert token_payload is not None
        user_id = token_payload.user_id
    user_record = db.get(UserRecord, user_id)
    if user_record is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = user_from_record(user_record)
    if not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    market_id = market_header or user.default_market_id
    if market_id not in user.market_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not assigned to this market")

    market_record = db.scalar(select(MarketRecord).where(MarketRecord.id == market_id))
    if market_record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
    market = market_from_record(market_record)
    if not market.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
    return RequestContext(user=user, market=market, request_id=current_request_id())
