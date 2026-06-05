# Pulse VM Environment

This environment hosts the React/Vite frontend, FastAPI backend, worker, Postgres database, release migrations, and attachment storage on one Pulse VM.

## Current Remote VM Deployment

The remote Pulse VM does not currently have Docker installed, so Omni Ticket is deployed there as a separate non-Docker app without touching the existing Pulse application.

- Host alias: `pulse-prod`
- Public URL: `https://omni.wakanow.com`
- Support mailbox / sender identity: `jimb@wakanow.com`
- App path: `/home/amechi/omni-ticket/current`
- Runtime env: `/home/amechi/omni-ticket/runtime/env.sh`
- Attachments: `/home/amechi/omni-ticket/attachments`
- Database: local PostgreSQL database/user `omni_ticket`
- Frontend: PM2 process `omni-ticket-frontend` on port `8088`
- API: PM2 process `omni-ticket-api` on `127.0.0.1:8090`
- Worker: PM2 process `omni-ticket-worker`
- AI guidance: Anthropic Messages API adapter is deployed. `/home/amechi/omni-ticket/current/AI_Key` is active and live-smoked against `claude-sonnet-4-6`; admins can also save a write-only Anthropic key in Setup -> Connectors -> Production credentials.
- Email inbound/outbound: IMAP intake and SMTP delivery adapter code is deployed. Admins can save the `jimb@wakanow.com` IMAP/SMTP host, username, sender, and write-only passwords from Setup. Runtime `OMNI_EMAIL_IMAP_*` and `OMNI_EMAIL_SMTP_*` values remain optional fallback values.
- WhatsApp outbound/callbacks: Cloud API text outbound and signed inbound/status webhook code are deployed; admins can save phone number ID, access token, optional base URL, and preview settings in Setup Production credentials after the Meta WhatsApp Business account is provisioned.
- Facebook Messenger outbound/callbacks: Graph API text outbound and signed inbound/postback/delivery webhook code are deployed; admins can save page ID, page access token, optional base URL, and messaging type in Setup Production credentials after the Meta page account is provisioned.
- Instagram DM outbound/callbacks: Graph API text outbound and signed inbound/postback/read webhook code are deployed; admins can save professional account ID, access token, and optional base URL in Setup Production credentials after the Meta Instagram professional account is provisioned.
- SMS outbound/callbacks: HTTP provider adapter and signed inbound/receipt webhook code are deployed; admins can save endpoint, API token, sender ID, callback URL, and auth header settings in Setup Production credentials after the SMS provider account is provisioned.
- Voice outbound/callbacks: HTTP callback adapter and signed call-log/voicemail/status webhook code are deployed; admins can save endpoint, API token, caller ID, status callback URL, and auth header settings in Setup Production credentials after the telephony provider account is provisioned.
- Alert delivery: durable attempts are enabled in the app; admins can save the destination webhook URL and optional signing secret in Setup Production credentials after the operations destination account is created.

The frontend is built with `VITE_OMNI_API_BASE_URL=/api/v1`. A small Node static server at `scripts/pulse-static-server.mjs` serves `dist/` for the PM2 deployment. The public Nginx route proxies `/api/*` directly to `http://127.0.0.1:8090`, so the existing Pulse app files, Pulse PM2 processes, and `pulse.wakanow.com` application route are not changed.

Verify on the VM:

```bash
ssh pulse-prod 'curl -fsS http://127.0.0.1:8088/api/v1/health'
ssh pulse-prod 'curl -fsSI http://127.0.0.1:8088/ | sed -n "1,8p"'
ssh pulse-prod 'pm2 jlist | node -e "let s=\"\";process.stdin.on(\"data\",d=>s+=d).on(\"end\",()=>{for(const p of JSON.parse(s)){if(p.name.includes(\"omni-ticket\")) console.log(p.name,p.pm2_env.status,p.pid)}})"'
```

