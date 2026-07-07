# Omni Ticket — Freshdesk-Parity Backlog

Goal: a fully functional replica of Freshdesk (Freshworks) — no dead links, no
dummy content without a database seed, credentials managed in Settings, UI
excellence + mobile responsiveness. Work happens in **verified vertical slices**:
every slice passes backend gates (ruff, mypy, pytest, alembic) + frontend gates
(tsc, eslint, vite build), is verified live in the preview, and lands as its own
commit on the `Claude` branch. Prod deploys are health-gated with auto-rollback
and only run with explicit user confirmation.

Update this file as items move. Status: ✅ done · 🔨 in progress · ⏳ next · 🧊 deferred

## Core platform (done)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| B-110 | Dashboard parity — live data + working filters | ✅ | server-side `/analytics/summary` (`3415021`) |
| B-111 | Ticket list/detail parity (action bar, composer, shortcuts) | ✅ | `7c271c3` + fixes |
| B-112 | Admin modules parity (Setup focused hub) | ✅ | `79eb7ac` |
| B-113 | Support operations surfaces (field service, exports, threads) | ✅ | earlier phases |
| B-114 | Analytics report library parity | ✅ | earlier phases |
| — | Credential management centralized in Settings (SMTP/IMAP, SSO, providers, widget) | ✅ | migrations 0037–0040 |
| — | Email & team inboxes clarity (transport + team-inbox table + receiving-inbox card) | ✅ | `79eb7ac` |
| — | Search by email/phone (global + list + customers) | ✅ | `d5d38a9` |
| — | Case entity — group a customer's tickets across channels | ✅ | `fb512e1`, `12d5a8e` (migration 0041) |
| — | Linked-case surfacing at triage (Group as case / Add to case / Merge) | ✅ | `19276bc` |
| — | Dashboard drill-downs apply precise filters | ✅ | `34fd037` |
| — | Honest demo seed (multi-channel case; no fabricated metrics) | ✅ | `b956b47` |

## Close-out overhaul (Freshdesk resolve/close semantics)

Audit: 18-agent adversarially-verified review of the close-out flow (2026-06-14).

| Slice | Item | Status | Evidence |
|-------|------|--------|----------|
| A | Lifecycle foundation: `resolved_at`/`closed_at`, frozen SLA outcome (fixes within-SLA drift bug), status timeline + audit | ✅ | `1e47f11` (migration 0042) |
| B | Backend: resolution note, resolution email dispatch (fires the `ticket_resolved` notification), auto-close worker (72h default) | ✅ | `541d021` |
| B | Frontend: resolve dialog (note + notify toggle + required-field guard); "Close no email" honest | ✅ | `23df6cc` |
| C | Public CSAT loop: survey invite on resolve, portal rating capture (no agent auth), rating widget; real customer CSAT feeds dashboard | ✅ | `4fd63db` |
| D | Case/child close-out: resolve case from UI, last-ticket-in-case prompt, block closing parent with open handoff-child tickets | ✅ | `b38ba92` |

## Parity slices E (2026-06-16)

| Slice | Item | Status | Evidence |
|-------|------|--------|----------|
| E1 | Closed vs Resolved as distinct UI statuses (dialog choice, filters, metrics on resolvedAt) | ✅ | `8b57637` |
| E2 | ticket_created ack + sla_breach notifications actually fire (config-gated) | ✅ | `bb65eb7` |
| E3 | Scenario-automation execution engine (validated, guarded, one-click run) | ✅ | `53b9343` + fixes |
| E4 | Handoff ↔ child ticket status sync (both directions; cancel closes child) | ✅ | `21e1f19` + fixes |
| — | Pre-deploy adversarial review: 24 agents, 17 confirmed findings fixed (1 critical) | ✅ | `5834d48` |
| F1 | Channel control shows LIVE stats (queued/active/SLA-risk/health from real tickets; real avg-wait; paused channels skip auto-assign) — was frozen seed numbers | ✅ | see git log |
| F2 | Customer 360 health/CSAT computed from real tickets + ratings (was seeded score / hardcoded 72 / fabricated CSAT); system service accounts hidden from Contacts | ✅ | see git log |

## Deploy state

- Prod (omni.wakanow.com): release `Claude-20260609175731` = up to `b956b47`.
- Shipping now: `3415021`…HEAD — server analytics + close-out A–D + parity E1–E4 + review fixes (includes migration **0042**).

## Deferred / known gaps (parity nice-to-haves)

| Item | Notes |
|------|-------|
| Microsoft 365 OAuth2 (XOAUTH2) IMAP intake | Current adapter is password-auth; M365 disabled basic auth. Needed only if support mailbox is on M365 — awaiting mailbox-provider confirmation. |
| Advanced ticketing / Purchase history admin tiles | Hidden pending build (B-113 leftovers). |
| Time logs: server-side + stop/stamp on resolve | Currently manual localStorage entries. |
