# Omni Ticket Backend Development Backlog

Last updated: 2026-05-29

## Current Milestone

Status: Working Python/FastAPI vertical slice is running locally on `http://127.0.0.1:8000` against local PostgreSQL database `omni_ticket`, with the primary mutable operational paths, core operational reads, market-scoped connector account metadata, admin user management, durable outbound delivery queue, worker foundation, and deployment packaging moved onto SQLAlchemy-backed repositories. Local smoke tests pass, and the repository now includes a GitHub Actions CI workflow for lint, typecheck, and tests.

Completed in this build:

- Independent backend repository and virtual environment.
- FastAPI app, config, CORS, health route, and Swagger docs.
- Typed domain model for channels, connector accounts, agents, companies, customers, tickets, SLA, timeline, handoffs, knowledge, rules, connector events, audit, settings, and AI decisions.
- In-memory repository boundary with realistic seeded omnichannel data.
- Ticket, timeline, reply, handoff, customer, company, knowledge, rule, analytics, settings, connector, audit, and tracker APIs.
- AI Work Queue automation default-on with admin disable switch.
- Login/session flow with user role and market context.
- Market-scoped access so one SPA can serve Nigeria, Ghana, UK, and future markets.
- Connector intake simulation for email/WhatsApp/Facebook/Instagram/SMS-style payloads with idempotency.
- Production persistence foundation with SQLAlchemy, Alembic, PostgreSQL-ready configuration, local SQLite fallback, and readiness endpoint.
- Database-backed local auth/session validation with market access enforcement.
- Database-backed workspace settings with durable AI Work Queue automation enable/disable behavior.
- Database-backed customer and company APIs with restart-safe rehydration before ticket creation.
- Database-first ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows.
- Database-first channel, agent status, knowledge article, and automation-rule management workflows.
- Database-first simulated inbound connector intake with customer creation/reuse, ticket creation, connector receipt timeline events, and idempotent deduplication.
- Database-first analytics summary and Work Queue reads with SLA refresh, channel volume, agent occupancy, and queue scoring.
- Database-backed connector account readiness for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice, including status, credential reference, webhook state, send permission, failures, capabilities, and market isolation.
- Database-backed admin user creation and update APIs for role, active status, market assignment, and default market.
- Database-backed outbound message queue for public replies with idempotency keys, connector-account readiness checks, delivery status, retry, and dead-letter states.
- Background worker service and `python -m app.worker` entrypoint for due outbound retries, dead-letter handling, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events.
- Dockerfile, Procfile, compose stack, `.env.example`, deployment docs, and staging/production configuration validation for separate release, web, and worker processes.
- Isolated smoke-test path that rebinds backend tests to a temporary SQLite database instead of mutating the repo-default PostgreSQL runtime.
- Database-backed ticket task completion updates through the existing ticket patch API, with persistence across runtime reset.
- Local PostgreSQL runtime configured through `.env` with Postgres-safe seed ordering.
- Database-backed mirror for channels, agents, companies, customers, tickets, timeline events, handoffs, knowledge, rules, connector events, AI decisions, and audit history, with startup rehydration into the runtime store.
- Smoke tests, lint, and typecheck passing.
- GitHub Actions CI workflow added for `ruff`, `mypy`, and `pytest`.

Known production dependencies:

- PostgreSQL provider.
- Identity provider and tenant/RBAC policy.
- WhatsApp Business API credentials.
- Meta app credentials for Facebook Messenger and Instagram DM.
- Mailbox provider credentials.
- SMS/voice provider credentials.
- Attachment object storage and scanning.

## Phase 0: Repository Foundation

1. Initialize independent Python repository. Done.
2. Add FastAPI app shell, health route, test harness, linting, typing, and environment config. Done.
3. Add CI pipeline for lint, typecheck, tests, and build. Done for backend lint/typecheck/tests; frontend build remains tracked in the separate frontend repo.
4. Define environment strategy for local, staging, and production. Done for current deployable package, including isolated smoke-test database rebinding; hosting-specific values pending.

## Phase 1: Data Platform

1. Choose and provision PostgreSQL. Local PostgreSQL runtime is active; managed production provider pending.
2. Add SQLAlchemy or SQLModel models and Alembic migrations. Done.
3. Model tenants, users, roles, teams, agents, customers, companies, channels, tickets, timeline events, SLAs, handoffs, knowledge articles, settings, and audit events. Done at schema level.
4. Add seed data migration for local development. Started with database seeding from reference data.
5. Add repository layer with transaction boundaries. Auth/session/settings/customer/company/ticket/timeline/handoff/channel/agent/knowledge/rule/inbound connector/analytics/work-queue/connector account/outbound queue/worker paths are database-first; production deployment scheduling and observability remain pending.

