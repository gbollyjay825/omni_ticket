from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record, production_account_reference_from_record
from app.db.models import AuditEventRecord, MarketRecord, ProductionAccountReferenceRecord
from app.models.domain import (
    CreateProductionAccountReferenceRequest,
    ProductionAccountReference,
    UpdateProductionAccountReferenceRequest,
    utc_now,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _clean_lines(value: str | None) -> str:
    return (value or "").strip()


def _clean_callbacks(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(_clean(value) for value in (values or []) if _clean(value)))


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_id: str,
    market_id: str,
    details: dict,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type="production_account_reference",
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class ProductionAccountReferenceRepository:
    def _market_or_404(self, db: Session, market_id: str) -> MarketRecord:
        market = db.get(MarketRecord, market_id)
        if market is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
        return market

    def _record_or_404(
        self,
        db: Session,
        reference_id: str,
        market_id: str,
    ) -> ProductionAccountReferenceRecord:
        record = db.get(ProductionAccountReferenceRecord, reference_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Production account reference not found")
        return record

    def list_references(
        self,
        db: Session,
        *,
        market_id: str,
        status_filter: str | None = None,
        provider: str | None = None,
    ) -> list[ProductionAccountReference]:
        query = select(ProductionAccountReferenceRecord).where(
            ProductionAccountReferenceRecord.market_id == market_id
        )
        if status_filter:
            query = query.where(ProductionAccountReferenceRecord.status == status_filter)
        if provider:
            query = query.where(ProductionAccountReferenceRecord.provider == _clean(provider).lower())
        records = db.scalars(
            query.order_by(
                ProductionAccountReferenceRecord.updated_at.desc(),
                ProductionAccountReferenceRecord.account_name.asc(),
            )
        ).all()
        return [production_account_reference_from_record(record) for record in records]

    def create_reference(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        request: CreateProductionAccountReferenceRequest,
        actor: str,
    ) -> ProductionAccountReference:
        self._market_or_404(db, market_id)
        provider = _clean(request.provider).lower()
        account_name = _clean(request.account_name)
        existing = db.scalar(
            select(ProductionAccountReferenceRecord).where(
                ProductionAccountReferenceRecord.market_id == market_id,
                ProductionAccountReferenceRecord.provider == provider,
                ProductionAccountReferenceRecord.account_name == account_name,
            )
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Production account reference already exists for this provider and name",
            )
        record = ProductionAccountReferenceRecord(
            id=_new_id("prodacct"),
            market_id=market_id,
            provider=provider,
            area=_clean(request.area),
            account_name=account_name,
            account_identifier=_clean(request.account_identifier),
            status=request.status.value,
            owner_email=str(request.owner_email or ""),
            credential_reference=_clean(request.credential_reference),
            docs_reference=_clean(request.docs_reference),
            callback_urls=_clean_callbacks(request.callback_urls),
            notes=_clean_lines(request.notes),
            created_by=actor,
            updated_by=actor,
        )
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="production_account_reference.create",
            entity_id=record.id,
            market_id=market_id,
            details={
                "provider": record.provider,
                "account_name": record.account_name,
                "status": record.status,
                "credential_reference": record.credential_reference,
            },
        )
        db.commit()
        db.refresh(record)
        return production_account_reference_from_record(record)

    def update_reference(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        reference_id: str,
        market_id: str,
        request: UpdateProductionAccountReferenceRequest,
        actor: str,
    ) -> ProductionAccountReference:
        record = self._record_or_404(db, reference_id, market_id)
        patch = request.model_dump(exclude_unset=True, mode="json")
        if "provider" in patch and patch["provider"] is not None:
            record.provider = _clean(str(patch["provider"])).lower()
        if "area" in patch and patch["area"] is not None:
            record.area = _clean(str(patch["area"]))
        if "account_name" in patch and patch["account_name"] is not None:
            record.account_name = _clean(str(patch["account_name"]))
        if "account_identifier" in patch and patch["account_identifier"] is not None:
            record.account_identifier = _clean(str(patch["account_identifier"]))
        if "status" in patch and patch["status"] is not None:
            record.status = str(patch["status"])
        if "owner_email" in patch:
            record.owner_email = str(patch["owner_email"] or "")
        if "credential_reference" in patch and patch["credential_reference"] is not None:
            record.credential_reference = _clean(str(patch["credential_reference"]))
        if "docs_reference" in patch and patch["docs_reference"] is not None:
            record.docs_reference = _clean(str(patch["docs_reference"]))
        if "callback_urls" in patch and patch["callback_urls"] is not None:
            record.callback_urls = _clean_callbacks(patch["callback_urls"])
        if "notes" in patch and patch["notes"] is not None:
            record.notes = _clean_lines(str(patch["notes"]))
        record.updated_by = actor
        record.updated_at = utc_now()
        _audit(
            db,
            state,
            actor=actor,
            action="production_account_reference.update",
            entity_id=record.id,
            market_id=market_id,
            details={
                "provider": record.provider,
                "account_name": record.account_name,
                "status": record.status,
                "credential_reference": record.credential_reference,
            },
        )
        db.commit()
        db.refresh(record)
        return production_account_reference_from_record(record)

    def docs_snippet(
        self,
        db: Session,
        *,
        market_id: str,
    ) -> str:
        references = self.list_references(db, market_id=market_id)
        if not references:
            return "No production account references have been recorded yet."
        lines = [
            "| Provider | Account | Status | Credential Reference | Docs Reference | Owner |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for reference in references:
            lines.append(
                " | ".join(
                    [
                        f"| {reference.provider}",
                        reference.account_name,
                        reference.status.value,
                        reference.credential_reference or "Pending",
                        reference.docs_reference or "Pending",
                        str(reference.owner_email or "Unassigned"),
                    ]
                )
                + " |"
            )
        return "\n".join(lines)


production_account_reference_repository = ProductionAccountReferenceRepository()
