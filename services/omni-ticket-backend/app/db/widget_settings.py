from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record
from app.db.models import AuditEventRecord, MarketRecord, WidgetSettingsRecord
from app.models.domain import UpdateWidgetSettingsRequest, WidgetSettings, utc_now

_POSITIONS = {"bottom-right", "bottom-left"}


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


class WidgetSettingsRepository:
    def _record(self, db: Session, market_id: str) -> WidgetSettingsRecord | None:
        return db.get(WidgetSettingsRecord, market_id)

    def get_or_create(self, db: Session, *, market_id: str) -> WidgetSettingsRecord:
        record = self._record(db, market_id)
        if record is not None:
            return record
        if db.get(MarketRecord, market_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
        record = WidgetSettingsRecord(
            market_id=market_id,
            offline_message=(
                "We're offline right now — leave a message and we'll reply by email."
            ),
        )
        db.add(record)
        db.flush()
        return record

    def _to_domain(self, record: WidgetSettingsRecord) -> WidgetSettings:
        return WidgetSettings(
            market_id=record.market_id,
            enabled=record.enabled,
            display_name=record.display_name,
            welcome_message=record.welcome_message,
            primary_color=record.primary_color,
            launcher_label=record.launcher_label,
            position=record.position,
            auto_open_seconds=record.auto_open_seconds,
            collect_email=record.collect_email,
            offline_message=record.offline_message,
            updated_at=record.updated_at,
        )

    def read(self, db: Session, *, market_id: str) -> WidgetSettings:
        return self._to_domain(self.get_or_create(db, market_id=market_id))

    def update(
        self,
        db: Session,
        state: InMemoryStore,
        request: UpdateWidgetSettingsRequest,
        *,
        market_id: str,
        actor: str,
    ) -> WidgetSettings:
        record = self.get_or_create(db, market_id=market_id)
        patch = request.model_dump(exclude_unset=True)
        for key in ("enabled", "collect_email", "auto_open_seconds"):
            if key in patch and patch[key] is not None:
                setattr(record, key, patch[key])
        for key in ("display_name", "welcome_message", "launcher_label", "offline_message"):
            if key in patch and patch[key] is not None:
                setattr(record, key, _clean(str(patch[key])))
        if request.primary_color is not None:
            record.primary_color = request.primary_color.strip() or "#0b5eea"
        if request.position is not None:
            position = request.position.strip().lower()
            if position not in _POSITIONS:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Widget position must be bottom-right or bottom-left",
                )
            record.position = position
        record.updated_at = utc_now()
        audit = AuditEventRecord(
            id=f"audit_{uuid4().hex}",
            actor=actor,
            action="widget_settings.update",
            entity_type="widget_settings",
            entity_id=market_id,
            market_id=market_id,
            details=patch,
        )
        db.add(audit)
        db.flush()
        state.audit.append(audit_event_from_record(audit))
        db.commit()
        db.refresh(record)
        return self._to_domain(record)


widget_settings_repository = WidgetSettingsRepository()
