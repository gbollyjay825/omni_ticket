from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_admin, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.core.auth import create_session_token
from app.core.config import settings
from app.core.rate_limit import (
    RateLimitExceeded,
    client_identity,
    raise_rate_limit_exceeded,
)
from app.db.mappers import market_from_record, user_from_record
from app.db.models import AuditEventRecord, MarketRecord, SessionRecord, UserRecord
from app.db.rate_limit import database_rate_limiter
from app.db.session import get_db
from app.models.domain import (
    AuthSession,
    CreateUserRequest,
    LoginRequest,
    Market,
    UpdateUserRequest,
    User,
    UserRole,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_PASSWORD = "omni-demo"


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


def _audit_user_write(
    db: Session,
    *,
    actor: str,
    action: str,
    user_id: str,
    market_id: str | None,
    details: dict,
) -> None:
    db.add(
        AuditEventRecord(
            id=f"audit_{uuid4().hex}",
            actor=actor,
            action=action,
            entity_type="user",
            entity_id=user_id,
            market_id=market_id,
            details=details,
        )
    )


@router.post("/login", response_model=AuthSession)
def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AuthSession:
    try:
        database_rate_limiter.check(
            db,
            f"auth-login:{client_identity(http_request)}:{str(request.email).lower()}",
            limit=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise_rate_limit_exceeded(exc)

    user_record = db.scalar(
        select(UserRecord).where(UserRecord.email == str(request.email).lower())
    )
    if user_record is None or not user_record.active or request.password != DEMO_PASSWORD:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = user_from_record(user_record)
    market_id = request.market_id or user.default_market_id
    if market_id not in user.market_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not assigned to this market")

    market_record = db.get(MarketRecord, market_id)
    if market_record is None or not market_record.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")

    token, expires_at = create_session_token(user.id)
    db.add(SessionRecord(token=token, user_id=user.id, expires_at=expires_at))
    db.commit()

    return AuthSession(
        access_token=token,
        user=user,
        market=market_from_record(market_record),
        available_markets=_assigned_markets(db, user.market_ids),
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
    record = UserRecord(
        id=f"user_{uuid4().hex}",
        name=request.name.strip(),
        email=str(request.email).lower(),
        role=request.role.value,
        default_market_id=default_market_id,
        market_ids=market_ids,
        active=request.active,
    )
    db.add(record)
    _audit_user_write(
        db,
        actor=context.user.id,
        action="user.create",
        user_id=record.id,
        market_id=context.market_id,
        details={"email": record.email, "role": record.role, "market_ids": market_ids},
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
    if request.name is not None:
        record.name = request.name.strip()
    if request.role is not None:
        record.role = request.role.value
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
    _audit_user_write(
        db,
        actor=context.user.id,
        action="user.update",
        user_id=record.id,
        market_id=context.market_id,
        details=patch,
    )
    db.commit()
    db.refresh(record)
    return user_from_record(record)
