# Omni Ticket UI Plan

## Product Principles

- Start in operations. The first screen is an Omni Command center with live support pressure and fast entry into work.
- Treat channels as first-class. Email, web chat, phone/voice, WhatsApp, SMS, Instagram, Facebook, portal, API, and internal handoffs must be visible and filterable.
- Keep agent work dense but readable. The app is for repeated daily operations, not marketing.
- Preserve customer continuity across channels with one timeline and one customer 360 profile.
- Make AI assistance visible as decision support, not magic: summary, sentiment, intent, tags, suggested reply, article, and escalation reason.
- Keep AI Work Queue automation on by default for triage, routing, prioritization, assignment, and next-action guidance unless an admin turns it off in Setup.
- Make offline state honest: cached workspace, local drafts, and an offline outbox for simulated sends.

## Primary Users

- Agent: works assigned tickets, replies across channels, adds notes, escalates, and uses knowledge/macros.
- Supervisor: monitors queues, SLA risk, agent availability, channel health, and escalations.
- Operations Admin: manages channels, automations, SLAs, teams, forms, roles, and knowledge workflows.
- Product/Project Owner: tracks epics, backlog, pending items, closed issues, and implementation status.

## Navigation

- Omni Command: live operations board, channel queues, AI alerts, SLA watch, workforce load, and supervisor actions.
- Unified Inbox: all conversations with filters for channel, status, SLA, priority, sentiment, group, and assignee.
- Live Channels: channel health, queue depth, response targets, availability, and active conversations by channel.
- Customers: customer 360 records with contact methods, health, open issues, history, and preferred channel.
- Knowledge: article library, approval state, suggested articles, deflection, and portal readiness.
- Automation: routing rules, SLA policies, escalation flows, business hours, and rule health.
- Handoffs: structured cross-team queue for requested, accepted, in-progress, blocked, and completed internal handoffs.
- Analytics: channel volume, SLA compliance, CSAT, response time, resolution time, agent performance.
- Workforce: agent status, occupancy, skill coverage, active load, shifts, and reassignment recommendations.
- Setup: roles, fields, forms, groups, connector control center, audit/security posture, PWA status.
- Setup: includes an AI Work Queue automation switch that defaults on and controls whether backend AI performs triage, routing, prioritization, owner assignment, and next-action recommendations.
- Setup: shows market-scoped Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice account readiness with credential reference state, webhook health, send permission, failure count, and capabilities.
- Project Tracker: epics, backlog, pending items, and closed issues for the build.

## Core Screen Requirements

Omni Command:

- KPI strip: open conversations, SLA at risk, active channels, CSAT, occupancy, offline outbox.
- Channel command grid: each channel shows state, queue depth, active work, SLA pressure, response target, and health.
- AI alerts: breach risk, sentiment spikes, duplicate detection, article gaps, automation failures.
- Supervisor actions: reassign, trigger escalation, pause channel intake, broadcast note, review automations.
- Workforce snapshot: agent availability, current load, skills, occupancy, and recommended redistribution.

Unified Inbox:

- Left filter column: saved queues, channel filters, SLA filters, priority, assignee, sentiment, status.
- Center conversation list: channel icon, requester, subject, preview, priority, SLA state, age, assignee, tags.
- Detail cockpit: header, timeline, composer, customer 360, SLA card, Copilot card, properties, tasks, article suggestions.
- Composer modes: reply, internal note, handoff. Handoff mode includes receiving team, reason, channel selector, macro selector, suggested reply, translation toggle, attachment placeholder, and offline queue behavior.

Handoffs:

- Summary strip for active, due-soon, blocked, and completed handoffs.
- Board columns for requested, accepted, in-progress, blocked, and completed work.
- Each handoff card shows ticket, customer, source team, receiving team, owner, due time, priority, reason, checklist progress, blockers, status control, and quick open-ticket action.
- Status changes write back to the ticket timeline so the support history stays complete.

Live Channels:

- Channel cards for email, chat, phone, WhatsApp, SMS, Instagram, Facebook, portal, API, internal handoffs.
- Each card includes queue depth, active sessions, average wait, target response, health, and intake status.

Customers:

- Searchable customer list and detail profile.
- Customer health, preferred channels, contact methods, open conversations, lifetime stats, recent timeline, tags.

Knowledge/Automation/Admin:

- Dense operational tables with status chips, health bars, owners, last updated, and quick actions.
- No decorative hero sections or nested cards.

## Responsive Behavior

- Desktop: operations shell with rail navigation and dense multi-column workspace.
- Tablet: navigation rail compacts; inbox detail moves below list when needed.
- Mobile: bottom navigation, stacked queues/list/detail, composer remains usable, tables become cards.

## Visual Direction

- Neutral operational base with distinct status colors: teal for healthy/routing, blue for information, amber for risk, red for breach, green for success, violet for AI.
- Compact typography with stable table/card dimensions.
- Lucide icons for channels, actions, filters, status, and admin tools.
- Avoid one-color dashboards; channel/status states must be scannable.

## Accessibility

- Semantic buttons and form controls.
- Clear focus styles.
- No hover-only critical actions.
- Contrast-conscious chips and badges.
- Keyboard-reachable filters and composer actions.
- Text must not overlap at desktop, tablet, or mobile widths.
