from __future__ import annotations

import hashlib
import json
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.connectors import connector_account_repository
from app.db.integration_credentials import integration_credential_settings_repository
from app.db.mappers import (
    customer_from_record,
    outbound_message_from_record,
    ticket_from_record,
    timeline_event_from_record,
)
from app.db.models import (
    AuditEventRecord,
    CustomerRecord,
    MarketRecord,
    OutboundMessageRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.outbound import outbound_repository
from app.db.production_accounts import production_account_reference_repository
from app.db.ticketing import _next_public_ticket_id
from app.models.domain import (
    AttachmentProviderConfig,
    ChannelType,
    default_sla,
    InboundProviderConfig,
    IntegrationCredentialSettings,
    OidcProviderConfig,
    OperationalAlertDeliveryConfig,
    OutboundProviderConfig,
    Priority,
    ProductionAccountRequestDelivery,
    ProductionAccountRequestItem,
    ProductionAccountRequestPack,
    ProductionReadinessChecklist,
    ProductionReadinessItem,
    Sentiment,
    TicketStatus,
    TimelineEventType,
    utc_now,
)
from app.services import attachments as attachment_services
from app.services import identity as identity_service
from app.services.alert_delivery import alert_delivery_service
from app.services.inbound_adapters import inbound_adapter_router
from app.services.outbound_adapters import outbound_adapter_router

ACCOUNT_REQUEST_RECIPIENT = "gbolahans@wakanow.com"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _origin(base_url: str) -> str:
    return base_url.rstrip("/")


def _status(is_ready: bool, missing_settings: list[str]) -> str:
    if is_ready:
        return "ready"
    return "missing" if missing_settings else "action_required"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _inbound_provider_config(
    configs: list[InboundProviderConfig],
    provider: ChannelType,
) -> InboundProviderConfig | None:
    return next((config for config in configs if config.provider == provider), None)


def _outbound_provider_config(
    configs: list[OutboundProviderConfig],
    provider: ChannelType,
) -> OutboundProviderConfig | None:
    return next((config for config in configs if config.provider == provider), None)


def _provider_missing(
    inbound: InboundProviderConfig | None,
    outbound: OutboundProviderConfig | None,
) -> list[str]:
    return _dedupe([
        *(inbound.missing_settings if inbound else []),
        *(outbound.missing_settings if outbound else []),
    ])


def _provider_required(
    inbound: InboundProviderConfig | None,
    outbound: OutboundProviderConfig | None,
) -> list[str]:
    return _dedupe([
        *(inbound.required_settings if inbound else []),
        *(outbound.required_settings if outbound else []),
    ])


def _connector_callback_url(base_url: str, provider: ChannelType, market: MarketRecord) -> str:
    return f"{_origin(base_url)}/api/v1/webhooks/{provider.value}/{market.code.lower()}"


def _item(
    *,
    item_id: str,
    area: str,
    provider: str,
    purpose: str,
    backend_use: str,
    ready: bool,
    required_credentials: list[str],
    missing_settings: list[str],
    callback_urls: list[str] | None = None,
    setup_location: str = "Setup -> Connectors",
    credential_reference_name: str = "",
    account_owner: str = "",
    notes: str = "",
) -> ProductionAccountRequestItem:
    return ProductionAccountRequestItem(
        id=item_id,
        area=area,
        provider=provider,
        purpose=purpose,
        backend_use=backend_use,
        status=_status(ready, missing_settings),
        required_credentials=_dedupe(required_credentials),
        missing_settings=_dedupe(missing_settings),
        callback_urls=_dedupe(callback_urls or []),
        setup_location=setup_location,
        credential_reference_name=credential_reference_name,
        account_owner=account_owner,
        notes=notes,
    )


def _email_item(
    *,
    inbound: InboundProviderConfig | None,
    outbound: OutboundProviderConfig | None,
) -> ProductionAccountRequestItem:
    missing = _provider_missing(inbound, outbound)
    return _item(
        item_id="email",
        area="Email inbound/outbound",
        provider="Mailbox provider for jimb@wakanow.com",
        purpose="Convert mailbox messages to tickets and send customer replies or handoff forwards.",
        backend_use="IMAP intake, SMTP delivery, thread context, attachments, and outbound queue retries.",
        ready=not missing,
        required_credentials=_provider_required(inbound, outbound)
        or ["Mailbox provider", "IMAP settings", "SMTP settings", "sender identity"],
        missing_settings=missing,
        setup_location="Setup -> Connectors -> Email setup",
        credential_reference_name="settings://email/{market}",
        account_owner="Wakanow email administrator",
        notes="Passwords are write-only in Setup; API responses only expose configured booleans.",
    )


def _channel_item(
    *,
    provider: ChannelType,
    label: str,
    inbound: InboundProviderConfig | None,
    outbound: OutboundProviderConfig | None,
    market: MarketRecord,
    base_url: str,
    credential_reference_name: str,
    account_owner: str,
) -> ProductionAccountRequestItem:
    missing = _provider_missing(inbound, outbound)
    return _item(
        item_id=provider.value,
        area=f"{label} channel",
        provider=label,
        purpose=f"Support {label} customer intake, replies, delivery receipts, and audit history.",
        backend_use=(
            "Signed webhook intake, replay protection, connector events, outbound provider adapter, "
            "timeline receipts, and worker retry/dead-letter handling."
        ),
        ready=not missing,
        required_credentials=_provider_required(inbound, outbound),
        missing_settings=missing,
        callback_urls=[_connector_callback_url(base_url, provider, market)],
        setup_location="Setup -> Connectors -> Production credentials",
        credential_reference_name=credential_reference_name,
        account_owner=account_owner,
        notes=f"{label} secrets remain write-only; webhook signing secrets live in connector account settings.",
    )


def _ai_item(settings: IntegrationCredentialSettings) -> ProductionAccountRequestItem:
    missing = [] if settings.anthropic_api_key_configured else ["Anthropic API key"]
    return _item(
        item_id="anthropic-ai",
        area="AI guidance",
        provider="Anthropic",
        purpose="Production ticket summaries, recommended next actions, and decision metadata.",
        backend_use="Anthropic Messages adapter with deterministic fallback when unavailable.",
        ready=not missing,
        required_credentials=["Anthropic API key", "Model access"],
        missing_settings=missing,
        setup_location="Setup -> Connectors -> Production credentials",
        credential_reference_name="settings://integration/{market}/anthropic",
        account_owner="AI platform owner",
        notes=f"Configured model target: {settings.anthropic_model}.",
    )


def _alert_item(config: OperationalAlertDeliveryConfig) -> ProductionAccountRequestItem:
    missing = [] if config.webhook_configured else ["Alert webhook URL"]
    return _item(
        item_id="alert-webhook",
        area="Operational alert delivery",
        provider="Alerting / incident destination",
        purpose="Deliver API, worker, SLA, connector, and queue incidents outside Omni.",
        backend_use="Durable alert delivery queue with retry attempts and optional webhook signing.",
        ready=not missing,
        required_credentials=["Webhook URL", "Optional signing secret", "Destination owner"],
        missing_settings=missing,
        setup_location="Setup -> Connectors -> Production credentials",
        credential_reference_name="settings://integration/{market}/alerts",
        account_owner="Operations alerting owner",
        notes=f"Minimum severity: {config.min_severity.value}; max attempts: {config.max_attempts}.",
    )


def _identity_item(config: OidcProviderConfig, base_url: str) -> ProductionAccountRequestItem:
    return _item(
        item_id="identity-oidc",
        area="Enterprise identity",
        provider=config.provider_name,
        purpose="Production SSO login, user lifecycle, and external identity federation.",
        backend_use="OIDC PKCE start, one-time callback state, verified-email linking, and guarded provisioning.",
        ready=config.login_available,
        required_credentials=config.required_settings,
        missing_settings=config.missing_settings,
        callback_urls=[f"{_origin(base_url)}/api/v1/auth/oidc/callback"],
        setup_location="Runtime env / managed identity settings",
        credential_reference_name="runtime://oidc",
        account_owner="Identity provider administrator",
        notes=config.notes,
    )


def _attachment_items(config: AttachmentProviderConfig) -> list[ProductionAccountRequestItem]:
    storage_missing: list[str] = []
    scanner_missing: list[str] = []
    if config.storage_backend != "s3":
        storage_missing = [
            "S3-compatible bucket",
            "Storage access policy",
            "Region or endpoint URL",
            "Credential reference",
        ]
    elif not config.storage_live:
        storage_missing = [value for value in config.missing_settings if value.startswith("OMNI_ATTACHMENT_S3")]

    if config.scanner_adapter != "http":
        scanner_missing = ["Scanner service endpoint", "Scanner auth token if required"]
    elif not config.live_scanning:
        scanner_missing = [
            value for value in config.missing_settings if value.startswith("OMNI_ATTACHMENT_SCANNER")
        ]

    return [
        _item(
            item_id="attachment-storage",
            area="Attachment object storage",
            provider="S3-compatible object storage",
            purpose="Production attachment storage with managed durability and access policy control.",
            backend_use="S3-compatible attachment storage adapter and signed download path.",
            ready=not storage_missing,
            required_credentials=[
                "Bucket",
                "Region or endpoint URL",
                "Access key reference",
                "Secret key reference",
                "Encryption/access policy",
            ],
            missing_settings=storage_missing,
            setup_location="Runtime env / managed secret storage",
            credential_reference_name="runtime://attachments/storage",
            account_owner="Infrastructure/storage owner",
            notes=config.notes,
        ),
        _item(
            item_id="attachment-scanner",
            area="Malware scanning",
            provider="HTTP malware scanner",
            purpose="Block unsafe binary uploads before storage and customer download.",
            backend_use="External HTTP scanner adapter before binary persistence.",
            ready=not scanner_missing,
            required_credentials=["Scanner endpoint", "Optional auth header/token", "Result schema policy"],
            missing_settings=scanner_missing,
            setup_location="Runtime env / managed secret storage",
            credential_reference_name="runtime://attachments/scanner",
            account_owner="Security/platform owner",
            notes=config.notes,
        ),
    ]


def _portal_and_api_items(
    db: Session,
    *,
    market_id: str,
    base_url: str,
) -> list[ProductionAccountRequestItem]:
    accounts = {
        account.provider: account
        for account in connector_account_repository.list_accounts(db, market_id)
    }
    items: list[ProductionAccountRequestItem] = []
    portal = accounts.get(ChannelType.portal)
    if portal is not None:
        missing = [] if portal.status == "connected" and portal.secret_configured else portal.required_credentials
        items.append(
            _item(
                item_id="portal",
                area="Customer portal",
                provider="Customer auth / portal provider",
                purpose="Authenticated customer self-service, answer deflection, ticket lookup, and replies.",
                backend_use="Public portal intake/status/reply route with future authenticated portal boundary.",
                ready=not missing,
                required_credentials=portal.required_credentials,
                missing_settings=missing,
                callback_urls=[f"{_origin(base_url)}/?screen=portal"],
                setup_location="Setup -> Connectors -> Market channel accounts",
                credential_reference_name="connector://portal/{market}",
                account_owner="Customer identity or web platform owner",
                notes=portal.last_error or "Portal account is tracked from connector account metadata.",
            )
        )
    api = accounts.get(ChannelType.api)
    if api is not None:
        missing = [] if api.status == "connected" and api.secret_configured else api.required_credentials
        items.append(
            _item(
                item_id="partner-api",
                area="Partner API",
                provider="Partner webhook/API provider",
                purpose="Partner system intake, callbacks, idempotency, and replay protection.",
                backend_use="Authenticated connector intake plus signed webhook boundary for partner events.",
                ready=not missing,
                required_credentials=api.required_credentials,
                missing_settings=missing,
                callback_urls=[f"{_origin(base_url)}/api/v1/connectors/inbound"],
                setup_location="Setup -> Connectors -> Market channel accounts",
                credential_reference_name="connector://api/{market}",
                account_owner="Partner integrations owner",
                notes=api.last_error or "Partner API account is tracked from connector account metadata.",
            )
        )
    return items


def _observability_item() -> ProductionAccountRequestItem:
    return _item(
        item_id="observability",
        area="External observability",
        provider="APM / log drain / dashboard provider",
        purpose="Monitor deployed web, API, worker, queue, and database health outside the app.",
        backend_use="Complements in-app operational alerts, structured API logs, request IDs, and analytics rollups.",
        ready=False,
        required_credentials=[
            "APM/log drain destination",
            "Dashboard workspace",
            "Alert routing destination",
            "Environment tags",
        ],
        missing_settings=["External APM/log drain account", "Production dashboard workspace"],
        setup_location="Infrastructure / deployment platform",
        credential_reference_name="runtime://observability",
        account_owner="Infrastructure/operations owner",
        notes="In-app alerts are available; external dashboards/APM still need provider activation.",
    )


def _body_for_pack(
    *,
    market: MarketRecord,
    items: list[ProductionAccountRequestItem],
    base_url: str,
) -> str:
    action_items = [item for item in items if item.status != "ready"]
    ready_items = [item for item in items if item.status == "ready"]
    lines = [
        f"Omni Ticket production account request for {market.name} ({market.code})",
        "",
        f"Environment: {_origin(base_url)}",
        f"Action items: {len(action_items)}",
        f"Already ready: {len(ready_items)}",
        "",
        "Please provision or share the non-secret account references for the items below.",
        "Do not email raw passwords, private keys, access tokens, or webhook secrets; send owner/account references and confirm where secrets will be stored.",
        "",
    ]
    for item in action_items:
        lines.extend(
            [
                f"Provider: {item.provider}",
                f"Purpose: {item.purpose}",
                f"Market(s): {market.code} - {market.name}",
                f"Account owner: {item.account_owner}",
                f"Credential reference name: {item.credential_reference_name}",
                f"Webhook URL: {', '.join(item.callback_urls) or 'N/A'}",
                f"Callback/redirect URL: {', '.join(item.callback_urls) or 'N/A'}",
                "Secret storage location: managed secret storage or write-only Omni Setup field",
                f"Missing: {', '.join(item.missing_settings) or 'Account activation/confirmation'}",
                f"Required: {', '.join(item.required_credentials) or 'Provider account details'}",
                f"Setup location: {item.setup_location}",
                f"Operational notes: {item.notes}",
                "",
            ]
        )
    if ready_items:
        lines.extend(["Already ready / no action needed:", ""])
        for item in ready_items:
            lines.append(f"- {item.provider}: {item.area}")
    return "\n".join(lines).strip()


def production_account_request_pack(
    db: Session,
    *,
    market_id: str,
    base_url: str,
    recipient_email: str = ACCOUNT_REQUEST_RECIPIENT,
) -> ProductionAccountRequestPack:
    market = db.get(MarketRecord, market_id)
    if market is None:
        raise ValueError(f"Unknown market: {market_id}")

    inbound_configs = inbound_adapter_router.config_summary(db, market_id)
    outbound_configs = outbound_adapter_router.config_summary(db, market_id)
    integration_settings = integration_credential_settings_repository.read(db, market_id=market_id)
    alert_config = alert_delivery_service.config_summary(db, market_id)
    oidc_config = identity_service.oidc_provider_config()
    attachment_config = attachment_services.attachment_provider_config()

    email_inbound = _inbound_provider_config(inbound_configs, ChannelType.email)
    email_outbound = _outbound_provider_config(outbound_configs, ChannelType.email)
    items: list[ProductionAccountRequestItem] = [
        _email_item(inbound=email_inbound, outbound=email_outbound),
        _ai_item(integration_settings),
        _alert_item(alert_config),
        _identity_item(oidc_config, base_url),
    ]
    for provider, label, credential_ref, owner in (
        (ChannelType.whatsapp, "WhatsApp Business", "settings://integration/{market}/whatsapp", "Meta Business owner"),
        (ChannelType.facebook, "Facebook Messenger", "settings://integration/{market}/facebook", "Meta Page owner"),
        (ChannelType.instagram, "Instagram DM", "settings://integration/{market}/instagram", "Meta/Instagram owner"),
        (ChannelType.sms, "SMS provider", "settings://integration/{market}/sms", "SMS provider owner"),
        (ChannelType.voice, "Voice provider", "settings://integration/{market}/voice", "Telephony provider owner"),
    ):
        items.append(
            _channel_item(
                provider=provider,
                label=label,
                inbound=_inbound_provider_config(inbound_configs, provider),
                outbound=_outbound_provider_config(outbound_configs, provider),
                market=market,
                base_url=base_url,
                credential_reference_name=credential_ref,
                account_owner=owner,
            )
        )
    items.extend(_attachment_items(attachment_config))
    items.extend(_portal_and_api_items(db, market_id=market_id, base_url=base_url))
    items.append(_observability_item())

    ready_items = len([item for item in items if item.status == "ready"])
    missing_items = len(items) - ready_items
    subject = f"Omni Ticket production account requests - {market.code}"
    body = _body_for_pack(market=market, items=items, base_url=base_url)
    mailto_url = (
        f"mailto:{quote(recipient_email)}?subject={quote(subject)}&body={quote(body)}"
    )
    return ProductionAccountRequestPack(
        market_id=market_id,
        recipient_email=recipient_email,
        generated_at=utc_now(),
        total_items=len(items),
        ready_items=ready_items,
        missing_items=missing_items,
        subject=subject,
        body=body,
        mailto_url=mailto_url,
        items=items,
    )


def _checklist_status_from_pack(item: ProductionAccountRequestItem) -> str:
    if item.status == "ready":
        return "ready"
    if item.status == "missing":
        return "blocked"
    return "action_required"


def _readiness_item(
    *,
    item_id: str,
    category: str,
    label: str,
    status: str,
    summary: str,
    evidence: list[str] | None = None,
    next_action: str = "",
    docs_reference: str = "",
) -> ProductionReadinessItem:
    return ProductionReadinessItem(
        id=item_id,
        category=category,
        label=label,
        status=status,
        summary=summary,
        evidence=[item for item in (evidence or []) if item],
        next_action=next_action,
        docs_reference=docs_reference,
    )


def _current_alembic_version(db: Session) -> str:
    try:
        return str(db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar() or "")
    except Exception:
        return ""


def _latest_account_request_message(db: Session, market_id: str) -> OutboundMessageRecord | None:
    records = db.scalars(
        select(OutboundMessageRecord)
        .where(
            OutboundMessageRecord.market_id == market_id,
            OutboundMessageRecord.provider == ChannelType.email.value,
        )
        .order_by(OutboundMessageRecord.created_at.desc())
    ).all()
    for record in records:
        if (record.payload or {}).get("source") == "production_account_request":
            return record
    return None


def _reference_secret_hygiene_evidence(values: list[str]) -> tuple[str, list[str]]:
    suspicious_markers = [
        "-----BEGIN",
        "sk-ant-",
        "sk-",
        "Bearer ",
        "xoxb-",
        "ghp_",
        "gho_",
        "AKIA",
    ]
    suspicious = [
        value
        for value in values
        if any(marker in value for marker in suspicious_markers)
    ]
    if suspicious:
        return "blocked", ["Potential secret-like value detected in account references."]
    return "ready", ["No obvious raw secret markers found in account-reference metadata."]


def production_readiness_checklist(
    db: Session,
    *,
    market_id: str,
    base_url: str,
) -> ProductionReadinessChecklist:
    pack = production_account_request_pack(db, market_id=market_id, base_url=base_url)
    account_refs = production_account_reference_repository.list_references(db, market_id=market_id)
    connected_refs = [
        reference
        for reference in account_refs
        if reference.status.value in {"provisioned", "connected"}
    ]
    latest_request = _latest_account_request_message(db, market_id)
    alembic_version = _current_alembic_version(db)
    items: list[ProductionReadinessItem] = []

    items.append(
        _readiness_item(
            item_id="database-migrations",
            category="Platform",
            label="Database schema",
            status="ready" if alembic_version >= "20260605_0025" else "blocked",
            summary="Database migration state is current for the deployed production-account reference schema.",
            evidence=[f"Alembic version: {alembic_version or 'unknown'}"],
            next_action="Run Alembic migrations before launch." if alembic_version < "20260605_0025" else "",
            docs_reference="services/omni-ticket-backend/docs/DEPLOYMENT.md",
        )
    )
    items.append(
        _readiness_item(
            item_id="account-request-email",
            category="Provider Accounts",
            label="Provider account request email",
            status="ready" if latest_request is not None else "action_required",
            summary=(
                "The sanitized provider account request has been queued through the outbound email pipeline."
                if latest_request is not None
                else "The sanitized provider account request has not been queued yet."
            ),
            evidence=[
                f"Outbound message: {latest_request.id}" if latest_request is not None else "",
                f"Status: {latest_request.status}" if latest_request is not None else "",
            ],
            next_action="Use Setup -> Connectors -> Queue email to send the account request."
            if latest_request is None
            else "",
            docs_reference="API_DOCS.md#external-accounts-needed",
        )
    )
    items.append(
        _readiness_item(
            item_id="account-reference-tracking",
            category="Provider Accounts",
            label="Non-secret account references",
            status="ready" if connected_refs else "action_required",
            summary=(
                f"{len(connected_refs)} provisioned/connected provider account reference(s) recorded."
                if connected_refs
                else "No provisioned provider account references have been recorded yet."
            ),
            evidence=[
                f"Total references: {len(account_refs)}",
                f"Provisioned or connected: {len(connected_refs)}",
            ],
            next_action="Record provider account IDs, owners, callback URLs, and credential references after accounts are provisioned."
            if not connected_refs
            else "",
            docs_reference="API_DOCS.md#external-accounts-needed",
        )
    )
    hygiene_status, hygiene_evidence = _reference_secret_hygiene_evidence(
        [
            value
            for reference in account_refs
            for value in [
                reference.account_identifier,
                reference.credential_reference,
                reference.docs_reference,
                reference.notes,
                *reference.callback_urls,
            ]
        ]
    )
    items.append(
        _readiness_item(
            item_id="account-reference-secret-hygiene",
            category="Security",
            label="Account reference secret hygiene",
            status=hygiene_status,
            summary="Account references should only contain non-secret metadata and secret-location references.",
            evidence=hygiene_evidence,
            next_action="Remove raw secrets from account references and rotate exposed provider credentials."
            if hygiene_status != "ready"
            else "",
            docs_reference="API_DOCS.md#external-accounts-needed",
        )
    )
    for item in pack.items:
        items.append(
            _readiness_item(
                item_id=f"provider-{item.id}",
                category=item.area,
                label=item.provider,
                status=_checklist_status_from_pack(item),
                summary=item.purpose,
                evidence=[
                    f"Status: {item.status}",
                    f"Missing: {', '.join(item.missing_settings)}" if item.missing_settings else "No missing settings",
                    f"Setup: {item.setup_location}",
                ],
                next_action=(
                    f"Provision/save: {', '.join(item.missing_settings or item.required_credentials)}"
                    if item.status != "ready"
                    else ""
                ),
                docs_reference="API_DOCS.md#external-accounts-needed",
            )
        )
    ready_items = len([item for item in items if item.status == "ready"])
    blocked_items = len([item for item in items if item.status == "blocked"])
    action_items = len(items) - ready_items - blocked_items
    if blocked_items:
        overall_status = "blocked"
    elif action_items:
        overall_status = "action_required"
    else:
        overall_status = "ready"
    return ProductionReadinessChecklist(
        market_id=market_id,
        overall_status=overall_status,
        total_items=len(items),
        ready_items=ready_items,
        action_items=action_items,
        blocked_items=blocked_items,
        items=items,
    )


def _pack_signature(pack: ProductionAccountRequestPack) -> str:
    fingerprint = [
        {
            "id": item.id,
            "status": item.status,
            "missing_settings": item.missing_settings,
            "callback_urls": item.callback_urls,
        }
        for item in sorted(pack.items, key=lambda item: item.id)
    ]
    payload = json.dumps(
        {
            "market_id": pack.market_id,
            "recipient_email": str(pack.recipient_email),
            "subject": pack.subject,
            "items": fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _write_audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str,
    details: dict,
) -> AuditEventRecord:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    return record


def _ensure_account_request_customer(
    db: Session,
    state: InMemoryStore,
    *,
    market_id: str,
    recipient_email: str,
) -> CustomerRecord:
    customer = db.scalar(
        select(CustomerRecord).where(
            CustomerRecord.market_id == market_id,
            CustomerRecord.email == recipient_email,
        )
    )
    if customer is None:
        customer = CustomerRecord(
            id=_new_id("cust"),
            market_id=market_id,
            name="Production Account Requests",
            email=recipient_email,
            company_id=None,
            location="",
            sentiment=Sentiment.neutral.value,
            preferred_channels=[ChannelType.email.value],
            contact_points=[{"channel": ChannelType.email.value, "value": recipient_email}],
            tags=["production-readiness", "api-accounts"],
            notes="Internal recipient for Omni Ticket provider account and credential activation requests.",
        )
        db.add(customer)
        db.flush()
    else:
        customer.tags = sorted(set(customer.tags or []) | {"production-readiness", "api-accounts"})
        customer.preferred_channels = sorted(
            set(customer.preferred_channels or []) | {ChannelType.email.value}
        )
        contact_points = list(customer.contact_points or [])
        if not any(
            point.get("channel") == ChannelType.email.value and point.get("value") == recipient_email
            for point in contact_points
        ):
            contact_points.append({"channel": ChannelType.email.value, "value": recipient_email})
        customer.contact_points = contact_points
        customer.updated_at = utc_now()
        db.flush()
    state.customers[customer.id] = customer_from_record(customer)
    return customer


def _account_request_tasks(pack: ProductionAccountRequestPack) -> list[dict[str, object]]:
    return [
        {"id": _new_id("task"), "label": "Email provider/account request pack", "complete": False},
        {
            "id": _new_id("task"),
            "label": f"Track {pack.missing_items} missing provider account item(s)",
            "complete": pack.missing_items == 0,
        },
        {"id": _new_id("task"), "label": "Add non-secret account references to API_DOCS", "complete": False},
    ]


def _create_account_request_ticket(
    db: Session,
    state: InMemoryStore,
    *,
    market: MarketRecord,
    customer: CustomerRecord,
    pack: ProductionAccountRequestPack,
    pack_signature: str,
    actor: str,
) -> tuple[TicketRecord, TimelineEventRecord]:
    now = utc_now()
    ticket = TicketRecord(
        id=_new_id("ticket"),
        market_id=market.id,
        public_id=_next_public_ticket_id(db),
        subject=pack.subject,
        description=pack.body,
        customer_id=customer.id,
        channel=ChannelType.internal.value,
        status=TicketStatus.open.value,
        priority=Priority.high.value,
        sentiment=Sentiment.neutral.value,
        assignee_id=None,
        team="Setup",
        tags=["production-readiness", "api-accounts", "account-request"],
        custom_fields={
            "account_request_pack_signature": pack_signature,
            "recipient_email": str(pack.recipient_email),
            "missing_items": pack.missing_items,
            "total_items": pack.total_items,
        },
        tasks=_account_request_tasks(pack),
        sla=default_sla(Priority.high, now).model_dump(mode="json"),
        ai_summary="Production provider account request pack queued for operator follow-through.",
        recommended_action=(
            "Confirm the account request email is delivered, then update API_DOCS with non-secret "
            "provider references as accounts are provisioned."
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()
    state.tickets[ticket.id] = ticket_from_record(ticket)

    timeline_event = TimelineEventRecord(
        id=_new_id("event"),
        market_id=market.id,
        ticket_id=ticket.id,
        type=TimelineEventType.internal_note.value,
        channel=ChannelType.internal.value,
        actor=actor,
        body=pack.body,
        public=False,
        event_metadata={
            "source": "production_account_request",
            "recipient_email": str(pack.recipient_email),
            "pack_signature": pack_signature,
            "missing_items": pack.missing_items,
            "total_items": pack.total_items,
        },
        created_at=now,
        updated_at=now,
    )
    db.add(timeline_event)
    db.flush()
    state.timeline.setdefault(ticket.id, []).append(timeline_event_from_record(timeline_event))
    _write_audit(
        db,
        state,
        actor=actor,
        action="production.account_request.ticket.create",
        entity_type="ticket",
        entity_id=ticket.id,
        market_id=market.id,
        details={
            "public_id": ticket.public_id,
            "recipient_email": str(pack.recipient_email),
            "pack_signature": pack_signature,
            "missing_items": pack.missing_items,
            "total_items": pack.total_items,
        },
    )
    return ticket, timeline_event


def queue_production_account_request_email(
    db: Session,
    state: InMemoryStore,
    *,
    market_id: str,
    base_url: str,
    actor: str,
    recipient_email: str = ACCOUNT_REQUEST_RECIPIENT,
) -> ProductionAccountRequestDelivery:
    pack = production_account_request_pack(
        db,
        market_id=market_id,
        base_url=base_url,
        recipient_email=recipient_email,
    )
    market = db.get(MarketRecord, market_id)
    if market is None:
        raise ValueError(f"Unknown market: {market_id}")

    pack_signature = _pack_signature(pack)
    idempotency_key = f"{market_id}:production-account-request:{pack_signature}:email"
    existing = db.scalar(
        select(OutboundMessageRecord).where(
            OutboundMessageRecord.market_id == market_id,
            OutboundMessageRecord.provider == ChannelType.email.value,
            OutboundMessageRecord.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        ticket = db.get(TicketRecord, existing.ticket_id)
        return ProductionAccountRequestDelivery(
            pack=pack,
            outbound_message=outbound_message_from_record(existing),
            ticket_id=existing.ticket_id,
            ticket_public_id=ticket.public_id if ticket else existing.ticket_id,
            already_queued=True,
            queued_at=existing.created_at,
        )

    customer = _ensure_account_request_customer(
        db,
        state,
        market_id=market_id,
        recipient_email=recipient_email,
    )
    ticket, timeline_event = _create_account_request_ticket(
        db,
        state,
        market=market,
        customer=customer,
        pack=pack,
        pack_signature=pack_signature,
        actor=actor,
    )
    message = outbound_repository.queue_email(
        db,
        state,
        ticket=ticket,
        timeline_event=timeline_event,
        actor=actor,
        to_email=recipient_email,
        subject=pack.subject,
        body=pack.body,
        source="production_account_request",
        idempotency_key=idempotency_key,
        payload_extra={
            "pack_signature": pack_signature,
            "recipient_email": recipient_email,
            "missing_items": pack.missing_items,
            "ready_items": pack.ready_items,
            "total_items": pack.total_items,
            "mailto_url": pack.mailto_url,
        },
        audit_action="production.account_request.email.queue",
    )
    db.commit()
    return ProductionAccountRequestDelivery(
        pack=pack,
        outbound_message=message,
        ticket_id=ticket.id,
        ticket_public_id=ticket.public_id,
        already_queued=False,
        queued_at=message.created_at,
    )
