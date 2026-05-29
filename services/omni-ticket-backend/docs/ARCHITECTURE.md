# Omni Ticket Backend Architecture

## Goal

Build an independent Python backend for Omni Ticket that powers ticketing, omnichannel communication, AI queue automation, SLA tracking, customer management, handoffs, analytics, and admin controls.

## Backend Stack

- Python 3.11+
- FastAPI for APIs
- Pydantic for validation and settings
- SQLAlchemy persistence foundation with active local PostgreSQL runtime and SQLite fallback
- PostgreSQL for transactional production data
- Redis for queues, locks, short-lived cache, rate limits, and connector state in the production phase
- Celery, Dramatiq, or RQ for background work in the production phase
- OpenTelemetry-compatible logging/tracing
- Object storage for attachments

## Current Vertical Slice

The current backend is intentionally usable before the production data platform is selected. It includes typed domain models, seeded operational data, an in-memory repository boundary, live FastAPI routes, connector intake simulation, queue automation, SLA risk refresh, audit events, and tests. The repository boundary is designed to be replaced by PostgreSQL without changing the public API contract.

The production persistence foundation now includes:

- `OMNI_DATABASE_URL` configuration.
- SQLAlchemy engine/session setup.
- Alembic migration scaffolding.
- Local PostgreSQL database `omni_ticket` configured through `.env`.
- Durable schema for markets, users, sessions, channels, connector accounts, agents, companies, customers, tickets, timeline events, handoffs, knowledge, rules, connector events, settings, AI decisions, and audit events.
- Local SQLite fallback under `data/` for development.
- `GET /api/v1/platform/readiness` to verify database connectivity and required tables.
- Database-backed bearer sessions for local login and protected API request context.
- Route-level RBAC for agents, supervisors, admins, and auditors across operational writes, setup controls, audit visibility, and platform readiness.
- Database-backed workspace settings per market, including the AI Work Queue automation switch.
- Database-backed customer and company APIs with state rehydration before ticket creation.
- Database-first ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows.
- Database-backed handoff lifecycle updates for acceptance, blocker capture, due-date changes, checklist progress, and close-loop timeline history.
- Database-first ticket task completion updates through the existing ticket mutation path.
- Database-first channel, agent status, knowledge article, and automation-rule management workflows.
- Database-first automation-rule execution during ticket creation for routing, priority escalation, tags, checklist tasks, rule `last_fired_at`, failure count, timeline history, and audit history.
- Database-first simulated inbound connector intake that creates/reuses customers, creates tickets, records connector events, writes connector receipt timeline events, and deduplicates provider payloads.
- Database-first analytics summary and Work Queue reads that refresh SLA state, score priority queues, calculate channel volume, and report active agent occupancy.
- Database-backed connector account readiness for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice, including credential references rather than raw secrets.
- Signed connector webhook endpoint for provider callbacks with account readiness checks, HMAC verification, timestamp freshness, delivery-id replay protection, connector-account failure state, and audit history.
- Database-backed fixed-window rate limiter for login, authenticated connector intake, and signed provider webhooks, returning `429` plus `Retry-After` before expensive downstream work.
- Database-backed admin user creation and management for role, active state, market assignment, and default market.
- Database-backed outbound message queue for public replies, including idempotency keys, connector-account readiness checks, delivery status, retry, and dead-letter states.
- Background worker service and `python -m app.worker` entrypoint for due outbound retries, dead-letter handling, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events.
- Deployment packaging with Dockerfile, Procfile, compose stack, `.env.example`, and staging/production configuration validation.
- Test-only database rebinding so smoke tests can run against a temporary SQLite file instead of the repo-default PostgreSQL database.
- Runtime-store mirroring for channels, agents, companies, customers, tickets, timeline events, handoffs, knowledge, rules, connector events, AI decisions, and audit history, with startup hydration from the database.
- Repository CI automation for backend lint, typecheck, and tests on push and pull request.

