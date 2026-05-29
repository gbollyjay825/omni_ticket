from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.v1.security import RequestContext, require_context
from app.db.bootstrap import table_names
from app.db.session import engine, get_db

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/readiness")
def readiness(
    _: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> dict:
    db.execute(text("select 1"))
    tables = table_names(engine)
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
                "audit_events",
            ]
        ),
        "tables": tables,
    }
