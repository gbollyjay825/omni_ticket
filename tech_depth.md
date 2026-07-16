# Deferred Technical Depth

## Freshchat tenant-wide historical discovery

**Status:** External API limitation; continue with export ingestion plus incremental API sync.

Freshchat's documented v2 API can list users only when at least one search criterion is
provided, and conversations are discovered from a known user ID. It does not document an
unfiltered tenant-wide users or conversations endpoint equivalent to Freshdesk's pageable
ticket list. The migration therefore needs both of the following inputs:

1. A complete Freshchat account export for historical users, conversations, and messages.
2. Freshchat API credentials for reconciliation and incremental sync of the discovered
   user and conversation IDs.

Official references:

- https://developers.freshchat.com/api/#users
- https://developers.freshchat.com/api/#retrieve-all-conversations-for-a-user
- https://developers.freshchat.com/api/#list-messages-in-a-conversation

Before final cutover, confirm the tenant export format and whether Wakanow's Freshworks
plan exposes a private bulk export API. Do not claim complete historical reconciliation
until the export has been ingested and its counts match the source tenant.

## Proactive campaign delivery aggregate

**Status:** Resolved in code on 2026-07-14; external provider approval remains.

Campaign sends now use a dedicated `campaign_deliveries` aggregate with consent,
idempotency, retry, suppression, provider receipts, audit history, and no support-ticket
side effects. Production delivery remains gated until Wakanow supplies active channel
credentials, approved WhatsApp template names and languages, and confirmation that each
Meta proactive-messaging use case is allowed for the connected account. The application
reports these as unconfigured and never simulates delivery.

## Verified portal customer identity

**Status:** External identity dependency; continue building portal workflows behind the
current signed ticket lookup and widget conversation tokens.

The public portal can create tickets, look up a reference using the customer's email, add
replies and attachments, and submit CSAT. Full authenticated history, profile management,
and cross-device case access require Wakanow's customer identity source and either OIDC
metadata or an approved email-verification provider. Do not expose an email-only endpoint
that lists every case for a customer before that identity proof is available.

## Legacy workspace compatibility boundary

**Status:** Internal technical depth; continue extracting route modules while preserving
the passing end-to-end workflows.

The staff workspace still carries a legacy in-memory compatibility store alongside the
PostgreSQL repositories. Most durable operations now call real APIs, and server-backed
tasks, watches, time logs, reports, campaigns, consent, portal, widget, and migration
records no longer depend on browser storage. Some older company, customer, and setup
mutations still update the compatibility store after the database commit, however, which
keeps `OmniApp.tsx` and `App.css` substantially larger than the target architecture.

The unreachable portal implementation was removed from `OmniApp.tsx` on 2026-07-14 and
the portal remains a lazy route. Tickets, Omnichat, Solutions, Forums, Workflows,
Scheduling, AI Agents, Campaigns, and Custom Objects were extracted into lazy, API-backed
route modules on 2026-07-14. Continue the same extraction pattern for Dashboard, Contacts,
and Admin. New product work must live in route modules with generated API clients; do not
add new durable state or provider logic to the compatibility store. Remove
`persist_store_state` only after each remaining caller has a repository-owned audit and
realtime path plus regression coverage.

## Ticket command endpoints

**Status:** Resolved in code on 2026-07-14.

The ticket workspace now uses the consolidated workspace endpoint and version-aware APIs
for assignment, priority, status, replies, private notes, watchers, merge, scenarios, time
logs, attachments, activity, links, pagination, previous/next navigation, forwarding,
child tasks, new-ticket creation, and server-side export. Saved queue views and advanced
customer, age, tag, assignment, group, status, priority, source, sorting, and pagination
filters are persisted through the backend and covered at desktop, tablet, and mobile sizes.

## First-class conversation provider delivery

**Status:** Resolved in code on 2026-07-15; external provider credentials remain.

Omnichat public replies now create first-class outbound records linked directly to the
conversation and chat message, use the existing email, Meta, SMS, voice, and web-chat
adapter boundary, and persist queued, sending, sent, failed, delivered, and read state.
Private notes remain internal. Provider failures update both the outbound record and chat
message without fabricating success, and provider receipts can resolve the conversation
message directly. Active Wakanow channel credentials are still required before live
customer delivery can be enabled.

## First-class conversation attachments

**Status:** Resolved in code on 2026-07-15; managed production storage remains external.

The conversation workspace now supports binary upload, malware-policy scanning, governed
retention and deletion, message linkage, outbound attachment references, authenticated
downloads, and signed downloads. Blocked files cannot be attached to a message. The UI
supports upload, removal before send, attachment-only replies, message download links, and
conversation attachment history. Production activation still requires Wakanow's managed
S3-compatible bucket and HTTP malware scanner because the production runtime correctly
rejects VM-local attachment storage and development scanning fallbacks.

## Live Freshworks data migration workstream

**Status:** Deliberately separate from primary implementation; blocks migration cutover
only.

No live Freshdesk or Freshchat tenant data has been imported into the local developer
database. The importers now write Freshdesk tickets and first-class Freshchat conversations,
messages, participants, identities, and canonical cases against schema revision `0054`.
They support protected CLI full exports, dry runs, committed runs, incremental cursors,
source manifests, reconciliation checks, final-delta gates, audited cutover approval, and
the 72-hour rollback window. Live execution still requires Freshworks admin API credentials,
complete exports, and isolated staging storage. Synthetic local records are test fixtures only.

## Production Entra activation

**Status:** Implementation complete; external tenant configuration blocks live activation only.

Production startup requires Microsoft Entra OIDC, verified `wakanow.com` identities,
disabled automatic provisioning, explicit group-to-role and group-to-market maps, secure
cookies, managed Redis, PostgreSQL, S3-compatible storage, and an HTTP malware scanner.
Password access is limited to named `wakanow.com` break-glass administrators with TOTP.
The login, claim mapping, market denial, unprovisioned-user denial, replay protection, and
break-glass paths are covered by backend tests. Wakanow must still provide the Entra tenant
metadata, client credentials, approved group IDs, and named break-glass identities before
the production identity gate can be activated.

The Vercel production target was redeployed on 2026-07-15, but its current environment
still sets `OMNI_ENVIRONMENT=local`; OIDC is disabled and password login remains available
to all configured users. Switching that target to `production` is intentionally blocked
until the required Entra, Redis, S3, scanner, secure-session, and break-glass settings are
provided, because the backend correctly rejects an incomplete production configuration.
The same Vercel target currently uses function-local SQLite, so QA authentication can be
re-established by the one-click login but tickets, conversations, attachments, and session
records are not guaranteed to survive a cold start or stay consistent across function
instances. Connect the managed PostgreSQL database before treating the Vercel target as a
shared integration environment; no application fallback should pretend that ephemeral
state is durable.

## Pulse VM production runtime gate

**Status:** External infrastructure and identity configuration still block the strict
production profile.

The live VM currently identifies itself as `pulse-vm`, uses PostgreSQL and the real Gmail
IMAP/SMTP connector, but still has password login for all seeded users, non-secure session
cookies, VM-local attachment storage, and the local outbound fallback enabled. Changing
the runtime to `production` is intentionally blocked until Wakanow supplies managed Redis,
S3-compatible attachment storage, the HTTP malware scanner, Entra metadata and group maps,
and named TOTP break-glass administrators. SMTP now refuses reserved placeholder recipients
in `pulse-vm` so seeded `*.example.com` team addresses cannot create false sends or mailbox
bounces while IT replaces them with real support group inboxes.