The current API keeps the in-memory store as a compatibility cache for the frontend snapshot while core operational reads and writes move through SQLAlchemy-backed repositories. Auth, users, markets, sessions, workspace settings, customers, companies, tickets, ticket tasks, timelines, replies, handoffs, AI decisions, inbound/outbound connector events, outbound messages, connector accounts, channels, agents, knowledge, automation rule management and execution, analytics summary, and Work Queue reads are on the direct database path.

## Market And User Boundary

Omni Ticket is a single SPA that serves multiple markets. The backend now resolves every protected request through a session token plus `X-Omni-Market` header. A user can belong to one or more markets, and every operational resource is scoped by market before it is returned or mutated.

Current market-scoped resources:

- Channels and channel accounts, including support email, WhatsApp number, Facebook page, and Instagram handle.
- Connector accounts and credential references for each market-owned provider account.
- Agents and users assigned to market access lists.
- Companies, customers, tickets, handoffs, connector events, settings, rules, analytics, and audit events.

Current local auth model:

- `POST /api/v1/auth/login` returns a bearer token, user, active market, and available markets from durable user/market records.
- `GET /api/v1/auth/me` validates the current database session and market.
- `GET /api/v1/auth/markets` lists database markets assigned to the user.
- `GET /api/v1/auth/users` lists database users visible to supervisors/admins.
- `POST /api/v1/auth/users` creates database-backed users for admins.
- `PATCH /api/v1/auth/users/{user_id}` updates user role, active state, market assignments, and default market.

Production auth still needs a real identity provider, password policy, MFA/SSO, token expiry/refresh, deeper RBAC policy enforcement, and audit events for auth decisions.

Current role policy:

- Agents can read market work and perform day-to-day ticket, reply, note, customer, company, handoff, and connector-intake operations.
- Supervisors can use workforce/channel controls, work-queue overrides, outbound retries, audit views, readiness checks, and knowledge publishing controls.
- Admins can manage setup surfaces such as users, settings, connector accounts, and automation rules.
- Auditors are read-only and can inspect operational records plus audit history without mutating customer or ticket data.

## Core Services

- Auth and tenant service
- Customer service
- Ticket service
- Conversation timeline service
- Work Queue service
- AI automation service
- SLA service
- Handoff service
- Knowledge service
- Channel connector service
- Notification service
- Audit service
- Analytics service
- Background worker service

## Background Worker

The backend now has a production-shaped worker entrypoint:

```bash
python -m app.worker --once --market-id market-ng
```

Without `--once`, it runs continuously on an interval. The worker currently performs these market-scoped jobs:

- Process due outbound messages where status is queued, retrying, failed with a due `next_attempt_at`, or stale sending.
- Retry failed sends through the local-dev provider adapter and dead-letter messages after max attempts.
- Refresh SLA risk and breach state for open tickets.
- Recompute the Work Queue ordering using the same scoring service used by the API.
- Run analytics summary rollups.
- Write worker audit events for traceability.

Production deployment should run this as a separate process from the FastAPI web service. The later production phase can swap the interval loop for Celery, Dramatiq, RQ, or a managed scheduler without changing the current service boundary.

## Deployment Packaging

The backend package defines three deployable process types:

- `release`: `alembic upgrade head`
- `web`: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `worker`: `python -m app.worker --interval-seconds ${OMNI_WORKER_INTERVAL_SECONDS:-60}`

The `Dockerfile` builds the Python runtime image. `docker-compose.yml` provides a local staging-style stack with Postgres, migrations, API, and worker. `docs/DEPLOYMENT.md` documents required environment variables and guardrails.

When `OMNI_ENVIRONMENT` is `staging` or `production`, startup validation requires PostgreSQL, explicit CORS origins, positive worker settings, and `OMNI_INITIALIZE_DATABASE=false` so migrations run as a release step instead of silently seeding demo data.

## AI Work Queue Automation

AI Work Queue automation must be enabled by default for every tenant unless an admin disables it in settings.

When enabled, backend automation must:

- Classify channel, intent, topic, language, priority, sentiment, and SLA risk.
- Detect duplicates and related open tickets.
- Route tickets to queue, group, and owner by skill, availability, occupancy, customer tier, and SLA pressure.
- Rank the Work Queue by urgency and operational risk.
- Recommend next action, reply draft, article, escalation, or handoff.
- Record every AI decision as an auditable event with confidence, model version, input references, and override status.

