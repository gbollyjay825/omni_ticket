# Omni Ticket Backend

Independent Python backend project for Omni Ticket.

## Direction

- Python backend using FastAPI.
- API-first service boundary for the Omni Ticket frontend PWA.
- AI Work Queue automation is default-on unless disabled in tenant settings.
- Real channel connectors, ticket storage, audit trails, and AI orchestration live here, not in the frontend.

## Current Build Status

This repository now runs a working FastAPI backend slice for Omni Ticket:

- Default-on AI Work Queue automation with an admin setting to disable it.
- Login/session flow with user role and market context.
- Market-scoped API access for one SPA serving multiple markets.
- Route-level RBAC for agents, supervisors, admins, and auditors across operational writes, setup controls, audit visibility, and platform readiness.
- SQLAlchemy/Alembic persistence foundation with PostgreSQL-ready configuration and local SQLite fallback.
- Local PostgreSQL runtime through `OMNI_DATABASE_URL=postgresql+psycopg:///omni_ticket`.
- Database-backed local login/session validation.
- Durable audit records for login success, login denial, rate-limit denial, explicit market selection, missing authentication, invalid sessions, and market access denial.
- Permission-gated audit CSV/JSON export, retention policy readout, admin prune endpoint, worker retention pruning, and Setup controls.
- Attachment lifecycle governance with active/deleted/purged states, supervisor delete/purge, configurable retention policy, admin prune endpoint, worker cleanup, and Setup controls.
- S3-compatible attachment storage adapter, external HTTP scanner adapter, pre-storage binary scan blocking, sanitized provider-readiness endpoint, and Setup visibility.
- Database-backed admin user creation and management for role, active state, assigned markets, and default market.
- Database-backed local TOTP MFA enrollment, confirmation, login enforcement, disable flow, account-recovery reset, and MFA audit events.
- Database-backed permission profiles with per-user allow/deny overrides, permission-aware route enforcement, and setup self-lockout protection.
- Database-backed market settings, including durable AI Work Queue automation enable/disable behavior.
- Anthropic Messages API guidance adapter for production ticket summaries and recommended next actions, with `AI_Key`/`OMNI_ANTHROPIC_API_KEY` support and deterministic fallback.
- Database-backed customer and company APIs.
- Database-first ticket creation, update, timeline, reply/note, AI decision, outbound connector event, and structured handoff lifecycle.
- Database-first channel, agent, support group, customer, company, knowledge, and automation-rule management.
- Market-scoped support groups with live member/open-ticket/SLA-risk counters, admin create/update APIs, audit history, and rename propagation across agents, tickets, and handoffs.
- Backend-ranked knowledge suggestions with match scores, matched terms, and Agent Assist reasons.
- Database-backed response macros with ticket-aware ranking, usage tracking, audit history, and composer insertion visibility.
- Public customer portal endpoints for market-scoped answer deflection, unauthenticated ticket intake, ticket status lookup, and customer replies, including customer reuse, portal contact points, ticket-field validation, safe public timeline visibility, reply-driven reopening, rate limiting, and audit history.
- Database-first automation-rule execution for ticket routing, priority escalation, tags, checklist tasks, last-fired state, timeline history, and audit history.
- Email, WhatsApp, Facebook Messenger, Instagram DM, SMS, voice, portal, and API-ready channel model.
- Database-backed connector account readiness for market-specific Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice accounts.
- Database-first connector intake simulation with idempotency, customer creation/reuse, ticket creation, connector receipt timeline events, and outbound connector event recording.
- Signed connector webhook endpoint for provider callbacks with HMAC verification, timestamp tolerance, delivery-id replay protection, account failure tracking, and audit history.
- Database-backed fixed-window rate limiting for login, authenticated connector intake, signed provider webhooks, and public portal requests, with Redis, gateway, or WAF limits still recommended for multi-region scale.
- Request correlation middleware with `X-Request-ID`, `X-Process-Time-Ms`, and structured JSON access logs for production traceability.
- IMAP email inbound adapter for `jimb@wakanow.com`, with worker polling, connector-ingest reuse, sanitized readiness visibility, and disabled-by-default runtime controls until mailbox credentials are provisioned.
- Database-first outbound message queue for public replies with connector-account readiness checks, delivery status, retry, and dead-letter states.
- SMTP email outbound adapter for `jimb@wakanow.com`, with sanitized provider-readiness visibility and local-dev fallback until mailbox credentials are provisioned.
- WhatsApp Cloud API outbound adapter, with provider `wamid` capture, sanitized provider-readiness visibility, signed inbound message callbacks, and signed outbound status receipt handling until Meta credentials are provisioned.
- Facebook Messenger Graph API outbound adapter, with provider message-id capture, sanitized provider-readiness visibility, signed inbound message/postback callbacks, and signed outbound delivery receipt handling until Meta page credentials are provisioned.
- Instagram DM Graph API outbound adapter, with provider message-id capture, sanitized provider-readiness visibility, signed inbound message/postback callbacks, and signed outbound read receipt handling until Meta Instagram credentials are provisioned.
- Configurable SMS HTTP outbound adapter with provider message-id capture, sanitized readiness visibility, and local-dev fallback until SMS provider credentials are provisioned.
- Configurable voice HTTP callback adapter with provider call-id capture, sanitized readiness visibility, and local-dev fallback until voice provider credentials are provisioned.
- Signed SMS webhook adapter for inbound texts and outbound delivery receipts, reusing connector intake, outbound-message payload updates, replay protection, timeline receipts, and audit history.
- Signed voice webhook adapter for call logs, callback requests, voicemail summaries, and call-status receipts, reusing connector intake, outbound-message payload updates, replay protection, timeline receipts, and audit history.
- Database-backed CSAT feedback per ticket, including timeline history, audit records, analytics summary, durable rollup values, and frontend Insights visibility.
- Database-backed operational alerts for outbound failures, dead letters, worker exceptions, and SLA supervisor notifications.
- Durable operational alert delivery attempts with webhook retry tracking, sanitized config endpoints, and supervisor/admin Setup visibility.
- Background worker entrypoint for due outbound retries, dead-letter handling, SLA refresh, Work Queue recompute, analytics rollups, operational alert delivery, and worker audit events.
- Production packaging for release, web, and worker processes through Docker, Procfile, compose, and environment validation.
- Temporary SQLite rebinding for smoke tests so local verification does not need to drop or reseed the repo-default PostgreSQL database.
- Database-first SLA refresh, Work Queue scoring, analytics summary, CSAT averaging, durable hourly analytics rollups, audit trail, and generated API docs.
- Production list controls for customer and ticket APIs, including market-scoped search, filters, sorting, optional pagination, and count headers.
- Optional ETag/If-Match optimistic concurrency protection for company, customer, and ticket updates.
- CORS configured for the local Vite frontend.

