from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.audit import write_audit_event
from app.db.models import CustomerRecord, SegmentRecord
from app.models.segments import (
    CreateSegmentRequest,
    SegmentResponse,
    SegmentRules,
    UpdateSegmentRequest,
)


def _matches(customer: CustomerRecord, rules: SegmentRules) -> bool:
    if rules.include_all:
        return True
    tags = {str(tag).strip().lower() for tag in customer.tags or []}
    preferred_channels = {
        str(channel).strip().lower() for channel in customer.preferred_channels or []
    }
    if rules.tags_any and not tags.intersection(rules.tags_any):
        return False
    if rules.tags_all and not set(rules.tags_all).issubset(tags):
        return False
    if rules.preferred_channels_any and not preferred_channels.intersection(
        rules.preferred_channels_any
    ):
        return False
    if rules.sentiments and customer.sentiment not in rules.sentiments:
        return False
    if rules.company_ids and customer.company_id not in rules.company_ids:
        return False
    return True


def _response(db: Session, record: SegmentRecord) -> SegmentResponse:
    rules = SegmentRules.model_validate(record.rules)
    customers = db.scalars(
        select(CustomerRecord).where(CustomerRecord.market_id == record.market_id)
    ).all()
    return SegmentResponse(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        description=record.description,
        rules=rules,
        active=record.active,
        member_count=sum(1 for customer in customers if _matches(customer, rules)),
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SegmentService:
    def list_segments(self, db: Session, *, market_id: str) -> list[SegmentResponse]:
        records = db.scalars(
            select(SegmentRecord)
            .where(SegmentRecord.market_id == market_id)
            .order_by(SegmentRecord.updated_at.desc())
        ).all()
        return [_response(db, record) for record in records]

    def create(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        request: CreateSegmentRequest,
    ) -> SegmentResponse:
        record = SegmentRecord(
            id=f"segment_{uuid4().hex}",
            market_id=market_id,
            name=request.name.strip(),
            description=request.description.strip(),
            rules=request.rules.model_dump(),
            active=True,
            created_by=actor,
        )
        db.add(record)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A segment with this name already exists in the active market",
            ) from exc
        write_audit_event(
            db,
            actor=actor,
            action="segment.create",
            entity_type="segment",
            entity_id=record.id,
            market_id=market_id,
            details={"rules": request.rules.model_dump()},
        )
        db.commit()
        db.refresh(record)
        return _response(db, record)

    def update(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        segment_id: str,
        request: UpdateSegmentRequest,
    ) -> SegmentResponse:
        record = db.get(SegmentRecord, segment_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Segment not found")
        patch = request.model_dump(exclude_unset=True)
        if "rules" in patch and request.rules is not None:
            patch["rules"] = request.rules.model_dump()
        for key, value in patch.items():
            if key in {"name", "description"} and isinstance(value, str):
                value = value.strip()
            setattr(record, key, value)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A segment with this name already exists in the active market",
            ) from exc
        write_audit_event(
            db,
            actor=actor,
            action="segment.update",
            entity_type="segment",
            entity_id=record.id,
            market_id=market_id,
            details={"changed_fields": sorted(patch)},
        )
        db.commit()
        db.refresh(record)
        return _response(db, record)


segment_service = SegmentService()
