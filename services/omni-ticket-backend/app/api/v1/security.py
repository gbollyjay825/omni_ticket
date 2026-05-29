from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.mappers import market_from_record, user_from_record
from app.db.models import MarketRecord, SessionRecord, UserRecord
from app.db.session import get_db
from app.models.domain import Market, User


@dataclass(frozen=True)
class RequestContext:
    user: User
    market: Market

    @property
    def market_id(self) -> str:
        return self.market.id


def require_context(
    authorization: str | None = Header(default=None),
    market_header: str | None = Header(default=None, alias="X-Omni-Market"),
    db: Session = Depends(get_db),
) -> RequestContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    session_record = db.get(SessionRecord, token)
    if session_record is None or session_record.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if session_record.expires_at and session_record.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_record = db.get(UserRecord, session_record.user_id)
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
    return RequestContext(user=user, market=market)
