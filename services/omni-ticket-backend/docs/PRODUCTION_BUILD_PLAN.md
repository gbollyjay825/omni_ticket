# Omni Ticket Production Build Plan

Last updated: 2026-06-05

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

Status: Started. Database foundation, local PostgreSQL runtime, session persistence, market settings persistence, admin user management, database-backed local TOTP MFA, custom permission profiles, customer/company persistence, database-first ticketing core, database-first management surfaces, market-scoped support groups, support-group team inboxes, linked handoff team tickets, handoff-forward email queueing, threaded handoff email replies, threaded customer email replies, audited signed attachment links in handoff forwards, IMAP attachment capture, public portal attachment upload, backend global search, sanitized production account-request packs, backend-queued account-request email with an internal readiness ticket, non-secret provider account-reference tracking with API_DOCS snippet generation, production launch readiness checklist, database-first simulated connector intake, database-first analytics/work-queue reads, database-backed CSAT feedback, market-scoped connector account metadata, backend-ranked knowledge suggestions, backend-ranked response macros, backend-ranked supervisor recommendations, Anthropic AI guidance adapter with root `AI_Key` support, IMAP email inbound adapter, durable outbound delivery queue, SMTP email outbound adapter, WhatsApp Cloud API outbound adapter, WhatsApp signed inbound/status callbacks, Facebook Messenger Graph API outbound adapter, Facebook signed inbound/delivery callbacks, Instagram DM Graph API outbound adapter, Instagram signed inbound/read callbacks, SMS HTTP outbound adapter, signed SMS inbound/receipt callback handling, voice HTTP callback adapter, voice signed inbound/status callbacks, signed attachment link audit correlation, worker foundation, database-backed operational alerts, durable alert delivery attempts, frontend operational alert controls, production customer/ticket list search and pagination controls, optimistic concurrency guards, and deployment packaging implemented locally and on the isolated Omni VM deployment at `https://omni.wakanow.com`.

Build:

