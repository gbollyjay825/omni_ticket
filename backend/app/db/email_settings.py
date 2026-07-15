from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record
from app.db.models import (
    AuditEventRecord,
    ConnectorAccountRecord,
    EmailProviderSettingsRecord,
    MarketRecord,
)
from app.models.domain import (
    EmailProviderSettings,
    UpdateEmailProviderSettingsRequest,
    utc_now,
)


@dataclass(frozen=True)
class RuntimeEmailProviderSettings:
    inbound_enabled: bool
    inbound_host: str
    inbound_port: int
    inbound_username: str
    inbound_password: str | None
    inbound_mailbox: str
    inbound_use_ssl: bool
    inbound_mark_seen: bool
    outbound_enabled: bool
    outbound_host: str
    outbound_port: int
    outbound_username: str
    outbound_password: str | None
    outbound_from_email: str
    outbound_use_starttls: bool
    outbound_use_ssl: bool

    @property
    def inbound_password_configured(self) -> bool:
        return bool(self.inbound_password)

    @property
    def outbound_password_configured(self) -> bool:
        return bool(self.outbound_password)

    @property
    def inbound_live(self) -> bool:
        return bool(
            self.inbound_enabled
            and self.inbound_host
            and self.inbound_username
            and self.inbound_password
        )

    @property
    def outbound_live(self) -> bool:
        return bool(self.outbound_enabled and self.outbound_host)


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


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
        id=f"audit_{uuid4().hex}",
        actor=actor,
        action=action,
        entity_type="email_provider_settings",
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class EmailProviderSettingsRepository:
    def _market_or_404(self, db: Session, market_id: str) -> MarketRecord:
        market = db.get(MarketRecord, market_id)
        if market is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
        return market

    def _record(self, db: Session, market_id: str) -> EmailProviderSettingsRecord | None:
        return db.get(EmailProviderSettingsRecord, market_id)

    def get_or_create(
        self,
        db: Session,
        *,
        market_id: str,
    ) -> EmailProviderSettingsRecord:
        record = self._record(db, market_id)
        if record is not None:
            return record
        market = self._market_or_404(db, market_id)
        support_email = market.support_email or ""
        record = EmailProviderSettingsRecord(
            market_id=market_id,
            inbound_enabled=settings.email_imap_poll_enabled,
            inbound_host=settings.email_imap_host or "",
            inbound_port=settings.email_imap_port,
            inbound_username=settings.email_imap_username or support_email,
            inbound_password=None,
            inbound_mailbox=settings.email_imap_mailbox,
            inbound_use_ssl=settings.email_imap_use_ssl,
            inbound_mark_seen=settings.email_imap_mark_seen,
            outbound_enabled=bool(settings.email_smtp_host),
            outbound_host=settings.email_smtp_host or "",
            outbound_port=settings.email_smtp_port,
            outbound_username=settings.email_smtp_username or support_email,
            outbound_password=None,
            outbound_from_email=settings.email_smtp_from_email or support_email,
            outbound_use_starttls=settings.email_smtp_use_starttls,
            outbound_use_ssl=settings.email_smtp_use_ssl,
        )
        db.add(record)
        db.flush()
        return record

    def runtime_settings(
        self,
        db: Session | None = None,
        *,
        market_id: str | None = None,
    ) -> RuntimeEmailProviderSettings:
        record = self._record(db, market_id) if db is not None and market_id is not None else None
        return RuntimeEmailProviderSettings(
            inbound_enabled=(
                record.inbound_enabled if record is not None else settings.email_imap_poll_enabled
            ),
            inbound_host=(
                record.inbound_host if record is not None else settings.email_imap_host or ""
            ),
            inbound_port=(
                record.inbound_port if record is not None else settings.email_imap_port
            ),
            inbound_username=(
                record.inbound_username
                if record is not None
                else settings.email_imap_username or ""
            ),
            inbound_password=(
                record.inbound_password
                if record is not None and record.inbound_password
                else settings.email_imap_password
            ),
            inbound_mailbox=(
                record.inbound_mailbox if record is not None else settings.email_imap_mailbox
            ),
            inbound_use_ssl=(
                record.inbound_use_ssl if record is not None else settings.email_imap_use_ssl
            ),
            inbound_mark_seen=(
                record.inbound_mark_seen if record is not None else settings.email_imap_mark_seen
            ),
            outbound_enabled=(
                record.outbound_enabled if record is not None else bool(settings.email_smtp_host)
            ),
            outbound_host=(
                record.outbound_host if record is not None else settings.email_smtp_host or ""
            ),
            outbound_port=(
                record.outbound_port if record is not None else settings.email_smtp_port
            ),
            outbound_username=(
                record.outbound_username
                if record is not None
                else settings.email_smtp_username or ""
            ),
            outbound_password=(
                record.outbound_password
                if record is not None and record.outbound_password
                else settings.email_smtp_password
            ),
            outbound_from_email=(
                record.outbound_from_email
                if record is not None
                else settings.email_smtp_from_email or ""
            ),
            outbound_use_starttls=(
                record.outbound_use_starttls
                if record is not None
                else settings.email_smtp_use_starttls
            ),
            outbound_use_ssl=(
                record.outbound_use_ssl if record is not None else settings.email_smtp_use_ssl
            ),
        )

    def _to_domain(
        self,
        record: EmailProviderSettingsRecord,
        runtime: RuntimeEmailProviderSettings,
    ) -> EmailProviderSettings:
        return EmailProviderSettings(
            market_id=record.market_id,
            inbound_enabled=record.inbound_enabled,
            inbound_host=record.inbound_host,
            inbound_port=record.inbound_port,
            inbound_username=record.inbound_username,
            inbound_mailbox=record.inbound_mailbox,
            inbound_use_ssl=record.inbound_use_ssl,
            inbound_mark_seen=record.inbound_mark_seen,
            inbound_password_configured=runtime.inbound_password_configured,
            outbound_enabled=record.outbound_enabled,
            outbound_host=record.outbound_host,
            outbound_port=record.outbound_port,
            outbound_username=record.outbound_username,
            outbound_from_email=record.outbound_from_email,
            outbound_use_starttls=record.outbound_use_starttls,
            outbound_use_ssl=record.outbound_use_ssl,
            outbound_password_configured=runtime.outbound_password_configured,
            updated_at=record.updated_at,
        )

    def read(self, db: Session, *, market_id: str) -> EmailProviderSettings:
        record = self.get_or_create(db, market_id=market_id)
        return self._to_domain(record, self.runtime_settings(db, market_id=market_id))

    def _sync_connector_account(
        self,
        db: Session,
        *,
        market_id: str,
        runtime: RuntimeEmailProviderSettings,
    ) -> None:
        account = db.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == market_id,
                ConnectorAccountRecord.provider == "email",
            )
        )
        if account is None:
            return
        display_identifier = (
            runtime.outbound_from_email or runtime.outbound_username or runtime.inbound_username
        )
        if display_identifier:
            account.account_identifier = display_identifier
        account.intake_enabled = runtime.inbound_enabled
        account.outbound_enabled = runtime.outbound_enabled
        account.secret_configured = runtime.inbound_live or runtime.outbound_live
        account.credential_ref = (
            f"settings://email/{market_id}" if runtime.inbound_live or runtime.outbound_live else None
        )
        account.status = (
            "connected"
            if runtime.inbound_live or runtime.outbound_live
            else "pending_credentials"
        )
        account.last_error = None if runtime.inbound_live or runtime.outbound_live else account.last_error
        account.updated_at = utc_now()

    def update(
        self,
        db: Session,
        state: InMemoryStore,
        request: UpdateEmailProviderSettingsRequest,
        *,
        market_id: str,
        actor: str,
    ) -> EmailProviderSettings:
        record = self.get_or_create(db, market_id=market_id)
        patch = request.model_dump(exclude_unset=True)
        for key in (
            "inbound_enabled",
            "inbound_port",
            "inbound_use_ssl",
            "inbound_mark_seen",
            "outbound_enabled",
            "outbound_port",
            "outbound_use_starttls",
            "outbound_use_ssl",
        ):
            if key in patch:
                setattr(record, key, patch[key])
        for key in (
            "inbound_host",
            "inbound_username",
            "inbound_mailbox",
            "outbound_host",
            "outbound_username",
            "outbound_from_email",
        ):
            if key in patch and patch[key] is not None:
                setattr(record, key, _clean(str(patch[key])))
        if request.clear_inbound_password:
            record.inbound_password = None
        elif request.inbound_password:
            record.inbound_password = request.inbound_password.strip()
        if request.clear_outbound_password:
            record.outbound_password = None
        elif request.outbound_password:
            record.outbound_password = request.outbound_password.strip()
        if record.outbound_use_ssl and record.outbound_use_starttls:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SMTP SSL and STARTTLS cannot both be enabled.",
            )
        record.updated_at = utc_now()
        runtime = self.runtime_settings(db, market_id=market_id)
        self._sync_connector_account(db, market_id=market_id, runtime=runtime)
        audit_details = {
            key: value
            for key, value in patch.items()
            if key not in {"inbound_password", "outbound_password"}
        }
        if request.inbound_password:
            audit_details["inbound_password_configured"] = True
        if request.outbound_password:
            audit_details["outbound_password_configured"] = True
        _audit(
            db,
            state,
            actor=actor,
            action="email_provider_settings.update",
            entity_id=market_id,
            market_id=market_id,
            details=audit_details,
        )
        db.commit()
        db.refresh(record)
        return self._to_domain(record, self.runtime_settings(db, market_id=market_id))


email_provider_settings_repository = EmailProviderSettingsRepository()
