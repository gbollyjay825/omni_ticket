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
    "sms_status",
    "status",
}
INBOUND_EVENT_TYPES = {
    "inbound",
    "inbound_message",
    "message.received",
    "sms_received",
}


@dataclass(frozen=True)
class SmsDeliveryReceipt:
    status: str
    provider_message_id: str | None = None
    outbound_message_id: str | None = None
    idempotency_key: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SmsWebhookEvent:
    kind: str
    inbound: ConnectorInboundRequest | None = None
    receipt: SmsDeliveryReceipt | None = None


class SmsWebhookAdapter:
    def webhook_external_id(self, payload: dict[str, Any], delivery_id: str | None = None) -> str:
        provider_message_id = self._first_text(
            payload,
            "external_id",
            "message_id",
            "messageId",
            "id",
            "sid",
            "reference",
            "provider_id",
        )
        if provider_message_id:
            if self._is_receipt(payload):
                if delivery_id:
                    return f"receipt:{delivery_id}"
                receipt_status = self._receipt_status(payload) or "unknown"
                return f"receipt:{provider_message_id}:{receipt_status}"
            return provider_message_id
        if delivery_id:
            return f"sms:webhook:{delivery_id}"
        body = json.dumps(payload, sort_keys=True, default=str)
        return f"sms:webhook:{hashlib.sha256(body.encode()).hexdigest()[:24]}"

    def parse(
        self,
        payload: dict[str, Any],
        *,
        metadata: dict[str, Any],
        delivery_id: str | None = None,
    ) -> SmsWebhookEvent:
        if self._is_receipt(payload):
            return SmsWebhookEvent(kind="delivery_receipt", receipt=self._receipt(payload))
        return SmsWebhookEvent(kind="inbound", inbound=self._inbound(payload, metadata, delivery_id))

    def _is_receipt(self, payload: dict[str, Any]) -> bool:
        event_type = self._event_type(payload)
        if event_type in RECEIPT_EVENT_TYPES:
            return True
        if event_type in INBOUND_EVENT_TYPES:
            return False
        return any(
            self._first_text(payload, key)
            for key in ("outbound_message_id", "omni_outbound_message_id", "idempotency_key")
        )

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

    def _receipt(self, payload: dict[str, Any]) -> SmsDeliveryReceipt:
        status = self._receipt_status(payload) or "unknown"
        return SmsDeliveryReceipt(
            status=status,
            provider_message_id=self._first_text(
                payload,
                "provider_message_id",
                "message_id",
                "messageId",
                "id",
                "sid",
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
        handle = self._first_text(payload, "from", "sender", "msisdn", "phone", "handle") or ""
        body = self._first_text(payload, "body", "text", "message", "content") or ""
        external_id = self.webhook_external_id(payload, delivery_id)
        customer_email = (
            self._first_text(payload, "customer_email", "email")
            or self._synthetic_email(handle or external_id)
        )
        return ConnectorInboundRequest(
            provider=ChannelType.sms,
            external_id=external_id,
            customer_name=(
                self._first_text(payload, "customer_name", "name", "profile_name")
                or handle
                or "SMS Customer"
            ),
            customer_email=customer_email,
            subject=self._first_text(payload, "subject") or f"SMS from {handle or 'customer'}",
            body=body,
            handle=handle or None,
            metadata={**metadata, "sms_webhook_payload": payload, "sms_event_kind": "inbound"},
        )

    def _synthetic_email(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "", value).lower() or "unknown"
        return f"sms-{normalized[:80]}@sms.omniticket.app"

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


sms_webhook_adapter = SmsWebhookAdapter()
