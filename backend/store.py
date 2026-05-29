from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .data import initial_state


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=1))).isoformat(timespec="seconds")


class BackendStore:
    def __init__(self) -> None:
        self.state = initial_state()

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.state)

    def list_collection(self, name: str) -> list[dict[str, Any]]:
        return deepcopy(self.state[name])

    def get_by_id(self, name: str, item_id: str) -> dict[str, Any] | None:
        for item in self.state[name]:
            if item["id"] == item_id:
                return deepcopy(item)
        return None

    def _find_live(self, name: str, item_id: str) -> dict[str, Any] | None:
        for item in self.state[name]:
            if item["id"] == item_id:
                return item
        return None

    def list_tickets(self) -> list[dict[str, Any]]:
        return self.list_collection("tickets")

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        return self.get_by_id("tickets", ticket_id)

    def update_ticket(self, ticket_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        ticket = self._find_live("tickets", ticket_id)
        if ticket is None:
            return None
        allowed = {"status", "priority", "group", "assigneeId", "tags", "unread", "slaState"}
        for key, value in patch.items():
            if key in allowed:
                ticket[key] = value
        ticket["updatedAt"] = now_iso()
        return deepcopy(ticket)

    def append_ticket_event(
        self,
        ticket_id: str,
        event_type: str,
        body: str,
        *,
        author: str,
        author_role: str,
        channel_id: str | None = None,
    ) -> dict[str, Any] | None:
        ticket = self._find_live("tickets", ticket_id)
        if ticket is None:
            return None
        event = {
            "id": f"event-{ticket_id}-{len(ticket['timeline']) + 1}",
            "type": event_type,
            "channelId": channel_id or ticket["channelId"],
            "author": author,
            "authorRole": author_role,
            "timestamp": now_iso(),
            "body": body,
            "deliveryState": "sent" if event_type == "agent-reply" else None,
        }
        ticket["timeline"].append({k: v for k, v in event.items() if v is not None})
        ticket["updatedAt"] = event["timestamp"]
        if event_type == "agent-reply":
            ticket["status"] = "pending"
            ticket["unread"] = False
        if event_type == "handoff":
            ticket["status"] = "waiting"
        return deepcopy(ticket)

    def create_handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        ticket = self._find_live("tickets", payload["conversationId"])
        handoff = {
            "id": f"handoff-{len(self.state['handoffs']) + 1002}",
            "ticketNumber": ticket["ticketNumber"] if ticket else payload.get("ticketNumber", "UNKNOWN"),
            "customerId": ticket["customerId"] if ticket else payload.get("customerId"),
            "status": "requested",
            "priority": payload.get("priority", ticket["priority"] if ticket else "medium"),
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "checklist": payload.get("checklist", []),
            "blockers": payload.get("blockers", []),
            **payload,
        }
        self.state["handoffs"].append(handoff)
        if ticket is not None:
            self.append_ticket_event(
                ticket["id"],
                "handoff",
                f"Handoff opened for {handoff['receivingTeam']}: {handoff['reason']}",
                author="Handoff desk",
                author_role="system",
                channel_id="internal",
            )
        return deepcopy(handoff)

    def update_handoff(self, handoff_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        handoff = self._find_live("handoffs", handoff_id)
        if handoff is None:
            return None
        allowed = {"status", "ownerId", "receivingTeam", "reason", "context", "customerImpact", "acceptanceCriteria", "blockers"}
        for key, value in patch.items():
            if key in allowed:
                handoff[key] = value
        handoff["updatedAt"] = now_iso()
        return deepcopy(handoff)

    def toggle_handoff_checklist(self, handoff_id: str, task_id: str) -> dict[str, Any] | None:
        handoff = self._find_live("handoffs", handoff_id)
        if handoff is None:
            return None
        for task in handoff["checklist"]:
            if task["id"] == task_id:
                task["done"] = not task["done"]
                handoff["updatedAt"] = now_iso()
                return deepcopy(handoff)
        return None

    def timeline(self, conversation_id: str) -> list[dict[str, Any]] | None:
        ticket = self._find_live("tickets", conversation_id)
        return deepcopy(ticket["timeline"]) if ticket else None

    def update_channel(self, channel_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        channel = self._find_live("channels", channel_id)
        if channel is None:
            return None
        allowed = {"status", "intakeEnabled", "queueDepth", "avgWaitMinutes", "health"}
        for key, value in patch.items():
            if key in allowed:
                channel[key] = value
        return deepcopy(channel)

    def update_agent_status(self, agent_id: str, availability: str) -> dict[str, Any] | None:
        agent = self._find_live("agents", agent_id)
        if agent is None:
            return None
        agent["availability"] = availability
        return deepcopy(agent)

    def update_rule(self, rule_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        rule = self._find_live("automationRules", rule_id)
        if rule is None:
            return None
        allowed = {"status", "health", "failures"}
        for key, value in patch.items():
            if key in allowed:
                rule[key] = value
        return deepcopy(rule)

    def update_settings(self, enabled: bool) -> dict[str, Any]:
        self.state["settings"]["aiWorkQueueAutomationEnabled"] = enabled
        return deepcopy(self.state["settings"])

    def update_knowledge(self, article_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        article = self._find_live("knowledge", article_id)
        if article is None:
            return None
        allowed = {"status", "title", "category"}
        for key, value in patch.items():
            if key in allowed:
                article[key] = value
        article["updatedAt"] = now_iso()
        return deepcopy(article)

    def analytics(self) -> dict[str, Any]:
        tickets = self.state["tickets"]
        channels = self.state["channels"]
        agents = self.state["agents"]
        open_tickets = [ticket for ticket in tickets if ticket["status"] != "resolved"]
        risk_tickets = [ticket for ticket in open_tickets if ticket["slaState"] in {"risk", "breached"}]
        avg_health = round(sum(channel["health"] for channel in channels) / len(channels))
        avg_occupancy = round(sum(agent["occupancy"] for agent in agents) / len(agents))
        return {
            "openTickets": len(open_tickets),
            "riskTickets": len(risk_tickets),
            "avgChannelHealth": avg_health,
            "avgAgentOccupancy": avg_occupancy,
            "aiWorkQueueAutomationEnabled": self.state["settings"]["aiWorkQueueAutomationEnabled"],
        }
