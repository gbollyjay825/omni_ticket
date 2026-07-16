from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
import json
import re
import smtplib
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from app.core.config import settings
from app.db.email_settings import (
    RuntimeEmailProviderSettings,
    email_provider_settings_repository,
)
from app.db.integration_credentials import (
    RuntimeIntegrationCredentials,
    integration_credential_settings_repository,
)
from app.db.models import (
    ChatConversationRecord,
    ConnectorAccountRecord,
    CustomerRecord,
    MarketRecord,
    OutboundMessageRecord,
    TicketRecord,
)
from app.models.domain import ChannelType, OutboundProviderConfig


@dataclass(frozen=True)
class OutboundSendContext:
    account: ConnectorAccountRecord
    ticket: TicketRecord | None
    message: OutboundMessageRecord
    customer: CustomerRecord | None
    market: MarketRecord | None
    conversation: ChatConversationRecord | None = None
    email_settings: RuntimeEmailProviderSettings | None = None
    integration_credentials: RuntimeIntegrationCredentials | None = None

    @property
    def source_id(self) -> str:
        return self.ticket.id if self.ticket is not None else self.conversation.id if self.conversation else ""

    @property
    def source_public_id(self) -> str:
        if self.ticket is not None:
            return self.ticket.public_id
        return self.conversation.public_id if self.conversation else ""

    @property
    def source_customer_id(self) -> str:
        if self.ticket is not None:
            return self.ticket.customer_id
        return self.conversation.customer_id if self.conversation else ""

    @property
    def source_subject(self) -> str:
        if self.ticket is not None:
            return self.ticket.subject
        return self.conversation.subject if self.conversation else ""


@dataclass(frozen=True)
class OutboundSendResult:
    succeeded: bool
    adapter: str
    external_id: str | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class OutboundAdapter(Protocol):
    name: str

    def send(self, context: OutboundSendContext) -> OutboundSendResult: ...


class LocalDevOutboundAdapter:
    name = "local-dev"

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        if not settings.outbound_local_adapter_enabled:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"No live {context.message.provider} outbound adapter is configured.",
            )
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=f"local-dev:{context.message.id}",
            payload={"mode": "local-dev", "provider": context.message.provider},
        )


