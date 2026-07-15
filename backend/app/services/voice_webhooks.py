from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from app.models.domain import ChannelType, ConnectorInboundRequest


RECEIPT_EVENT_TYPES = {
    "callback_status",
    "call_status",
    "delivery_receipt",
    "outbound_call_status",
    "status",
    "voice_status",
}
INBOUND_EVENT_TYPES = {
    "callback_request",
    "call_log",
    "inbound",
    "inbound_call",
    "missed_call",
    "voice_call",
    "voicemail",
    "voicemail_summary",
}


@dataclass(frozen=True)
class VoiceDeliveryReceipt:
    status: str
    provider_message_id: str | None = None
    outbound_message_id: str | None = None
    idempotency_key: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceWebhookEvent:
    kind: str
    inbound: ConnectorInboundRequest | None = None
    receipt: VoiceDeliveryReceipt | None = None


class VoiceWebhookAdapter:
    def webhook_external_id(self, payload: dict[str, Any], delivery_id: str | None = None) -> str:
        if self._is_receipt(payload):
            provider_call_id = self._provider_call_id(payload)
            if delivery_id:
                return f"receipt:{delivery_id}"
            if provider_call_id:
                return f"receipt:{provider_call_id}:{self._receipt_status(payload) or 'unknown'}"

        provider_call_id = self._provider_call_id(payload)
        if provider_call_id:
            return provider_call_id
        if delivery_id:
            return f"voice:webhook:{delivery_id}"
        body = json.dumps(payload, sort_keys=True, default=str)
        return f"voice:webhook:{hashlib.sha256(body.encode()).hexdigest()[:24]}"

    def parse(
        self,
        payload: dict[str, Any],
        *,
        metadata: dict[str, Any],
        delivery_id: str | None = None,
    ) -> VoiceWebhookEvent:
        if self._is_receipt(payload):
            return VoiceWebhookEvent(kind="delivery_receipt", receipt=self._receipt(payload))
        return VoiceWebhookEvent(
            kind="inbound",
            inbound=self._inbound(payload, metadata, delivery_id),
        )

    def _is_receipt(self, payload: dict[str, Any]) -> bool:
        event_type = self._event_type(payload)
        if event_type in INBOUND_EVENT_TYPES:
            return False
        if event_type in RECEIPT_EVENT_TYPES:
            return True
        if self._first_text(payload, "outbound_message_id", "omni_outbound_message_id", "idempotency_key"):
            return bool(self._receipt_status(payload))
        direction = (self._first_text(payload, "direction") or "").lower()
        return direction == "outbound" and bool(self._receipt_status(payload))

    def _event_type(self, payload: dict[str, Any]) -> str:
        return (
            self._first_text(payload, "event_type", "event", "type", "message_type") or ""
        ).strip().lower()

    def _receipt_status(self, payload: dict[str, Any]) -> str | None:
        status = self._first_text(payload, "status", "call_status", "state", "result")
        if not status:
            return None
        normalized = status.strip().lower().replace(" ", "_").replace("-", "_")
        status_map = {
            "answered": "delivered",
            "completed": "delivered",
            "complete": "delivered",
            "connected": "delivered",
            "no_answer": "failed",
            "busy": "failed",
            "canceled": "failed",
            "cancelled": "failed",
        }
        return status_map.get(normalized, normalized)

    def _receipt(self, payload: dict[str, Any]) -> VoiceDeliveryReceipt:
        return VoiceDeliveryReceipt(
            status=self._receipt_status(payload) or "unknown",
            provider_message_id=self._provider_call_id(payload),
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
        handle = self._caller(payload)
        external_id = self.webhook_external_id(payload, delivery_id)
        customer_name = (
            self._first_text(payload, "customer_name", "caller_name", "name", "profile_name")
            or handle
            or "Voice Caller"
        )
        metadata_payload = {
            **metadata,
            "voice_webhook_payload": payload,
            "voice_event_kind": "inbound",
            "voice_event_type": self._event_type(payload) or "voice_call",
            "voice_call_id": self._provider_call_id(payload),
            "voice_direction": self._first_text(payload, "direction"),
            "voice_recording_url": self._first_text(payload, "recording_url", "recordingUrl"),
        }
        return ConnectorInboundRequest(
            provider=ChannelType.voice,
            external_id=external_id,
            customer_name=customer_name,
            customer_email=(
                self._first_text(payload, "customer_email", "email")
                or self._synthetic_email(handle or external_id)
            ),
            subject=self._first_text(payload, "subject") or self._subject(payload, customer_name),
            body=self._body(payload),
            handle=handle or None,
            metadata=metadata_payload,
        )

    def _subject(self, payload: dict[str, Any], customer_name: str) -> str:
        event_type = self._event_type(payload)
        if event_type in {"callback_request", "missed_call"}:
            return f"Voice callback request from {customer_name}"
        if event_type in {"voicemail", "voicemail_summary"}:
            return f"Voicemail from {customer_name}"
        return f"Voice call from {customer_name}"

    def _body(self, payload: dict[str, Any]) -> str:
        for key in ("transcript", "summary", "body", "message", "notes", "voicemail_text"):
            text = self._first_text(payload, key)
            if text:
                return text
        parts: list[str] = []
        status_value = self._first_text(payload, "status", "call_status", "state")
        duration = self._first_text(payload, "duration_seconds", "duration", "call_duration")
        recording_url = self._first_text(payload, "recording_url", "recordingUrl")
        if status_value:
            parts.append(f"Status: {status_value}")
        if duration:
            parts.append(f"Duration: {duration} seconds")
        if recording_url:
            parts.append(f"Recording: {recording_url}")
        if parts:
            return "\n".join(parts)
        return "[Voice call event received]"

    def _caller(self, payload: dict[str, Any]) -> str:
        return (
            self._first_text(
                payload,
                "from",
                "caller",
                "caller_number",
                "from_number",
                "msisdn",
                "phone",
                "handle",
            )
            or ""
        )

    def _provider_call_id(self, payload: dict[str, Any]) -> str | None:
        return self._first_text(
            payload,
            "call_id",
            "callId",
            "message_id",
            "messageId",
            "id",
            "sid",
            "reference",
            "provider_id",
        )

    def _synthetic_email(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "", value).lower() or "unknown"
        return f"voice-{normalized[:80]}@voice.omniticket.app"

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


voice_webhook_adapter = VoiceWebhookAdapter()
