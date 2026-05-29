from fastapi import HTTPException, status

from app.api.v1.security import RequestContext
from app.models.domain import UserRole


def require_operator(context: RequestContext) -> None:
    if context.user.role == UserRole.auditor:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Operator access required")


def require_supervisor(context: RequestContext) -> None:
    if context.user.role not in {UserRole.admin, UserRole.supervisor}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Supervisor access required")


def require_audit_reader(context: RequestContext) -> None:
    if context.user.role not in {UserRole.admin, UserRole.supervisor, UserRole.auditor}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Audit access required")


def require_admin(context: RequestContext) -> None:
    if context.user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
