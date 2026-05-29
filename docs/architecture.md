# Omni Ticket Building Architecture

## Goal

Build a high-fidelity omnichannel operations support PWA with a production-shaped frontend and an independent Python/FastAPI backend. The current delivery still carries realistic local seed data for offline fallback, while the authenticated happy path reads and writes through market-scoped backend routes.

## Stack

- Vite, React, TypeScript.
- Independent Python/FastAPI backend in `/Users/gbolahan.salami/Documents/omni-ticket-backend`.
- Lucide React icons.
- IndexedDB persistence via `idb`.
- Local storage only for lightweight UI preferences.
- Production-only service worker and web app manifest.
- Static PWA deployment container via frontend `Dockerfile` and `nginx.conf`.
- Browser verification with the in-app browser.

## Module Structure

- `src/domain.ts`: shared TypeScript types for channels, conversations, tickets, customers, agents, SLA policies, automation rules, knowledge articles, analytics, tracker items, and store actions.
- `src/seed.ts`: realistic omnichannel seed data across all channels and operational screens.
- `src/store.ts`: IndexedDB hydration/persistence, derived metrics, workflow actions, and local UI state helpers.
- `src/OmniApp.tsx`: app shell, navigation, screen rendering, and workflow wiring.
- `src/App.css` and `src/index.css`: dense operational visual system and responsive behavior.
- `src/pwa.ts`: production service worker registration.
- `public/manifest.webmanifest` and `public/sw.js`: PWA install metadata and app shell cache.
- `src/backend.ts`: authenticated API bridge to the independent Python backend.
- `Dockerfile` and `nginx.conf`: production static container for the SPA.

## Data Model

Core entities:

- `Channel`: email, chat, phone, WhatsApp, SMS, Instagram, Facebook, portal, API, internal handoff.
- `OmniConversation`: ticket/conversation record with channel, requester, subject, status, priority, SLA, sentiment, intent, group, assignee, tags, timeline, tasks, linked customer, and Copilot recommendation.
- `TimelineEvent`: customer message, agent reply, internal note, handoff, voice log, chat transcript, social DM, portal comment, API event, automation event.
- `CustomerProfile`: identity, company, contact methods, preferred channels, health, open value, history, tags, recent issues.
- `AgentProfile`: availability, load, skills, shift, occupancy, CSAT, active conversations.
- `KnowledgeArticle`: article status, category, language, helpfulness, deflection, owner, suggested intents.
- `AutomationRule`: trigger, condition, action, owner, status, health, last fired, failure count.
- `HandoffRecord`: structured internal handoff with ticket link, source team, receiving team, owner, reason, context, customer impact, acceptance criteria, lifecycle status, due time, checklist, and blockers.
- `WorkspaceSettings`: tenant-level controls. `aiWorkQueueAutomationEnabled` defaults to `true` and can be switched off by admins.
- `TrackerItem`: epics, backlog, pending items, and closed issues.

## Local Persistence

- Use IndexedDB store `omni-ticket`.
- Persist the full demo state after workflow actions.
- Store offline composer drafts and simulated send/handoff events in an outbox collection within app state.
- Include a reset action internally by changing the persisted state version when the seed model changes.

## Workflow Actions

- Select conversation/customer/channel.
- Filter inbox by channel, SLA, status, priority, assignee, and sentiment.
- Add reply, internal note, or handoff timeline event.
- Create and track structured handoff records from handoff composer mode.
- Update handoff lifecycle status and checklist completion.
- Queue outbound events to offline outbox when offline.
- Update status, priority, assignee, group, tags, and tasks.
- Toggle channel intake status.
- Toggle automation rule state.
- Toggle AI Work Queue automation from Setup.
- Review connector account readiness from Setup for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice.
- Create and manage backend users from Setup, including role, active state, assigned markets, and default market.
- Monitor outbound customer messages from Setup, including queued, sending, sent, failed, retrying, and dead-lettered delivery states.
- Retry failed outbound customer messages after a connector account is corrected.
- Publish/approve knowledge article.

## Backend AI Work Queue Automation

Backend development must treat AI Work Queue automation as default-on tenant behavior unless explicitly disabled in Settings.

When `aiWorkQueueAutomationEnabled=true`, the Python backend should automatically:

- Classify new messages by intent, topic, priority, sentiment, language, SLA risk, and channel.
- Route the item to the right queue/group and assign the best available owner by skill, occupancy, availability, and customer context.
- Move work into the correct priority position in the Work Queue.
- Recommend the next action, response draft, knowledge article, escalation, or handoff path.
- Record AI decisions as audit events with model/version, confidence, input references, decision reason, and override history.

