from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.v1.rbac import require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.db.bootstrap import table_names
from app.db.session import get_db, get_engine

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/readiness")
def readiness(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> dict:
    require_supervisor(context)
    db.execute(text("select 1"))
    tables = table_names(get_engine())
    return {
        "database": "ok",
        "table_count": len(tables),
        "required_tables_present": all(
            table in tables
            for table in [
                "markets",
                "users",
                "workspace_settings",
                "tickets",
                "customers",
                "connector_accounts",
                "connector_events",
                "attachments",
                "rate_limit_counters",
                "audit_events",
            ]
        ),
        "tables": tables,
    }