Local bootstrap sign-in accounts for development only:

- `gbolahan@omniticket.example.com` / `omni-demo`: admin with Nigeria, Ghana, and UK access.
- `amara.ng@omniticket.example.com` / `omni-demo`: Nigeria supervisor.
- `kofi.gh@omniticket.example.com` / `omni-demo`: Ghana agent.

Production dependencies still required:

- PostgreSQL provider for production deployment.
- Anthropic API key in root `AI_Key` or `OMNI_ANTHROPIC_API_KEY`; adapter code is built and falls back safely until the key is present.
- External SSO/OIDC client credentials; OIDC PKCE start/callback boundary, local database-backed TOTP MFA, and custom permission profiles are built.
- WhatsApp Business Cloud API phone number ID, access token, templates, and webhook secret reference.
- Facebook Messenger Meta app, page ID, page access token with `pages_messaging`, page webhook subscription, and webhook secret reference; adapter code is built, credentials remain pending.
- Instagram professional account ID, access token with messaging permissions, webhook subscription, and webhook secret reference; adapter code is built, credentials remain pending.
- Mailbox provider IMAP and SMTP credentials for `jimb@wakanow.com`; inbound/outbound adapter code is built, credentials remain pending.
- SMS provider HTTP endpoint/token/sender ID plus webhook signing secret; SMS outbound and signed callback code is built, credentials remain pending.
- Voice provider HTTP endpoint/token/caller ID plus webhook signing secret and recording access policy; voice callback and signed webhook code is built, credentials remain pending.
- Managed object storage bucket credentials and production malware scanning account; adapter boundaries, local lifecycle governance, delete/purge, and clean-only download gates are built.
- Observability/operations alert webhook destination for `OMNI_ALERT_WEBHOOK_URL`.

## Structure

- `app/api/v1`: versioned HTTP API routes.
- `app/core`: configuration, security, logging, and app lifecycle.
- `app/models`: domain and persistence models.
- `app/db`: SQLAlchemy models, sessions, migrations helpers, and database-backed setting/auth utilities.
- `app/services`: business services for queue automation, routing, AI, connectors, SLA, and handoffs.
- `app/db/outbound.py`: durable outbound delivery queue.
- `app/services/inbound_adapters.py`: provider intake adapters, including IMAP email polling.
- `app/services/outbound_adapters.py`: provider send adapters, including SMTP email, WhatsApp Cloud API, Facebook Messenger Graph API, Instagram DM Graph API, HTTP SMS, HTTP voice, and local-dev fallback.
- `app/worker.py`: one-shot or continuous background worker runner.
- `Dockerfile`, `Procfile`, and `docker-compose.yml`: deployment process definitions.
- `docs/DEPLOYMENT.md`: deployment environment and process guide.
- `docs/BACKEND_BACKLOG.md`: step-by-step backend build backlog.
- `docs/ARCHITECTURE.md`: backend architecture and service boundaries.
- `tests`: backend test suite.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs are available at `http://127.0.0.1:8000/docs`.

Database readiness is available at `GET /api/v1/platform/readiness` after login.

This workspace now uses local PostgreSQL by default through `.env`:

```bash
createdb omni_ticket
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Set `OMNI_DATABASE_URL` to another PostgreSQL URL for staging/production without changing application code. SQLite remains available by changing `OMNI_DATABASE_URL` back to `sqlite:///./data/omni-ticket.db`.

Run one worker cycle locally:

```bash
python -m app.worker --once --market-id market-ng
```

`pytest` now rebinds the backend to a temporary SQLite database for the test session, so smoke tests do not depend on the repo `.env` PostgreSQL target.

Run the worker continuously:

```bash
python -m app.worker --interval-seconds 60
```

Run the local deployment-shaped stack:

```bash
docker compose up --build
```

Docker is optional for local development; use the direct Python commands above when Docker is unavailable.

## Smoke Tests

```bash
python -m compileall app tests
pytest -q
ruff check app tests
mypy app tests
alembic upgrade head
python -m app.worker --once --market-id market-ng
```
