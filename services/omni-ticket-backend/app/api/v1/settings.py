from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_store
from app.api.v1.security import RequestContext, require_context
from app.core.store import InMemoryStore
from app.db.models import AuditEventRecord
from app.db.session import get_db
from app.db.settings import get_or_create_workspace_settings, workspace_settings_from_record
from app.models.domain import WorkspaceSettings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=WorkspaceSettings)
def read_settings(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> WorkspaceSettings:
    record = get_or_create_workspace_settings(db, context.market)
    db.commit()
    return workspace_settings_from_record(record)


@router.patch("", response_model=WorkspaceSettings)
def update_settings(
    patch: dict,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WorkspaceSettings:
    record = get_or_create_workspace_settings(db, context.market)
    allowed = WorkspaceSettings.model_fields.keys()
    for key, value in patch.items():
        if key in allowed and key != "market_id":
            setattr(record, key, value)
    settings = workspace_settings_from_record(record)
    state.settings_by_market[context.market_id] = settings
    state.audit_event(
        actor=context.user.email,
        action="settings.update",
        entity_type="workspace_settings",
        entity_id=context.market_id,
        market_id=context.market_id,
        details=patch,
    )
    db.add(
        AuditEventRecord(
            id=f"audit_{uuid4().hex}",
            actor=str(context.user.email),
            action="settings.update",
            entity_type="workspace_settings",
            entity_id=context.market_id,
            market_id=context.market_id,
            details=patch,
        )
    )
    db.commit()
    return settings


@router.patch("/ai-work-queue-automation", response_model=WorkspaceSettings)
def update_ai_work_queue_automation(
    patch: dict,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> WorkspaceSettings:
    record = get_or_create_workspace_settings(db, context.market)
    enabled = patch.get("enabled")
    if enabled is not None:
        record.ai_work_queue_automation_enabled = bool(enabled)
        settings = workspace_settings_from_record(record)
        state.settings_by_market[context.market_id] = settings
        state.audit_event(
            actor=context.user.email,
            action="settings.ai_work_queue_automation.update",
            entity_type="workspace_settings",
            entity_id=context.market_id,
            market_id=context.market_id,
            details={"enabled": bool(enabled)},
        )
        db.add(
            AuditEventRecord(
                id=f"audit_{uuid4().hex}",
                actor=str(context.user.email),
                action="settings.ai_work_queue_automation.update",
                entity_type="workspace_settings",
                entity_id=context.market_id,
                market_id=context.market_id,
                details={"enabled": bool(enabled)},
            )
        )
    db.commit()
    return workspace_settings_from_record(record)
