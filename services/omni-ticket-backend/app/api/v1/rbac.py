from fastapi import HTTPException, status

from app.api.v1.security import RequestContext
from app.core.permissions import has_permission
from app.models.domain import Permission


def require_operator(context: RequestContext) -> None:
    if not has_permission(context.user, Permission.operations_write):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Operator access required")


def require_supervisor(context: RequestContext) -> None:
    if not has_permission(context.user, Permission.supervisor_control):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Supervisor access required")


def require_audit_reader(context: RequestContext) -> None:
    if not has_permission(context.user, Permission.audit_read):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Audit access required")


def require_admin(context: RequestContext) -> None:
    if not has_permission(context.user, Permission.setup_manage):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
