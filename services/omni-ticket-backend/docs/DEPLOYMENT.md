# Omni Ticket Backend Deployment

## Process Model

Run the backend as three separate process types:

- `release`: runs `alembic upgrade head`.
- `web`: runs the FastAPI API with Uvicorn.
- `worker`: runs background jobs for outbound retries, dead-lettering, SLA refresh, Work Queue recompute, and analytics rollups.

The included `Procfile` defines those commands for platforms that support Procfile-style deployments.

## Required Environment

Set these values in every environment:

```bash
OMNI_ENVIRONMENT=staging
OMNI_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB
OMNI_INITIALIZE_DATABASE=false
OMNI_SESSION_SECRET=replace-with-a-long-random-secret
OMNI_SESSION_TTL_MINUTES=480
OMNI_WEBHOOK_SIGNATURE_TOLERANCE_SECONDS=300
OMNI_LOGIN_RATE_LIMIT_ATTEMPTS=10
OMNI_LOGIN_RATE_LIMIT_WINDOW_SECONDS=60
OMNI_CONNECTOR_INBOUND_RATE_LIMIT_ATTEMPTS=120
OMNI_CONNECTOR_INBOUND_RATE_LIMIT_WINDOW_SECONDS=60
OMNI_WEBHOOK_RATE_LIMIT_ATTEMPTS=120
OMNI_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS=60
OMNI_ALLOWED_ORIGINS='["https://your-frontend.example.com"]'
OMNI_WORKER_INTERVAL_SECONDS=60
OMNI_WORKER_OUTBOUND_LIMIT=50
```

Local development may use `OMNI_INITIALIZE_DATABASE=true` so reference data is seeded automatically. Staging and production must run migrations explicitly and keep automatic initialization off.

## Docker

Build the backend image:

```bash
docker build -t omni-ticket-backend .
```

Run the web process:

```bash
docker run --rm -p 8000:8000 \
  -e OMNI_ENVIRONMENT=local \
  -e OMNI_DATABASE_URL=postgresql+psycopg://omni:omni@host.docker.internal:5432/omni_ticket \
  -e OMNI_INITIALIZE_DATABASE=true \
  -e OMNI_ALLOWED_ORIGINS='["http://127.0.0.1:5173"]' \
  omni-ticket-backend
```

Run one worker cycle:

```bash
docker run --rm \
  -e OMNI_ENVIRONMENT=local \
  -e OMNI_DATABASE_URL=postgresql+psycopg://omni:omni@host.docker.internal:5432/omni_ticket \
  -e OMNI_INITIALIZE_DATABASE=true \
  -e OMNI_ALLOWED_ORIGINS='["http://127.0.0.1:5173"]' \
  omni-ticket-backend python -m app.worker --once --market-id market-ng
```

## Local Compose Smoke

The compose stack starts Postgres, runs migrations, then starts `web` and `worker`:

```bash
docker compose up --build
```

API health:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Deployment Guardrails

At startup, the API and worker validate staging/production configuration:

- `OMNI_DATABASE_URL` must not be SQLite.
- `OMNI_INITIALIZE_DATABASE` must be `false`.
- `OMNI_SESSION_SECRET` must not use the local development default.
- `OMNI_ALLOWED_ORIGINS` must be explicit and cannot contain `*`.
- Worker interval and outbound limit must be positive.
- Rate-limit attempt and window settings must be positive.

This keeps staging/production from silently starting with local/demo defaults.

## Rate Limits

The backend includes a database-backed fixed-window limiter for the routes most exposed to abuse:

- `POST /api/v1/auth/login`
- `POST /api/v1/connectors/inbound`
- `POST /api/v1/webhooks/{provider}/{market_code}`

When the limit is exceeded, the API returns `429` with a `Retry-After` header. The current implementation stores counters in the application database so serverless invocations share the same state. Login limits are keyed by email address, connector intake by authenticated user, market, and provider, and signed webhooks by market and provider. A high-scale multi-region deployment should still pair the same policy with Redis, gateway/WAF rules, or the hosting provider's edge rate limit.

## Signed Connector Webhooks

Provider adapter callbacks can post to:

```bash
POST /api/v1/webhooks/{provider}/{market_code}
```

The endpoint is unauthenticated by user session because external providers call it directly. It requires:

- `X-Omni-Timestamp`: Unix timestamp within `OMNI_WEBHOOK_SIGNATURE_TOLERANCE_SECONDS`.
- `X-Omni-Signature`: `sha256=<hmac>` over `{timestamp}.{raw_body}` using the connector account webhook secret material.
- `X-Omni-Delivery`: provider delivery identifier for replay protection.

The connector account must be intake-enabled, webhook-verified, and have a configured secret reference. Invalid signatures, stale timestamps, disabled intake, and replayed delivery identifiers are rejected and written back to connector account failure state plus audit history.
