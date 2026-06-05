# Omni Ticket Project Tracker

Last updated: 2026-06-05

## Epics

| Epic | Outcome | Status | Pending |
| --- | --- | --- | --- |
| E1 Research and product definition | Omni support desk transition research, UI plan, architecture, and tracker docs | Done | None |
| E2 Omni data model and app shell | Split TypeScript domain, seed data, store, navigation, and IndexedDB persistence | Done | None |
| E3 Omnichannel operations workflow | Command Center, Work Queue, Channel Chats, Customer 360, composer, handoffs, and assistive guidance | Done | None |
| E4 Admin, analytics, knowledge, workforce, and tracker | Operational management screens with meaningful data and controls | Done | None |
| E5 Install-ready app, verification, and delivery | Offline state, app shell, responsive verification, and milestone emails | Done | None |
| E6 Python backend vertical slice | Durable API, worker, Pulse VM deployment, frontend write-through bridge, local TOTP MFA, custom permission profiles, OIDC SSO provider boundary, Anthropic AI guidance adapter, IMAP email intake, SMTP email delivery, IMAP attachment capture, WhatsApp/Facebook/Instagram/SMS/voice provider boundaries, signed inbound/status callbacks, analytics rollups, CSAT feedback, operational alert controls, alert delivery attempts, attachment lifecycle retention, S3-compatible storage boundary, external scanner boundary, production list search/pagination controls, optimistic concurrency guards, backend-ranked knowledge suggestions, backend-ranked response macros, duplicate ticket suggestions and audited merge, supervisor recommendations, public portal answer deflection, public portal ticket intake, public portal ticket status/reply, public portal attachments, market-scoped support groups, market-scoped SLA policies, linked handoff team tickets, threaded handoff email replies, threaded customer email replies, audited handoff attachment links, production account-request pack, backend-queued account-request email, non-secret provider account-reference tracking, production launch readiness checklist, and frontend write-through bridge | In Progress | Provision external OIDC provider credentials, alert destination account, external dashboards/APM, channel provider credentials, and managed storage/scanner accounts flagged by the readiness checklist |

## Backlog