- Environment configuration for local, staging, and production.
- PostgreSQL-ready SQLAlchemy engine with active local PostgreSQL runtime and local SQLite fallback. Done.
- Alembic migration scaffolding. Done.
- Durable schema for markets, users, sessions, channels, connector accounts, support groups, companies, customers, tickets, timeline events, handoffs, knowledge, automation rules, connector events, settings, AI decisions, and audit events. Done.
- Seed baseline local markets and demo users through the database path. Done.
- Health/readiness endpoints that report database connectivity. Done.
- Database-backed login and session validation for protected APIs. Done.
- Database-backed local TOTP MFA enrollment, confirmation, login enforcement, disable flow, account-recovery reset, audit events, and frontend Setup controls. Done. OIDC SSO readiness, PKCE authorization start, one-time callback state, existing-user linking, and guarded provisioning are also built; external SSO/OIDC client credentials remain pending.
- Database-backed permission profiles, per-user allow/deny overrides, permission-aware route enforcement, frontend Setup controls, and self-lockout protection for setup access. Done.
- Database-backed workspace settings, including the AI Work Queue automation switch. Done.
- Anthropic Messages API adapter for production ticket summaries and recommended next actions, with `OMNI_AI_PROVIDER=auto`, root `AI_Key` support, safe deterministic fallback, and stored model metadata. Done; `AI_Key` is active locally and on the isolated Omni VM, and live smoke passes against `claude-sonnet-4-6`.
- Database-backed customer and company APIs with restart-safe ticket creation rehydration. Done.
- Database-first ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows. Done.
- Customer and ticket list APIs with market-scoped search, filters, allowlisted sorting, optional pagination, and count headers. Done.
- Optional ETag/If-Match optimistic concurrency for company, customer, and ticket updates. Done.
- Database-first channels, agent status, support groups, knowledge articles, and automation-rule management. Done.
- Support groups are market-scoped, admin-managed, audit-visible, included in frontend snapshots, used by handoff routing choices, store optional team inboxes, and are safe to rename because agent/ticket/handoff ownership labels are retargeted in the same transaction. Done.
- Handoff creation queues an internal email forward to the receiving group's team inbox when configured, including ticket, customer, company, custom field, recent comment/note, attachment, SLA, and handoff context. Clean active attachments are included with audited signed download links controlled by `OMNI_PUBLIC_APP_URL` and `OMNI_HANDOFF_ATTACHMENT_DOWNLOAD_TTL_MINUTES`; blocked/deleted files remain metadata-only. Done.
- Public portal ticket creation and replies can upload proof files through an unauthenticated public-ID/email-verified endpoint; portal detail returns sanitized attachment metadata and hides internal storage keys. Done.
- Handoff-forward SMTP messages carry source-ticket, linked-ticket, handoff, and reply-target headers; IMAP replies append privately to the linked internal ticket and write a source-ticket note instead of creating duplicate cases. Done.
- Backend global search spans tickets, customers, companies, answers, support groups, handoffs, and agents, and the frontend topbar routes results into the right screen. Done.
- Backend-ranked knowledge suggestions for ticket contexts with match score, matched terms, and Agent Assist reasons. Done.
- Durable response macros with ticket ranking, usage tracking, audit events, and composer insertion visibility. Done.
- Backend-ranked duplicate ticket suggestions and audited merge controls in the Work Queue, with source ticket closure/merge markers and source thread/attachment context copied into the target note. Done.
- Supervisor recommendations for blocked handoffs, due handoffs, queue pressure, and reassignment, with supervisor-only API access and Command Center visibility. Done.
- Database-first simulated inbound connector intake for email, WhatsApp, Facebook, Instagram, SMS-style payloads, including customer creation/reuse, ticket creation, connector event persistence, and idempotency. Done.
- Database-first analytics summary and Work Queue reads, including SLA refresh, channel volume, agent occupancy, and priority queue scoring. Done.
- Market-scoped connector account and credential metadata for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice. Done.
- Admin user creation/update APIs for roles, active state, assigned markets, and default market. Done.
- Durable outbound send queue with idempotency, connector-account readiness checks, delivery status, retry endpoint, and dead-letter states. Done.
- IMAP email inbound adapter with worker polling, connector-ingest reuse, attachment capture through scan/storage, runtime/env fallback configuration, database-backed Setup configuration, sanitized provider-readiness API, and frontend Setup visibility. Done; `jimb@wakanow.com` provider values can be saved in Setup.
- SMTP email outbound adapter with runtime/env fallback configuration, database-backed Setup configuration, provider message metadata, sanitized provider-readiness API, and frontend Setup visibility. Done; `jimb@wakanow.com` provider values can be saved in Setup.
- Email reply threading matches inbound customer responses to Omni outbound `Message-ID`/thread headers/public IDs, appends them to the originating ticket, reopens non-open cases, tags `customer-replied`, and writes timeline, connector, and audit evidence. Done.
- WhatsApp Cloud API outbound adapter with runtime configuration, provider `wamid` metadata, sanitized provider-readiness API, signed inbound message callbacks, signed status receipt handling, and frontend Setup visibility. Done; Meta WhatsApp phone number ID, access token, templates, and webhook secret reference pending.
- Facebook Messenger Graph API outbound adapter with runtime configuration, provider message metadata, sanitized provider-readiness API, signed inbound/postback callbacks, signed delivery receipt handling, and frontend Setup visibility. Done; Meta page ID, page access token, page webhook subscription, and webhook secret reference pending.
- Instagram DM Graph API outbound adapter with runtime configuration, provider message metadata, sanitized provider-readiness API, signed inbound/postback callbacks, signed read receipt handling, and frontend Setup visibility. Done; Meta Instagram professional account ID, access token, webhook subscription, and webhook secret reference pending.
- SMS HTTP outbound adapter with runtime configuration, provider message metadata, sanitized provider-readiness API, and frontend Setup visibility. Done; SMS provider endpoint/token/sender ID pending.
- Signed SMS webhook handling for inbound texts and outbound delivery receipts with connector replay protection, outbound-message payload updates, timeline receipts, and audit history. Done; SMS provider webhook signing secret pending.
- Voice HTTP callback adapter with runtime configuration, provider call metadata, sanitized provider-readiness API, signed call-log/callback/voicemail intake, signed call-status receipt handling, and frontend Setup visibility. Done; voice provider endpoint/token/caller ID and webhook secret pending.
- Worker entrypoint for outbound retries, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events. Done.
- Durable hourly analytics rollups with worker persistence, rollup API, CSAT average capture, and frontend Insights history. Done.
- Database-backed CSAT feedback with ticket timeline, audit, analytics summary, rollup, and Insights visibility. Done.
- Database-backed operational alerts for outbound retry failures, dead letters, worker exceptions, and SLA supervisor notifications. Done.
- Durable external alert delivery attempts with webhook retries, sanitized config visibility, and audit history. Done; external destination account/webhook URL pending.
- Frontend Command Center and Setup controls for supervisor/admin alert visibility, acknowledgement, and resolution. Done.
- Production launch readiness checklist combines Alembic state, queued account-request evidence, non-secret account references, secret-hygiene checks, provider credential readiness, storage/scanner readiness, SSO readiness, alert delivery readiness, and observability next actions in Setup. Done.
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
- Restart smoke test proves ticket, reply, handoff, support group, timeline, AI decision, and outbound connector event survive API restart. Done.
- Restart smoke test proves channel updates, agent status updates, knowledge articles, and automation rules survive API restart. Done.
- Restart smoke test proves simulated inbound connector intake, connector receipt timeline events, and deduplication survive API restart. Done.
- Regression tests prove customer email replies referencing an outbound SMTP message thread back to the original ticket instead of creating duplicates. Done.
- Regression tests prove duplicate suggestions rank a matching customer/reference case and merge closes/marks the source while writing target/source timeline and audit history. Done.
- Restart smoke test proves analytics summary and Work Queue reads use database records after runtime reset. Done.
- Restart smoke test proves connector account status, credential references, webhook verification, and market isolation survive API restart. Done.
- Production readiness checklist returns sanitized live evidence and blocked/action items for the launch dependencies. Done.

