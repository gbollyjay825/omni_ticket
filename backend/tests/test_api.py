from __future__ import annotations

import unittest

from backend.app import docs_html, openapi_schema
from backend.store import BackendStore


class ApiSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.store = BackendStore()

    def test_reply_updates_ticket(self) -> None:
        ticket = self.store.append_ticket_event(
            "conv-1001",
            "agent-reply",
            "We have confirmed the processor trace.",
            author="Omni Agent",
            author_role="agent",
        )
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["status"], "pending")
        self.assertEqual(ticket["timeline"][-1]["type"], "agent-reply")

    def test_toggle_setting(self) -> None:
        settings = self.store.update_settings(False)
        self.assertFalse(settings["aiWorkQueueAutomationEnabled"])

    def test_toggle_handoff_checklist(self) -> None:
        handoff = self.store.toggle_handoff_checklist("handoff-1001", "handoff-1001-2")
        self.assertIsNotNone(handoff)
        self.assertTrue(handoff["checklist"][1]["done"])

    def test_docs_and_schema(self) -> None:
        self.assertIn("Omni Ticket API", docs_html())
        schema = openapi_schema()
        self.assertIn("/tickets", schema["paths"])

    def test_analytics_shape(self) -> None:
        analytics = self.store.analytics()
        self.assertEqual(set(analytics), {"openTickets", "riskTickets", "avgChannelHealth", "avgAgentOccupancy", "aiWorkQueueAutomationEnabled"})


if __name__ == "__main__":
    unittest.main()
