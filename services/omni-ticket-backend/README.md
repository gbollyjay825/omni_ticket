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
- SQLAlchemy/Alembic persistence foundation with PostgreSQL-ready configuration and local SQLite fallback.
- Local PostgreSQL runtime through `OMNI_DATABASE_URL=postgresql+psycopg:///omni_ticket`.
- Database-backed local login/session validation.
- Database-backed admin user creation and management for role, active state, assigned markets, and default market.
- Database-backed market settings, including durable AI Work Queue automation enable/disable behavior.
- Database-backed customer and company APIs.
- Database-first ticket creation, update, timeline, reply/note, AI decision, outbound connector event, and structured handoff lifecycle.
- Database-first channel, agent, customer, company, knowledge, and automation-rule management.
- Email, WhatsApp, Facebook Messenger, Instagram DM, SMS, voice, portal, and API-ready channel model.
- Database-backed connector account readiness for market-specific Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice accounts.
- Database-first connector intake simulation with idempotency, customer creation/reuse, ticket creation, connector receipt timeline events, and outbound connector event recording.
- Database-first outbound message queue for public replies with connector-account readiness checks, delivery status, retry, and dead-letter states.
- Background worker entrypoint for due outbound retries, dead-letter handling, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events.
- Production packaging for release, web, and worker processes through Docker, Procfile, compose, and environment validation.
- Temporary SQLite rebinding for smoke tests so local verification does not need to drop or reseed the repo-default PostgreSQL database.
- Database-first SLA refresh, Work Queue scoring, analytics summary, audit trail, and generated API docs.
- CORS configured for the local Vite frontend.

Local sign-in accounts:

- `gbolahan@omniticket.example.com` / `omni-demo`: admin with Nigeria, Ghana, and UK access.
- `amara.ng@omniticket.example.com` / `omni-demo`: Nigeria supervisor.
- `kofi.gh@omniticket.example.com` / `omni-demo`: Ghana agent.

Production dependencies still required:

- PostgreSQL provider for production deployment.
- Identity provider and RBAC policy enforcement.
- WhatsApp Business API credentials.
- Meta app credentials for Facebook Messenger and Instagram DM.
- Mailbox provider credentials.
- SMS/voice provider credentials.
- Object storage and attachment scanning.

## Structure

- `app/api/v1`: versioned HTTP API routes.
- `app/core`: configuration, security, logging, and app lifecycle.
- `app/models`: domain and persistence models.
- `app/db`: SQLAlchemy models, sessions, migrations helpers, and database-backed setting/auth utilities.
- `app/services`: business services for queue automation, routing, AI, connectors, SLA, and handoffs.
- `app/db/outbound.py`: durable outbound delivery queue and local-dev provider adapter boundary.
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
