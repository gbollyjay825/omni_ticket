from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from app.models.domain import ChannelType, ConnectorInboundRequest


RECEIPT_EVENT_TYPES = {
    "delivery",
    "delivery_receipt",
    "delivery-status",
    "delivery_status",
    "message_delivered",
    "message_read",
    "messaging_seen",
    "read",
    "seen",
    "status",
}
INBOUND_EVENT_TYPES = {
    "instagram_message",
    "inbound",
    "inbound_message",
    "message",
    "message.received",
    "postback",
}


@dataclass(frozen=True)
class InstagramDeliveryReceipt:
    status: str
    provider_message_id: str | None = None
    outbound_message_id: str | None = None
    idempotency_key: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InstagramWebhookEvent:
    kind: str
    inbound: ConnectorInboundRequest | None = None
    receipt: InstagramDeliveryReceipt | None = None


class InstagramWebhookAdapter:
    def webhook_external_id(self, payload: dict[str, Any], delivery_id: str | None = None) -> str:
        event = self._first_messaging(payload)
        if (event is not None and self._messaging_receipt_status(event)) or self._is_flat_receipt(payload):
            provider_message_id = self._receipt_provider_message_id(event or payload)
            if delivery_id:
                return f"receipt:{delivery_id}"
            if provider_message_id:
                status = self._messaging_receipt_status(event or payload) or self._receipt_status(payload) or "unknown"
                return f"receipt:{provider_message_id}:{status}"

        message_payload = self._message_payload(event or payload)
        provider_message_id = self._first_text(
            message_payload or payload,
            "external_id",
            "message_id",
            "messageId",
            "id",
            "mid",
            "reference",
            "provider_id",
        )
        if provider_message_id:
            return provider_message_id
        if delivery_id:
            return f"instagram:webhook:{delivery_id}"
        body = json.dumps(payload, sort_keys=True, default=str)
        return f"instagram:webhook:{hashlib.sha256(body.encode()).hexdigest()[:24]}"

    def parse(
        self,
        payload: dict[str, Any],
        *,
        metadata: dict[str, Any],
        delivery_id: str | None = None,
    ) -> InstagramWebhookEvent:
        event = self._first_messaging(payload)
        if (event is not None and self._messaging_receipt_status(event)) or self._is_flat_receipt(payload):
            return InstagramWebhookEvent(
                kind="delivery_receipt",
                receipt=self._receipt(payload),
            )
        return InstagramWebhookEvent(
            kind="inbound",
            inbound=self._inbound(payload, metadata, delivery_id),
        )

    def _first_messaging(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        entries = payload.get("entry")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                messaging_events = entry.get("messaging")
                if not isinstance(messaging_events, list):
                    continue
                for event in messaging_events:
                    if isinstance(event, dict):
                        return event
        if any(key in payload for key in ("message", "postback", "delivery", "read", "seen", "message_seen")):
            return payload
        return None

    def _message_payload(self, event: dict[str, Any]) -> dict[str, Any] | None:
        message = event.get("message")
        if isinstance(message, dict) and not message.get("is_echo"):
            return message
        postback = event.get("postback")
        if isinstance(postback, dict):
            return postback
        return None

    def _messaging_receipt_status(self, event: dict[str, Any]) -> str | None:
        delivery = event.get("delivery")
        if isinstance(delivery, dict):
            return "delivered"
        for key in ("read", "seen", "message_seen"):
            value = event.get(key)
            if isinstance(value, dict):
                return "read"
        message = event.get("message")
        if isinstance(message, dict) and message.get("is_echo"):
            return "echo"
        return None

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

    def _receipt_provider_message_id(self, event: dict[str, Any]) -> str | None:
        delivery = event.get("delivery")
        if isinstance(delivery, dict):
            mids = delivery.get("mids")
            if isinstance(mids, list):
                for mid in mids:
                    if mid:
                        return str(mid)
            return self._first_text(delivery, "mid", "message_id", "messageId", "id")
        for key in ("read", "seen", "message_seen"):
            status_payload = event.get(key)
            if isinstance(status_payload, dict):
                return self._first_text(status_payload, "mid", "message_id", "messageId", "id")
        message = event.get("message")
        if isinstance(message, dict):
            return self._first_text(message, "mid", "message_id", "messageId", "id")
        return self._first_text(
            event,
            "provider_message_id",
            "message_id",
            "messageId",
            "id",
            "mid",
            "reference",
        )

    def _receipt(self, payload: dict[str, Any]) -> InstagramDeliveryReceipt:
        event = self._first_messaging(payload) or payload
        status_value = self._messaging_receipt_status(event) or self._receipt_status(payload) or "unknown"
        return InstagramDeliveryReceipt(
            status=status_value,
            provider_message_id=self._receipt_provider_message_id(event),
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
        event = self._first_messaging(payload) or payload
        message_payload = self._message_payload(event) or payload
        handle = (
            self._sender_id(event)
            or self._first_text(payload, "from", "sender", "igsid", "instagram_scoped_id", "handle")
            or ""
        )
        body = self._message_body(message_payload)
        external_id = self.webhook_external_id(payload, delivery_id)
        customer_email = (
            self._first_text(payload, "customer_email", "email")
            or self._synthetic_email(handle or external_id)
        )
        customer_name = (
            self._first_text(payload, "customer_name", "name", "profile_name", "username")
            or handle
            or "Instagram Customer"
        )
        metadata_payload = {
            **metadata,
            "instagram_webhook_payload": payload,
            "instagram_event_kind": "inbound",
            "instagram_business_account_id": self._recipient_id(event),
            "instagram_message_type": "postback" if isinstance(event.get("postback"), dict) else "message",
        }
        return ConnectorInboundRequest(
            provider=ChannelType.instagram,
            external_id=external_id,
            customer_name=customer_name,
            customer_email=customer_email,
            subject=self._first_text(payload, "subject") or f"Instagram DM from {customer_name}",
            body=body,
            handle=handle or None,
            metadata=metadata_payload,
        )

    def _message_body(self, message: dict[str, Any]) -> str:
        text = self._first_text(message, "text", "title", "payload", "body", "message", "content")
        if text:
            payload = self._first_text(message, "payload")
            if payload and payload != text and self._first_text(message, "title"):
                return f"{text}\n\nPayload: {payload}"
            return text
        attachments = message.get("attachments")
        if isinstance(attachments, list) and attachments:
            return "[Instagram DM attachment received]"
        return "[Instagram DM message received]"

    def _sender_id(self, event: dict[str, Any]) -> str | None:
        sender = event.get("sender")
        if isinstance(sender, dict):
            return self._first_text(sender, "id")
        return None

    def _recipient_id(self, event: dict[str, Any]) -> str | None:
        recipient = event.get("recipient")
        if isinstance(recipient, dict):
            return self._first_text(recipient, "id")
        return None

    def _synthetic_email(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "", value).lower() or "unknown"
        return f"instagram-{normalized[:80]}@instagram.omniticket.app"

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


instagram_webhook_adapter = InstagramWebhookAdapter()
