from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from app.core.config import settings
from app.core.store import InMemoryStore
from app.db.integration_credentials import (
    RuntimeIntegrationCredentials,
    integration_credential_settings_repository,
)
from app.models.domain import (
    Agent,
    AiDecision,
    ChannelType,
    Customer,
    Priority,
    Sentiment,
    Ticket,
    WorkQueueItem,
    utc_now,
)
from app.services.sla import sla_service


NEGATIVE_TERMS = {
    "angry",
    "terrible",
    "failed",
    "breach",
    "complaint",
    "escalate",
    "refund",
    "duplicate",
    "missed",
    "delay",
    "public",
}

URGENT_TERMS = {"breach", "public", "angry", "escalate", "failed", "fraud", "legal"}
PAYMENT_TERMS = {"payment", "invoice", "billing", "duplicate", "refund", "charge"}
DELIVERY_TERMS = {"delivery", "order", "shipment", "fulfillment"}


@dataclass(frozen=True)
class AiTicketGuidance:
    summary: str
    recommended_action: str
    confidence: float = 0.72
    model_version: str = "rules-v1"
    input_reference: str = "rules"


class AnthropicGuidanceError(RuntimeError):
    pass


def _clean_text(value: object, fallback: str, *, max_length: int = 420) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return fallback
    return cleaned[:max_length]


def _normalize_confidence(value: object, fallback: float = 0.78) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return fallback
    try:
        confidence = float(value)
    except ValueError:
        return fallback
    if confidence > 1:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if match is None:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Anthropic guidance response was not a JSON object.")
    return data


