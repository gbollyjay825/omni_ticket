# Omni Ticket Production Build Plan

Last updated: 2026-05-29

## Production Goal

Deliver Omni Ticket as a production-ready single-page web app backed by an independent Python API. The same SPA must serve multiple markets, with user access, channel accounts, customers, tickets, settings, SLAs, automation, and reporting scoped by market.

## Non-Negotiable Principles

- One frontend SPA, many markets.
- Every backend request resolves an authenticated user and active market.
- All customer, ticket, channel, queue, handoff, and reporting reads/writes are market-scoped.
- AI Work Queue automation is enabled by default unless an admin disables it for that market.
- AI can recommend and route, but cannot send customer-facing messages without a separately approved policy.
- Real connectors must be provider-isolated, idempotent, signed where applicable, and auditable.
- Production state must live in durable storage, not browser IndexedDB or in-memory backend state.

## Phase 1: Production Platform Foundation

Status: Started. Database foundation, local PostgreSQL runtime, session persistence, market settings persistence, admin user management, customer/company persistence, database-first ticketing core, database-first management surfaces, database-first simulated connector intake, database-first analytics/work-queue reads, market-scoped connector account metadata, durable outbound delivery queue, worker foundation, and deployment packaging implemented locally.

Build:

- Environment configuration for local, staging, and production.
- PostgreSQL-ready SQLAlchemy engine with active local PostgreSQL runtime and local SQLite fallback. Done.
- Alembic migration scaffolding. Done.
- Durable schema for markets, users, sessions, channels, connector accounts, companies, customers, tickets, timeline events, handoffs, knowledge, automation rules, connector events, settings, AI decisions, and audit events. Done.
- Seed baseline local markets and demo users through the database path. Done.
- Health/readiness endpoints that report database connectivity. Done.
- Database-backed login and session validation for protected APIs. Done.
- Database-backed workspace settings, including the AI Work Queue automation switch. Done.
- Database-backed customer and company APIs with restart-safe ticket creation rehydration. Done.
- Database-first ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows. Done.
- Database-first channels, agent status, knowledge articles, and automation-rule management. Done.
- Database-first simulated inbound connector intake for email, WhatsApp, Facebook, Instagram, SMS-style payloads, including customer creation/reuse, ticket creation, connector event persistence, and idempotency. Done.
- Database-first analytics summary and Work Queue reads, including SLA refresh, channel volume, agent occupancy, and priority queue scoring. Done.
- Market-scoped connector account and credential metadata for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice. Done.
- Admin user creation/update APIs for roles, active state, assigned markets, and default market. Done.
- Durable outbound send queue with idempotency, connector-account readiness checks, delivery status, retry endpoint, and dead-letter states. Done.
- Worker entrypoint for outbound retries, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events. Done.
- Docker/Procfile-style packaging for release, web, and worker process definitions. Done.
- Staging/production runtime configuration validation. Done.
- Postgres-safe seed ordering and local `omni_ticket` database smoke coverage. Done.
- CI checks for frontend lint/build plus backend compile, lint, typecheck, unit tests, migration sanity, and worker smoke. Done.

Acceptance:

- Backend boots with database initialization enabled. Done.
- `OMNI_DATABASE_URL` can point at Postgres without code changes. Done at config/engine boundary.
- Local `.env` points `OMNI_DATABASE_URL` at PostgreSQL database `omni_ticket`. Done.
- Local fallback persists data under `data/`. Done.
- Tests prove tables are created and seeded. Done.
- Restart smoke test proves market settings survive API restart and ticket creation honors the persisted AI automation switch. Done.
- Restart smoke test proves newly created customer/company records survive API restart and can open tickets. Done.
- Restart smoke test proves ticket, reply, handoff, timeline, AI decision, and outbound connector event survive API restart. Done.
- Restart smoke test proves channel updates, agent status updates, knowledge articles, and automation rules survive API restart. Done.
- Restart smoke test proves simulated inbound connector intake, connector receipt timeline events, and deduplication survive API restart. Done.
- Restart smoke test proves analytics summary and Work Queue reads use database records after runtime reset. Done.
- Restart smoke test proves connector account status, credential references, webhook verification, and market isolation survive API restart. Done.

Next increment:

- Choose the managed hosting target and wire environment variables, database, API, frontend, and worker process deployment.
- Replace the local-dev outbound adapter with real provider adapters for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice.

## Phase 2: Auth, RBAC, And Market Tenancy

Build:

- Replace prototype local-session shim with database-backed sessions. Done.
- Add production identity adapter boundary for SSO/MFA provider.
- Add role policy checks for agent, supervisor, admin, auditor, and service account. Done for current user roles; service-account policy remains pending.
- Add market-access enforcement in reusable dependencies.
- Add admin user management APIs.
- Add admin user management APIs. Done for local backend.
- Add audit trail for all auth, market switch, and access-denied events.

