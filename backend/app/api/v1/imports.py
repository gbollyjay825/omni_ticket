from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_admin
from app.api.v1.security import RequestContext, require_context
from app.db.audit import write_audit_event
from app.db.imports import import_repository
from app.db.session import get_db
from app.models.domain import utc_now

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportRunResponse(BaseModel):
    id: str
    market_id: str
    provider: str
    mode: str
    status: str
    dry_run: bool
    started_by: str
    started_at: datetime
    finished_at: datetime | None
    source_cursor: dict[str, Any] = Field(default_factory=dict)
    next_cursor: dict[str, Any] = Field(default_factory=dict)
    statistics: dict[str, int | dict[str, int]] = Field(default_factory=dict)
    error_summary: str
    created_at: datetime
    updated_at: datetime


class ImportCursorResponse(BaseModel):
    id: str
    market_id: str
    provider: str
    resource: str
    cursor: dict[str, Any] = Field(default_factory=dict)
    checkpoint_at: datetime


class ImportReconciliationResponse(BaseModel):
    market_id: str
    providers: dict[str, dict[str, int]] = Field(default_factory=dict)
    source_manifests: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    provider_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    readiness: dict[str, Any] = Field(default_factory=dict)
    cutover: dict[str, Any] | None = None


class ReconciliationEntityRequest(BaseModel):
    entity_type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    source_count: int = Field(ge=0)
    source_checksum: str = Field(default="", max_length=128)
    sample_size: int = Field(default=0, ge=0)
    sample_failures: int = Field(default=0, ge=0)
    missing_attachments: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=2000)


class ReconciliationManifestRequest(BaseModel):
    provider: Literal["freshdesk", "freshchat"]
    source_snapshot_at: datetime
    entities: list[ReconciliationEntityRequest] = Field(min_length=1, max_length=100)


class CutoverDecisionRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


@router.get("/runs", response_model=list[ImportRunResponse])
def list_import_runs(
    provider: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ImportRunResponse]:
    require_admin(context)
    return [
        ImportRunResponse.model_validate(item)
        for item in import_repository.list_runs(
            db,
            market_id=context.market_id,
            provider=provider,
            limit=limit,
        )
    ]


@router.get("/runs/{run_id}", response_model=ImportRunResponse)
def read_import_run(
    run_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ImportRunResponse:
    require_admin(context)
    run = import_repository.read_run(db, market_id=context.market_id, run_id=run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Import run not found")
    return ImportRunResponse.model_validate(run)


@router.get("/cursors", response_model=list[ImportCursorResponse])
def list_import_cursors(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[ImportCursorResponse]:
    require_admin(context)
    return [
        ImportCursorResponse.model_validate(item)
        for item in import_repository.list_cursors(db, market_id=context.market_id)
    ]


@router.get("/reconciliation", response_model=ImportReconciliationResponse)
def read_import_reconciliation(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ImportReconciliationResponse:
    require_admin(context)
    return ImportReconciliationResponse.model_validate(
        import_repository.reconciliation(db, market_id=context.market_id)
    )


@router.post(
    "/reconciliation/manifests",
    response_model=ImportReconciliationResponse,
)
def record_import_reconciliation_manifest(
    request: ReconciliationManifestRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ImportReconciliationResponse:
    require_admin(context)
    if request.source_snapshot_at.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source snapshot timestamp must include a timezone.",
        )
    if request.source_snapshot_at > utc_now() + timedelta(minutes=5):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source snapshot timestamp cannot be in the future.",
        )
    entity_types = [entity.entity_type for entity in request.entities]
    if len(entity_types) != len(set(entity_types)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each entity type may appear only once in a source manifest.",
        )
    for entity in request.entities:
        if entity.sample_failures > entity.sample_size:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Sample failures cannot exceed sample size for {entity.entity_type}.",
            )
        import_repository.set_reconciliation_manifest(
            db,
            market_id=context.market_id,
            provider=request.provider,
            entity_type=entity.entity_type,
            source_count=entity.source_count,
            source_checksum=entity.source_checksum,
            sample_size=entity.sample_size,
            sample_failures=entity.sample_failures,
            missing_attachments=entity.missing_attachments,
            source_snapshot_at=request.source_snapshot_at,
            recorded_by=str(context.user.email),
            notes=entity.notes,
        )
    write_audit_event(
        db,
        actor=str(context.user.email),
        action="import.reconciliation.recorded",
        entity_type="import_reconciliation",
        entity_id=f"{context.market_id}:{request.provider}",
        market_id=context.market_id,
        details={
            "provider": request.provider,
            "source_snapshot_at": request.source_snapshot_at.isoformat(),
            "entity_types": entity_types,
        },
    )
    db.commit()
    return ImportReconciliationResponse.model_validate(
        import_repository.reconciliation(db, market_id=context.market_id)
    )


@router.post("/cutover/approve", response_model=ImportReconciliationResponse)
def approve_import_cutover(
    request: CutoverDecisionRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ImportReconciliationResponse:
    require_admin(context)
    try:
        decision, reconciliation = import_repository.approve_cutover(
            db,
            market_id=context.market_id,
            decided_by=str(context.user.email),
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    write_audit_event(
        db,
        actor=str(context.user.email),
        action="import.cutover.approved",
        entity_type="import_cutover",
        entity_id=decision.id,
        market_id=context.market_id,
        details={
            "rollback_until": decision.rollback_until.isoformat()
            if decision.rollback_until
            else None,
            "readiness_hash": decision.readiness_hash,
            "reason": request.reason,
        },
    )
    db.commit()
    reconciliation = import_repository.reconciliation(db, market_id=context.market_id)
    return ImportReconciliationResponse.model_validate(reconciliation)


@router.post("/cutover/revoke", response_model=ImportReconciliationResponse)
def revoke_import_cutover(
    request: CutoverDecisionRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> ImportReconciliationResponse:
    require_admin(context)
    try:
        decision = import_repository.revoke_cutover(
            db,
            market_id=context.market_id,
            decided_by=str(context.user.email),
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    write_audit_event(
        db,
        actor=str(context.user.email),
        action="import.cutover.revoked",
        entity_type="import_cutover",
        entity_id=decision.id,
        market_id=context.market_id,
        details={"reason": request.reason, "readiness_hash": decision.readiness_hash},
    )
    db.commit()
    return ImportReconciliationResponse.model_validate(
        import_repository.reconciliation(db, market_id=context.market_id)
    )
