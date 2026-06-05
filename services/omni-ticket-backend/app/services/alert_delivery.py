from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any, Protocol
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.alert_deliveries import operational_alert_delivery_repository
from app.db.audit import write_audit_event
from app.db.integration_credentials import (
    RuntimeIntegrationCredentials,
    integration_credential_settings_repository,
)
from app.db.mappers import operational_alert_from_record
from app.db.models import OperationalAlertRecord
from app.models.domain import (
    OperationalAlertDeliveryConfig,
    OperationalAlertSeverity,
    utc_now,
)


@dataclass
class AlertWebhookResponse:
    status_code: int
    body: str = ""


class AlertWebhookTransport(Protocol):
    def send(self, payload: dict[str, Any]) -> AlertWebhookResponse: ...


class AlertWebhookSender:
    def __init__(self, credentials: RuntimeIntegrationCredentials | None = None) -> None:
        self.credentials = credentials or integration_credential_settings_repository.runtime_credentials()

    def send(self, payload: dict[str, Any]) -> AlertWebhookResponse:
        if not self.credentials.alert_webhook_url:
            raise RuntimeError("OMNI_ALERT_WEBHOOK_URL is not configured.")
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(utc_now().timestamp()))
        headers = {
            "Content-Type": "application/json",
            "X-Omni-Alert-Timestamp": timestamp,
        }
        if self.credentials.alert_webhook_secret:
            digest = hmac.new(
                self.credentials.alert_webhook_secret.encode(),
                f"{timestamp}.".encode() + body,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Omni-Alert-Signature"] = f"sha256={digest}"
        request = urllib.request.Request(
            self.credentials.alert_webhook_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - controlled by deployment config.
                request,
                timeout=settings.alert_webhook_timeout_seconds,
            ) as response:
                return AlertWebhookResponse(
                    status_code=response.status,
                    body=response.read(500).decode(errors="replace"),
                )
        except urllib.error.HTTPError as exc:
            return AlertWebhookResponse(
                status_code=exc.code,
                body=exc.read(500).decode(errors="replace"),
            )


def _severity_from_config(
    credentials: RuntimeIntegrationCredentials,
) -> OperationalAlertSeverity:
    return OperationalAlertSeverity(credentials.alert_delivery_min_severity)


class AlertDeliveryService:
    destination_name = "operations_webhook"

    def config_summary(
        self,
        db: Session | None = None,
        market_id: str | None = None,
    ) -> OperationalAlertDeliveryConfig:
        credentials = integration_credential_settings_repository.runtime_credentials(
            db,
            market_id=market_id,
        )
        return OperationalAlertDeliveryConfig(
            webhook_configured=bool(credentials.alert_webhook_url),
            destination_type="webhook",
            destination_name=self.destination_name,
            min_severity=_severity_from_config(credentials),
            max_attempts=settings.alert_delivery_max_attempts,
        )

    def _payload_for_alert(self, alert_record: OperationalAlertRecord) -> dict[str, Any]:
        alert = operational_alert_from_record(alert_record)
        return {
            "event": "omni.operational_alert",
            "market_id": alert.market_id,
            "alert": alert.model_dump(mode="json"),
        }

    def dispatch_due_webhooks(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        limit: int = 50,
        sender: AlertWebhookTransport | None = None,
    ) -> dict[str, Any]:
        credentials = integration_credential_settings_repository.runtime_credentials(db, market_id=market_id)
        config = self.config_summary(db, market_id)
        details: dict[str, Any] = {
            "webhook_configured": config.webhook_configured,
            "destination_type": config.destination_type,
            "destination_name": config.destination_name,
            "min_severity": config.min_severity.value,
            "max_attempts": config.max_attempts,
            "queued": 0,
            "sent": 0,
            "failed": 0,
            "delivery_ids": [],
        }
        if not config.webhook_configured:
            return details

        details["queued"] = operational_alert_delivery_repository.enqueue_missing_webhook_deliveries(
            db,
            market_id=market_id,
            destination_name=config.destination_name,
            max_attempts=config.max_attempts,
            min_severity=config.min_severity,
        )
        db.flush()

        webhook_sender = sender or AlertWebhookSender(credentials)
        due_records = operational_alert_delivery_repository.due_webhook_deliveries(
            db,
            market_id=market_id,
            destination_name=config.destination_name,
            limit=limit,
        )
        details["delivery_ids"] = [record.id for record in due_records]
        for delivery in due_records:
            alert_record = db.get(OperationalAlertRecord, delivery.alert_id)
            if alert_record is None or alert_record.market_id != market_id:
                continue
            payload = self._payload_for_alert(alert_record)
            operational_alert_delivery_repository.mark_sending(delivery)
            db.flush()
            try:
                response = webhook_sender.send(payload)
                if 200 <= response.status_code < 300:
                    operational_alert_delivery_repository.mark_sent(delivery, payload)
                    details["sent"] += 1
                    write_audit_event(
                        db,
                        actor=actor,
                        action="alert_delivery.sent",
                        entity_type="operational_alert_delivery",
                        entity_id=delivery.id,
                        market_id=market_id,
                        details={
                            "alert_id": delivery.alert_id,
                            "destination_type": delivery.destination_type,
                            "destination_name": delivery.destination_name,
                            "status_code": response.status_code,
                        },
                    )
                else:
                    error = f"Webhook returned HTTP {response.status_code}: {response.body}"
                    operational_alert_delivery_repository.mark_failed(
                        delivery,
                        error=error,
                        payload=payload,
                        retry_minutes=settings.alert_delivery_retry_minutes,
                    )
                    details["failed"] += 1
                    write_audit_event(
                        db,
                        actor=actor,
                        action="alert_delivery.failed",
                        entity_type="operational_alert_delivery",
                        entity_id=delivery.id,
                        market_id=market_id,
                        details={
                            "alert_id": delivery.alert_id,
                            "destination_type": delivery.destination_type,
                            "destination_name": delivery.destination_name,
                            "error": error,
                            "attempts": delivery.attempts,
                        },
                    )
            except Exception as exc:  # pragma: no cover - network defensive path
                error = str(exc)
                operational_alert_delivery_repository.mark_failed(
                    delivery,
                    error=error,
                    payload=payload,
                    retry_minutes=settings.alert_delivery_retry_minutes,
                )
                details["failed"] += 1
                write_audit_event(
                    db,
                    actor=actor,
                    action="alert_delivery.failed",
                    entity_type="operational_alert_delivery",
                    entity_id=delivery.id,
                    market_id=market_id,
                    details={
                        "alert_id": delivery.alert_id,
                        "destination_type": delivery.destination_type,
                        "destination_name": delivery.destination_name,
                        "error": error,
                        "attempts": delivery.attempts,
                    },
                )
        return details


alert_delivery_service = AlertDeliveryService()