## Phase 2: Auth, Tenancy, And Security

1. Implement authentication provider integration. Database-backed local sessions done; production provider pending.
2. Add RBAC for agent, supervisor, admin, auditor, and service account roles. Started with admin-only user management.
3. Add tenant isolation middleware and database scoping. Session/user/market scoping and the primary operational write/read paths now enforce market scope through database-backed routes.
4. Add audit logging for every write action. Started.
5. Add attachment metadata model and malware scanning integration point. Pending dependency.

## Phase 3: Ticket And Conversation APIs

1. Implement ticket CRUD. Database-first local path done.
2. Implement conversation timeline append/read APIs. Database-first local path done.
3. Implement reply, note, and handoff endpoints. Database-first local path done.
4. Implement customer lookup and Customer 360 APIs. Database-backed customer/company list, create, detail, and update paths done.
5. Implement status, priority, assignee, tags, task, and SLA update APIs. Started with database-backed ticket field and task updates plus frontend-compatible channel/agent/settings mutation routes.

## Phase 4: AI Work Queue Automation

1. Add tenant setting `ai_work_queue_automation_enabled` defaulting to `true`. Done.
2. Build Work Queue scoring service for SLA, priority, sentiment, unread state, customer value, and age. Database-first read path done; deeper scoring factors still pending.
3. Build AI classification pipeline for channel, intent, topic, priority, sentiment, language, and duplicate detection. Started with deterministic classifier.
4. Build routing service for queue, group, and owner assignment using skills, availability, occupancy, capacity, channel, and SLA risk. Started.
5. Build next-action recommendation service for reply draft, article, escalation, and handoff. Started.
6. Persist AI decisions, confidence, model version, prompt/input references, and override history. Database-first ticket creation path done.
7. Add admin endpoint to disable or enable AI Work Queue automation. Done.
8. Add manual override endpoints for priority, routing, owner, and recommendation. Done with `POST /api/v1/work-queue/{ticket_id}/override`.
9. Add tests proving automation runs by default and stops when disabled. Done.
10. Persist the AI automation setting by market and prove it survives API restart. Done.

## Phase 5: SLA And Escalation Engine

1. Model business hours and priority-based response targets. Started.
2. Calculate first response and resolution promises. Done.
3. Add background job to update risk and breach states. Done with `python -m app.worker`; deployment scheduler pending.
4. Add escalation policies by channel, priority, customer tier, and queue.
5. Add supervisor notification events.

## Phase 6: Omnichannel Connectors

1. Email connector: inbound mailbox sync, outbound send, thread mapping, attachments. Database-first simulated intake, account metadata, outbound queue, and local-dev send adapter done; real provider adapter pending.
2. WhatsApp connector: webhook intake, template messages, media, delivery receipts. Database-first simulated intake, account metadata, outbound queue, and local-dev send adapter done; real provider adapter pending.
3. Facebook Messenger connector: page webhook intake, replies, private reply flow, delivery state. Database-first simulated intake, account metadata, outbound queue, and local-dev send adapter done; real provider adapter pending.
4. Instagram DM connector: DM intake, comment-to-DM handoff, media, reply state. Database-first simulated intake, account metadata, outbound queue, and local-dev send adapter done; real provider adapter pending.
5. SMS connector: inbound/outbound texts and delivery receipts. Database-first simulated intake, account metadata, outbound queue, and local-dev send adapter done; real provider adapter pending.
6. Phone/voice connector: call logs, callback requests, voicemail summaries. Account metadata done; real provider adapter pending.
7. Portal connector: authenticated customer updates and article deflection.
8. Partner/API connector: webhook intake, idempotency, replay protection.

## Phase 7: Handoffs And Internal Operations

1. Implement structured handoff lifecycle. Done.
2. Add receiving team acceptance, blocker, due date, checklist, and close-loop actions. Started.
3. Write handoff changes back into ticket timeline. Done.
4. Add SLA impact and customer update prompts for blocked handoffs.

## Phase 8: Knowledge And Automation Rules

1. Implement knowledge article CRUD and approval state. Started.
2. Add article suggestion index by intent, channel, language, and tags.
3. Implement automation rules engine for routing, SLA, escalation, tagging, and notifications. Rule management started; execution engine pending.
4. Add rule health, last fired, failure count, and safe rollback.

