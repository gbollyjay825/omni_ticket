from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.observability import current_request_id
from app.db.models import AuditEventRecord


def write_audit_event(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str | None,
    details: dict,
    commit: bool = False,
) -> AuditEventRecord:
    enriched_details = dict(details)
    request_id = current_request_id()
    if request_id and "request_id" not in enriched_details:
        enriched_details["request_id"] = request_id
    record = AuditEventRecord(
        id=f"audit_{uuid4().hex}",
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=enriched_details,
    )
    db.add(record)
    if commit:
        db.commit()
    else:
        db.flush()
    return record
