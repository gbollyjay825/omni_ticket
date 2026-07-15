from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from app.core.config import settings
from app.db.integration_credentials import RuntimeIntegrationCredentials
from app.models.campaigns import CampaignChannel


@dataclass(frozen=True)
class CampaignSendRequest:
    delivery_id: str
    campaign_id: str
    market_id: str
    customer_id: str
    channel: CampaignChannel
    recipient: str
    body: str
    idempotency_key: str
    template_name: str = ""
    template_language: str = "en_US"
    template_variables: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CampaignSendResult:
    succeeded: bool
    adapter: str
    external_id: str | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class CampaignDeliveryTransport:
    def missing_settings(
        self,
        channel: CampaignChannel,
        credentials: RuntimeIntegrationCredentials,
    ) -> list[str]:
        if channel == "sms":
            missing = []
            if not credentials.sms_http_endpoint:
                missing.append("SMS HTTP endpoint")
            if not credentials.sms_http_auth_token:
                missing.append("SMS auth token")
            if not credentials.sms_http_from:
                missing.append("SMS sender")
            return missing
        if channel == "whatsapp":
            missing = []
            if not credentials.whatsapp_cloud_api_base_url:
                missing.append("WhatsApp Cloud API base URL")
            if not credentials.whatsapp_phone_number_id:
                missing.append("WhatsApp phone number ID")
            if not credentials.whatsapp_access_token:
                missing.append("WhatsApp access token")
            return missing
        if channel == "facebook":
            missing = []
            if not credentials.facebook_graph_api_base_url:
                missing.append("Facebook Graph API base URL")
            if not credentials.facebook_page_id:
                missing.append("Facebook page ID")
            if not credentials.facebook_page_access_token:
                missing.append("Facebook page access token")
            return missing
        missing = []
        if not credentials.instagram_graph_api_base_url:
            missing.append("Instagram Graph API base URL")
        if not credentials.instagram_business_account_id:
            missing.append("Instagram business account ID")
        if not credentials.instagram_access_token:
            missing.append("Instagram access token")
        return missing

    def _post_json(
        self,
        *,
        adapter: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
        fallback_id: str,
    ) -> CampaignSendResult:
        request = urlrequest.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=timeout) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return CampaignSendResult(
                succeeded=False,
                adapter=adapter,
                error=f"Provider returned HTTP {exc.code}: {response_body[:240]}",
                payload={"status_code": exc.code},
            )
        except OSError as exc:
            return CampaignSendResult(succeeded=False, adapter=adapter, error=str(exc))

        try:
            provider_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            provider_response = {"raw": response_body}
        if not isinstance(provider_response, dict):
            provider_response = {"data": provider_response}
        if status_code < 200 or status_code >= 300:
            return CampaignSendResult(
                succeeded=False,
                adapter=adapter,
                error=f"Provider returned HTTP {status_code}: {response_body[:240]}",
                payload={"status_code": status_code, "provider_response": provider_response},
            )
        external_id = self._provider_id(provider_response) or fallback_id
        return CampaignSendResult(
            succeeded=True,
            adapter=adapter,
            external_id=external_id,
            payload={
                "status_code": status_code,
                "provider_response": provider_response,
            },
        )

    def _provider_id(self, payload: dict[str, Any]) -> str | None:
        messages = payload.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and message.get("id"):
                    return str(message["id"])
        for key in (
            "message_id",
            "messageId",
            "id",
            "mid",
            "sid",
            "reference",
            "provider_id",
        ):
            if payload.get(key):
                return str(payload[key])
        nested = payload.get("data")
        return self._provider_id(nested) if isinstance(nested, dict) else None

    def send(
        self,
        request: CampaignSendRequest,
        credentials: RuntimeIntegrationCredentials,
    ) -> CampaignSendResult:
        missing = self.missing_settings(request.channel, credentials)
        if missing:
            return CampaignSendResult(
                succeeded=False,
                adapter=f"{request.channel}-campaign",
                error=f"Campaign delivery is missing settings: {', '.join(missing)}.",
            )
        if request.channel == "sms":
            token = credentials.sms_http_auth_token or ""
            scheme = credentials.sms_http_auth_scheme.strip()
            auth_value = f"{scheme} {token}".strip() if scheme else token
            payload: dict[str, Any] = {
                "to": request.recipient,
                "from": credentials.sms_http_from,
                "body": request.body,
                "market_id": request.market_id,
                "campaign_id": request.campaign_id,
                "idempotency_key": request.idempotency_key,
                "metadata": {
                    "campaign_delivery_id": request.delivery_id,
                    "customer_id": request.customer_id,
                },
            }
            if credentials.sms_http_delivery_callback_url:
                payload["callback_url"] = credentials.sms_http_delivery_callback_url
            return self._post_json(
                adapter="http-sms-campaign",
                url=credentials.sms_http_endpoint,
                headers={
                    credentials.sms_http_auth_header: auth_value,
                    "X-Omni-Idempotency-Key": request.idempotency_key,
                },
                payload=payload,
                timeout=settings.sms_http_timeout_seconds,
                fallback_id=f"sms-campaign:{request.delivery_id}",
            )
        if request.channel == "whatsapp":
            if not request.template_name:
                return CampaignSendResult(
                    succeeded=False,
                    adapter="whatsapp-template-campaign",
                    error="WhatsApp proactive delivery requires an approved template name.",
                )
            components = []
            if request.template_variables:
                components.append(
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": value}
                            for value in request.template_variables
                        ],
                    }
                )
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": request.recipient.lstrip("+"),
                "type": "template",
                "template": {
                    "name": request.template_name,
                    "language": {"code": request.template_language},
                    **({"components": components} if components else {}),
                },
            }
            base_url = credentials.whatsapp_cloud_api_base_url.rstrip("/")
            phone_id = credentials.whatsapp_phone_number_id.strip().strip("/")
            return self._post_json(
                adapter="whatsapp-template-campaign",
                url=f"{base_url}/{phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {credentials.whatsapp_access_token}",
                    "X-Omni-Idempotency-Key": request.idempotency_key,
                },
                payload=payload,
                timeout=settings.whatsapp_timeout_seconds,
                fallback_id=f"whatsapp-campaign:{request.delivery_id}",
            )
        if request.channel == "facebook":
            base_url = credentials.facebook_graph_api_base_url.rstrip("/")
            page_id = credentials.facebook_page_id.strip().strip("/")
            return self._post_json(
                adapter="facebook-campaign",
                url=f"{base_url}/{page_id}/messages",
                headers={
                    "Authorization": f"Bearer {credentials.facebook_page_access_token}",
                    "X-Omni-Idempotency-Key": request.idempotency_key,
                },
                payload={
                    "recipient": {"id": request.recipient},
                    "messaging_type": credentials.facebook_messaging_type,
                    "message": {"text": request.body},
                },
                timeout=settings.facebook_timeout_seconds,
                fallback_id=f"facebook-campaign:{request.delivery_id}",
            )
        base_url = credentials.instagram_graph_api_base_url.rstrip("/")
        account_id = credentials.instagram_business_account_id.strip().strip("/")
        return self._post_json(
            adapter="instagram-campaign",
            url=f"{base_url}/{account_id}/messages",
            headers={
                "Authorization": f"Bearer {credentials.instagram_access_token}",
                "X-Omni-Idempotency-Key": request.idempotency_key,
            },
            payload={"recipient": {"id": request.recipient}, "message": {"text": request.body}},
            timeout=settings.instagram_timeout_seconds,
            fallback_id=f"instagram-campaign:{request.delivery_id}",
        )


campaign_delivery_transport = CampaignDeliveryTransport()
