from sqlalchemy.orm import Session

from app.db.models import WorkspaceSettingsRecord
from app.models.domain import Market, WorkspaceSettings


def workspace_settings_from_record(record: WorkspaceSettingsRecord) -> WorkspaceSettings:
    return WorkspaceSettings(
        market_id=record.market_id,
        ai_work_queue_automation_enabled=record.ai_work_queue_automation_enabled,
        ai_can_send_customer_messages=record.ai_can_send_customer_messages,
        default_timezone=record.default_timezone,
        business_hours=record.business_hours,
        public_brand_name=record.public_brand_name,
    )


def get_or_create_workspace_settings(db: Session, market: Market) -> WorkspaceSettingsRecord:
    record = db.get(WorkspaceSettingsRecord, market.id)
    if record is not None:
        return record
    record = WorkspaceSettingsRecord(
        market_id=market.id,
        default_timezone=market.timezone,
        public_brand_name=f"Omni Ticket {market.code}",
    )
    db.add(record)
    db.flush()
    return record
