from __future__ import annotations

import json
from copy import deepcopy
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .store import BackendStore


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    payload = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def not_found(handler: BaseHTTPRequestHandler, message: str = "Not found") -> None:
    json_response(handler, HTTPStatus.NOT_FOUND, {"error": message})


def docs_html() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Omni Ticket API Docs</title>
        <style>
          body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 40px; color: #12202d; }
          h1 { margin-bottom: 8px; }
          code { background: #eef4f8; padding: 2px 6px; border-radius: 4px; }
          li { margin: 8px 0; }
        </style>
      </head>
      <body>
        <h1>Omni Ticket API</h1>
        <p>Local Python backend slice for the Freshdesk-inspired omnichannel PWA rebuild.</p>
        <p>Machine-readable schema: <a href="/openapi.json"><code>/openapi.json</code></a></p>
        <ul>
          <li><code>GET /health</code></li>
          <li><code>GET /tickets</code>, <code>GET /tickets/:id</code>, <code>PATCH /tickets/:id</code></li>
          <li><code>POST /tickets/:id/replies</code>, <code>POST /tickets/:id/notes</code>, <code>POST /tickets/:id/handoffs</code></li>
          <li><code>GET /handoffs</code>, <code>POST /handoffs</code>, <code>PATCH /handoffs/:id</code></li>
          <li><code>PATCH /handoffs/:id/checklist/:taskId</code></li>
          <li><code>GET /conversations/:id/timeline</code></li>
          <li><code>GET /customers</code>, <code>GET /customers/:id</code></li>
          <li><code>GET /channels</code>, <code>PATCH /channels/:id</code></li>
          <li><code>GET /agents</code>, <code>PATCH /agents/:id/status</code></li>
          <li><code>GET /sla-policies</code>, <code>GET /automation-rules</code>, <code>PATCH /automation-rules/:id</code></li>
          <li><code>GET /settings</code>, <code>PATCH /settings/ai-work-queue-automation</code></li>
          <li><code>GET /knowledge</code>, <code>PATCH /knowledge/:id</code></li>
          <li><code>GET /analytics/overview</code>, <code>GET /tracker</code></li>
        </ul>
      </body>
    </html>
    """


def openapi_schema() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Omni Ticket API",
            "version": "0.1.0",
            "description": "Local Python backend slice for the omnichannel operations support PWA.",
        },
        "paths": {
            "/health": {"get": {"summary": "Health check"}},
            "/tickets": {"get": {"summary": "List tickets"}},
            "/tickets/{ticketId}": {"get": {"summary": "Get one ticket"}, "patch": {"summary": "Patch one ticket"}},
            "/tickets/{ticketId}/replies": {"post": {"summary": "Append agent reply"}},
            "/tickets/{ticketId}/notes": {"post": {"summary": "Append internal note"}},
            "/tickets/{ticketId}/handoffs": {"post": {"summary": "Open handoff from ticket"}},
            "/handoffs": {"get": {"summary": "List handoffs"}, "post": {"summary": "Create handoff"}},
            "/handoffs/{handoffId}": {"patch": {"summary": "Patch handoff"}},
            "/handoffs/{handoffId}/checklist/{taskId}": {"patch": {"summary": "Toggle checklist task"}},
            "/conversations/{conversationId}/timeline": {"get": {"summary": "Get ticket timeline"}},
            "/customers": {"get": {"summary": "List customers"}},
            "/customers/{customerId}": {"get": {"summary": "Get one customer"}},
            "/channels": {"get": {"summary": "List channels"}},
            "/channels/{channelId}": {"patch": {"summary": "Patch one channel"}},
            "/agents": {"get": {"summary": "List agents"}},
            "/agents/{agentId}/status": {"patch": {"summary": "Set agent availability"}},
            "/sla-policies": {"get": {"summary": "List SLA policies"}},
            "/automation-rules": {"get": {"summary": "List automation rules"}},
            "/automation-rules/{ruleId}": {"patch": {"summary": "Patch one automation rule"}},
            "/settings": {"get": {"summary": "Get settings"}},
            "/settings/ai-work-queue-automation": {"patch": {"summary": "Toggle AI work queue automation"}},
            "/knowledge": {"get": {"summary": "List knowledge articles"}},
            "/knowledge/{articleId}": {"patch": {"summary": "Patch one knowledge article"}},
            "/analytics/overview": {"get": {"summary": "Get overview metrics"}},
            "/tracker": {"get": {"summary": "Get milestone tracker"}},
        },
    }


class OmniTicketHandler(BaseHTTPRequestHandler):
    server_version = "OmniTicket/0.1"

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def store(self) -> BackendStore:
        return self.server.store  # type: ignore[attr-defined]

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path
        parts = [part for part in path.split("/") if part]

        if method == "GET" and path == "/health":
            return json_response(self, HTTPStatus.OK, {"status": "ok"})
        if method == "GET" and path == "/docs":
            return html_response(self, HTTPStatus.OK, docs_html())
        if method == "GET" and path == "/openapi.json":
            return json_response(self, HTTPStatus.OK, openapi_schema())
        if method == "GET" and path == "/tickets":
            return json_response(self, HTTPStatus.OK, self.store.list_tickets())
        if len(parts) == 2 and parts[0] == "tickets" and method == "GET":
            ticket = self.store.get_ticket(parts[1])
            return json_response(self, HTTPStatus.OK, ticket) if ticket else not_found(self, "Ticket not found")
        if len(parts) == 2 and parts[0] == "tickets" and method == "PATCH":
            ticket = self.store.update_ticket(parts[1], parse_json_body(self))
            return json_response(self, HTTPStatus.OK, ticket) if ticket else not_found(self, "Ticket not found")
        if len(parts) == 3 and parts[0] == "tickets" and method == "POST":
            body = parse_json_body(self)
            event_map = {
                "replies": ("agent-reply", "Omni Agent", "agent"),
                "notes": ("internal-note", body.get("author", "Omni Agent"), "agent"),
            }
            if parts[2] in event_map:
                event_type, author, author_role = event_map[parts[2]]
                ticket = self.store.append_ticket_event(
                    parts[1],
                    event_type,
                    body.get("body", "").strip(),
                    author=author,
                    author_role=author_role,
                )
                return json_response(self, HTTPStatus.CREATED, ticket) if ticket else not_found(self, "Ticket not found")
            if parts[2] == "handoffs":
                payload = body
                payload["conversationId"] = parts[1]
                return json_response(self, HTTPStatus.CREATED, self.store.create_handoff(payload))
        if method == "GET" and path == "/handoffs":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("handoffs"))
        if method == "POST" and path == "/handoffs":
            return json_response(self, HTTPStatus.CREATED, self.store.create_handoff(parse_json_body(self)))
        if len(parts) == 2 and parts[0] == "handoffs" and method == "PATCH":
            handoff = self.store.update_handoff(parts[1], parse_json_body(self))
            return json_response(self, HTTPStatus.OK, handoff) if handoff else not_found(self, "Handoff not found")
        if len(parts) == 4 and parts[0] == "handoffs" and parts[2] == "checklist" and method == "PATCH":
            handoff = self.store.toggle_handoff_checklist(parts[1], parts[3])
            return json_response(self, HTTPStatus.OK, handoff) if handoff else not_found(self, "Checklist task not found")
        if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "timeline" and method == "GET":
            timeline = self.store.timeline(parts[1])
            return json_response(self, HTTPStatus.OK, timeline) if timeline else not_found(self, "Conversation not found")
        if method == "GET" and path == "/customers":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("customers"))
        if len(parts) == 2 and parts[0] == "customers" and method == "GET":
            customer = self.store.get_by_id("customers", parts[1])
            return json_response(self, HTTPStatus.OK, customer) if customer else not_found(self, "Customer not found")
        if method == "GET" and path == "/channels":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("channels"))
        if len(parts) == 2 and parts[0] == "channels" and method == "PATCH":
            channel = self.store.update_channel(parts[1], parse_json_body(self))
            return json_response(self, HTTPStatus.OK, channel) if channel else not_found(self, "Channel not found")
        if method == "GET" and path == "/agents":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("agents"))
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "status" and method == "PATCH":
            payload = parse_json_body(self)
            agent = self.store.update_agent_status(parts[1], payload.get("availability", "available"))
            return json_response(self, HTTPStatus.OK, agent) if agent else not_found(self, "Agent not found")
        if method == "GET" and path == "/sla-policies":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("slaPolicies"))
        if method == "GET" and path == "/automation-rules":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("automationRules"))
        if len(parts) == 2 and parts[0] == "automation-rules" and method == "PATCH":
            rule = self.store.update_rule(parts[1], parse_json_body(self))
            return json_response(self, HTTPStatus.OK, rule) if rule else not_found(self, "Rule not found")
        if method == "GET" and path == "/settings":
            return json_response(self, HTTPStatus.OK, deepcopy(self.store.state["settings"]))
        if method == "PATCH" and path == "/settings/ai-work-queue-automation":
            payload = parse_json_body(self)
            return json_response(
                self,
                HTTPStatus.OK,
                self.store.update_settings(bool(payload.get("aiWorkQueueAutomationEnabled", True))),
            )
        if method == "GET" and path == "/knowledge":
            return json_response(self, HTTPStatus.OK, self.store.list_collection("knowledge"))
        if len(parts) == 2 and parts[0] == "knowledge" and method == "PATCH":
            article = self.store.update_knowledge(parts[1], parse_json_body(self))
            return json_response(self, HTTPStatus.OK, article) if article else not_found(self, "Article not found")
        if method == "GET" and path == "/analytics/overview":
            return json_response(self, HTTPStatus.OK, self.store.analytics())
        if method == "GET" and path == "/tracker":
            return json_response(self, HTTPStatus.OK, deepcopy(self.store.state["tracker"]))

        not_found(self)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    store = BackendStore()
    server = ThreadingHTTPServer((host, port), partial(OmniTicketHandler))
    server.store = store  # type: ignore[attr-defined]
    return server


def main() -> None:
    server = create_server()
    print("Omni Ticket backend listening on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
