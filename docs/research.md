# Omni Ticket Research Notes

Research date: 2026-05-25

## Freshdesk/Freshworks Product Signals

Omni Ticket is being rebuilt as a generic omnichannel operations support PWA inspired by current Freshdesk/Freshworks product patterns. The goal is not to clone Freshworks branding or connect to Freshdesk credentials in this phase; it is to capture the operating model of a mature omnichannel helpdesk.

Freshdesk/Freshworks patterns reflected in this build:

- Unified support inbox: agents need one queue where email, chat, phone, WhatsApp, SMS, social, portal, API, and internal handoffs can be triaged together.
- Ticket detail as an operating cockpit: the ticket view should combine timeline, customer profile, SLA state, assignment, tags, priority, linked articles, and next best action.
- Omnichannel continuity: channel changes should not fragment the customer history. A chat can become a ticket, a call can add a voice log, and a portal reply should preserve context.
- Automation and SLA controls: support operations need dispatch rules, skill-based routing, workload balancing, business hours, first-response and resolution timers, escalations, and breached/risk queues.
- AI assistance: Freshworks emphasizes Freddy AI for summaries, suggested responses, customer sentiment, intent, classification, article suggestions, and service insights. Omni Ticket will simulate these surfaces without live model calls.
- Self-service and knowledge: the app should include knowledge articles, article approval states, deflection metrics, suggested articles, and portal-oriented content.
- Analytics and workforce visibility: managers need channel volume, SLA compliance, resolution time, CSAT, channel health, agent availability, occupancy, queue pressure, and escalations.
- Admin/security posture: production-grade helpdesk products include roles, groups, fields/forms, audit trail, integrations, branding, compliance, and channel credentials.
- API-aligned resource boundaries: tickets, conversations, contacts/customers, companies, agents, groups, ticket fields, articles, rules, and analytics are treated as separable resources.

## Required Product Shape

The rebuilt app should open directly into an **Omni Command** center, not a landing page. It should make a support operations lead feel that they can immediately understand:

- Which channels are under pressure.
- Which tickets risk SLA breach.
- Which agents are available or overloaded.
- Which customers need escalation.
- What Copilot recommends next.
- Which automations are firing or failing.
- Which backlog items and implementation epics are done or pending.

## Sources

- Freshdesk features overview: https://www.freshworks.com/freshdesk/features/
- Freshdesk omnichannel customer support use case: https://www.freshworks.com/freshdesk/usecases/omnichannel-customer-support/
- Freshdesk AI/Freddy overview: https://www.freshworks.com/freshdesk/ai/
- Freshdesk reporting and analytics: https://www.freshworks.com/freshdesk/reporting-analytics/
- Freshdesk ticketing overview: https://www.freshworks.com/freshdesk/ticketing/
- Freshdesk support docs, ticket details view: https://support.freshdesk.com/en/support/solutions/articles/37588-understand-the-ticket-details-view
- Freshdesk support docs, ticket fields: https://support.freshdesk.com/en/support/solutions/articles/50000010094-understand-and-customize-ticket-fields
- Freshdesk SDK Tickets API: https://developers.freshworks.com/freshdesk-sdk/docs/TicketsApi.html
- Freshdesk SDK Conversations API: https://developers.freshworks.com/freshdesk-sdk/docs/ConversationsApi.html
- Freshdesk SDK Contacts API: https://developers.freshworks.com/freshdesk-sdk/docs/ContactsApi.html