Next increment:

- Provision `jimb@wakanow.com` IMAP/SMTP credentials and save them in Setup, or set `OMNI_EMAIL_IMAP_*` plus `OMNI_EMAIL_SMTP_*` as runtime fallback values.
- Move the active Anthropic `AI_Key` into managed secret storage when the production secret manager is selected.
- Provision the WhatsApp Business Cloud API phone number ID, access token, templates, and webhook setup, then save those values in Setup Production credentials or keep `OMNI_WHATSAPP_*` as runtime fallback values.
- Provision the Facebook Messenger page ID, page access token with `pages_messaging`, page webhook subscription, and webhook setup, then save those values in Setup Production credentials or keep `OMNI_FACEBOOK_*` as runtime fallback values.
- Provision the Instagram professional account ID, access token with messaging permissions, webhook subscription, and webhook setup, then save those values in Setup Production credentials or keep `OMNI_INSTAGRAM_*` as runtime fallback values.
- Provision the SMS provider endpoint, API token, sender ID, and webhook setup, then save those values in Setup Production credentials or keep `OMNI_SMS_HTTP_*` as runtime fallback values.
- Provision the voice provider endpoint, API token, caller ID, webhook setup, and recording policy, then save those values in Setup Production credentials or keep `OMNI_VOICE_HTTP_*` as runtime fallback values.
- Provision the external alert destination account/webhook and save it in Setup Production credentials or keep `OMNI_ALERT_WEBHOOK_URL` plus optional `OMNI_ALERT_WEBHOOK_SECRET` as runtime fallback values.
- Add external dashboards/APM for deployed web/API/worker health, using the in-app readiness checklist to keep observability marked action-required until the external destination is active.
- Choose and provision the external SSO/OIDC client credentials for production federation, then decide whether guarded auto-provisioning remains disabled or moves into an approved identity lifecycle process.