| ID | Item | Priority | Status |
| --- | --- | --- | --- |
| B-001 | Refresh source support-desk research for omnichannel operations | P0 | Done |
| B-002 | Rewrite comprehensive UI plan | P0 | Done |
| B-003 | Rewrite building architecture | P0 | Done |
| B-004 | Update progress automation to gbolahans@wakanow.com | P0 | Done |
| B-005 | Add IndexedDB persistence dependency | P0 | Done |
| B-006 | Create `src/domain.ts` | P0 | Done |
| B-007 | Create realistic omnichannel seed data | P0 | Done |
| B-008 | Create local-first store and derived metrics | P0 | Done |
| B-009 | Rebuild app shell and navigation | P0 | Done |
| B-010 | Build Omni Command screen | P0 | Done |
| B-011 | Build Unified Inbox and conversation cockpit | P0 | Done |
| B-012 | Add reply, note, handoff, macros, translation, and offline outbox UX | P0 | Done |
| B-013 | Build Live Channels and Customers screens | P1 | Done |
| B-014 | Build Knowledge, Automation, Analytics, Workforce, Admin, and Tracker screens | P1 | Done |
| B-015 | Update PWA manifest and service worker | P0 | Done |
| B-016 | Run lint, build, desktop browser verification, mobile browser verification, and PWA checks | P0 | Done |
| B-017 | Send milestone and final emails; include tracker inline when attachment upload fails | P0 | Done |
| B-018 | Create structured internal handoff queue and lifecycle | P0 | Done |
| B-019 | Add SVP-ready operations UI pass with priority queue, ticket operating strip, and resolution plan | P0 | Done |
| B-020 | Set AI work queue automation as default-on backend requirement with admin off switch | P0 | Done |
| B-021 | Start independent Python backend with ticket, customer, connector, handoff, analytics, and settings APIs | P0 | Done |
| B-022 | Wire the frontend PWA to the new Python backend API | P0 | Done |
| B-023 | Add backend login, user roles, market-scoped APIs, and SPA login gate with market switcher | P0 | Done |
| B-024 | Add production backend build plan, SQLAlchemy/Alembic schema, SQLite fallback, PostgreSQL-ready config, and readiness endpoint | P0 | Done |
| B-025 | Move backend login and session validation onto database records | P0 | Done |
| B-026 | Move market workspace settings and AI automation switch onto database records | P0 | Done |
| B-027 | Move customer and company APIs onto database records with ticket-creation rehydration | P0 | Done |
| B-028 | Clear stale frontend backend sessions on 401 and return to login gate | P0 | Done |
| B-029 | Move ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows onto database-first repositories | P0 | Done |
| B-030 | Move channel, agent, knowledge, and automation-rule management APIs onto database-first repositories | P0 | Done |
| B-031 | Move simulated inbound connector intake onto database-first repositories with customer creation, ticket creation, receipt timeline, and idempotency | P0 | Done |
| B-032 | Move analytics summary and Work Queue reads onto database-first repositories | P0 | Done |
| B-033 | Add market-scoped connector account readiness for Email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice | P0 | Done |
| B-034 | Add Setup connector control center UI for provider status, credentials, webhook health, send permission, failures, and capabilities | P0 | Done |
| B-035 | Switch local backend runtime to PostgreSQL database `omni_ticket` | P0 | Done |
| B-036 | Add database-backed admin user creation and management APIs | P0 | Done |
| B-037 | Add Setup user management UI for role, active state, assigned markets, and default market | P0 | Done |
| B-038 | Fix Postgres seed ordering so local data is FK-safe under PostgreSQL | P0 | Done |
| B-039 | Re-verify frontend/backend workspaces and refresh progress docs after backend bridge confirmation | P0 | Done |
| B-040 | Add durable outbound message queue with connector-account readiness checks, delivery status, retry, dead-letter states, and Setup visibility | P0 | Done |
| B-041 | Add backend worker foundation for due outbound retries, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events | P0 | Done |
| B-042 | Add production packaging for frontend static container, backend API container, worker process, release migrations, compose stack, and env validation | P0 | Done |
| B-044 | Isolate backend smoke tests from the repo-default PostgreSQL runtime and local socket assumptions | P0 | Done |
| B-043 | Fix Vercel serverless login by adding signed session tokens and same-origin backend service routing | P0 | Done |
| B-045 | Execute automation rules on ticket creation for routing, priority, tags, checklist tasks, rule health, timeline, and audit | P0 | Done |
| B-046 | Add signed connector webhook intake with timestamp freshness, delivery-id replay protection, account failure state, and audit history | P0 | Done |
| B-047 | Add route-level RBAC for agents, supervisors, admins, and auditors across setup, operations, audit, and readiness surfaces | P0 | Done |
| B-048 | Add database-backed rate limiting for login, authenticated connector intake, and signed provider webhooks with `429` and `Retry-After` behavior | P0 | Done |
| B-049 | Stabilize production rate-limit keys behind Vercel proxy routing and verify live login smoke tests | P0 | Done |
| B-050 | Add root GitHub Actions CI for frontend lint/build and backend compile, lint, typecheck, tests, migration sanity, and worker smoke | P0 | Done |
| B-051 | Add request correlation headers, processing-time headers, and structured backend access logs | P0 | Done |
| B-052 | Add durable audit records for login success/failure, rate-limit denial, explicit market selection, missing auth, invalid session, and market denial | P0 | Done |
| B-053 | Complete database-backed handoff acceptance, blocker, due-date, checklist, and close-loop timeline updates | P0 | Done |
| B-054 | Replace shared demo-password auth with per-user password hashes, admin temporary password reset, and self-service password change endpoint | P0 | Done |
| B-055 | Add ticket attachment metadata, policy scan state, audit history, timeline entries, and composer write-through bridge | P0 | Done |
| B-056 | Add raw binary attachment upload/download endpoints, local storage adapter, file-size guardrails, and frontend file picker upload path | P0 | Done |
| B-057 | Add expiring signed attachment download links with token validation and audit records | P0 | Done |
| B-058 | Align local SQLite bootstrap with Alembic head stamping and legacy auth-column repair so worker and migration smoke checks stay green | P0 | Done |
| B-059 | Add knowledge article review states with submitted-for-review and approval metadata across API, persistence, and migration paths | P0 | Done |
| B-060 | Repair legacy SQLite knowledge review columns in the embedded backend bootstrap path and rerun verification | P0 | Done |
| B-061 | Add worker-driven supervisor notifications for at-risk or breached high-priority, public-social, and VIP-impact tickets | P1 | Done |
| B-062 | Add market-scoped portal and partner API connector-account readiness metadata to the embedded backend copy | P1 | Done |
| B-064 | Add database-backed operational alerts with supervisor/admin APIs | P0 | Done |
| B-065 | Wire operational alerts into Command Center and Setup with acknowledge and resolve actions | P0 | Done |
| B-066 | Add durable alert delivery attempts and webhook dispatch status visibility | P0 | Done |
| B-067 | Add SMTP email outbound adapter and Setup provider-readiness visibility | P0 | Done |
| B-068 | Add durable hourly analytics rollups and Insights backend history panel | P0 | Done |
| B-069 | Add database-backed CSAT feedback with analytics and Insights visibility | P0 | Done |
| B-070 | Add configurable IMAP email inbound sync and Setup readiness visibility | P0 | Done |
| B-071 | Add configurable SMS HTTP outbound adapter and Setup readiness visibility | P0 | Done |
| B-072 | Add signed SMS inbound text and delivery-receipt callback handling | P0 | Done |
| B-073 | Add WhatsApp Cloud API outbound adapter and signed inbound/status callbacks | P0 | Done |
| B-074 | Add Facebook Messenger Graph API outbound adapter and signed inbound/delivery callbacks | P0 | Done |
| B-075 | Add Instagram DM Graph API outbound adapter and signed inbound/read callbacks | P0 | Done |
| B-076 | Add voice HTTP callback adapter and signed call/status callbacks | P0 | Done |
| B-077 | Add database-backed local TOTP MFA enrollment, login enforcement, and Setup controls | P0 | Done |
| B-078 | Add database-backed custom permission profiles, allow/deny overrides, self-lockout guard, and Setup controls | P0 | Done |
| B-079 | Add filtered durable audit CSV/JSON export, retention policy endpoints, admin prune action, worker pruning, and Setup controls | P0 | Done |
| B-080 | Add attachment lifecycle status, delete/purge endpoint, retention policy/prune endpoints, worker cleanup, and Setup controls | P0 | Done |
| B-081 | Add S3-compatible attachment storage adapter, external HTTP scanner boundary, pre-storage binary scan blocking, provider readiness endpoint, and Setup visibility | P0 | Done |
| B-082 | Add OIDC SSO readiness, PKCE start, one-time callback state, existing-user linking, guarded provisioning, and Login/Setup visibility | P0 | Done |
| B-083 | Add production-grade customer and ticket list search, sort, pagination headers, and market-scoped filters | P0 | Done |
| B-084 | Add optional ETag and If-Match optimistic concurrency protection for company, customer, and ticket updates | P0 | Done |
| B-085 | Add backend-ranked knowledge article suggestions with match reasons and Agent Assist visibility | P0 | Done |
| B-086 | Add durable market-scoped response macros with ticket ranking, usage tracking, audit history, and composer visibility | P0 | Done |
| B-087 | Add market-scoped configurable ticket fields with required validation, custom field persistence, Setup field builder, quick ticket fields, and ticket property editing | P0 | Done |
| B-088 | Declutter Setup into focused People, Ticket forms, Governance, Connectors, and Automation sections with compact backend user access controls | P0 | Done |
| B-089 | Add public customer portal answer deflection and unauthenticated ticket intake with backend field validation and frontend portal route | P0 | Done |
| B-090 | Add public portal ticket status lookup and customer reply/reopen flow with safe timeline visibility | P0 | Done |
| B-091 | Add market-scoped support groups with backend CRUD, ownership counters, rename propagation, Setup management, and handoff routing choices | P0 | Done |
| B-092 | Add market-scoped SLA policies with backend CRUD, ticket SLA resolution, frontend snapshot hydration, and Setup management | P0 | Done |
| B-093 | Add Anthropic Messages API guidance adapter, gitignored `AI_Key` handling, jimb support identity migration, and token-safe frontend market switching | P0 | Done |
| B-094 | Add database-backed email setup in Settings for IMAP intake and SMTP replies with write-only passwords and adapter readiness updates | P0 | Done |
| B-095 | Add database-backed production credentials in Settings for AI, alerts, SMS, voice, WhatsApp, Facebook, and Instagram with write-only secrets and adapter readiness updates | P0 | Done |
| B-096 | Add backend-ranked supervisor recommendations for blocked handoffs, queue pressure, and reassignment with Command Center visibility | P0 | Done |
| B-097 | Add support-group team inboxes and queue handoff-forward email threads with ticket, customer, comments, notes, custom fields, attachments, and SLA context | P0 | Done |
| B-098 | Add backend global search across tickets, customers, companies, answers, teams, handoffs, and agents with topbar result routing | P0 | Done |
| B-099 | Create linked internal team tickets for every handoff and expose the linked team ticket from the handoff board | P0 | Done |
| B-100 | Add sanitized production account-request pack for missing provider accounts, callback URLs, and `gbolahans@wakanow.com` email draft | P0 | Done |
| B-101 | Queue the sanitized production account-request pack to `gbolahans@wakanow.com` through the durable outbound email pipeline with an internal readiness ticket and idempotency | P0 | Done |
| B-102 | Add non-secret production account-reference tracking with provider IDs, owner, credential reference, docs snippet, audit history, and Setup controls | P0 | Done |
| B-103 | Add production launch readiness checklist that combines migration state, queued account-request evidence, account references, secret hygiene, provider readiness, storage/scanner, SSO, alerting, and observability gates | P0 | Done |
| B-104 | Thread team replies to handoff-forward emails back into linked internal tickets with source-ticket notes and audit history | P0 | Done |
| B-105 | Thread customer email replies back into the originating ticket with reopen, tags, timeline, and audit history instead of duplicate cases | P0 | Done |
| B-106 | Add audited signed attachment links to handoff-forward emails and linked team-ticket context for clean active case files | P0 | Done |
| B-107 | Capture IMAP email attachments through ticket attachment scanning/storage with duplicate-safe sync behavior | P0 | Done |
| B-108 | Add public portal attachment uploads for ticket creation and replies with sanitized customer-safe attachment visibility | P0 | Done |
| B-109 | Add backend-ranked duplicate ticket suggestions and audited merge controls in the Work Queue | P0 | Done |
| B-110 | Omni parity: expand Omnichannel Dashboard with source-style ticket/chat trends, ticket/chat CSAT, available agents, product/group filters, todo, and recent activity | P0 | Done |
| B-111 | Omni parity: expand ticket list/detail with saved views, export, collapsible filters, inline assign, due labels, keyboard shortcuts, watch, reply/note/forward, child service tasks, activities, threads, linked tickets, parent/child, time logs, and average handling time | P0 | Done |
| B-112 | Omni parity: expand Admin modules for AI, agents, groups, roles, business hours, portals, email, widgets, phone, chat, feedback form, WhatsApp, ticket forms, automations, email notifications, CSAT surveys, proactive outreach, routing, canned responses, ticket templates, scenario automations, canned forms, tags, threads, and security | P0 | Pending |
| B-113 | Omni parity: add support operations surfaces for forums, WhatsApp proactive campaigns, custom objects/purchase history, contact/company fields, multiple products, advanced ticketing, field service scheduling, account exports, scheduled exports, and helpdesk branding settings | P0 | Pending |
| B-114 | Omni parity: add full Analytics report-library parity beyond current Insights rollups, including report catalog/navigation, saved reports, and export/scheduled report controls | P0 | Pending |
| B-115 | Add Omni transition shell with mirrored navigation labels, utility actions, dashboard-first layout, ticket views/actions/context tabs, Omnichat modules, Admin module catalog, and Analytics report library | P0 | Done |