Public access is routed through a separate Nginx site named `omni-ticket` for `omni.wakanow.com`. It serves HTTPS with the existing wildcard Wakanow certificate, proxies `/api/*` directly to the Omni API on `127.0.0.1:8090`, and proxies all other paths to the Omni frontend on `127.0.0.1:8088`. The `jimb@wakanow.com` address is the production mailbox/sender identity for future email provider setup; the HTTP server hostname remains `omni.wakanow.com`.

Verify the public route:

```bash
curl -fsSI https://omni.wakanow.com/
curl -fsS https://omni.wakanow.com/api/v1/health
```

## Optional Docker Setup For Future VMs

The current remote VM does not use this Docker path because Docker is not installed there. Keep these commands for a future clean VM where Docker Compose is available.

## First-Time Docker Setup

From the repo root on the VM:

```bash
cp .env.pulse.example .env.pulse
```

Edit `.env.pulse`:

- Set `PULSE_PUBLIC_ORIGIN` to the VM URL, for example `https://pulse.example.com`.
- Set `OMNI_ALLOWED_ORIGINS` to the same frontend origin as a JSON list.
- Replace `PULSE_POSTGRES_PASSWORD`.
- Replace `OMNI_SESSION_SECRET`; generate one with `openssl rand -hex 32`.
- Keep `PULSE_PUBLIC_API_BASE_URL=/api/v1` so the frontend uses the same public origin and Nginx proxies API traffic to the backend container.
- Put the Anthropic key in `AI_Key` beside the project root or set `OMNI_ANTHROPIC_API_KEY`; never commit the key.
- Leave `OMNI_EMAIL_IMAP_POLL_ENABLED=false`, `OMNI_EMAIL_IMAP_HOST` empty, and `OMNI_EMAIL_SMTP_HOST` empty when using the Setup-managed mailbox settings path.
- Leave `OMNI_WHATSAPP_PHONE_NUMBER_ID` and `OMNI_WHATSAPP_ACCESS_TOKEN` empty until the WhatsApp Business Cloud API credentials are available.
- Leave `OMNI_FACEBOOK_PAGE_ID` and `OMNI_FACEBOOK_PAGE_ACCESS_TOKEN` empty until the Facebook page credentials are available.
- Leave `OMNI_INSTAGRAM_BUSINESS_ACCOUNT_ID` and `OMNI_INSTAGRAM_ACCESS_TOKEN` empty until the Instagram professional account credentials are available.
- Leave `OMNI_VOICE_HTTP_ENDPOINT`, `OMNI_VOICE_HTTP_AUTH_TOKEN`, and `OMNI_VOICE_HTTP_FROM` empty until the voice provider credentials are available.
- Leave `OMNI_ALERT_WEBHOOK_URL` empty until the operations alert destination account/webhook is provisioned.

## Start The Docker Stack

```bash
docker compose --env-file .env.pulse -f docker-compose.pulse.yml up -d --build
```

The stack exposes only the frontend Nginx container on `PULSE_HTTP_PORT` by default. Nginx serves the SPA and proxies `/api/*` to the FastAPI service.

## Verify Docker Stack

```bash
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/api/v1/platform/readiness
docker compose --env-file .env.pulse -f docker-compose.pulse.yml ps
```

Then open the VM URL in a browser.

## Docker Operations

View logs:

```bash
docker compose --env-file .env.pulse -f docker-compose.pulse.yml logs -f api worker frontend
```

Run migrations manually:

```bash
docker compose --env-file .env.pulse -f docker-compose.pulse.yml run --rm migrate
```

Restart after pulling code:

```bash
docker compose --env-file .env.pulse -f docker-compose.pulse.yml up -d --build
```

## Production Notes

The Pulse VM template defaults `OMNI_ENVIRONMENT=pulse` and `OMNI_INITIALIZE_DATABASE=true` so the first VM boot can seed baseline workspace data. For strict staging or production, set:

```bash
OMNI_ENVIRONMENT=production
OMNI_INITIALIZE_DATABASE=false
```

Then run the `migrate` service explicitly and manage initial users/data through the production onboarding path.
