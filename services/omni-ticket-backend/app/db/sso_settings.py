from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record
from app.db.models import AuditEventRecord, SsoProviderSettingsRecord
from app.models.domain import (
    SsoProviderSettings,
    UpdateSsoProviderSettingsRequest,
    UserRole,
    utc_now,
)
from app.services.identity import ResolvedOidcConfig

GLOBAL_ID = "global"


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _normalize_domains(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        cleaned = value.strip().lower().removeprefix("@")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


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
        action="sso_provider_settings.update",
        entity_type="sso_provider_settings",
        entity_id=GLOBAL_ID,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class SsoProviderSettingsRepository:
    def _record(self, db: Session) -> SsoProviderSettingsRecord | None:
        return db.get(SsoProviderSettingsRecord, GLOBAL_ID)

    def get_or_create(self, db: Session) -> SsoProviderSettingsRecord:
        record = self._record(db)
        if record is not None:
            return record
        # Seed the database row from the current environment configuration so the
        # editable Settings surface starts from the deployed defaults.
        env = ResolvedOidcConfig.from_env()
        record = SsoProviderSettingsRecord(
            id=GLOBAL_ID,
            enabled=env.enabled,
            provider_name=env.provider_name,
            issuer_url=env.issuer_url or "",
            authorization_url=env.authorization_url or "",
            token_url=env.token_url or "",
            userinfo_url=env.userinfo_url or "",
            client_id=env.client_id or "",
            client_secret=env.client_secret,
            redirect_url=env.redirect_url or "",
            allowed_email_domains=_normalize_domains(env.allowed_email_domains),
            auto_provision_enabled=env.auto_provision_enabled,
            default_role=env.default_role,
            default_market_id=env.default_market_id,
            require_email_verified=env.require_email_verified,
        )
        db.add(record)
        db.flush()
        return record

    def resolve(self, db: Session | None = None) -> ResolvedOidcConfig:
        """Effective OIDC config: database overrides on top of environment defaults."""
        record = self._record(db) if db is not None else None
        if record is None:
            return ResolvedOidcConfig.from_env()
        env = ResolvedOidcConfig.from_env()
        return ResolvedOidcConfig(
            enabled=record.enabled,
            provider_name=record.provider_name or env.provider_name,
            issuer_url=record.issuer_url or env.issuer_url,
            authorization_url=record.authorization_url or env.authorization_url,
            token_url=record.token_url or env.token_url,
            userinfo_url=record.userinfo_url or env.userinfo_url,
            client_id=record.client_id or env.client_id,
            client_secret=record.client_secret or env.client_secret,
            redirect_url=record.redirect_url or env.redirect_url,
            allowed_email_domains=(
                list(record.allowed_email_domains)
                if record.allowed_email_domains
                else list(env.allowed_email_domains)
            ),
            auto_provision_enabled=record.auto_provision_enabled,
            default_role=record.default_role or env.default_role,
            default_market_id=record.default_market_id or env.default_market_id,
            require_email_verified=record.require_email_verified,
        )

    def _to_domain(self, db: Session, record: SsoProviderSettingsRecord) -> SsoProviderSettings:
        resolved = self.resolve(db)
        return SsoProviderSettings(
            enabled=record.enabled,
            provider_name=record.provider_name,
            issuer_url=record.issuer_url,
            authorization_url=record.authorization_url,
            token_url=record.token_url,
            userinfo_url=record.userinfo_url,
            client_id=record.client_id,
            client_secret_configured=bool(resolved.client_secret),
            redirect_url=record.redirect_url,
            allowed_email_domains=list(record.allowed_email_domains),
            auto_provision_enabled=record.auto_provision_enabled,
            default_role=UserRole(record.default_role),
            default_market_id=record.default_market_id,
            require_email_verified=record.require_email_verified,
            managed_in_database=True,
            updated_at=record.updated_at,
        )

    def read(self, db: Session) -> SsoProviderSettings:
        record = self.get_or_create(db)
        return self._to_domain(db, record)

    def update(
        self,
        db: Session,
        state: InMemoryStore,
        request: UpdateSsoProviderSettingsRequest,
        *,
        actor: str,
        market_id: str,
    ) -> SsoProviderSettings:
        record = self.get_or_create(db)
        patch = request.model_dump(exclude_unset=True)
        for key in ("enabled", "auto_provision_enabled", "require_email_verified"):
            if key in patch and patch[key] is not None:
                setattr(record, key, bool(patch[key]))
        for key in (
            "issuer_url",
            "authorization_url",
            "token_url",
            "userinfo_url",
            "client_id",
            "redirect_url",
            "provider_name",
            "default_market_id",
        ):
            if key in patch and patch[key] is not None:
                setattr(record, key, _clean(str(patch[key])))
        if request.default_role is not None:
            record.default_role = request.default_role.value
        if request.allowed_email_domains is not None:
            record.allowed_email_domains = _normalize_domains(request.allowed_email_domains)
        if request.clear_client_secret:
            record.client_secret = None
        elif request.client_secret:
            record.client_secret = request.client_secret.strip()
        record.updated_at = utc_now()
        audit_details = {key: value for key, value in patch.items() if key != "client_secret"}
        if request.client_secret:
            audit_details["client_secret_configured"] = True
        _audit(db, state, actor=actor, market_id=market_id, details=audit_details)
        db.commit()
        db.refresh(record)
        return self._to_domain(db, record)


sso_provider_settings_repository = SsoProviderSettingsRepository()