## Pending Items

- Use the authenticated Wakanow source support workspaces observed on 2026-06-05 as the parity reference for B-110 through B-115; avoid copying proprietary styling verbatim, but mirror operational workflows under Omni language and Wakanow terminology.
- Rotate/centralize the Anthropic secret in managed secret storage when available; root `AI_Key` is active locally and on the isolated Omni VM, and Anthropic keys can now be saved as write-only Setup Production credentials.
- Provision provider credentials for built adapters: `jimb@wakanow.com` mailbox values, alert webhook, WhatsApp Cloud API, Facebook Messenger, Instagram DM, SMS HTTP, and voice HTTP values can now be saved in Setup; OIDC SSO still needs production identity-provider credentials. The production readiness checklist now surfaces these as live blocked/action items.
- Provision managed object storage, malware scanning provider, external dashboards/APM, and hardened secret storage.
- Connect historical support-desk import/sync only if requested.
- Add database tenant isolation hardening, provider account activation, and signed public download policy hardening.
- Sync documentation changes into the standalone backend repository at `/Users/gbolahan.salami/Documents/omni-ticket-backend`; the current automation sandbox can verify that repo but cannot write to it.
- Commit the workspace to git and open the first delivery PR when the review path is agreed.

## Closed Issues

| Issue | Resolution | Closed On |
| --- | --- | --- |
| C-001 | User clarified the expected result is a full omnichannel operations support solution, not a thin demo | 2026-05-25 |
| C-002 | Rebuild plan accepted with generic support desk, full channel set, Omni Command home, simulated Copilot, and docs plus tracker | 2026-05-25 |
| C-003 | Progress automation updated to continue every 3 hours and email gbolahans@wakanow.com | 2026-05-25 |
| C-004 | Research, UI plan, architecture, and tracker docs rewritten for the Omni rebuild | 2026-05-25 |
| C-005 | Omni domain model, seed data, IndexedDB store, and app shell implemented | 2026-05-25 |
| C-006 | Omni Command, Unified Inbox, Live Channels, Customers, Knowledge, Automation, Analytics, Workforce, Admin, and Tracker screens implemented | 2026-05-25 |
| C-007 | Lint, production build, browser workflow verification, manifest check, and service worker asset check passed | 2026-05-25 |
| C-008 | Final email sent with tracker summary inline after attachment upload failed; separate tracker attachment retry also failed in connector upload | 2026-05-25 |
| C-009 | Progress email delivery resumed with `docs/project-tracker.md` attached through local `sendmail` fallback after Gmail connector startup failure | 2026-05-26 |
| C-010 | Latest local state re-verified with lint and production build, and a refreshed progress email was prepared with the tracker attachment | 2026-05-26 |
| C-011 | Current workspace state re-verified with lint and production build before sending the next progress update with the tracker attachment | 2026-05-26 |
| C-012 | SVP-ready UI improvement pass completed with clearer priority work, ticket operating signals, and next-best-action guidance | 2026-05-26 |
| C-013 | AI work queue automation locked as default-on behavior unless disabled in Setup | 2026-05-27 |
| C-014 | Independent Python backend vertical slice created with passing smoke tests and local API docs | 2026-05-27 |
| C-015 | Frontend now reads backend health/settings/tracker/analytics/provider readiness and writes the AI automation toggle back to the independent API | 2026-05-27 |
| C-016 | Login gate, backend sessions, market selector, and market-scoped API isolation added for the single SPA model | 2026-05-27 |
| C-017 | Production backend build plan and durable persistence foundation completed with database readiness smoke tests | 2026-05-27 |
| C-018 | Backend login now creates durable database sessions and protected APIs validate user and market access through SQLAlchemy | 2026-05-27 |
| C-019 | Market settings now persist in the backend database, including the AI Work Queue automation switch used by ticket and connector intake | 2026-05-27 |
| C-020 | Frontend operational screens now hydrate channels, agents, customers, tickets, handoffs, knowledge, and rules from authenticated backend snapshots | 2026-05-27 |
| C-021 | Customer and company APIs now read/write database records, survive API restart, and can rehydrate a customer before opening a ticket | 2026-05-27 |
| C-022 | Frontend now clears stale backend sessions after a 401 and successfully re-authenticates against the local API | 2026-05-27 |
| C-023 | Ticket, timeline, reply/note, handoff, AI decision, and outbound connector-event workflows now use database-first repositories and survive API restart | 2026-05-27 |
| C-024 | Frontend ticket creation, replies, notes, handoffs, and key admin controls now write through the authenticated backend and rehydrate from fresh market snapshots | 2026-05-27 |
| C-025 | Channel, agent, knowledge, and automation-rule management APIs now use database-first repositories and survive API restart | 2026-05-27 |
| C-026 | Simulated inbound connector intake now uses database-first repositories with persisted customer creation, ticket creation, connector receipt timeline, and deduplication | 2026-05-27 |
| C-027 | Analytics summary and Work Queue reads now use database-first repositories and survive runtime reset | 2026-05-27 |
| C-028 | Market-scoped connector account readiness APIs and Setup connector control center UI added for Email, WhatsApp, Facebook, Instagram, SMS, and voice | 2026-05-27 |
| C-029 | Local backend switched to PostgreSQL database `omni_ticket`, with Postgres-safe seeding and smoke tests passing | 2026-05-27 |
| C-030 | Admins can now create users, change roles, assign markets, set default market, and deactivate/reactivate users from Setup | 2026-05-27 |
| C-031 | Frontend backend-snapshot bridge re-confirmed and current frontend/backend verification rerun completed | 2026-05-28 |
| C-032 | Public replies now create durable outbound messages with provider readiness checks, delivery status, retry endpoint, connector receipts, and Setup queue visibility | 2026-05-29 |
| C-033 | Backend worker foundation now runs one-shot or looping jobs for outbound retries, SLA refresh, Work Queue recompute, analytics rollups, and worker audit events | 2026-05-29 |
| C-034 | Production packaging added for static frontend, backend API, release migrations, worker process, local compose, and staging/production environment validation | 2026-05-29 |
| C-036 | Backend smoke tests now isolate to a temporary SQLite database and signed sessions can survive a missing session row when the token is still valid | 2026-05-29 |
| C-035 | Vercel 401 login failure fixed by using signed session tokens and pointing the deployed PWA at the same-origin backend service route | 2026-05-29 |
| C-037 | Automation rules now execute during ticket creation, applying deterministic routing, priority, tags, checklist tasks, last-fired state, timeline entries, and audit history even when AI routing is disabled | 2026-05-29 |
| C-038 | Signed provider webhook intake added with account readiness checks, HMAC signature verification, timestamp freshness, delivery-id replay protection, failure tracking, and audit history | 2026-05-29 |
| C-039 | Route-level RBAC now enforces agent operational writes, supervisor controls, admin-only setup, auditor read-only access, audit visibility, and readiness restrictions | 2026-05-29 |
| C-040 | Login, authenticated connector intake, and signed provider webhooks now have configurable database-backed rate limits with `429` and `Retry-After` responses | 2026-05-29 |
| C-041 | Production Vercel smoke tests now confirm admin login returns `200` and repeated invalid login attempts return `429` after the configured limit | 2026-05-29 |
| C-042 | Root GitHub Actions CI now gates push and pull request changes with frontend and backend production checks | 2026-05-29 |
| C-043 | Backend responses now include request IDs and processing time while structured JSON access logs provide production traceability | 2026-05-29 |
| C-044 | Auth and access-control decisions now write request-correlated audit records into the durable backend audit trail | 2026-05-29 |
| C-045 | Handoff acceptance, blocker capture, due-date updates, checklist progress, and close-loop timeline history now persist through the database-backed lifecycle | 2026-05-29 |
| C-046 | Users now authenticate against per-user PBKDF2 password hashes; admins can create/reset temporary credentials and users can change passwords to clear reset requirements | 2026-05-29 |
| C-047 | Ticket attachments now have database-backed metadata, local policy scan status, timeline events, audit history, and a composer metadata flow that writes through to the backend | 2026-05-29 |
| C-048 | Clean binary attachments can now be uploaded through a raw backend endpoint, stored behind a local storage adapter, downloaded after scan clearance, and selected through the frontend file picker | 2026-05-29 |
| C-049 | Attachment downloads now support expiring signed links with token validation and durable audit records for link creation and signed downloads | 2026-05-29 |
| C-050 | Frontend lint/build plus backend compile, lint, typecheck, tests (`60 passed`), migration sanity, and worker smoke were rerun successfully before the 2026-05-30 progress update with tracker and backend docs attachments | 2026-05-30 |
| C-051 | Embedded backend local SQLite bootstrap now repairs legacy auth columns and stamps Alembic head so worker startup and `alembic upgrade head` pass against the current local database | 2026-05-30 |
| C-052 | Embedded backend now matches the standalone repo on knowledge review states, approval metadata, and Alembic head `20260530_0007`, with verification rerun green | 2026-05-30 |
| C-053 | Embedded backend bootstrap now also repairs legacy knowledge review columns, and the 2026-05-31 rerun passed frontend lint/build plus backend compile, lint, typecheck, tests (`61 passed`), migration sanity, and worker smoke | 2026-05-31 |
| C-054 | Worker-side supervisor notifications now write one deduplicated internal note and audit event per SLA risk state for high-priority, public-social, and VIP-impact tickets; the 2026-05-31 rerun passed frontend lint/build plus backend compile, lint, typecheck, tests (`62 passed`), migration sanity, and worker smoke | 2026-05-31 |
| C-055 | Frontend and standalone backend were re-verified together, the embedded backend copy was aligned with standalone service-account RBAC coverage, and the 2026-05-31 rerun passed frontend lint, no-emit TypeScript checks, frontend build, backend compile, lint, typecheck, tests (`63 passed`), migration sanity, and worker smoke | 2026-05-31 |
| C-056 | The 2026-06-02 rerun again passed frontend lint, no-emit TypeScript checks, frontend build, backend compile, lint, typecheck, tests (`63 passed`), migration sanity, and worker smoke; the remaining delivery gap is syncing the standalone backend repo with the newer embedded backend copy | 2026-06-02 |
| C-057 | The 2026-06-04 rerun again passed frontend lint, no-emit TypeScript checks, frontend build, and standalone backend compile, lint, typecheck, tests (`63 passed`), migration sanity, and worker smoke; implementation is functionally aligned across workspaces, with standalone doc sync still blocked by read-only sandbox access | 2026-06-04 |
| C-058 | Embedded backend connector readiness now includes portal and partner API accounts so the Setup surface matches the full omnichannel channel model used by the frontend | 2026-06-04 |
| C-062 | Email outbound now has a configurable SMTP adapter and Setup provider-readiness visibility | 2026-06-03 |
| C-063 | Worker analytics now persist durable hourly rollups with an Insights backend history panel | 2026-06-03 |
| C-064 | Ticket CSAT feedback now persists in the database and feeds analytics summary, rollups, and Insights | 2026-06-03 |
| C-065 | Email inbound now has configurable IMAP polling through the backend worker and Setup readiness panel | 2026-06-03 |
| C-066 | SMS outbound now has a configurable HTTP provider adapter for queued public replies and Setup readiness | 2026-06-03 |
| C-067 | SMS signed webhooks now support inbound text tickets and outbound delivery receipts | 2026-06-03 |
| C-068 | WhatsApp Cloud API delivery and signed inbound/status callbacks now use the durable connector pipeline | 2026-06-03 |
| C-069 | Facebook Messenger Graph API delivery and signed inbound/delivery callbacks now use the durable connector pipeline | 2026-06-03 |
| C-070 | Instagram DM delivery and signed inbound/read callbacks now use the durable connector pipeline | 2026-06-03 |
| C-071 | Voice HTTP callback delivery and signed inbound/status callbacks now use the durable connector pipeline | 2026-06-03 |
| C-072 | Local TOTP MFA enrollment, confirmation, login enforcement, disable, and account-recovery reset are now backed by the database and visible in Setup | 2026-06-04 |
| C-073 | User access now supports database-backed permission profiles, per-permission allow/deny overrides, permission-aware route enforcement, and a self-lockout guard for setup access | 2026-06-04 |
| C-074 | Audit governance now supports permission-gated CSV/JSON export, configurable retention policy, admin pruning, worker pruning, export audit records, and Setup controls | 2026-06-04 |
| C-075 | Attachment governance now supports lifecycle status, supervisor delete/purge, configurable retention, admin pruning, worker cleanup, and Setup storage-lifecycle controls | 2026-06-04 |
| C-076 | Attachment provider hardening now includes S3-compatible object storage, external HTTP malware scanner configuration, pre-storage binary scan blocking, sanitized readiness API, and Setup provider visibility | 2026-06-04 |
| C-077 | Production identity now has an OIDC SSO boundary with PKCE authorization start, one-time callback state, existing-user linking, guarded provisioning, and Login/Setup readiness | 2026-06-04 |
| C-078 | Customer and ticket list APIs now support market-scoped search, filters, allowlisted sorting, optional pagination, and count headers without changing the list response shape | 2026-06-04 |
| C-079 | Company, customer, and ticket create/read/update APIs now emit ETags, and stale `If-Match` updates return `412 Precondition Failed` instead of overwriting newer changes | 2026-06-04 |
| C-080 | Ticket contexts now include backend-ranked knowledge suggestions with score, matched terms, and reasons; Agent Assist uses the top backend article as the best answer | 2026-06-04 |
| C-081 | Response macros are now database-backed, ticket-ranked, usage-counted, audit-visible, included in frontend snapshots, and wired into the composer dropdown/suggestion buttons | 2026-06-04 |
| C-082 | Ticket fields are now database-backed, admin-configurable by market/channel, validated on create/update, included in frontend snapshots, and rendered in quick ticket and ticket property forms | 2026-06-04 |
| C-083 | Setup was split into focused sections and the People roster was compacted so add-user remains visible while heavier access controls expand per user | 2026-06-04 |
| C-084 | Public portal answer search and customer ticket submission now use backend-ranked published answers, portal ticket fields, customer reuse, audit history, and the unauthenticated `?screen=portal` frontend route | 2026-06-04 |
| C-085 | Public portal ticket status lookup and customer replies now verify public ID plus requester email, expose only public timeline entries, audit replies, and reopen tickets when customers respond | 2026-06-04 |
| C-086 | Support groups are now database-backed per market, exposed through admin CRUD APIs and frontend snapshots, shown in Setup with live counters, used by handoff routing choices, and safely propagated across agents, tickets, and handoffs when renamed | 2026-06-04 |
| C-087 | SLA policies are now database-backed per market, exposed through admin CRUD APIs and frontend snapshots, used by ticket creation and urgency escalation, and manageable from a compact Setup Automation panel | 2026-06-04 |
| C-088 | Production AI guidance now has an Anthropic Messages adapter with gitignored root `AI_Key` support, jimb support identity migration, and frontend market switching no longer depends on the demo password | 2026-06-04 |
| C-089 | The supplied `AI_Key.rtf` was normalized into gitignored plain `AI_Key`, deployed to the isolated Omni VM, and live-smoked through Anthropic `claude-sonnet-4-6` from both local and VM runtimes | 2026-06-04 |
| C-090 | Setup now includes an Email setup panel for market IMAP and SMTP configuration, persists sanitized provider settings, keeps passwords write-only, and drives adapter readiness plus email connector status | 2026-06-04 |
| C-091 | Supervisor recommendations now compute live backend-ranked actions for blocked handoffs, due handoffs, queue pressure, and reassignment; Command Center uses the backend payload with agent access blocked | 2026-06-05 |
| C-092 | Attachment signed download links now include a unique token ID and creator identity, correlate link creation/download audit records, reject mismatched paths, and return no-store/nosniff download headers | 2026-06-05 |
| C-093 | Support groups now store team inboxes, handoff requests queue internal email forwards with full case context, and the topbar global search is backed by a market-scoped API | 2026-06-05 |
| C-094 | Handoff requests now create linked internal team tickets, stamp `linked_ticket_id` on the handoff, carry the full case context into the child ticket, and expose a Team ticket action on handoff cards | 2026-06-05 |
| C-095 | Setup now exposes a sanitized production account-request pack with missing provider credentials, callback URLs, credential reference names, and a mailto draft to `gbolahans@wakanow.com` | 2026-06-05 |
| C-096 | Admins can queue the sanitized production account-request pack to `gbolahans@wakanow.com`; the backend creates an internal readiness ticket, writes audit history, and returns the durable outbound email message | 2026-06-05 |
| C-097 | Setup now tracks non-secret provider account references and generates a copy-ready API_DOCS Markdown snippet after accounts are provisioned | 2026-06-05 |
| C-098 | Setup now exposes a production launch readiness checklist backed by live API evidence, provider credential gates, account-reference hygiene, and sanitized next actions | 2026-06-05 |
| C-099 | Handoff-forward emails now carry source/linked-ticket thread headers, and inbound team replies append to the linked internal ticket instead of creating duplicate cases | 2026-06-05 |
| C-100 | Customer email replies that reference an Omni outbound message now append to the originating ticket, reopen non-open cases, tag `customer-replied`, and write connector/audit history | 2026-06-05 |
| C-101 | Handoff-forward emails and linked team tickets now include audited signed download links for clean active attachments while blocked/deleted files remain metadata-only | 2026-06-05 |
| C-102 | IMAP email intake now scans attachments, stores clean files on the ticket, records blocked files as metadata-only attachments, and avoids duplicate files during replay | 2026-06-05 |
| C-103 | Public portal users can upload proof files to their tickets and replies; clean files are stored, blocked files are metadata-only, and portal detail shows sanitized attachment status | 2026-06-05 |
| C-104 | Ticket contexts now include duplicate suggestions, and agents can merge a source ticket into the selected target with both timelines audited and the source closed/marked as merged | 2026-06-05 |
| C-105 | B-110 done: the Omnichannel Dashboard now computes live ticket/chat first-response, resolution-within-SLA, and CSAT breakdowns from conversation timelines and backend CSAT feedback (new `src/metrics.ts`); Product/group filters were replaced with working live support-group and date-range filters; the To-do widget persists per user and Recent activity is a live, clickable timeline feed; removed all hardcoded dashboard tiles; frontend typecheck, lint, and production build pass | 2026-06-05 |
| C-106 | B-111 done: the ticket list now has working sort, card/table layout, CSV export, pagination, collapsible filters with active-count, bulk select + bulk assign/status, inline assign/priority/status per row, and live group/created/resolution-due filters (removed dead date filters and the no-op Apply); the ticket detail has a working Watch toggle (persisted per user), keyboard shortcuts (w/r/n/f), Jump-to-search, and the Activities/Threads/Linked/Time tabs now render real content with live average handling time and per-ticket time logging; typecheck, lint, and build pass | 2026-06-05 |
