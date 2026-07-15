# Omni Ticket Backend Deployment

## Process Model

Run the backend as three separate process types:

- `release`: runs `alembic upgrade head`.
- `web`: runs the FastAPI API with Uvicorn.
- `worker`: runs background jobs for outbound retries, dead-lettering, SLA refresh, Work Queue recompute, analytics rollups, audit retention, and attachment retention.

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
OMNI_PUBLIC_APP_URL=https://omni.wakanow.com
OMNI_WORKER_INTERVAL_SECONDS=60
OMNI_WORKER_OUTBOUND_LIMIT=50
OMNI_ATTACHMENT_STORAGE_BACKEND=local
OMNI_ATTACHMENT_STORAGE_DIR=/tmp/omni-ticket-attachments
OMNI_ATTACHMENT_S3_BUCKET=
OMNI_ATTACHMENT_S3_PREFIX=omni-ticket/attachments
OMNI_ATTACHMENT_S3_REGION=
OMNI_ATTACHMENT_S3_ENDPOINT_URL=
OMNI_ATTACHMENT_S3_ACCESS_KEY_ID=
OMNI_ATTACHMENT_S3_SECRET_ACCESS_KEY=
OMNI_ATTACHMENT_S3_SERVER_SIDE_ENCRYPTION=AES256
OMNI_ATTACHMENT_SCANNER_ADAPTER=local
OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT=
OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_TOKEN=
OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_HEADER=Authorization
OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_SCHEME=Bearer
OMNI_ATTACHMENT_SCANNER_HTTP_TIMEOUT_SECONDS=10
OMNI_HANDOFF_ATTACHMENT_DOWNLOAD_TTL_MINUTES=10080
OMNI_ATTACHMENT_RETENTION_DAYS=365
OMNI_ATTACHMENT_DELETED_RETENTION_DAYS=30
OMNI_ATTACHMENT_RETENTION_PRUNE_LIMIT=250
OMNI_AUDIT_RETENTION_DAYS=365
OMNI_AUDIT_EXPORT_MAX_ROWS=5000
OMNI_OIDC_ENABLED=false
OMNI_OIDC_PROVIDER_NAME="Enterprise SSO"
OMNI_OIDC_ISSUER_URL=
OMNI_OIDC_AUTHORIZATION_URL=
OMNI_OIDC_TOKEN_URL=
OMNI_OIDC_USERINFO_URL=
OMNI_OIDC_CLIENT_ID=
OMNI_OIDC_CLIENT_SECRET=
OMNI_OIDC_REDIRECT_URL=https://omni.wakanow.com/?auth=oidc
OMNI_OIDC_ALLOWED_EMAIL_DOMAINS='["wakanow.com"]'
OMNI_OIDC_AUTO_PROVISION_ENABLED=false
OMNI_OIDC_DEFAULT_ROLE=agent
OMNI_OIDC_DEFAULT_MARKET_ID=
OMNI_OIDC_REQUIRE_EMAIL_VERIFIED=true
OMNI_OIDC_HTTP_TIMEOUT_SECONDS=10
OMNI_OIDC_STATE_TTL_MINUTES=10
OMNI_WHATSAPP_CLOUD_API_BASE_URL=https://graph.facebook.com/v25.0
OMNI_WHATSAPP_PHONE_NUMBER_ID=
OMNI_WHATSAPP_ACCESS_TOKEN=
OMNI_FACEBOOK_GRAPH_API_BASE_URL=https://graph.facebook.com/v25.0
OMNI_FACEBOOK_PAGE_ID=
OMNI_FACEBOOK_PAGE_ACCESS_TOKEN=
OMNI_FACEBOOK_MESSAGING_TYPE=RESPONSE
OMNI_FACEBOOK_TIMEOUT_SECONDS=10
OMNI_INSTAGRAM_GRAPH_API_BASE_URL=https://graph.instagram.com/v25.0
OMNI_INSTAGRAM_BUSINESS_ACCOUNT_ID=
OMNI_INSTAGRAM_ACCESS_TOKEN=
OMNI_INSTAGRAM_TIMEOUT_SECONDS=10
OMNI_VOICE_HTTP_ENDPOINT=
OMNI_VOICE_HTTP_AUTH_TOKEN=
OMNI_VOICE_HTTP_FROM=
OMNI_VOICE_HTTP_AUTH_HEADER=Authorization
OMNI_VOICE_HTTP_AUTH_SCHEME=Bearer
OMNI_VOICE_HTTP_STATUS_CALLBACK_URL=
OMNI_VOICE_HTTP_TIMEOUT_SECONDS=10
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
- WhatsApp Cloud API settings must include both `OMNI_WHATSAPP_PHONE_NUMBER_ID` and `OMNI_WHATSAPP_ACCESS_TOKEN` when either one is set.
- Facebook Messenger Graph API settings must include both `OMNI_FACEBOOK_PAGE_ID` and `OMNI_FACEBOOK_PAGE_ACCESS_TOKEN` when either one is set, and `OMNI_FACEBOOK_MESSAGING_TYPE` must be `RESPONSE`, `UPDATE`, or `MESSAGE_TAG`.
- Instagram DM Graph API settings must include both `OMNI_INSTAGRAM_BUSINESS_ACCOUNT_ID` and `OMNI_INSTAGRAM_ACCESS_TOKEN` when either one is set.
- Voice HTTP settings must include `OMNI_VOICE_HTTP_ENDPOINT`, `OMNI_VOICE_HTTP_AUTH_TOKEN`, and `OMNI_VOICE_HTTP_FROM` when voice callback delivery is configured.
- OIDC settings require `OMNI_OIDC_ENABLED=true` when any identity-provider URL/client field is set. When enabled, authorization, token, userinfo, client, secret, and redirect settings are required; staging/production OIDC URLs must use HTTPS, and auto-provisioning requires a default market.

This keeps staging/production from silently starting with local/demo defaults.

## Rate Limits

The backend includes a database-backed fixed-window limiter for the routes most exposed to abuse:

- `POST /api/v1/auth/login`
- `POST /api/v1/connectors/inbound`
- `POST /api/v1/webhooks/{provider}/{market_code}`

When the limit is exceeded, the API returns `429` with a `Retry-After` header. The current implementation stores counters in the application database so serverless invocations share the same state. Login limits are keyed by email address, connector intake by authenticated user, market, and provider, and signed webhooks by market and provider. A high-scale multi-region deployment should still pair the same policy with Redis, gateway/WAF rules, or the hosting provider's edge rate limit.

## Request Traceability

Every API response includes:

- `X-Request-ID`: caller-provided when safe, otherwise generated as `req_<uuid>`.
- `X-Process-Time-Ms`: backend processing time for the request.

The API also emits structured JSON access logs through the `omni_ticket.access` logger with request ID, method, path, status code, and duration. These logs are intentionally provider-neutral so they can be captured by local Docker logs, Vercel logs, or a future OpenTelemetry/log drain integration without changing route handlers.

## Security Audit Trail

The database-backed audit endpoint includes operational and security events. Auth and access-control events now cover:

- Successful login and explicit market selection.
- OIDC start, successful OIDC login, denied OIDC login, existing-user linking, and auto-provisioned users.
- Failed login and rate-limit denial.
- Missing authentication, invalid sessions, expired sessions, inactive users, and denied market access.

Audit details include the request ID when present so an administrator can correlate a UI incident, backend response, and log line.

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