class AnthropicTicketGuidanceClient:
    name = "anthropic"

    def _candidate_key_paths(self) -> list[Path]:
        configured = settings.anthropic_api_key_file
        if not configured:
            return []
        path = Path(configured).expanduser()
        if path.is_absolute():
            return [path]

        candidates = [Path.cwd() / path]
        backend_root = Path(__file__).resolve().parents[2]
        candidates.append(backend_root / path)
        for parent in Path(__file__).resolve().parents:
            if (parent / "package.json").exists() and (parent / "services").exists():
                candidates.append(parent / path)
                break

        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique

    def _read_key_file(self) -> str | None:
        for path in self._candidate_key_paths():
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in raw.splitlines():
                cleaned = line.strip().strip('"').strip("'")
                if not cleaned or cleaned.startswith("#"):
                    continue
                if "=" in cleaned:
                    key, value = cleaned.split("=", 1)
                    if key.strip() not in {
                        "AI_Key",
                        "AI_KEY",
                        "ANTHROPIC_API_KEY",
                        "OMNI_ANTHROPIC_API_KEY",
                    }:
                        continue
                    cleaned = value.strip().strip('"').strip("'")
                return cleaned or None
        return None

    def api_key(self, credentials: RuntimeIntegrationCredentials | None = None) -> str | None:
        if credentials is not None and credentials.anthropic_api_key:
            return credentials.anthropic_api_key
        return settings.anthropic_api_key or self._read_key_file()

    def configured(self, credentials: RuntimeIntegrationCredentials | None = None) -> bool:
        return bool(self.api_key(credentials))

    def _messages_url(self, credentials: RuntimeIntegrationCredentials | None = None) -> str:
        base_url = (
            credentials.anthropic_api_base_url if credentials is not None else settings.anthropic_api_base_url
        ).rstrip("/")
        if base_url.endswith("/v1/messages"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/messages"
        return f"{base_url}/v1/messages"

    def _ticket_payload(self, ticket: Ticket, customer: Customer) -> dict[str, Any]:
        return {
            "ticket": {
                "public_id": ticket.public_id,
                "subject": ticket.subject,
                "description": ticket.description,
                "channel": ticket.channel.value,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "sentiment": ticket.sentiment.value,
                "team": ticket.team,
                "tags": ticket.tags,
                "sla_risk": ticket.sla.risk,
                "sla_breached": ticket.sla.breached,
            },
            "customer": {
                "name": customer.name,
                "company_id": customer.company_id,
                "sentiment": customer.sentiment.value,
                "location": customer.location,
                "tags": customer.tags,
            },
        }

    def _request_payload(
        self,
        ticket: Ticket,
        customer: Customer,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> dict[str, Any]:
        model = credentials.anthropic_model if credentials is not None else settings.anthropic_model
        return {
            "model": model,
            "max_tokens": settings.anthropic_max_tokens,
            "temperature": 0.2,
            "system": (
                "You are Omni Ticket's production support operations AI for Wakanow. "
                "Use the ticket context to produce concise, agent-safe guidance. "
                "Do not invent customer data, do not claim a message was sent, and do not promise refunds. "
                "Return JSON only with keys summary, recommended_action, and confidence."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(self._ticket_payload(ticket, customer), ensure_ascii=True),
                }
            ],
        }

    def generate_guidance(
        self,
        ticket: Ticket,
        customer: Customer,
        credentials: RuntimeIntegrationCredentials | None = None,
    ) -> AiTicketGuidance:
        api_key = self.api_key(credentials)
        if not api_key:
            raise AnthropicGuidanceError("Anthropic API key is not configured.")
        request = urlrequest.Request(
            self._messages_url(credentials),
            data=json.dumps(self._request_payload(ticket, customer, credentials)).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=settings.anthropic_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            raise AnthropicGuidanceError(f"Anthropic API returned HTTP {exc.code}.") from exc
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise AnthropicGuidanceError("Anthropic API guidance request failed.") from exc

        content = payload.get("content")
        if not isinstance(content, list):
            raise AnthropicGuidanceError("Anthropic response did not include content.")
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        guidance_json = _extract_json_object("\n".join(text_parts))
        fallback_summary = WorkQueueAutomationService.rules_summary(ticket, customer)
        fallback_action = WorkQueueAutomationService.rules_recommended_action(ticket, customer)
        return AiTicketGuidance(
            summary=_clean_text(guidance_json.get("summary"), fallback_summary),
            recommended_action=_clean_text(
                guidance_json.get("recommended_action"),
                fallback_action,
            ),
            confidence=_normalize_confidence(guidance_json.get("confidence")),
            model_version=str(
                payload.get("model")
                or (credentials.anthropic_model if credentials is not None else settings.anthropic_model)
            ),
            input_reference=f"anthropic:{ticket.id}",
        )


anthropic_guidance_client = AnthropicTicketGuidanceClient()


class WorkQueueAutomationService:
    def classify_priority(self, text: str, requested_priority: Priority | None) -> Priority:
        if requested_priority:
            return requested_priority
        normalized = text.lower()
        if any(term in normalized for term in URGENT_TERMS):
            return Priority.urgent
        if any(term in normalized for term in PAYMENT_TERMS | DELIVERY_TERMS):
            return Priority.high
        return Priority.normal

    def classify_sentiment(self, text: str) -> Sentiment:
        normalized = text.lower()
        hits = sum(1 for term in NEGATIVE_TERMS if term in normalized)
        if hits >= 3:
            return Sentiment.angry
        if hits >= 1:
            return Sentiment.frustrated
        return Sentiment.neutral

    def classify_tags(self, text: str, channel: ChannelType, incoming_tags: list[str]) -> list[str]:
        normalized = text.lower()
        tags = set(incoming_tags)
        tags.add(channel.value)
        if any(term in normalized for term in PAYMENT_TERMS):
            tags.add("payment-risk")
        if any(term in normalized for term in DELIVERY_TERMS):
            tags.add("delivery")
        if channel in {ChannelType.facebook, ChannelType.instagram} or "public" in normalized:
            tags.add("reputation-risk")
        return sorted(tags)

    def choose_agent(self, store: InMemoryStore, channel: ChannelType, market_id: str) -> Agent | None:
        candidates = [
            agent
            for agent in store.agents.values()
            if agent.status != "offline" and market_id in agent.market_ids and channel in agent.skills
        ]
        if not candidates:
            candidates = [
                agent
                for agent in store.agents.values()
                if agent.status != "offline" and market_id in agent.market_ids
            ]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda agent: (
                0 if agent.status == "available" else 1,
                agent.occupancy,
                -agent.capacity,
                agent.name,
            ),
        )[0]

    @staticmethod
    def rules_recommended_action(ticket: Ticket, customer: Customer) -> str:
        if ticket.channel in {ChannelType.facebook, ChannelType.instagram}:
            return "Move private details into direct chat, acknowledge publicly, and update fulfillment."
        if "payment-risk" in ticket.tags:
            return "Confirm transaction reference, validate gateway state, and send the reversal timeline."
        if ticket.priority == Priority.urgent:
            return "Acknowledge within the SLA window and notify a supervisor if the blocker remains open."
        return f"Reply on {ticket.channel.value} with the next clear owner and promise time."

    @staticmethod
    def rules_summary(ticket: Ticket, customer: Customer) -> str:
        return (
            f"{customer.name} has a {ticket.priority.value} {ticket.channel.value} issue "
            f"with {ticket.sentiment.value} sentiment and {ticket.sla.risk.replace('_', ' ')} SLA state."
        )

    def recommended_action(self, ticket: Ticket, customer: Customer) -> str:
        return self.generate_guidance(ticket, customer).recommended_action

    def summary(self, ticket: Ticket, customer: Customer) -> str:
        return self.generate_guidance(ticket, customer).summary

    def rules_guidance(self, ticket: Ticket, customer: Customer) -> AiTicketGuidance:
        return AiTicketGuidance(
            summary=self.rules_summary(ticket, customer),
            recommended_action=self.rules_recommended_action(ticket, customer),
        )

    def generate_guidance(self, ticket: Ticket, customer: Customer) -> AiTicketGuidance:
        credentials = integration_credential_settings_repository.runtime_credentials_for_market_id(
            ticket.market_id,
        )
        if credentials.ai_provider == "rules":
            return self.rules_guidance(ticket, customer)
        try:
            return anthropic_guidance_client.generate_guidance(ticket, customer, credentials)
        except AnthropicGuidanceError:
            return AiTicketGuidance(
                summary=self.rules_summary(ticket, customer),
                recommended_action=self.rules_recommended_action(ticket, customer),
                model_version="rules-v1",
                input_reference="rules:fallback",
            )

    def score_ticket(self, ticket: Ticket, customer: Customer) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        priority_scores = {
            Priority.urgent: 45,
            Priority.high: 32,
            Priority.normal: 18,
            Priority.low: 8,
        }
        sentiment_scores = {
            Sentiment.angry: 25,
            Sentiment.frustrated: 18,
            Sentiment.neutral: 6,
            Sentiment.positive: 0,
        }
        score += priority_scores[ticket.priority]
        score += sentiment_scores[ticket.sentiment]
        if ticket.sla.breached:
            score += 40
            reasons.append("SLA breached")
        elif ticket.sla.risk == "at_risk":
            score += 20
            reasons.append("SLA at risk")
        if "reputation-risk" in ticket.tags:
            score += 16
            reasons.append("Public reputation risk")
        if customer.company_id:
            company = customer.company_id
            if company:
                score += 4
        reasons.append(f"{ticket.priority.value} priority")
        reasons.append(f"{ticket.sentiment.value} sentiment")
        return score, reasons

    def queue(self, store: InMemoryStore, market_id: str | None = None) -> list[WorkQueueItem]:
        items: list[WorkQueueItem] = []
        for ticket in store.tickets.values():
            if market_id and ticket.market_id != market_id:
                continue
            if ticket.status in {"solved", "closed"}:
                continue
            ticket.sla = sla_service.refresh(ticket.sla)
            customer = store.customers[ticket.customer_id]
            score, reasons = self.score_ticket(ticket, customer)
            assignee = store.agents.get(ticket.assignee_id or "")
            items.append(
                WorkQueueItem(
                    ticket=ticket,
                    customer=customer,
                    assignee=assignee,
                    score=score,
                    reasons=reasons,
                )
            )
        return sorted(items, key=lambda item: (-item.score, item.ticket.created_at))

    def make_decision(
        self,
        ticket: Ticket,
        guidance: AiTicketGuidance | None = None,
    ) -> AiDecision:
        decision_guidance = guidance or AiTicketGuidance(
            summary=ticket.ai_summary,
            recommended_action=ticket.recommended_action,
        )
        return AiDecision(
            id=f"ai-{ticket.id}",
            ticket_id=ticket.id,
            created_at=utc_now(),
            decision_type="work_queue_routing",
            confidence=decision_guidance.confidence,
            summary=(
                f"Routed {ticket.public_id} to {ticket.team} as "
                f"{ticket.priority.value} priority from {ticket.channel.value}. "
                f"Next action: {decision_guidance.recommended_action}"
            ),
            model_version=decision_guidance.model_version,
            input_reference=decision_guidance.input_reference,
        )


automation_service = WorkQueueAutomationService()