class SmtpEmailOutboundAdapter:
    name = "smtp"
    deployed_environments = {"staging", "production", "pulse-vm"}
    reserved_recipient_domains = {"example.com", "example.net", "example.org", "invalid", "test"}

    def configured(self, email_settings: RuntimeEmailProviderSettings | None = None) -> bool:
        config = email_settings or email_provider_settings_repository.runtime_settings()
        return bool(config.outbound_enabled and config.outbound_host)

    def _from_address(self, context: OutboundSendContext) -> str:
        email_settings = context.email_settings or email_provider_settings_repository.runtime_settings()
        return (
            email_settings.outbound_from_email
            or context.account.account_identifier
            or (context.market.support_email if context.market else "")
        )

    def _subject(self, context: OutboundSendContext) -> str:
        payload_subject = str((context.message.payload or {}).get("subject") or "").strip()
        if payload_subject:
            return payload_subject
        subject = context.source_subject.strip() or "Omni support update"
        if context.source_public_id and context.source_public_id not in subject:
            return f"Re: {subject} [{context.source_public_id}]"
        return f"Re: {subject}"

    def _set_optional_header(self, message: EmailMessage, header: str, value: object) -> None:
        text = str(value or "").strip()
        if text:
            message[header] = text

    def _non_routable_recipient(self, address: str) -> bool:
        domain = address.strip().lower().rsplit("@", 1)[-1]
        return any(
            domain == reserved or domain.endswith(f".{reserved}")
            for reserved in self.reserved_recipient_domains
        )

    def _build_message(self, context: OutboundSendContext) -> EmailMessage | None:
        payload = context.message.payload or {}
        to_address = str(payload.get("to_email") or "").strip()
        if not to_address and context.customer is not None:
            to_address = context.customer.email
        if not to_address:
            return None
        from_address = self._from_address(context)
        if not from_address:
            return None
        message = EmailMessage()
        message["From"] = from_address
        message["To"] = to_address
        message["Subject"] = self._subject(context)
        message["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])
        if context.ticket is not None:
            message["X-Omni-Ticket-ID"] = context.ticket.id
        if context.conversation is not None:
            message["X-Omni-Conversation-ID"] = context.conversation.id
        message["X-Omni-Market-ID"] = context.message.market_id
        if payload.get("handoff_id"):
            message["X-Omni-Handoff-ID"] = str(payload["handoff_id"])
        self._set_optional_header(message, "X-Omni-Source-Ticket-ID", payload.get("source_ticket_id"))
        self._set_optional_header(
            message,
            "X-Omni-Source-Ticket-Public-ID",
            payload.get("source_ticket_public_id"),
        )
        self._set_optional_header(message, "X-Omni-Linked-Ticket-ID", payload.get("linked_ticket_id"))
        self._set_optional_header(
            message,
            "X-Omni-Linked-Ticket-Public-ID",
            payload.get("linked_ticket_public_id"),
        )
        self._set_optional_header(
            message,
            "X-Omni-Reply-Target",
            payload.get("reply_target"),
        )
        self._set_optional_header(
            message,
            "X-Omni-Reply-Target-Ticket-ID",
            payload.get("reply_target_ticket_id"),
        )
        if payload.get("source"):
            message["X-Omni-Delivery-Mode"] = str(payload["source"])
        self._set_optional_header(message, "In-Reply-To", payload.get("in_reply_to"))
        references = payload.get("references")
        if isinstance(references, list):
            references = " ".join(str(reference).strip() for reference in references if reference)
        self._set_optional_header(message, "References", references)
        message.set_content(context.message.body)
        return message

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        email_settings = context.email_settings or email_provider_settings_repository.runtime_settings()
        if not email_settings.outbound_enabled or not email_settings.outbound_host:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="SMTP email delivery is not configured.",
            )
        email = self._build_message(context)
        if email is None:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="Email delivery requires a recipient address and sender address.",
            )
        recipient = str(email["To"] or "").strip()
        if (
            settings.environment.strip().lower() in self.deployed_environments
            and self._non_routable_recipient(recipient)
        ):
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=(
                    "Email recipient uses a non-routable placeholder domain. "
                    "Configure the real customer or team address before delivery."
                ),
            )
        smtp_class = smtplib.SMTP_SSL if email_settings.outbound_use_ssl else smtplib.SMTP
        try:
            with smtp_class(
                email_settings.outbound_host,
                email_settings.outbound_port,
                timeout=settings.email_smtp_timeout_seconds,
            ) as smtp:
                if email_settings.outbound_use_starttls and not email_settings.outbound_use_ssl:
                    smtp.starttls()
                if email_settings.outbound_username:
                    smtp.login(
                        email_settings.outbound_username,
                        email_settings.outbound_password or "",
                    )
                smtp.send_message(email)
        except (OSError, smtplib.SMTPException) as exc:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=str(exc),
            )
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=email["Message-ID"],
            payload={
                "message_id": email["Message-ID"],
                "to": email["To"],
                "from": email["From"],
                "subject": email["Subject"],
                "reply_target_ticket_id": email.get("X-Omni-Reply-Target-Ticket-ID"),
                "handoff_id": email.get("X-Omni-Handoff-ID"),
            },
        )