Acceptance:

- Unauthenticated users cannot enter the app or call protected APIs. Done for local bearer sessions.
- A user assigned only to Ghana cannot read Nigeria/UK records. Done in API tests.
- Admin can add/remove users from markets. Done for local backend and frontend Setup screen.
- Agents, supervisors, admins, and auditors are constrained by route-level RBAC across operations, setup, audit, and readiness APIs. Done.

## Phase 3: Durable Ticketing And Customer Management

Build:

- Add production-grade search, pagination, sorting, optimistic concurrency, and audit metadata around the database-first APIs. Customer, company, settings, auth, users, markets, tickets, timeline, replies, handoffs, AI decisions, inbound/outbound connector events, channels, agents, knowledge, automation rules, analytics, and Work Queue reads are already on the direct database path.
- Expose market-scoped CRUD and search APIs.
- Add pagination, sorting, filtering, optimistic concurrency, and audit metadata.
- Replace frontend local ticket/customer state with authenticated backend snapshots and mutations.

Acceptance:

- Browser refresh preserves tickets/customers. Done locally.
- Ticket replies, notes, status changes, and handoffs persist. Done locally.
- Frontend can run with backend as source of truth. Done locally through the authenticated snapshot and write-through bridge.

## Phase 4: Omnichannel Connectors

Build:

- Email connector: OAuth/IMAP or provider webhook intake, SMTP/provider send, thread mapping, attachments. Account metadata done; real provider adapter pending.
- WhatsApp Business connector: webhook intake, templates, media, receipts. Account metadata done; real provider adapter pending.
- Facebook Messenger connector: page webhook, replies, private reply flow. Account metadata done; real provider adapter pending.
- Instagram DM connector: DM intake, comment-to-DM, media. Account metadata done; real provider adapter pending.
- SMS and voice connector provider boundaries. Account metadata done; real provider adapters pending.
- Connector signature verification, inbound replay protection, provider-specific send adapters, and provider-specific retry policies. Canonical signed webhook verification, delivery-id replay protection, durable outbound queue, send idempotency, and worker retry/dead-letter execution are done locally; provider-native signature adapters remain pending.

Acceptance:

- Each market can own separate channel credentials/accounts.
- Incoming provider events create/update tickets in the correct market.
- Signed webhooks reject invalid signatures, stale timestamps, disabled accounts, and replayed delivery identifiers.
- Outbound sends are auditable and retryable.

## Phase 5: AI Work Queue And Automation Engine

Build:

- Durable AI decisions with confidence, model/provider/version, input references, override history, and prompt metadata.
- Queue scoring by SLA, priority, sentiment, unread state, age, customer value, and market rules.
- Routing by skills, availability, load, occupancy, language, market, and SLA pressure.
- Rules engine for routing, tagging, escalation, notification, and SLA.
- Human override APIs.

Acceptance:

- AI queue automation runs by default per market.
- Admin can disable it per market. Done for the local database path.
- Every AI decision is explainable and auditable.

## Phase 6: SLA, Workforce, Analytics, And Reporting

Build:

- Business hours by market.
- First-response and resolution clocks by priority/customer tier/channel.
- SLA breach jobs and supervisor escalation.
- Worker-triggered SLA refresh. Done locally.
- Workforce occupancy/capacity APIs.
- Analytics rollups for volume, SLA, CSAT, response time, resolution time, backlog age, and channel pressure.
- Worker-triggered analytics rollups. Done locally for current summary metrics.

Acceptance:

- Dashboards use backend rollups, not frontend calculations.
- SLA states update even when no user is actively viewing the ticket.

## Phase 7: Security, Compliance, And Operations

Build:

- Attachment object storage and malware scanning.
- Rate limiting, WAF/deployment rules, request IDs, structured logs, OpenTelemetry traces. Database-backed route limits are done for auth and connector intake, and request ID plus structured access logging is done for API traceability; edge/WAF rules, dashboards, alerting, and full OpenTelemetry export remain pending.
- Backup, retention, export, deletion, and legal hold workflows.
- Secrets management and credential rotation.
- Load tests for queue recompute, webhook ingestion, and ticket reads.
- Deployment scripts and production runbooks.
- Dockerfile, compose stack, Procfile, and deployment docs. Done locally.

Acceptance:

- Staging and production deploy from CI.
- Rollback and recovery are documented and tested.
- Operational alerts exist for connector failures, queue lag, SLA jobs, and database health.

## Current Known Dependencies

- PostgreSQL provider.
- Identity provider/SSO decision.
- WhatsApp Business API credentials.
- Meta app credentials for Facebook Messenger and Instagram DM.
- Mailbox provider credentials.
- SMS/voice provider.
- Object storage and attachment scanning provider.