## Phase 2: Auth, RBAC, And Market Tenancy

Build:

- Replace prototype local-session shim with database-backed sessions. Done.
- Add production identity adapter boundary for SSO/OIDC provider. Done for PKCE start, callback exchange, userinfo lookup, one-time state, and existing-user linking; external provider credentials pending.
- Add role policy checks for agent, supervisor, admin, auditor, service account, and custom permission profiles. Done; external identity lifecycle activation remains pending.
- Add market-access enforcement in reusable dependencies.
- Add admin user management APIs.
- Add admin user management APIs. Done for local backend.
- Add audit trail for all auth, market switch, and access-denied events. Done for local sessions, explicit market selection, failed login, missing authentication, invalid sessions, rate limiting, and market-scope denial.

Acceptance:

- Unauthenticated users cannot enter the app or call protected APIs. Done for local bearer sessions.
- A user assigned only to Ghana cannot read Nigeria/UK records. Done in API tests.
- Admin can add/remove users from markets. Done for local backend and frontend Setup screen.
- Agents, supervisors, admins, and auditors are constrained by route-level RBAC across operations, setup, audit, and readiness APIs. Done.
- Auth and access-denied audit records include request IDs and can be read from the database-backed audit endpoint. Done.
- Users can enroll local TOTP MFA, confirm with a one-time code, and must provide an MFA code on login once enabled. Done.
- Admins can assign permission profiles and per-permission allow/deny overrides without removing their own setup access. Done.

## Phase 3: Durable Ticketing And Customer Management

Build:

- Add production-grade search, pagination, sorting, optimistic concurrency, and audit metadata around the database-first APIs. Customer and ticket list search/sort/pagination headers are now done, market-scoped global search is done across major operational entities, and optional ETag/If-Match optimistic concurrency is done for company, customer, and ticket updates. Broader list coverage and deeper audit metadata remain pending. Customer, company, settings, auth, users, markets, tickets, timeline, replies, handoffs, support groups, AI decisions, inbound/outbound connector events, channels, agents, knowledge, automation rules, analytics, and Work Queue reads are already on the direct database path.
- Expose market-scoped CRUD and search APIs.
- Add pagination, sorting, filtering, optimistic concurrency, and audit metadata.
- Replace frontend local ticket/customer state with authenticated backend snapshots and mutations.

Acceptance:

- Browser refresh preserves tickets/customers. Done locally.
- Ticket replies, notes, status changes, and handoffs persist. Done locally.
- Frontend can run with backend as source of truth. Done locally through the authenticated snapshot and write-through bridge.

## Phase 4: Omnichannel Connectors

Build:

- Email connector: OAuth/IMAP or provider webhook intake, SMTP/provider send, thread mapping, attachments. Account metadata, Setup-managed IMAP/SMTP settings, IMAP inbound polling with attachment scan/storage, outbound queue, attachment boundary, handoff signed attachment links, and SMTP outbound adapter are done; mailbox/provider values still need to be supplied by operations.
- WhatsApp Business connector: webhook intake, templates, media, receipts. Account metadata, Cloud API text outbound adapter, and signed inbound/status callbacks done; Meta credentials, templates, and media support pending.
- Facebook Messenger connector: page webhook, replies, private reply flow. Account metadata, Graph API text outbound adapter, and signed inbound/postback/delivery callbacks done; Meta page credentials, private reply specifics, and media support pending.
- Instagram DM connector: DM intake, comment-to-DM, media. Account metadata, Graph API text outbound adapter, and signed inbound/postback/read callbacks done; Meta Instagram credentials, comment-to-DM specifics, and media support pending.
- SMS and voice connector provider boundaries. SMS outbound HTTP adapter plus signed inbound/receipt callbacks are done with account metadata and durable queue dispatch; voice HTTP callback adapter plus signed call-log/voicemail/status callbacks are done with account metadata and durable queue dispatch.
- Connector signature verification, inbound replay protection, provider-specific send adapters, and provider-specific retry policies. Canonical signed webhook verification, delivery-id replay protection, durable outbound queue, WhatsApp/SMS receipt handling, send idempotency, and worker retry/dead-letter execution are done locally; provider-native signature adapters remain pending.