When `aiWorkQueueAutomationEnabled=false`, the backend must keep intake and ticket creation active but leave prioritization, assignment, routing, and next-action decisions manual. Customer-facing sends still require the explicit send action unless a future approved policy enables autonomous outbound messages.

## Current Backend Boundary

The independent backend now exposes these routes and keeps them intentionally close to the frontend state shape. The frontend uses the authenticated bridge for ticket creation, ticket updates, replies, notes, handoffs, channel intake toggles, automation-rule toggles, article publishing, settings writes, user management, market-scoped snapshots, and connector account readiness when the API is reachable.

- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/markets`
- `GET /api/v1/auth/users`, `POST /api/v1/auth/users`, `PATCH /api/v1/auth/users/{id}`
- `GET /api/v1/frontend/snapshot`
- `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`, `PATCH /api/v1/tickets/{id}`
- `POST /api/v1/tickets/{id}/reply`, `POST /api/v1/tickets/{id}/handoffs`
- `GET /api/v1/handoffs`, `PATCH /api/v1/handoffs/{id}`
- `GET /api/v1/customers`, `GET /api/v1/customers/{id}`
- `GET /api/v1/channels`, `PATCH /api/v1/channels/{id}`
- `GET /api/v1/agents`, `PATCH /api/v1/agents/{id}/status`
- `GET /api/v1/connectors/accounts`, `POST /api/v1/connectors/accounts`, `PATCH /api/v1/connectors/accounts/{id}`
- `GET /api/v1/connectors/providers`, `POST /api/v1/connectors/inbound`, `GET /api/v1/connectors/events`
- `GET /api/v1/outbound/messages`, `POST /api/v1/outbound/messages/{id}/retry`
- `GET /api/v1/automation-rules`, `PATCH /api/v1/automation-rules/{id}`
- `GET /api/v1/settings`, `PATCH /api/v1/settings`
- `GET /api/v1/knowledge`, `PATCH /api/v1/knowledge/{id}`
- `GET /api/v1/analytics/overview`, `GET /api/v1/work-queue`, `GET /api/v1/tracker`

The current backend uses SQLAlchemy persistence with local PostgreSQL database `omni_ticket` through the backend `.env`; SQLite remains available as a fallback by changing `OMNI_DATABASE_URL`. Public replies now move through a durable outbound-message table before the local-dev provider adapter marks them sent or failed. Live Freshdesk/Freshworks import or sync is still out of scope unless explicitly requested.

Security-sensitive backend paths now emit durable audit records for login success, failed login, rate-limit denial, explicit market selection, missing authentication, invalid sessions, and market-scope denial. These records include request IDs when available so operations admins can correlate audit entries with backend access logs and browser-visible request IDs.

## Backend Worker Boundary

The backend now includes a worker entrypoint in the independent Python project:

```bash
python -m app.worker --once --market-id market-ng
```

The worker can also run continuously with `--interval-seconds`. Its current jobs are market-scoped and audited:

- Process due outbound replies and retry failed sends when `next_attempt_at` is due.
- Dead-letter outbound replies after max attempts.
- Refresh SLA risk and breach state without a user opening the Work Queue.
- Recompute the Work Queue order.
- Run analytics rollups for operational dashboards.

Production deployment still needs a managed worker/scheduler target, alerting, and provider-specific adapter credentials.

## Deployment Packaging

The app now has deployable process definitions:

- Frontend `Dockerfile`: builds the PWA and serves it through Nginx with SPA fallback.
- Backend `Dockerfile`: builds the Python API image.
- Backend `Procfile`: defines `release`, `web`, and `worker` process commands.
- Backend `docker-compose.yml`: starts Postgres, runs migrations, then starts API and worker locally.
- Backend `.env.example`: documents local and staging/production environment variables.

Staging and production backend startup validates critical configuration so the service does not boot with SQLite, wildcard CORS, or automatic demo initialization.

## Offline/PWA Strategy

- Register service worker only in production builds.
- Cache app shell and static assets.
- Fall back to `index.html` for navigation.
- Display online/offline state.
- Keep offline drafts and simulated sends in the local outbox.
- Do not claim real outbound delivery while offline.

## Verification

- `npm run lint`
- `npm run build`
- Backend checks from `/Users/gbolahan.salami/Documents/omni-ticket-backend`: `python -m compileall app tests`, `ruff check app tests migrations`, `mypy app tests`, and `pytest -q`.
- Browser checks at desktop and mobile widths.
- PWA checks: manifest exists, production service worker registers, offline shell is nonblank.
