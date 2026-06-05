from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from app.models.domain import ChannelType, ConnectorInboundRequest


RECEIPT_EVENT_TYPES = {
    "delivery_receipt",
    "delivery-status",
    "delivery_status",
    "message_status",
    "status",
    "statuses",
}
INBOUND_EVENT_TYPES = {
    "inbound",
    "inbound_message",
    "message",
    "message.received",
    "whatsapp_message",
}


@dataclass(frozen=True)
class WhatsAppDeliveryReceipt:
    status: str
    provider_message_id: str | None = None
    outbound_message_id: str | None = None
    idempotency_key: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WhatsAppWebhookEvent:
    kind: str
    inbound: ConnectorInboundRequest | None = None
    receipt: WhatsAppDeliveryReceipt | None = None


class WhatsAppWebhookAdapter:
    def webhook_external_id(self, payload: dict[str, Any], delivery_id: str | None = None) -> str:
        status = self._first_status(payload)
        if status is not None or self._is_flat_receipt(payload):
            provider_message_id = self._first_text(
                status or payload,
                "provider_message_id",
                "message_id",
                "messageId",
                "id",
                "wamid",
                "reference",
            )
            if delivery_id:
                return f"receipt:{delivery_id}"
            if provider_message_id:
                receipt_status = self._receipt_status(status or payload) or "unknown"
                return f"receipt:{provider_message_id}:{receipt_status}"

        message, _value = self._first_message(payload)
        provider_message_id = self._first_text(
            message or payload,
            "external_id",
            "message_id",
            "messageId",
            "id",
            "wamid",
            "reference",
            "provider_id",
        )
        if provider_message_id:
            return provider_message_id
        if delivery_id:
            return f"whatsapp:webhook:{delivery_id}"
        body = json.dumps(payload, sort_keys=True, default=str)
        return f"whatsapp:webhook:{hashlib.sha256(body.encode()).hexdigest()[:24]}"

    def parse(
        self,
        payload: dict[str, Any],
        *,
        metadata: dict[str, Any],
        delivery_id: str | None = None,
    ) -> WhatsAppWebhookEvent:
        if self._first_status(payload) is not None or self._is_flat_receipt(payload):
            return WhatsAppWebhookEvent(
                kind="delivery_receipt",
                receipt=self._receipt(payload),
            )
        return WhatsAppWebhookEvent(
            kind="inbound",
            inbound=self._inbound(payload, metadata, delivery_id),
        )

    def _first_status(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        for value in self._change_values(payload):
            statuses = value.get("statuses")
            if not isinstance(statuses, list):
                continue
            for status in statuses:
                if isinstance(status, dict):
                    return status
        return None

    def _first_message(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        for value in self._change_values(payload):
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for message in messages:
                if isinstance(message, dict):
                    return message, value
        return None, None

    def _change_values(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        entries = payload.get("entry")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                changes = entry.get("changes")
                if not isinstance(changes, list):
                    continue
                for change in changes:
                    if not isinstance(change, dict):
                        continue
                    value = change.get("value")
                    if isinstance(value, dict):
                        values.append(value)
        if payload.get("messages") or payload.get("statuses"):
            values.append(payload)
        return values

    def _is_flat_receipt(self, payload: dict[str, Any]) -> bool:
        event_type = self._event_type(payload)
        if event_type in RECEIPT_EVENT_TYPES:
            return True
        if event_type in INBOUND_EVENT_TYPES:
            return False
        return any(
            self._first_text(payload, key)
            for key in ("outbound_message_id", "omni_outbound_message_id", "idempotency_key")
        ) and bool(self._receipt_status(payload))

    def _event_type(self, payload: dict[str, Any]) -> str:
        return (
            self._first_text(payload, "event_type", "event", "type", "message_type") or ""
        ).strip().lower()

    def _receipt_status(self, payload: dict[str, Any]) -> str | None:
        return self._first_text(
            payload,
            "status",
            "delivery_status",
            "message_status",
            "state",
        )

    def _receipt(self, payload: dict[str, Any]) -> WhatsAppDeliveryReceipt:
        status_payload = self._first_status(payload) or payload
        status_value = self._receipt_status(status_payload) or "unknown"
        return WhatsAppDeliveryReceipt(
            status=status_value,
            provider_message_id=self._first_text(
                status_payload,
                "provider_message_id",
                "message_id",
                "messageId",
                "id",
                "wamid",
                "reference",
            ),
            outbound_message_id=self._first_text(
                payload,
                "outbound_message_id",
                "omni_outbound_message_id",
            ),
            idempotency_key=self._first_text(payload, "idempotency_key", "client_reference"),
            raw_payload=payload,
        )

    def _inbound(
        self,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        delivery_id: str | None,
    ) -> ConnectorInboundRequest:
        message, value = self._first_message(payload)
        message_payload = message or payload
        value_payload = value or {}
        handle = self._first_text(message_payload, "from", "sender", "wa_id", "phone", "handle") or ""
        body = self._message_body(message_payload)
        external_id = self.webhook_external_id(payload, delivery_id)
        profile_name = self._profile_name(value_payload, handle) or self._first_text(
            payload,
            "customer_name",
            "name",
            "profile_name",
        )
        customer_email = (
            self._first_text(payload, "customer_email", "email")
            or self._synthetic_email(handle or external_id)
        )
        metadata_payload = {
            **metadata,
            "whatsapp_webhook_payload": payload,
            "whatsapp_event_kind": "inbound",
            "whatsapp_message_type": self._first_text(message_payload, "type"),
            "whatsapp_phone_number_id": self._phone_number_id(value_payload),
        }
        return ConnectorInboundRequest(
            provider=ChannelType.whatsapp,
            external_id=external_id,
            customer_name=profile_name or handle or "WhatsApp Customer",
            customer_email=customer_email,
            subject=self._first_text(payload, "subject") or f"WhatsApp from {profile_name or handle or 'customer'}",
            body=body,
            handle=handle or None,
            metadata=metadata_payload,
        )

    def _message_body(self, message: dict[str, Any]) -> str:
        text = message.get("text")
        if isinstance(text, dict):
            body = self._first_text(text, "body")
            if body:
                return body
        body = self._first_text(message, "body", "text", "message", "content")
        if body:
            return body
        message_type = self._first_text(message, "type") or "unknown"
        return f"[WhatsApp {message_type} message received]"

    def _profile_name(self, value: dict[str, Any], handle: str) -> str | None:
        contacts = value.get("contacts")
        if not isinstance(contacts, list):
            return None
        fallback_name: str | None = None
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            profile = contact.get("profile")
            name = self._first_text(profile, "name") if isinstance(profile, dict) else None
            if name and not fallback_name:
                fallback_name = name
            wa_id = self._first_text(contact, "wa_id")
            if handle and wa_id == handle and name:
                return name
        return fallback_name

    def _phone_number_id(self, value: dict[str, Any]) -> str | None:
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            return self._first_text(metadata, "phone_number_id")
        return None

    def _synthetic_email(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "", value).lower() or "unknown"
        return f"whatsapp-{normalized[:80]}@whatsapp.omniticket.app"

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


whatsapp_webhook_adapter = WhatsAppWebhookAdapter()
