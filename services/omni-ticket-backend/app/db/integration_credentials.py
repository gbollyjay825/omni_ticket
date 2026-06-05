from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
    IntegrationCredentialSettingsRecord,
    MarketRecord,
)
from app.models.domain import (
    ChannelType,
    IntegrationCredentialSettings,
    OperationalAlertSeverity,
    UpdateIntegrationCredentialSettingsRequest,
    utc_now,
)


@dataclass(frozen=True)
class RuntimeIntegrationCredentials:
    market_id: str | None
    ai_provider: str
    anthropic_api_key: str | None
    anthropic_api_base_url: str
    anthropic_model: str
    alert_webhook_url: str
    alert_webhook_secret: str | None
    alert_delivery_min_severity: str
    sms_http_endpoint: str
    sms_http_auth_token: str | None
    sms_http_from: str
    sms_http_auth_header: str
    sms_http_auth_scheme: str
    sms_http_delivery_callback_url: str
    voice_http_endpoint: str
    voice_http_auth_token: str | None
    voice_http_from: str
    voice_http_auth_header: str
    voice_http_auth_scheme: str
    voice_http_status_callback_url: str
    whatsapp_cloud_api_base_url: str
    whatsapp_phone_number_id: str
    whatsapp_access_token: str | None
    whatsapp_preview_urls: bool
    facebook_graph_api_base_url: str
    facebook_page_id: str
    facebook_page_access_token: str | None
    facebook_messaging_type: str
    instagram_graph_api_base_url: str
    instagram_business_account_id: str
    instagram_access_token: str | None

    @property
    def anthropic_api_key_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def alert_webhook_secret_configured(self) -> bool:
        return bool(self.alert_webhook_secret)

    @property
    def sms_http_auth_token_configured(self) -> bool:
        return bool(self.sms_http_auth_token)

    @property
    def voice_http_auth_token_configured(self) -> bool:
        return bool(self.voice_http_auth_token)

    @property
    def whatsapp_access_token_configured(self) -> bool:
        return bool(self.whatsapp_access_token)

    @property
    def facebook_page_access_token_configured(self) -> bool:
        return bool(self.facebook_page_access_token)

    @property
    def instagram_access_token_configured(self) -> bool:
        return bool(self.instagram_access_token)

    @property
    def sms_live(self) -> bool:
        return bool(self.sms_http_endpoint and self.sms_http_auth_token and self.sms_http_from)

    @property
    def voice_live(self) -> bool:
        return bool(self.voice_http_endpoint and self.voice_http_auth_token and self.voice_http_from)

    @property
    def whatsapp_live(self) -> bool:
        return bool(
            self.whatsapp_cloud_api_base_url
            and self.whatsapp_phone_number_id
            and self.whatsapp_access_token
        )

    @property
    def facebook_live(self) -> bool:
        return bool(
            self.facebook_graph_api_base_url
            and self.facebook_page_id
            and self.facebook_page_access_token
        )

    @property
    def instagram_live(self) -> bool:
        return bool(
            self.instagram_graph_api_base_url
            and self.instagram_business_account_id
            and self.instagram_access_token
        )


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _clean_secret(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _read_anthropic_key_file() -> str | None:
    configured = settings.anthropic_api_key_file
    if not configured:
        return None
    path = Path(configured).expanduser()
    candidates = [path] if path.is_absolute() else [Path.cwd() / path]
    backend_root = Path(__file__).resolve().parents[2]
    if not path.is_absolute():
        candidates.append(backend_root / path)
        for parent in Path(__file__).resolve().parents:
            if (parent / "package.json").exists() and (parent / "services").exists():
                candidates.append(parent / path)
                break
    for candidate in candidates:
        try:
            raw = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in raw.splitlines():
            cleaned = line.strip().strip('"').strip("'")
            if not cleaned or cleaned.startswith("#"):
                continue
            if "=" in cleaned:
                key, value = cleaned.split("=", 1)
                if key.strip() not in {
                    "AI_Key",
                    "AI_KEY",
                    "ANTHROPIC_API_KEY",
                    "OMNI_ANTHROPIC_API_KEY",
                }:
                    continue
                cleaned = value.strip().strip('"').strip("'")
            return cleaned or None
    return None


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    market_id: str,
    details: dict,
) -> None:
    record = AuditEventRecord(
        id=f"audit_{uuid4().hex}",
        actor=actor,
        action="integration_credentials.update",
        entity_type="integration_credential_settings",
        entity_id=market_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class IntegrationCredentialSettingsRepository:
    def _market_or_404(self, db: Session, market_id: str) -> MarketRecord:
        market = db.get(MarketRecord, market_id)
        if market is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Market not found")
        return market

    def _record(
        self,
        db: Session,
        market_id: str,
    ) -> IntegrationCredentialSettingsRecord | None:
        return db.get(IntegrationCredentialSettingsRecord, market_id)

    def get_or_create(
        self,
        db: Session,
        *,
        market_id: str,
    ) -> IntegrationCredentialSettingsRecord:
        record = self._record(db, market_id)
        if record is not None:
            return record
        self._market_or_404(db, market_id)
        record = IntegrationCredentialSettingsRecord(
            market_id=market_id,
            ai_provider=settings.ai_provider,
            anthropic_api_key=None,
            anthropic_api_base_url=settings.anthropic_api_base_url,
            anthropic_model=settings.anthropic_model,
            alert_webhook_url=settings.alert_webhook_url or "",
            alert_webhook_secret=None,
            alert_delivery_min_severity=settings.alert_delivery_min_severity,
            sms_http_endpoint=settings.sms_http_endpoint or "",
            sms_http_auth_token=None,
            sms_http_from=settings.sms_http_from or "",
            sms_http_auth_header=settings.sms_http_auth_header,
            sms_http_auth_scheme=settings.sms_http_auth_scheme,
            sms_http_delivery_callback_url=settings.sms_http_delivery_callback_url or "",
            voice_http_endpoint=settings.voice_http_endpoint or "",
            voice_http_auth_token=None,
            voice_http_from=settings.voice_http_from or "",
            voice_http_auth_header=settings.voice_http_auth_header,
            voice_http_auth_scheme=settings.voice_http_auth_scheme,
            voice_http_status_callback_url=settings.voice_http_status_callback_url or "",
            whatsapp_cloud_api_base_url=settings.whatsapp_cloud_api_base_url,
            whatsapp_phone_number_id=settings.whatsapp_phone_number_id or "",
            whatsapp_access_token=None,
            whatsapp_preview_urls=settings.whatsapp_preview_urls,
            facebook_graph_api_base_url=settings.facebook_graph_api_base_url,
            facebook_page_id=settings.facebook_page_id or "",
            facebook_page_access_token=None,
            facebook_messaging_type=settings.facebook_messaging_type,
            instagram_graph_api_base_url=settings.instagram_graph_api_base_url,
            instagram_business_account_id=settings.instagram_business_account_id or "",
            instagram_access_token=None,
        )
        db.add(record)
        db.flush()
        return record

    def runtime_credentials(
        self,
        db: Session | None = None,
        *,
        market_id: str | None = None,
    ) -> RuntimeIntegrationCredentials:
        record = self._record(db, market_id) if db is not None and market_id is not None else None
        return RuntimeIntegrationCredentials(
            market_id=market_id,
            ai_provider=record.ai_provider if record is not None else settings.ai_provider,
            anthropic_api_key=(
                record.anthropic_api_key
                if record is not None and record.anthropic_api_key
                else settings.anthropic_api_key or _read_anthropic_key_file()
            ),
            anthropic_api_base_url=(
                record.anthropic_api_base_url
                if record is not None
                else settings.anthropic_api_base_url
            ),
            anthropic_model=(
                record.anthropic_model if record is not None else settings.anthropic_model
            ),
            alert_webhook_url=(
                record.alert_webhook_url if record is not None else settings.alert_webhook_url or ""
            ),
            alert_webhook_secret=(
                record.alert_webhook_secret
                if record is not None and record.alert_webhook_secret
                else settings.alert_webhook_secret
            ),
            alert_delivery_min_severity=(
                record.alert_delivery_min_severity
                if record is not None
                else settings.alert_delivery_min_severity
            ),
            sms_http_endpoint=(
                record.sms_http_endpoint if record is not None else settings.sms_http_endpoint or ""
            ),
            sms_http_auth_token=(
                record.sms_http_auth_token
                if record is not None and record.sms_http_auth_token
                else settings.sms_http_auth_token
            ),
            sms_http_from=(
                record.sms_http_from if record is not None else settings.sms_http_from or ""
            ),
            sms_http_auth_header=(
                record.sms_http_auth_header if record is not None else settings.sms_http_auth_header
            ),
            sms_http_auth_scheme=(
                record.sms_http_auth_scheme if record is not None else settings.sms_http_auth_scheme
            ),
            sms_http_delivery_callback_url=(
                record.sms_http_delivery_callback_url
                if record is not None
                else settings.sms_http_delivery_callback_url or ""
            ),
            voice_http_endpoint=(
                record.voice_http_endpoint if record is not None else settings.voice_http_endpoint or ""
            ),
            voice_http_auth_token=(
                record.voice_http_auth_token
                if record is not None and record.voice_http_auth_token
                else settings.voice_http_auth_token
            ),
            voice_http_from=(
                record.voice_http_from if record is not None else settings.voice_http_from or ""
            ),
            voice_http_auth_header=(
                record.voice_http_auth_header if record is not None else settings.voice_http_auth_header
            ),
            voice_http_auth_scheme=(
                record.voice_http_auth_scheme if record is not None else settings.voice_http_auth_scheme
            ),
            voice_http_status_callback_url=(
                record.voice_http_status_callback_url
                if record is not None
                else settings.voice_http_status_callback_url or ""
            ),
            whatsapp_cloud_api_base_url=(
                record.whatsapp_cloud_api_base_url
                if record is not None
                else settings.whatsapp_cloud_api_base_url
            ),
            whatsapp_phone_number_id=(
                record.whatsapp_phone_number_id
                if record is not None
                else settings.whatsapp_phone_number_id or ""
            ),
            whatsapp_access_token=(
                record.whatsapp_access_token
                if record is not None and record.whatsapp_access_token
                else settings.whatsapp_access_token
            ),
            whatsapp_preview_urls=(
                record.whatsapp_preview_urls if record is not None else settings.whatsapp_preview_urls
            ),
            facebook_graph_api_base_url=(
                record.facebook_graph_api_base_url
                if record is not None
                else settings.facebook_graph_api_base_url
            ),
            facebook_page_id=(
                record.facebook_page_id if record is not None else settings.facebook_page_id or ""
            ),
            facebook_page_access_token=(
                record.facebook_page_access_token
                if record is not None and record.facebook_page_access_token
                else settings.facebook_page_access_token
            ),
            facebook_messaging_type=(
                record.facebook_messaging_type
                if record is not None
                else settings.facebook_messaging_type
            ),
            instagram_graph_api_base_url=(
                record.instagram_graph_api_base_url
                if record is not None
                else settings.instagram_graph_api_base_url
            ),
            instagram_business_account_id=(
                record.instagram_business_account_id
                if record is not None
                else settings.instagram_business_account_id or ""
            ),
            instagram_access_token=(
                record.instagram_access_token
                if record is not None and record.instagram_access_token
                else settings.instagram_access_token
            ),
        )

    def runtime_credentials_for_market_id(
        self,
        market_id: str,
    ) -> RuntimeIntegrationCredentials:
        try:
            from app.db.session import SessionLocal

            with SessionLocal() as db:
                return self.runtime_credentials(db, market_id=market_id)
        except Exception:
            return self.runtime_credentials(market_id=market_id)

    def _to_domain(
        self,
        record: IntegrationCredentialSettingsRecord,
        runtime: RuntimeIntegrationCredentials,
    ) -> IntegrationCredentialSettings:
        return IntegrationCredentialSettings(
            market_id=record.market_id,
            ai_provider=record.ai_provider,
            anthropic_api_base_url=record.anthropic_api_base_url,
            anthropic_model=record.anthropic_model,
            anthropic_api_key_configured=runtime.anthropic_api_key_configured,
            alert_webhook_url=record.alert_webhook_url,
            alert_webhook_secret_configured=runtime.alert_webhook_secret_configured,
            alert_delivery_min_severity=OperationalAlertSeverity(
                record.alert_delivery_min_severity
            ),
            sms_http_endpoint=record.sms_http_endpoint,
            sms_http_from=record.sms_http_from,
            sms_http_auth_header=record.sms_http_auth_header,
            sms_http_auth_scheme=record.sms_http_auth_scheme,
            sms_http_delivery_callback_url=record.sms_http_delivery_callback_url,
            sms_http_auth_token_configured=runtime.sms_http_auth_token_configured,
            voice_http_endpoint=record.voice_http_endpoint,
            voice_http_from=record.voice_http_from,
            voice_http_auth_header=record.voice_http_auth_header,
            voice_http_auth_scheme=record.voice_http_auth_scheme,
            voice_http_status_callback_url=record.voice_http_status_callback_url,
            voice_http_auth_token_configured=runtime.voice_http_auth_token_configured,
            whatsapp_cloud_api_base_url=record.whatsapp_cloud_api_base_url,
            whatsapp_phone_number_id=record.whatsapp_phone_number_id,
            whatsapp_preview_urls=record.whatsapp_preview_urls,
            whatsapp_access_token_configured=runtime.whatsapp_access_token_configured,
            facebook_graph_api_base_url=record.facebook_graph_api_base_url,
            facebook_page_id=record.facebook_page_id,
            facebook_messaging_type=record.facebook_messaging_type,
            facebook_page_access_token_configured=runtime.facebook_page_access_token_configured,
            instagram_graph_api_base_url=record.instagram_graph_api_base_url,
            instagram_business_account_id=record.instagram_business_account_id,
            instagram_access_token_configured=runtime.instagram_access_token_configured,
            updated_at=record.updated_at,
        )

    def read(self, db: Session, *, market_id: str) -> IntegrationCredentialSettings:
        record = self.get_or_create(db, market_id=market_id)
        return self._to_domain(record, self.runtime_credentials(db, market_id=market_id))

    def _sync_provider_account(
        self,
        db: Session,
        *,
        market_id: str,
        provider: ChannelType,
        live: bool,
        account_identifier: str,
    ) -> None:
        account = db.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == market_id,
                ConnectorAccountRecord.provider == provider.value,
            )
        )
        if account is None:
            return
        if account_identifier:
            account.account_identifier = account_identifier
        account.outbound_enabled = live
        account.intake_enabled = True
        account.secret_configured = live
        account.credential_ref = f"settings://{provider.value}/{market_id}" if live else None
        account.webhook_verified = live
        account.status = "connected" if live else "pending_credentials"
        account.last_error = None if live else account.last_error
        account.updated_at = utc_now()

    def _sync_connector_accounts(
        self,
        db: Session,
        *,
        market_id: str,
        runtime: RuntimeIntegrationCredentials,
    ) -> None:
        self._sync_provider_account(
            db,
            market_id=market_id,
            provider=ChannelType.whatsapp,
            live=runtime.whatsapp_live,
            account_identifier=runtime.whatsapp_phone_number_id,
        )
        self._sync_provider_account(
            db,
            market_id=market_id,
            provider=ChannelType.facebook,
            live=runtime.facebook_live,
            account_identifier=runtime.facebook_page_id,
        )
        self._sync_provider_account(
            db,
            market_id=market_id,
            provider=ChannelType.instagram,
            live=runtime.instagram_live,
            account_identifier=runtime.instagram_business_account_id,
        )
        self._sync_provider_account(
            db,
            market_id=market_id,
            provider=ChannelType.sms,
            live=runtime.sms_live,
            account_identifier=runtime.sms_http_from,
        )
        self._sync_provider_account(
            db,
            market_id=market_id,
            provider=ChannelType.voice,
            live=runtime.voice_live,
            account_identifier=runtime.voice_http_from,
        )

    def update(
        self,
        db: Session,
        state: InMemoryStore,
        request: UpdateIntegrationCredentialSettingsRequest,
        *,
        market_id: str,
        actor: str,
    ) -> IntegrationCredentialSettings:
        record = self.get_or_create(db, market_id=market_id)
        patch = request.model_dump(exclude_unset=True, mode="json")
        if request.ai_provider is not None:
            ai_provider = _clean(request.ai_provider).lower()
            if ai_provider not in {"auto", "rules", "anthropic"}:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="AI provider must be auto, rules, or anthropic.",
                )
            record.ai_provider = ai_provider
        for key in (
            "anthropic_api_base_url",
            "anthropic_model",
            "alert_webhook_url",
            "sms_http_endpoint",
            "sms_http_from",
            "sms_http_auth_header",
            "sms_http_auth_scheme",
            "sms_http_delivery_callback_url",
            "voice_http_endpoint",
            "voice_http_from",
            "voice_http_auth_header",
            "voice_http_auth_scheme",
            "voice_http_status_callback_url",
            "whatsapp_cloud_api_base_url",
            "whatsapp_phone_number_id",
            "facebook_graph_api_base_url",
            "facebook_page_id",
            "instagram_graph_api_base_url",
            "instagram_business_account_id",
        ):
            if key in patch and patch[key] is not None:
                setattr(record, key, _clean(str(patch[key])))
        if request.alert_delivery_min_severity is not None:
            record.alert_delivery_min_severity = request.alert_delivery_min_severity.value
        if request.facebook_messaging_type is not None:
            messaging_type = _clean(request.facebook_messaging_type).upper()
            if messaging_type not in {"RESPONSE", "UPDATE", "MESSAGE_TAG"}:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Facebook messaging type must be RESPONSE, UPDATE, or MESSAGE_TAG.",
                )
            record.facebook_messaging_type = messaging_type
        if request.whatsapp_preview_urls is not None:
            record.whatsapp_preview_urls = request.whatsapp_preview_urls
        secret_fields = {
            "anthropic_api_key": "clear_anthropic_api_key",
            "alert_webhook_secret": "clear_alert_webhook_secret",
            "sms_http_auth_token": "clear_sms_http_auth_token",
            "voice_http_auth_token": "clear_voice_http_auth_token",
            "whatsapp_access_token": "clear_whatsapp_access_token",
            "facebook_page_access_token": "clear_facebook_page_access_token",
            "instagram_access_token": "clear_instagram_access_token",
        }
        for secret_field, clear_field in secret_fields.items():
            if getattr(request, clear_field):
                setattr(record, secret_field, None)
            else:
                secret_value = _clean_secret(getattr(request, secret_field))
                if secret_value:
                    setattr(record, secret_field, secret_value)
        record.updated_at = utc_now()
        runtime = self.runtime_credentials(db, market_id=market_id)
        self._sync_connector_accounts(db, market_id=market_id, runtime=runtime)
        secret_names = set(secret_fields)
        audit_details = {
            key: value
            for key, value in patch.items()
            if key not in secret_names
        }
        for secret_name in secret_names:
            if _clean_secret(getattr(request, secret_name)):
                audit_details[f"{secret_name}_configured"] = True
        _audit(db, state, actor=actor, market_id=market_id, details=audit_details)
        db.commit()
        db.refresh(record)
        return self._to_domain(record, self.runtime_credentials(db, market_id=market_id))


integration_credential_settings_repository = IntegrationCredentialSettingsRepository()
