# Omni Ticket Project Tracker

Last updated: 2026-05-29

## Epics

| Epic | Outcome | Status | Pending |
| --- | --- | --- | --- |
| E1 Research and product definition | Freshdesk/Freshworks-informed Omni research, UI plan, architecture, and tracker docs | Done | None |
| E2 Omni data model and app shell | Split TypeScript domain, seed data, store, navigation, and IndexedDB persistence | Done | None |
| E3 Omnichannel operations workflow | Command Center, Work Queue, Channel Chats, Customer 360, composer, handoffs, and assistive guidance | Done | None |
| E4 Admin, analytics, knowledge, workforce, and tracker | Operational management screens with meaningful data and controls | Done | None |
| E5 Install-ready app, verification, and delivery | Offline state, app shell, responsive verification, and milestone emails | Done | None |
| E6 Python backend vertical slice | Local HTTP API, isolated smoke tests, authenticated market sync, login, market scoping, local PostgreSQL runtime, user management, route-level RBAC, durable persistence foundation, outbound delivery queue, signed inbound webhooks, rate limits, background worker foundation, deployment packaging, signed-session fallback, automation-rule execution, and frontend write-through bridge | In Progress | Add real provider adapters, production SSO/MFA, custom permissions, managed hosting, and observability |

## Backlog

| ID | Item | Priority | Status |
| --- | --- | --- | --- |
| B-001 | Refresh Freshdesk/Freshworks research for omnichannel operations | P0 | Done |
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

## Pending Items

- Decide hosting target for production deployment.
- Build real provider adapters for email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice.
- Add production identity provider, password policy, MFA/SSO, custom permission profiles, and approval workflows.
- Deploy the packaged web/API/worker processes to the selected managed hosting target with alerting and retry observability.
- Connect real channel credentials and Freshdesk/Freshworks import/sync only if requested.
- Add production RBAC enforcement, durable audit log export/retention, database tenant isolation hardening, and attachment scanning.
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
