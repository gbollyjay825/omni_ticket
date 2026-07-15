from __future__ import annotations

from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import imaplib
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.store import InMemoryStore
from app.db.connectors import connector_account_repository
from app.db.email_settings import (
    RuntimeEmailProviderSettings,
    email_provider_settings_repository,
)
from app.db.mappers import market_from_record
from app.db.models import ConnectorAccountRecord, MarketRecord
from app.db.settings import get_or_create_workspace_settings, workspace_settings_from_record
from app.db.ticketing import ticket_repository
from app.models.domain import (
    AttachmentScanStatus,
    ChannelType,
    ConnectorInboundRequest,
    CreateAttachmentRequest,
    InboundProviderConfig,
    utc_now,
)
from app.services import attachments as attachment_services


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return "\n".join(self.parts).strip()


@dataclass(frozen=True)
class InboundEmailAttachment:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class InboundEmailMessage:
    external_id: str
    customer_name: str
    customer_email: str
    subject: str
    body: str
    handle: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[InboundEmailAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class InboundSyncResult:
    provider: str
    adapter: str
    configured: bool
    live_intake: bool
    polling_enabled: bool
    processed: int = 0
    succeeded: int = 0
    deduplicated: int = 0
    failed: int = 0
    message_ids: list[str] = field(default_factory=list)
    attachment_ids: list[str] = field(default_factory=list)
    attachments_saved: int = 0
    attachments_blocked: int = 0
    attachments_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    missing_settings: list[str] = field(default_factory=list)

    def to_details(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "adapter": self.adapter,
            "configured": self.configured,
            "live_intake": self.live_intake,
            "polling_enabled": self.polling_enabled,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "deduplicated": self.deduplicated,
            "failed": self.failed,
            "message_ids": self.message_ids,
            "attachment_ids": self.attachment_ids,
            "attachments_saved": self.attachments_saved,
            "attachments_blocked": self.attachments_blocked,
            "attachments_skipped": self.attachments_skipped,
            "errors": self.errors,
            "missing_settings": self.missing_settings,
        }


class InboundAdapter(Protocol):
    name: str

    def config_summary(
        self,
        account: ConnectorAccountRecord | None = None,
    ) -> InboundProviderConfig: ...

    def sync(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int,
    ) -> InboundSyncResult: ...


class ImapEmailInboundAdapter:
    name = "imap"

    def missing_settings(self, email_settings: RuntimeEmailProviderSettings | None = None) -> list[str]:
        config = email_settings or email_provider_settings_repository.runtime_settings()
        missing: list[str] = []
        if not config.inbound_enabled:
            missing.append("Email inbound enabled")
        if not config.inbound_host:
            missing.append("IMAP host")
        if not config.inbound_username:
            missing.append("IMAP username")
        if not config.inbound_password:
            missing.append("IMAP password")
        return missing

    def configured(self, email_settings: RuntimeEmailProviderSettings | None = None) -> bool:
        return not self.missing_settings(email_settings)

    def config_summary(
        self,
        account: ConnectorAccountRecord | None = None,
        email_settings: RuntimeEmailProviderSettings | None = None,
    ) -> InboundProviderConfig:
        config = email_settings or email_provider_settings_repository.runtime_settings()
        missing = self.missing_settings(config)
        if account is None:
            missing = [*missing, "Email connector account"]
        elif not account.intake_enabled:
            missing = [*missing, "Email connector intake enabled"]
        live_intake = not missing
        return InboundProviderConfig(
            provider=ChannelType.email,
            adapter=self.name,
            configured=not missing,
            live_intake=live_intake,
            polling_enabled=config.inbound_enabled,
            required_settings=[
                "Email inbound enabled",
                "IMAP host",
                "IMAP username",
                "IMAP password",
            ],
            missing_settings=missing,
            notes=(
                "IMAP email intake polling is active."
                if live_intake
                else "Email intake will poll the mailbox after IMAP credentials are configured."
            ),
        )

    def _connect(self, email_settings: RuntimeEmailProviderSettings) -> imaplib.IMAP4:
        if not email_settings.inbound_host:
            raise ValueError("IMAP host is not configured.")
        imap_class = imaplib.IMAP4_SSL if email_settings.inbound_use_ssl else imaplib.IMAP4
        return imap_class(
            email_settings.inbound_host,
            email_settings.inbound_port,
            timeout=settings.email_imap_timeout_seconds,
        )

    def _plain_body(self, message) -> str:
        if message.is_multipart():
            html_fallback = ""
            for part in message.walk():
                if part.get_content_disposition() == "attachment":
                    continue
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    return str(part.get_content()).strip()
                if content_type == "text/html" and not html_fallback:
                    html_fallback = self._html_to_text(str(part.get_content()))
            return html_fallback.strip()
        if message.get_content_type() == "text/html":
            return self._html_to_text(str(message.get_content()))
        return str(message.get_content()).strip()

    def _html_to_text(self, html: str) -> str:
        parser = _HtmlTextExtractor()
        parser.feed(html)
        return parser.text()

    def _from_email(self, message) -> tuple[str, str]:
        addresses = getaddresses(message.get_all("reply-to", []) or message.get_all("from", []))
        for name, address in addresses:
            clean = address.strip().lower()
            if clean:
                return name.strip() or clean.split("@", 1)[0], clean
        raise ValueError("Email message is missing a sender address.")

    def _attachments(self, message) -> tuple[list[InboundEmailAttachment], list[dict[str, Any]]]:
        attachments: list[InboundEmailAttachment] = []
        skipped: list[dict[str, Any]] = []
        if not message.is_multipart():
            return attachments, skipped
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = (part.get_filename() or "").strip()
            disposition = (part.get_content_disposition() or "").lower()
            if disposition != "attachment" and not filename:
                continue
            content_type = part.get_content_type() or "application/octet-stream"
            payload = part.get_payload(decode=True)
            if payload is None:
                content = part.get_content()
                payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
            if not payload:
                skipped.append({
                    "filename": filename or "attachment",
                    "content_type": content_type,
                    "reason": "empty",
                })
                continue
            if len(payload) > settings.attachment_max_bytes:
                skipped.append({
                    "filename": filename or "attachment",
                    "content_type": content_type,
                    "size_bytes": len(payload),
                    "reason": "too_large",
                })
                continue
            attachments.append(
                InboundEmailAttachment(
                    filename=filename or "attachment",
                    content_type=content_type,
                    content=payload,
                )
            )
        return attachments, skipped

    def _parse_message(
        self,
        uid: bytes,
        raw_message: bytes,
        *,
        mailbox: str,
    ) -> InboundEmailMessage:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        name, address = self._from_email(message)
        message_id = (message.get("Message-ID") or "").strip()
        external_id = message_id or f"imap:{mailbox}:{uid.decode()}"
        subject = (message.get("Subject") or "New email support request").strip()
        body = self._plain_body(message)
        if not body:
            body = "(Email did not include a readable text body.)"
        attachments, skipped_attachments = self._attachments(message)
        metadata: dict[str, Any] = {
            "adapter": self.name,
            "imap_uid": uid.decode(),
            "message_id": message_id or None,
            "in_reply_to": (message.get("In-Reply-To") or "").strip() or None,
            "references": (message.get("References") or "").strip() or None,
            "omni_ticket_id": (message.get("X-Omni-Ticket-ID") or "").strip() or None,
            "omni_market_id": (message.get("X-Omni-Market-ID") or "").strip() or None,
            "omni_handoff_id": (message.get("X-Omni-Handoff-ID") or "").strip() or None,
            "omni_source_ticket_id": (
                message.get("X-Omni-Source-Ticket-ID") or ""
            ).strip() or None,
            "omni_source_ticket_public_id": (
                message.get("X-Omni-Source-Ticket-Public-ID") or ""
            ).strip() or None,
            "omni_linked_ticket_id": (
                message.get("X-Omni-Linked-Ticket-ID") or ""
            ).strip() or None,
            "omni_linked_ticket_public_id": (
                message.get("X-Omni-Linked-Ticket-Public-ID") or ""
            ).strip() or None,
            "omni_reply_target": (message.get("X-Omni-Reply-Target") or "").strip() or None,
            "omni_reply_target_ticket_id": (
                message.get("X-Omni-Reply-Target-Ticket-ID") or ""
            ).strip() or None,
            "omni_delivery_mode": (message.get("X-Omni-Delivery-Mode") or "").strip() or None,
            "from": address,
            "to": [item[1] for item in getaddresses(message.get_all("to", []))],
            "cc": [item[1] for item in getaddresses(message.get_all("cc", []))],
            "mailbox": mailbox,
            "attachments": [
                {
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size_bytes": len(attachment.content),
                }
                for attachment in attachments
            ],
            "skipped_attachments": skipped_attachments,
        }
        date_header = message.get("Date")
        if date_header is not None:
            try:
                metadata["sent_at"] = parsedate_to_datetime(str(date_header)).isoformat()
            except (TypeError, ValueError):
                metadata["sent_at"] = str(date_header)
        return InboundEmailMessage(
            external_id=external_id,
            customer_name=name,
            customer_email=address,
            subject=subject,
            body=body,
            handle=address,
            metadata=metadata,
            attachments=attachments,
        )

    def _extract_raw_message(self, fetch_data: list[Any]) -> bytes | None:
        for item in fetch_data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
        return None

    def _sync_ready_account(
        self,
        db: Session,
        market_id: str,
    ) -> ConnectorAccountRecord | None:
        account = connector_account_repository.get_account_for_provider(
            db,
            market_id=market_id,
            provider=ChannelType.email,
        )
        if account is None or not account.intake_enabled:
            return None
        return account

    def _base_result(
        self,
        *,
        account: ConnectorAccountRecord | None,
        email_settings: RuntimeEmailProviderSettings,
    ) -> InboundSyncResult:
        summary = self.config_summary(account, email_settings)
        return InboundSyncResult(
            provider=ChannelType.email.value,
            adapter=self.name,
            configured=summary.configured,
            live_intake=summary.live_intake,
            polling_enabled=summary.polling_enabled,
            missing_settings=summary.missing_settings,
        )

    def _attach_message_files(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        market_id: str,
        ticket_id: str,
        message: InboundEmailMessage,
    ) -> tuple[list[str], int, int, int]:
        attachment_ids: list[str] = []
        saved = blocked = 0
        skipped = len(message.metadata.get("skipped_attachments") or [])
        for attachment in message.attachments:
            attachment_id = f"attachment_{uuid4().hex}"
            scan_status, scan_result = attachment_services.scan_attachment_binary(
                filename=attachment.filename,
                content_type=attachment.content_type,
                data=attachment.content,
            )
            if scan_status == AttachmentScanStatus.clean:
                storage_key = attachment_services.attachment_storage.write(
                    market_id=market_id,
                    ticket_id=ticket_id,
                    attachment_id=attachment_id,
                    filename=attachment.filename,
                    data=attachment.content,
                    content_type=attachment.content_type,
                )
                saved += 1
            else:
                storage_key = attachment_services.blocked_storage_key(
                    market_id=market_id,
                    ticket_id=ticket_id,
                    attachment_id=attachment_id,
                    filename=attachment.filename,
                )
                blocked += 1
            created = ticket_repository.create_attachment(
                db,
                state,
                ticket_id,
                CreateAttachmentRequest(
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size_bytes=len(attachment.content),
                    storage_key=storage_key,
                ),
                market_id,
                actor=f"email-inbound:{message.external_id}",
                attachment_id=attachment_id,
                scan_status_override=scan_status,
                scan_result_override=(
                    f"Email inbound attachment from {message.external_id}. {scan_result}"
                ),
            )
            attachment_ids.append(created.id)
        return attachment_ids, saved, blocked, skipped

    def sync(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int,
    ) -> InboundSyncResult:
        account = self._sync_ready_account(db, market_id)
        email_settings = email_provider_settings_repository.runtime_settings(db, market_id=market_id)
        base = self._base_result(account=account, email_settings=email_settings)
        if not base.live_intake:
            return base
        if account is None:
            return base

        client = None
        processed = succeeded = deduplicated = failed = 0
        message_ids: list[str] = []
        attachment_ids: list[str] = []
        attachments_saved = attachments_blocked = attachments_skipped = 0
        errors: list[str] = []
        try:
            if not email_settings.inbound_username:
                raise ValueError("IMAP username is not configured.")
            client = self._connect(email_settings)
            client.login(email_settings.inbound_username, email_settings.inbound_password or "")
            client.select(email_settings.inbound_mailbox)
            status, search_data = client.uid("search", None, "UNSEEN")  # type: ignore[arg-type]
            if status != "OK" or not search_data:
                return InboundSyncResult(**base.to_details())
            search_bytes = search_data[0] if isinstance(search_data[0], bytes) else b""
            uids: list[bytes] = search_bytes.split()[:limit]
            market_record = db.get(MarketRecord, market_id)
            if market_record is None:
                raise ValueError("Market not found for email intake sync.")
            workspace_settings = workspace_settings_from_record(
                get_or_create_workspace_settings(db, market_from_record(market_record))
            )
            for uid in uids:
                processed += 1
                uid_text = uid.decode()
                try:
                    fetch_status, fetch_data = client.uid("fetch", uid_text, "(RFC822)")
                    raw_message = self._extract_raw_message(fetch_data or [])
                    if fetch_status != "OK" or raw_message is None:
                        raise ValueError(f"Unable to fetch IMAP UID {uid_text}.")
                    inbound_message = self._parse_message(
                        uid,
                        raw_message,
                        mailbox=email_settings.inbound_mailbox,
                    )
                    result = ticket_repository.ingest_connector(
                        db,
                        state,
                        ConnectorInboundRequest(
                            provider=ChannelType.email,
                            external_id=inbound_message.external_id,
                            customer_name=inbound_message.customer_name,
                            customer_email=inbound_message.customer_email,
                            subject=inbound_message.subject,
                            body=inbound_message.body,
                            handle=inbound_message.handle,
                            metadata=inbound_message.metadata,
                        ),
                        market_id,
                        ai_enabled=workspace_settings.ai_work_queue_automation_enabled,
                    )
                    message_ids.append(inbound_message.external_id)
                    if result.get("deduplicated"):
                        deduplicated += 1
                    else:
                        succeeded += 1
                        ticket_obj = result.get("ticket")
                        ticket_id = (
                            getattr(ticket_obj, "id", None)
                            if ticket_obj is not None
                            else None
                        )
                        if ticket_id is None and isinstance(ticket_obj, dict):
                            ticket_id = ticket_obj.get("id")
                        if ticket_id and inbound_message.attachments:
                            ids, saved, blocked, skipped = self._attach_message_files(
                                db,
                                state,
                                market_id=market_id,
                                ticket_id=str(ticket_id),
                                message=inbound_message,
                            )
                            attachment_ids.extend(ids)
                            attachments_saved += saved
                            attachments_blocked += blocked
                            attachments_skipped += skipped
                        else:
                            attachments_skipped += len(
                                inbound_message.metadata.get("skipped_attachments") or []
                            )
                    if email_settings.inbound_mark_seen:
                        client.uid("store", uid_text, "+FLAGS", "(\\Seen)")
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    errors.append(str(exc))
            account.last_sync_at = utc_now()
            account.last_error = errors[-1] if errors else None
            if errors:
                account.failure_count = (account.failure_count or 0) + len(errors)
            else:
                account.failure_count = 0
            db.flush()
            return InboundSyncResult(
                provider=ChannelType.email.value,
                adapter=self.name,
                configured=True,
                live_intake=True,
                polling_enabled=True,
                processed=processed,
                succeeded=succeeded,
                deduplicated=deduplicated,
                failed=failed,
                message_ids=message_ids,
                attachment_ids=attachment_ids,
                attachments_saved=attachments_saved,
                attachments_blocked=attachments_blocked,
                attachments_skipped=attachments_skipped,
                errors=errors,
                missing_settings=[],
            )
        except Exception as exc:
            if account is not None:
                account.last_error = str(exc)
                account.failure_count = (account.failure_count or 0) + 1
                db.flush()
            return InboundSyncResult(
                provider=ChannelType.email.value,
                adapter=self.name,
                configured=True,
                live_intake=True,
                polling_enabled=True,
                failed=1,
                errors=[str(exc)],
                missing_settings=[],
            )
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class InboundAdapterRouter:
    def __init__(self) -> None:
        self.email_imap = ImapEmailInboundAdapter()

    def _signed_webhook_config(
        self,
        *,
        provider: ChannelType,
        account: ConnectorAccountRecord | None,
        label: str,
        pending_note: str,
        active_note: str,
    ) -> InboundProviderConfig:
        missing: list[str] = []
        if account is None:
            missing.append(f"{label} webhook credentials")
        else:
            allowed_statuses = {"connected"} if settings.production_like else {"connected", "mocked"}
            if account.status not in allowed_statuses:
                missing.append(f"{label} connector connected status")
            if not account.intake_enabled:
                missing.append(f"{label} intake enabled")
            if not account.webhook_verified:
                missing.append(f"{label} webhook verification")
            if not account.secret_configured or not account.credential_ref:
                missing.append(f"{label} webhook secret reference")
        return InboundProviderConfig(
            provider=provider,
            adapter="signed-webhook",
            configured=not missing,
            live_intake=not missing,
            required_settings=[
                f"{label} connector account connected",
                f"{label} webhook verified",
                f"{label} webhook secret reference",
            ],
            missing_settings=missing,
            notes=active_note if not missing else pending_note,
        )

    def sync_email(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
        *,
        limit: int,
    ) -> InboundSyncResult:
        return self.email_imap.sync(db, state, market_id, limit=limit)

    def config_summary(
        self,
        db: Session | None = None,
        market_id: str | None = None,
    ) -> list[InboundProviderConfig]:
        account = None
        whatsapp_account = None
        facebook_account = None
        instagram_account = None
        sms_account = None
        voice_account = None
        if db is not None and market_id is not None:
            account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.email,
            )
            whatsapp_account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.whatsapp,
            )
            facebook_account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.facebook,
            )
            instagram_account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.instagram,
            )
            sms_account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.sms,
            )
            voice_account = connector_account_repository.get_account_for_provider(
                db,
                market_id=market_id,
                provider=ChannelType.voice,
            )
        email_settings = email_provider_settings_repository.runtime_settings(db, market_id=market_id)
        email_config = self.email_imap.config_summary(account, email_settings)
        whatsapp_config = self._signed_webhook_config(
            provider=ChannelType.whatsapp,
            account=whatsapp_account,
            label="WhatsApp Business",
            pending_note="WhatsApp signed webhook intake and delivery receipts remain pending.",
            active_note="WhatsApp signed webhook intake and delivery receipts are active.",
        )
        facebook_config = self._signed_webhook_config(
            provider=ChannelType.facebook,
            account=facebook_account,
            label="Facebook Messenger",
            pending_note="Facebook Messenger signed webhook intake and delivery receipts remain pending.",
            active_note="Facebook Messenger signed webhook intake and delivery receipts are active.",
        )
        instagram_config = self._signed_webhook_config(
            provider=ChannelType.instagram,
            account=instagram_account,
            label="Instagram DM",
            pending_note="Instagram DM signed webhook intake and delivery receipts remain pending.",
            active_note="Instagram DM signed webhook intake and delivery receipts are active.",
        )
        sms_config = self._signed_webhook_config(
            provider=ChannelType.sms,
            account=sms_account,
            label="SMS provider",
            pending_note="SMS signed webhook intake and delivery receipts remain pending.",
            active_note="SMS signed webhook intake and delivery receipts are active.",
        )
        voice_config = self._signed_webhook_config(
            provider=ChannelType.voice,
            account=voice_account,
            label="Voice provider",
            pending_note="Voice signed webhook intake and call-status receipts remain pending.",
            active_note="Voice signed webhook intake and call-status receipts are active.",
        )
        return [
            email_config,
            whatsapp_config,
            facebook_config,
            instagram_config,
            sms_config,
            voice_config,
        ]


inbound_adapter_router = InboundAdapterRouter()