Acceptance:

- Each market can own separate channel credentials/accounts.
- Incoming provider events create/update tickets in the correct market.
- Signed webhooks reject invalid signatures, stale timestamps, disabled accounts, and replayed delivery identifiers.
- Outbound sends are auditable and retryable.

## Phase 5: AI Work Queue And Automation Engine

Build:

- Durable AI decisions with confidence, model/provider/version, input references, override history, and prompt metadata.
- Anthropic provider call for production-grade ticket summary and recommended next action. Done with safe fallback; key activation pending.
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
- Analytics rollups for volume, SLA, CSAT, response time, resolution time, backlog age, and channel pressure. Durable hourly rollups for current summary metrics and persisted CSAT averages are done; deeper historical metrics remain pending.
- Worker-triggered analytics rollups. Done locally and on the deployable worker path for current summary metrics.
- Backend-ranked supervisor recommendations for reassignment, queue pressure, and blocked handoff escalation. Done.

Acceptance:

- Dashboards use backend rollups, not frontend calculations.
- SLA states update even when no user is actively viewing the ticket.

## Phase 7: Security, Compliance, And Operations

Build:

- Attachment lifecycle governance, retention pruning, clean-only download gates, signed-link token/audit correlation, no-store/nosniff download headers, S3-compatible storage adapter, external HTTP scanner adapter, and Setup readiness are done; managed bucket credentials and production malware scanning provider account remain pending.
- Rate limiting, WAF/deployment rules, request IDs, structured logs, OpenTelemetry traces. Database-backed route limits are done for auth and connector intake, request ID plus structured access logging is done for API traceability, and operational alerts now persist for worker/outbound/SLA incidents with durable webhook delivery attempts; edge/WAF rules, the external alert destination account, external dashboards/APM, and full OpenTelemetry export remain pending.
- Backup, retention, export, deletion, and legal hold workflows. Audit CSV/JSON export plus configurable audit retention, attachment lifecycle retention/delete/purge, and admin/worker pruning are done; broader backup and legal-hold workflows remain pending.
- Secrets management and credential rotation.
- Load tests for queue recompute, webhook ingestion, and ticket reads.
- Deployment scripts and production runbooks.
- Dockerfile, compose stack, Procfile, and deployment docs. Done locally.

Acceptance:

- Staging and production deploy from CI.
- Rollback and recovery are documented and tested.
- Operational alerts exist for connector failures, queue lag, SLA jobs, and database health, with retryable delivery attempts to the configured operations webhook.

## Current Known Dependencies

- PostgreSQL provider.
- Identity provider/SSO client credentials and lifecycle approval decision.
- WhatsApp Business API credentials.
- Facebook Messenger Meta page credentials and webhook secret reference.
- Instagram professional account credentials and webhook secret reference.
- Mailbox provider credentials.
- SMS provider endpoint/token/sender ID and webhook signing secret for activation, plus voice provider endpoint/token/caller ID/webhook secret for activation.
- Managed attachment object storage credentials and production malware scanning provider account; S3-compatible storage and external scanner adapter boundaries are built.
- Observability/operations alert destination webhook account.
- Resolve all `blocked` and `action_required` items reported by `GET /api/v1/production/readiness-checklist`.