When disabled, backend behavior must:

- Continue creating tickets and ingesting messages.
- Leave routing, priority, owner assignment, and next action as manual operations.
- Preserve manual audit events.

This enable/disable setting now persists in `workspace_settings`. Ticket creation and simulated connector intake read the database value before applying routing automation.

AI should not autonomously send customer-facing messages without a separately approved policy.

## API Boundary

- `GET /api/v1/health`
- `GET /api/v1/platform/readiness`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/markets`
- `GET /api/v1/auth/users`
- `POST /api/v1/auth/users`
- `PATCH /api/v1/auth/users/{user_id}`
- `GET /api/v1/settings`
- `PATCH /api/v1/settings`
- `GET /api/v1/companies`
- `POST /api/v1/companies`
- `PATCH /api/v1/companies/{company_id}`
- `GET /api/v1/customers`
- `POST /api/v1/customers`
- `GET /api/v1/customers/{customer_id}`
- `PATCH /api/v1/customers/{customer_id}`
- `GET /api/v1/tickets`
- `POST /api/v1/tickets`
- `GET /api/v1/tickets/{ticket_id}`
- `PATCH /api/v1/tickets/{ticket_id}`
- `GET /api/v1/tickets/{ticket_id}/timeline`
- `POST /api/v1/tickets/{ticket_id}/timeline`
- `POST /api/v1/tickets/{ticket_id}/reply`
- `POST /api/v1/tickets/{ticket_id}/handoffs`
- `GET /api/v1/work-queue`
- `POST /api/v1/work-queue/{ticket_id}/override`
- `GET /api/v1/channels`
- `PATCH /api/v1/channels/{channel_id}`
- `GET /api/v1/agents`
- `PATCH /api/v1/agents/{agent_id}/status`
- `POST /api/v1/connectors/inbound`
- `GET /api/v1/connectors/accounts`
- `POST /api/v1/connectors/accounts`
- `PATCH /api/v1/connectors/accounts/{account_id}`
- `GET /api/v1/connectors/providers`
- `GET /api/v1/connectors/events`
- `GET /api/v1/outbound/messages`
- `POST /api/v1/outbound/messages/{message_id}/retry`
- `GET /api/v1/handoffs`
- `PATCH /api/v1/handoffs/{handoff_id}`
- `GET /api/v1/knowledge`
- `POST /api/v1/knowledge`
- `PATCH /api/v1/knowledge/{article_id}`
- `GET /api/v1/automation-rules`
- `POST /api/v1/automation-rules`
- `PATCH /api/v1/automation-rules/{rule_id}`
- `GET /api/v1/analytics/summary`
- `GET /api/v1/analytics/overview`
- `GET /api/v1/audit`
- `GET /api/v1/tracker`
- `GET /api/v1/frontend/snapshot`
- `PATCH /api/v1/settings/ai-work-queue-automation`

Planned production additions:

- `POST /api/v1/work-queue/recompute`
- `POST /api/v1/work-queue/{ticket_id}/override`
- `PATCH /api/v1/channels/{channel_id}`
- Provider-specific webhook signature adapters for email, WhatsApp, Facebook Messenger, Instagram DM, SMS, and voice on top of the canonical signed webhook boundary.

## Repository Boundary

This backend must remain a separate repository from the frontend PWA. The frontend consumes this backend through HTTP APIs and does not share persistence or server-side connector code.

To reduce coupling during the transition away from seeded frontend data, the backend now also exposes a frontend-oriented snapshot payload plus a small set of compatibility mutation routes. That keeps the repository boundary intact while making incremental frontend hydration possible without waiting for full persistence or auth rollout.

At the moment, the remaining compatibility layer is primarily the frontend snapshot cache and provider adapter mocks. Core mutable resources and operational reads now move through database-first repositories, and the runtime store is refreshed from those records so the current SPA can keep using one snapshot payload while real provider adapters, production identity, deployment scheduling, and observability are added.