class HttpSmsOutboundAdapter:
    name = "http-sms"

    def _credentials(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> RuntimeIntegrationCredentials:
        return credentials or integration_credential_settings_repository.runtime_credentials()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return not self.missing_settings(credentials)

    def missing_settings(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> list[str]:
        config = self._credentials(credentials)
        missing: list[str] = []
        if not config.sms_http_endpoint:
            missing.append("SMS HTTP endpoint")
        if not config.sms_http_auth_token:
            missing.append("SMS auth token")
        if not config.sms_http_from:
            missing.append("SMS sender")
        return missing

    def _recipient(self, context: OutboundSendContext) -> str | None:
        if context.customer is None:
            return None
        contact_points = context.customer.contact_points or []
        preferred_channels = (ChannelType.sms.value, ChannelType.whatsapp.value, ChannelType.voice.value)
        for channel in preferred_channels:
            for point in contact_points:
                if point.get("channel") != channel:
                    continue
                value = self._normalize_phone(str(point.get("value", "")))
                if value:
                    return value
        return None

    def _normalize_phone(self, value: str) -> str:
        value = value.strip()
        if value.lower().startswith("tel:"):
            value = value[4:]
        return (
            value.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

    def _auth_value(self, credentials: RuntimeIntegrationCredentials) -> str:
        token = credentials.sms_http_auth_token or ""
        scheme = credentials.sms_http_auth_scheme.strip()
        return f"{scheme} {token}".strip() if scheme else token

    def _provider_message_id(self, response_payload: dict[str, Any], fallback: str) -> str:
        for key in ("message_id", "messageId", "id", "sid", "reference", "provider_id"):
            value = response_payload.get(key)
            if value:
                return str(value)
        nested = response_payload.get("data")
        if isinstance(nested, dict):
            for key in ("message_id", "messageId", "id", "sid", "reference", "provider_id"):
                value = nested.get(key)
                if value:
                    return str(value)
        return fallback

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        credentials = self._credentials(context.integration_credentials)
        missing = self.missing_settings(credentials)
        if missing:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"SMS HTTP delivery is missing settings: {', '.join(missing)}.",
            )
        recipient = self._recipient(context)
        if not recipient:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="SMS delivery requires a customer SMS, WhatsApp, or voice contact point.",
            )

        payload: dict[str, Any] = {
            "to": recipient,
            "from": credentials.sms_http_from,
            "body": context.message.body,
            "market_id": context.message.market_id,
            "ticket_id": context.ticket.id if context.ticket else None,
            "conversation_id": context.conversation.id if context.conversation else None,
            "public_id": context.source_public_id,
            "idempotency_key": context.message.idempotency_key,
            "metadata": {
                "outbound_message_id": context.message.id,
                "connector_event_id": context.message.connector_event_id,
                "actor": context.message.actor,
            },
        }
        if credentials.sms_http_delivery_callback_url:
            payload["callback_url"] = credentials.sms_http_delivery_callback_url

        headers = {
            "Content-Type": "application/json",
            "X-Omni-Idempotency-Key": context.message.idempotency_key,
        }
        headers[credentials.sms_http_auth_header] = self._auth_value(credentials)

        request = urlrequest.Request(
            credentials.sms_http_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.sms_http_timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"SMS provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return OutboundSendResult(succeeded=False, adapter=self.name, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if status_code < 200 or status_code >= 300:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"SMS provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )

        external_id = self._provider_message_id(provider_response, f"sms-http:{context.message.id}")
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=external_id,
            payload={
                "to": recipient,
                "from": credentials.sms_http_from,
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )


class HttpVoiceOutboundAdapter:
    name = "http-voice"

    def _credentials(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> RuntimeIntegrationCredentials:
        return credentials or integration_credential_settings_repository.runtime_credentials()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return not self.missing_settings(credentials)

    def missing_settings(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> list[str]:
        config = self._credentials(credentials)
        missing: list[str] = []
        if not config.voice_http_endpoint:
            missing.append("Voice HTTP endpoint")
        if not config.voice_http_auth_token:
            missing.append("Voice auth token")
        if not config.voice_http_from:
            missing.append("Voice caller ID")
        return missing

    def _recipient(self, context: OutboundSendContext) -> str | None:
        if context.customer is None:
            return None
        contact_points = context.customer.contact_points or []
        preferred_channels = (ChannelType.voice.value, ChannelType.sms.value, ChannelType.whatsapp.value)
        for channel in preferred_channels:
            for point in contact_points:
                if point.get("channel") != channel:
                    continue
                value = self._normalize_phone(str(point.get("value", "")))
                if value:
                    return value
        return None

    def _normalize_phone(self, value: str) -> str:
        value = value.strip()
        for prefix in ("tel:", "voice:", "phone:"):
            if value.lower().startswith(prefix):
                value = value.split(":", 1)[1]
                break
        return (
            value.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

    def _auth_value(self, credentials: RuntimeIntegrationCredentials) -> str:
        token = credentials.voice_http_auth_token or ""
        scheme = credentials.voice_http_auth_scheme.strip()
        return f"{scheme} {token}".strip() if scheme else token

    def _provider_call_id(self, response_payload: dict[str, Any], fallback: str) -> str:
        for key in ("call_id", "callId", "message_id", "messageId", "id", "sid", "reference", "provider_id"):
            value = response_payload.get(key)
            if value:
                return str(value)
        nested = response_payload.get("data")
        if isinstance(nested, dict):
            for key in ("call_id", "callId", "message_id", "messageId", "id", "sid", "reference", "provider_id"):
                value = nested.get(key)
                if value:
                    return str(value)
        return fallback

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        credentials = self._credentials(context.integration_credentials)
        missing = self.missing_settings(credentials)
        if missing:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Voice HTTP delivery is missing settings: {', '.join(missing)}.",
            )
        recipient = self._recipient(context)
        if not recipient:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="Voice delivery requires a customer voice, SMS, or WhatsApp phone contact point.",
            )

        payload: dict[str, Any] = {
            "action": "callback_request",
            "to": recipient,
            "from": credentials.voice_http_from,
            "body": context.message.body,
            "market_id": context.message.market_id,
            "ticket_id": context.ticket.id if context.ticket else None,
            "conversation_id": context.conversation.id if context.conversation else None,
            "public_id": context.source_public_id,
            "idempotency_key": context.message.idempotency_key,
            "metadata": {
                "outbound_message_id": context.message.id,
                "connector_event_id": context.message.connector_event_id,
                "actor": context.message.actor,
                "customer_id": context.source_customer_id,
            },
        }
        if credentials.voice_http_status_callback_url:
            payload["status_callback_url"] = credentials.voice_http_status_callback_url

        headers = {
            "Content-Type": "application/json",
            "X-Omni-Idempotency-Key": context.message.idempotency_key,
        }
        headers[credentials.voice_http_auth_header] = self._auth_value(credentials)

        request = urlrequest.Request(
            credentials.voice_http_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.voice_http_timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Voice provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return OutboundSendResult(succeeded=False, adapter=self.name, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if status_code < 200 or status_code >= 300:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Voice provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )

        external_id = self._provider_call_id(provider_response, f"voice-http:{context.message.id}")
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=external_id,
            payload={
                "to": recipient,
                "from": credentials.voice_http_from,
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )


class WhatsAppCloudOutboundAdapter:
    name = "whatsapp-cloud"

    def _credentials(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> RuntimeIntegrationCredentials:
        return credentials or integration_credential_settings_repository.runtime_credentials()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return not self.missing_settings(credentials)

    def missing_settings(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> list[str]:
        config = self._credentials(credentials)
        missing: list[str] = []
        if not config.whatsapp_cloud_api_base_url:
            missing.append("WhatsApp Cloud API base URL")
        if not config.whatsapp_phone_number_id:
            missing.append("WhatsApp phone number ID")
        if not config.whatsapp_access_token:
            missing.append("WhatsApp access token")
        return missing

    def _recipient(self, context: OutboundSendContext) -> str | None:
        if context.customer is None:
            return None
        contact_points = context.customer.contact_points or []
        preferred_channels = (ChannelType.whatsapp.value, ChannelType.sms.value, ChannelType.voice.value)
        for channel in preferred_channels:
            for point in contact_points:
                if point.get("channel") != channel:
                    continue
                value = self._normalize_recipient(str(point.get("value", "")))
                if value:
                    return value
        return None

    def _normalize_recipient(self, value: str) -> str:
        normalized = value.strip()
        if normalized.lower().startswith("whatsapp:"):
            normalized = normalized.split(":", 1)[1]
        normalized = re.sub(r"[\s().-]+", "", normalized)
        return normalized.lstrip("+")

    def _endpoint(self, credentials: RuntimeIntegrationCredentials) -> str:
        base_url = credentials.whatsapp_cloud_api_base_url.rstrip("/")
        phone_number_id = credentials.whatsapp_phone_number_id.strip().strip("/")
        return f"{base_url}/{phone_number_id}/messages"

    def _provider_message_id(self, response_payload: dict[str, Any], fallback: str) -> str:
        messages = response_payload.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and message.get("id"):
                    return str(message["id"])
        for key in ("message_id", "messageId", "id", "reference", "provider_id"):
            value = response_payload.get(key)
            if value:
                return str(value)
        return fallback

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        credentials = self._credentials(context.integration_credentials)
        missing = self.missing_settings(credentials)
        if missing:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"WhatsApp Cloud API delivery is missing settings: {', '.join(missing)}.",
            )
        recipient = self._recipient(context)
        if not recipient:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="WhatsApp delivery requires a customer WhatsApp, SMS, or voice contact point.",
            )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "preview_url": credentials.whatsapp_preview_urls,
                "body": context.message.body,
            },
        }
        headers = {
            "Authorization": f"Bearer {credentials.whatsapp_access_token}",
            "Content-Type": "application/json",
            "X-Omni-Idempotency-Key": context.message.idempotency_key,
        }
        request = urlrequest.Request(
            self._endpoint(credentials),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.whatsapp_timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"WhatsApp provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return OutboundSendResult(succeeded=False, adapter=self.name, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if status_code < 200 or status_code >= 300:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"WhatsApp provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )

        external_id = self._provider_message_id(
            provider_response,
            f"whatsapp-cloud:{context.message.id}",
        )
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=external_id,
            payload={
                "to": recipient,
                "phone_number_id": credentials.whatsapp_phone_number_id,
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )


class FacebookMessengerOutboundAdapter:
    name = "facebook-messenger"

    def _credentials(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> RuntimeIntegrationCredentials:
        return credentials or integration_credential_settings_repository.runtime_credentials()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return not self.missing_settings(credentials)

    def missing_settings(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> list[str]:
        config = self._credentials(credentials)
        missing: list[str] = []
        if not config.facebook_graph_api_base_url:
            missing.append("Facebook Graph API base URL")
        if not config.facebook_page_id:
            missing.append("Facebook page ID")
        if not config.facebook_page_access_token:
            missing.append("Facebook page access token")
        return missing

    def _recipient(self, context: OutboundSendContext) -> str | None:
        if context.customer is None:
            return None
        contact_points = context.customer.contact_points or []
        preferred_channels = (ChannelType.facebook.value, "social")
        for channel in preferred_channels:
            for point in contact_points:
                if point.get("channel") != channel:
                    continue
                value = self._normalize_recipient(str(point.get("value", "")))
                if value:
                    return value
        return None

    def _normalize_recipient(self, value: str) -> str:
        normalized = value.strip()
        for prefix in ("fb:", "facebook:", "messenger:", "psid:"):
            if normalized.lower().startswith(prefix):
                normalized = normalized.split(":", 1)[1]
                break
        return normalized.strip()

    def _endpoint(self, credentials: RuntimeIntegrationCredentials) -> str:
        base_url = credentials.facebook_graph_api_base_url.rstrip("/")
        page_id = credentials.facebook_page_id.strip().strip("/")
        return f"{base_url}/{page_id}/messages"

    def _provider_message_id(self, response_payload: dict[str, Any], fallback: str) -> str:
        for key in ("message_id", "messageId", "id", "mid", "reference", "provider_id"):
            value = response_payload.get(key)
            if value:
                return str(value)
        return fallback

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        credentials = self._credentials(context.integration_credentials)
        missing = self.missing_settings(credentials)
        if missing:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Facebook Messenger delivery is missing settings: {', '.join(missing)}.",
            )
        recipient = self._recipient(context)
        if not recipient:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="Facebook Messenger delivery requires a customer Facebook PSID contact point.",
            )

        payload: dict[str, Any] = {
            "recipient": {"id": recipient},
            "messaging_type": credentials.facebook_messaging_type,
            "message": {"text": context.message.body},
        }
        headers = {
            "Authorization": f"Bearer {credentials.facebook_page_access_token}",
            "Content-Type": "application/json",
            "X-Omni-Idempotency-Key": context.message.idempotency_key,
        }
        request = urlrequest.Request(
            self._endpoint(credentials),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.facebook_timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Facebook Messenger provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return OutboundSendResult(succeeded=False, adapter=self.name, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if status_code < 200 or status_code >= 300:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Facebook Messenger provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )

        external_id = self._provider_message_id(
            provider_response,
            f"facebook-messenger:{context.message.id}",
        )
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=external_id,
            payload={
                "to": recipient,
                "page_id": credentials.facebook_page_id,
                "messaging_type": credentials.facebook_messaging_type,
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )


class InstagramDmOutboundAdapter:
    name = "instagram-dm"

    def _credentials(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> RuntimeIntegrationCredentials:
        return credentials or integration_credential_settings_repository.runtime_credentials()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return not self.missing_settings(credentials)

    def missing_settings(
        self,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> list[str]:
        config = self._credentials(credentials)
        missing: list[str] = []
        if not config.instagram_graph_api_base_url:
            missing.append("Instagram Graph API base URL")
        if not config.instagram_business_account_id:
            missing.append("Instagram business account ID")
        if not config.instagram_access_token:
            missing.append("Instagram access token")
        return missing

    def _recipient(self, context: OutboundSendContext) -> str | None:
        if context.customer is None:
            return None
        contact_points = context.customer.contact_points or []
        preferred_channels = (ChannelType.instagram.value, "social")
        for channel in preferred_channels:
            for point in contact_points:
                if point.get("channel") != channel:
                    continue
                value = self._normalize_recipient(str(point.get("value", "")))
                if value:
                    return value
        return None

    def _normalize_recipient(self, value: str) -> str | None:
        normalized = value.strip()
        for prefix in ("ig:", "instagram:", "igsid:", "instagram_scoped_id:"):
            if normalized.lower().startswith(prefix):
                normalized = normalized.split(":", 1)[1]
                break
        normalized = normalized.strip()
        if not normalized or normalized.startswith("@"):
            return None
        return normalized

    def _endpoint(self, credentials: RuntimeIntegrationCredentials) -> str:
        base_url = credentials.instagram_graph_api_base_url.rstrip("/")
        account_id = credentials.instagram_business_account_id.strip().strip("/")
        return f"{base_url}/{account_id}/messages"

    def _provider_message_id(self, response_payload: dict[str, Any], fallback: str) -> str:
        for key in ("message_id", "messageId", "id", "mid", "reference", "provider_id"):
            value = response_payload.get(key)
            if value:
                return str(value)
        return fallback

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        credentials = self._credentials(context.integration_credentials)
        missing = self.missing_settings(credentials)
        if missing:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Instagram DM delivery is missing settings: {', '.join(missing)}.",
            )
        recipient = self._recipient(context)
        if not recipient:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error="Instagram DM delivery requires an Instagram-scoped user ID contact point from a prior webhook.",
            )

        payload: dict[str, Any] = {
            "recipient": {"id": recipient},
            "message": {"text": context.message.body},
        }
        headers = {
            "Authorization": f"Bearer {credentials.instagram_access_token}",
            "Content-Type": "application/json",
            "X-Omni-Idempotency-Key": context.message.idempotency_key,
        }
        request = urlrequest.Request(
            self._endpoint(credentials),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.instagram_timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Instagram DM provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return OutboundSendResult(succeeded=False, adapter=self.name, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if status_code < 200 or status_code >= 300:
            return OutboundSendResult(
                succeeded=False,
                adapter=self.name,
                error=f"Instagram DM provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )

        external_id = self._provider_message_id(
            provider_response,
            f"instagram-dm:{context.message.id}",
        )
        return OutboundSendResult(
            succeeded=True,
            adapter=self.name,
            external_id=external_id,
            payload={
                "to": recipient,
                "business_account_id": credentials.instagram_business_account_id,
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )


class OutboundAdapterRouter:
    def __init__(self) -> None:
        self.local_dev = LocalDevOutboundAdapter()
        self.smtp_email = SmtpEmailOutboundAdapter()
        self.http_sms = HttpSmsOutboundAdapter()
        self.http_voice = HttpVoiceOutboundAdapter()
        self.whatsapp_cloud = WhatsAppCloudOutboundAdapter()
        self.facebook_messenger = FacebookMessengerOutboundAdapter()
        self.instagram_dm = InstagramDmOutboundAdapter()

    def send(self, context: OutboundSendContext) -> OutboundSendResult:
        if (
            context.message.provider == ChannelType.email.value
            and self.smtp_email.configured(context.email_settings)
        ):
            return self.smtp_email.send(context)
        if (
            context.message.provider == ChannelType.whatsapp.value
            and self.whatsapp_cloud.configured(context.integration_credentials)
        ):
            return self.whatsapp_cloud.send(context)
        if (
            context.message.provider == ChannelType.facebook.value
            and self.facebook_messenger.configured(context.integration_credentials)
        ):
            return self.facebook_messenger.send(context)
        if (
            context.message.provider == ChannelType.instagram.value
            and self.instagram_dm.configured(context.integration_credentials)
        ):
            return self.instagram_dm.send(context)
        if (
            context.message.provider == ChannelType.sms.value
            and self.http_sms.configured(context.integration_credentials)
        ):
            return self.http_sms.send(context)
        if (
            context.message.provider == ChannelType.voice.value
            and self.http_voice.configured(context.integration_credentials)
        ):
            return self.http_voice.send(context)
        return self.local_dev.send(context)

    def config_summary(
        self,
        db: Any | None = None,
        market_id: str | None = None,
    ) -> list[OutboundProviderConfig]:
        email_settings = email_provider_settings_repository.runtime_settings(db, market_id=market_id)
        credentials = integration_credential_settings_repository.runtime_credentials(
            db,
            market_id=market_id,
        )
        missing_email: list[str] = []
        if not email_settings.outbound_enabled:
            missing_email.append("Email outbound enabled")
        if not email_settings.outbound_host:
            missing_email.append("SMTP host")
        if email_settings.outbound_use_ssl and email_settings.outbound_use_starttls:
            missing_email.append("Choose SSL or STARTTLS")
        missing_whatsapp = self.whatsapp_cloud.missing_settings(credentials)
        missing_facebook = self.facebook_messenger.missing_settings(credentials)
        missing_instagram = self.instagram_dm.missing_settings(credentials)
        missing_sms = self.http_sms.missing_settings(credentials)
        missing_voice = self.http_voice.missing_settings(credentials)
        return [
            OutboundProviderConfig(
                provider=ChannelType.email,
                adapter=self.smtp_email.name,
                configured=not missing_email,
                live_delivery=not missing_email,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=["SMTP host", "SMTP username", "SMTP password if required"],
                missing_settings=missing_email,
                notes=(
                    "SMTP email delivery is active."
                    if not missing_email
                    else "Email can use the local-dev adapter until SMTP credentials are added."
                ),
            ),
            OutboundProviderConfig(
                provider=ChannelType.whatsapp,
                adapter=self.whatsapp_cloud.name,
                configured=not missing_whatsapp,
                live_delivery=not missing_whatsapp,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=[
                    "WhatsApp Cloud API base URL",
                    "WhatsApp phone number ID",
                    "WhatsApp access token",
                ],
                missing_settings=missing_whatsapp,
                notes=(
                    "WhatsApp Cloud API delivery is active."
                    if not missing_whatsapp
                    else "WhatsApp can use the local-dev adapter until Cloud API credentials are added."
                ),
            ),
            OutboundProviderConfig(
                provider=ChannelType.facebook,
                adapter=self.facebook_messenger.name,
                configured=not missing_facebook,
                live_delivery=not missing_facebook,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=[
                    "Facebook Graph API base URL",
                    "Facebook page ID",
                    "Facebook page access token",
                ],
                missing_settings=missing_facebook,
                notes=(
                    "Facebook Messenger delivery is active."
                    if not missing_facebook
                    else "Facebook Messenger can use the local-dev adapter until page credentials are added."
                ),
            ),
            OutboundProviderConfig(
                provider=ChannelType.instagram,
                adapter=self.instagram_dm.name,
                configured=not missing_instagram,
                live_delivery=not missing_instagram,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=[
                    "Instagram Graph API base URL",
                    "Instagram business account ID",
                    "Instagram access token",
                ],
                missing_settings=missing_instagram,
                notes=(
                    "Instagram DM delivery is active."
                    if not missing_instagram
                    else "Instagram DM can use the local-dev adapter until business account credentials are added."
                ),
            ),
            OutboundProviderConfig(
                provider=ChannelType.sms,
                adapter=self.http_sms.name,
                configured=not missing_sms,
                live_delivery=not missing_sms,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=[
                    "SMS HTTP endpoint",
                    "SMS auth token",
                    "SMS sender",
                ],
                missing_settings=missing_sms,
                notes=(
                    "SMS HTTP provider delivery is active."
                    if not missing_sms
                    else "SMS can use the local-dev adapter until provider HTTP credentials are added."
                ),
            ),
            OutboundProviderConfig(
                provider=ChannelType.voice,
                adapter=self.http_voice.name,
                configured=not missing_voice,
                live_delivery=not missing_voice,
                fallback_adapter=(
                    self.local_dev.name if settings.outbound_local_adapter_enabled else None
                ),
                required_settings=[
                    "Voice HTTP endpoint",
                    "Voice auth token",
                    "Voice caller ID",
                ],
                missing_settings=missing_voice,
                notes=(
                    "Voice HTTP provider delivery is active."
                    if not missing_voice
                    else "Voice can use the local-dev adapter until provider HTTP credentials are added."
                ),
            ),
        ]


outbound_adapter_router = OutboundAdapterRouter()