## Phase 9: Analytics And Workforce

1. Build analytics rollups for volume, SLA, CSAT, queue pressure, response time, resolution time, and backlog age. Database-first summary read and worker-triggered rollup are done; historical rollup tables still pending.
2. Build workforce APIs for availability, occupancy, capacity, load, and skills. Started through agents API and database-first analytics occupancy reads.
3. Add supervisor recommendations for reassignment and channel pressure.

## Phase 10: Production Hardening

1. Add rate limiting and connector signature verification.
2. Add idempotency keys for all inbound webhooks and outbound sends.
3. Add retry policies and dead-letter queues. Done locally with the durable outbound message queue and worker execution; provider-specific retry policies and deployment alerting pending.
4. Add observability dashboards and alerting.
5. Add backup, retention, export, and deletion workflows.
6. Add load tests for queue recompute, webhook ingestion, and ticket timeline reads.

## Phase 11: Frontend Auth And Market UX

1. Add login gate to the SPA. Done.
2. Store backend bearer session locally for the prototype. Done.
3. Add market selector for users assigned to multiple markets. Done.
4. Display active market in the command header and sidebar. Done.
5. Send auth and market headers on backend sync and settings writes. Done.
6. Replace local IndexedDB ticket/customer state with backend market snapshots. Done locally for the current authenticated SPA bridge.
7. Add proper user management screen for admins. Done for local backend role, status, and market assignment management.

## Integration Notes

- Added a frontend-oriented snapshot endpoint at `GET /api/v1/frontend/snapshot` so the PWA can hydrate against one backend payload while the writable frontend workspace remains separate.
- Added compatibility aliases for `GET /api/v1/analytics/overview`, `PATCH /api/v1/settings/ai-work-queue-automation`, `PATCH /api/v1/channels/{channel_id}`, and `PATCH /api/v1/agents/{agent_id}/status`.
- The frontend repository now hydrates the primary operational views from authenticated market snapshots and writes key ticket, reply, note, handoff, settings, connector, and user-management mutations back through the backend bridge.
- Added production-readiness endpoint at `GET /api/v1/platform/readiness` to verify database connectivity and required table presence.
- Added `docs/PRODUCTION_BUILD_PLAN.md` as the long-running execution plan toward production readiness.
- Auth login now creates durable `sessions` rows and protected endpoints validate user and market access through the database.
- Settings reads/writes now use `workspace_settings`; ticket creation and connector intake honor the persisted AI automation switch.
- Customer and company endpoints now use database records directly and can rehydrate a customer/company into the runtime ticket service after API restart.
- Ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event endpoints now write database records directly.
- Channel, agent status, knowledge article, and automation-rule endpoints now write database records directly.
- Simulated inbound connector intake now writes customer, ticket, connector event, connector receipt timeline, and audit records directly.
- Analytics summary and Work Queue endpoints now read from database records directly and refresh the runtime snapshot only for frontend compatibility.
- Connector account endpoints now expose market-scoped provider readiness at `GET/POST/PATCH /api/v1/connectors/accounts` with `/api/v1/connector-accounts` aliases.
- Outbound message endpoints now expose `GET /api/v1/outbound/messages` and `POST /api/v1/outbound/messages/{message_id}/retry` for delivery visibility and manual retry.
- Worker execution is available through `python -m app.worker --once` or continuous interval mode for outbound retry/dead-letter processing, SLA refresh, Work Queue recompute, analytics rollups, and audit records.
- The frontend Setup screen now renders a connector control center for Email, WhatsApp, Facebook Messenger, Instagram DM, SMS, and voice using backend connector account data.
- Auth user endpoints now expose `GET/POST/PATCH /api/v1/auth/users` so admins can create users, change roles, activate/deactivate users, and assign market access.
- Added `POST /api/v1/work-queue/{ticket_id}/override` so operators can apply manual routing, priority, owner, recommendation, and tag overrides with audit and timeline history.
- The local backend now runs from PostgreSQL database `omni_ticket` through `.env`, while SQLite remains available as a fallback if `OMNI_DATABASE_URL` is changed.
- Mutable operational resources now persist through a SQLAlchemy-backed mirror and are loaded back into the runtime store during startup so local restarts retain state.
- Added `.github/workflows/ci.yml` so the backend repo now has repeatable lint, typecheck, and test automation on push and pull request.
- Added backend `Dockerfile`, `Procfile`, `docker-compose.yml`, `.env.example`, and `docs/DEPLOYMENT.md` for release/web/worker deployment packaging.
