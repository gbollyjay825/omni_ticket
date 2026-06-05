# Omni Ticket API Docs

Last updated: 2026-06-05

## Production Endpoint

- Frontend: `https://omni.wakanow.com`
- API base URL: `https://omni.wakanow.com/api/v1`
- API health: `GET https://omni.wakanow.com/api/v1/health`
- Support mailbox / sender identity: `jimb@wakanow.com`
- OpenAPI schema, when exposed by the FastAPI service directly: `/openapi.json`
- Interactive docs, when exposed by the FastAPI service directly: `/docs`

The current Pulse VM deployment runs Omni Ticket separately from the Pulse application:

- App path: `/home/amechi/omni-ticket/current`
- Runtime env: `/home/amechi/omni-ticket/runtime/env.sh`
- PM2 processes: `omni-ticket-api`, `omni-ticket-worker`, `omni-ticket-frontend`
- Database: local PostgreSQL database/user `omni_ticket`
- Public Nginx route: `omni.wakanow.com`

## Authentication

All protected API routes use bearer tokens returned by `POST /auth/login`. Users with MFA enabled must include `mfa_code` in the login payload.

```http
Authorization: Bearer <access_token>
X-Omni-Market: market-ng
```

Current roles:

- `agent`: operational ticket work.
- `supervisor`: operational control, queue override, readiness visibility.
- `admin`: setup, users, settings, connectors, automation rules.
- `auditor`: read-only audit visibility.
- `service_account`: machine-oriented role for connector or automation access.

Current permission keys:

- `operations.write`: ticket/customer/reply/handoff and connector-intake operations.
- `supervisor.control`: readiness, queue override, provider status, alert, and supervisor controls.
- `audit.read`: audit visibility.
- `setup.manage`: users, settings, connector accounts, SLA policies, and automation setup.

Users inherit permissions from role by default. Admins can also set `permission_profile` and `permission_overrides.allow` / `permission_overrides.deny` through `POST /auth/users` and `PATCH /auth/users/{user_id}`.

Enterprise SSO:

- `GET /auth/oidc/config` is public and returns sanitized OIDC readiness. It never returns the client secret, token values, or provider responses.
- `GET /auth/oidc/start?market_id=market-ng` starts an OIDC authorization-code flow when configured. It creates a short-lived one-time state row and returns a provider authorization URL using PKCE (`S256`).
- `POST /auth/oidc/callback` exchanges the provider code for userinfo, enforces verified email and allowed-domain policy, links an existing backend user by email or external subject, and returns the same `AuthSession` shape as password login.
- Auto-provisioning is off by default. If `OMNI_OIDC_AUTO_PROVISION_ENABLED=true`, new SSO users are created with `OMNI_OIDC_DEFAULT_ROLE` and `OMNI_OIDC_DEFAULT_MARKET_ID`; leave this disabled until the Wakanow identity lifecycle approval process is agreed.
- OIDC state is consumed once. Replay or expired state values return `401`.
- Runtime settings: `OMNI_OIDC_ENABLED`, `OMNI_OIDC_PROVIDER_NAME`, `OMNI_OIDC_ISSUER_URL`, `OMNI_OIDC_AUTHORIZATION_URL`, `OMNI_OIDC_TOKEN_URL`, `OMNI_OIDC_USERINFO_URL`, `OMNI_OIDC_CLIENT_ID`, `OMNI_OIDC_CLIENT_SECRET`, `OMNI_OIDC_REDIRECT_URL`, `OMNI_OIDC_ALLOWED_EMAIL_DOMAINS`, `OMNI_OIDC_AUTO_PROVISION_ENABLED`, `OMNI_OIDC_DEFAULT_ROLE`, `OMNI_OIDC_DEFAULT_MARKET_ID`, `OMNI_OIDC_REQUIRE_EMAIL_VERIFIED`, `OMNI_OIDC_HTTP_TIMEOUT_SECONDS`, and `OMNI_OIDC_STATE_TTL_MINUTES`.

AI Work Queue guidance:

- `OMNI_AI_PROVIDER=auto` uses Anthropic guidance when an API key is configured and falls back to deterministic routing if the key is absent or the provider is unavailable.
- `OMNI_AI_PROVIDER=anthropic` keeps Anthropic as the intended production provider; deployment validation requires either `OMNI_ANTHROPIC_API_KEY` or `OMNI_ANTHROPIC_API_KEY_FILE`.
- `OMNI_ANTHROPIC_API_KEY_FILE=AI_Key` reads the key from the project root by default. `AI_Key` is gitignored and must not be committed.
- `OMNI_ANTHROPIC_API_BASE_URL`, `OMNI_ANTHROPIC_MODEL`, `OMNI_ANTHROPIC_VERSION`, `OMNI_ANTHROPIC_TIMEOUT_SECONDS`, and `OMNI_ANTHROPIC_MAX_TOKENS` control the Anthropic Messages API call.
- Ticket creation stores the generated `ai_summary`, `recommended_action`, AI decision confidence, model version, and input reference. AI can recommend and route; it still cannot send customer messages without an approved policy.

## Core API Surface

Authentication and users:

- `POST /auth/login`
- `GET /auth/oidc/config`
- `GET /auth/oidc/start`
- `POST /auth/oidc/callback`
- `GET /auth/me`
- `GET /auth/markets`
- `GET /auth/users`
- `POST /auth/users`
- `PATCH /auth/users/{user_id}`
- `POST /auth/password`
- `POST /auth/mfa/enroll`
- `POST /auth/mfa/confirm`
- `POST /auth/mfa/disable`

Platform and settings:

- `GET /platform/readiness`
- `GET /settings`
- `PATCH /settings`
- `PATCH /settings/ai-work-queue-automation`

Operations:

- `GET /frontend/snapshot`
- `GET /portal/{market_code}/answers`
- `POST /portal/{market_code}/tickets`
- `GET /portal/{market_code}/tickets/{public_id}`
- `POST /portal/{market_code}/tickets/{public_id}/reply`
- `POST /portal/{market_code}/tickets/{public_id}/attachments?email={customer_email}&filename={filename}`
- `GET /channels`
- `PATCH /channels/{channel_id}`
- `GET /agents`
- `PATCH /agents/{agent_id}/status`
- `GET /search`
- `GET /support-groups`
- `GET /groups`
- `POST /support-groups`
- `PATCH /support-groups/{group_id}`
- `GET /sla-policies`
- `POST /sla-policies`
- `PATCH /sla-policies/{policy_id}`
- `GET /companies`
- `POST /companies`
- `PATCH /companies/{company_id}`
- `GET /customers`
- `POST /customers`
- `GET /customers/{customer_id}`
- `PATCH /customers/{customer_id}`
- `GET /tickets`
- `POST /tickets`
- `GET /tickets/{ticket_id}`
- `GET /tickets/{ticket_id}/knowledge-suggestions`
- `GET /tickets/{ticket_id}/macro-suggestions`
- `GET /tickets/{ticket_id}/duplicate-suggestions`
- `POST /tickets/{ticket_id}/merge`
- `PATCH /tickets/{ticket_id}`
- `GET /ticket-fields`
- `POST /ticket-fields`
- `PATCH /ticket-fields/{field_id}`
- `GET /tickets/{ticket_id}/timeline`
- `POST /tickets/{ticket_id}/timeline`
- `POST /tickets/{ticket_id}/reply`
- `GET /work-queue`
- `GET /operations/recommendations`
- `POST /work-queue/{ticket_id}/override`
- `GET /handoffs`
- `POST /tickets/{ticket_id}/handoffs`
- `PATCH /handoffs/{handoff_id}`
- `GET /csat/feedback`
- `POST /tickets/{ticket_id}/csat`

Knowledge suggestions:

- `GET /tickets/{ticket_id}/knowledge-suggestions?limit=3` returns ranked answer suggestions for the authenticated market.
- The response shape is `[{ article, score, reasons, matched_terms }]`. `article` is the normal knowledge article payload, `score` is capped at 100, `reasons` explains why the article was chosen, and `matched_terms` exposes the highest-signal terms.
- Only `approved` and `published` articles are suggested. Draft and in-review articles are excluded from Agent Assist.
- Suggestion scoring considers market access, channel fit, ticket tags, title/body term overlap, priority escalation fit, and customer recovery fit.
- `GET /tickets/{ticket_id}` and `GET /frontend/snapshot` include `knowledge_suggestions` in each ticket context so the frontend Agent Assist card can use backend-ranked answers without an extra request.

Response macros:

- `GET /macros?active_only=true&channel=email&query=refund` lists market-scoped canned responses. Channel filtering includes channel-specific macros and macros available to all channels.
- `POST /macros` and `PATCH /macros/{macro_id}` are supervisor/admin-managed catalog endpoints.
- `GET /tickets/{ticket_id}/macro-suggestions?limit=3` returns ranked macro suggestions with response shape `[{ macro, score, reasons, matched_terms }]`.
- `POST /macros/{macro_id}/use?ticket_id={ticket_id}` records agent usage, increments `usage_count`, sets `last_used_at`, and writes `response_macro.use` audit history.
- `GET /tickets/{ticket_id}` and `GET /frontend/snapshot` include `macro_suggestions` in each ticket context, and `/frontend/snapshot` includes the full `macros` catalog for the composer dropdown.

Duplicate ticket guard:

- `GET /tickets/{ticket_id}/duplicate-suggestions?limit=5` returns ranked likely duplicate tickets in the authenticated market with response shape `[{ ticket, customer, score, reasons, matched_terms }]`.
- Scoring considers same customer/contact, same company, booking/transaction/reference fields, subject/body term overlap, shared labels, channel, and near-term creation windows. Linked handoff child tickets and already-merged source tickets are excluded.
- `GET /tickets/{ticket_id}` and `GET /frontend/snapshot` include `duplicate_suggestions` in each ticket context so the Work Queue properties panel can surface merge candidates without a separate request.
- `POST /tickets/{ticket_id}/merge` accepts `{ source_ticket_id, reason, actor?, close_source? }`, writes internal merge notes to both tickets, carries recent source comments/notes and attachment metadata into the target note, marks the source with `merged_into_ticket_id` / `merged_into_public_id`, optionally closes the source, updates target `merged_source_ticket_ids`, and writes `ticket.merge` audit history.

Supervisor recommendations:

- `GET /operations/recommendations?limit=8` is supervisor/admin-only and returns live manager actions derived from current market tickets, handoffs, SLA state, support groups, and agent capacity.
- The response shape is `[{ id, market_id, title, summary, action, severity, category, priority_score, ticket_id, handoff_id, support_group, owner_id, reasons, created_at }]`.
- Current categories include `handoff_blocker`, `handoff_due`, `queue_pressure`, and `reassignment`.
- `GET /frontend/snapshot` includes `supervisor_recommendations` for users with `supervisor.control`; agent snapshots receive an empty list.
- The Command Center Manager Actions panel uses these backend-ranked recommendations when present and falls back to seeded review actions only when no recommendation payload exists.

Global search:

- `GET /search?q={query}&limit=12` returns market-scoped results across tickets, customers, companies, knowledge articles, support groups, handoffs, and agents.
- The response shape is `[{ id, type, title, subtitle, description, score, screen, entity_id, metadata }]`. `screen` lets the frontend route a result to Work Queue, Customer 360, Answers, Setup, Team Handoffs, or Staffing.
- Results are scored by exact, prefix, and contained matches against operational fields such as ticket public ID, subject, customer email, company, team inbox, article text, handoff reason, and agent identity.

Support groups:

- `GET /support-groups` lists market-scoped routing groups with live `member_count`, `open_ticket_count`, and `sla_risk_count` derived from agents and tickets. `GET /groups` is a compatibility alias.
- `POST /support-groups` creates an admin-managed group with `name`, optional `description`, optional `team_email`, `active`, `channels`, and `skills`.
- `PATCH /support-groups/{group_id}` updates group metadata, team inbox, and active state. Renaming a group also retargets existing agent team labels, ticket team ownership, and handoff source/receiving team labels in the same market.
- Group names are unique per market and group writes create `support_group.create` / `support_group.update` audit events.
- `GET /frontend/snapshot` includes `support_groups`, and the frontend uses those groups for Setup ownership cards and handoff receiving-team choices.
- When a handoff is requested for an active support group with `team_email`, the backend queues an email outbound message with `payload.source=handoff_forward`. The message includes ticket, customer, company, custom field, recent comment/note, attachment, SLA, and handoff details; clean active attachments are included as signed download links, while blocked/deleted attachments are listed without links. Timeline metadata and audit records link the handoff to the queued message and `attachment.handoff_link.create` records.
- Handoff creation also creates a linked internal ticket assigned to the receiving team. `POST /tickets/{ticket_id}/handoffs`, `GET /handoffs`, and ticket contexts expose `linked_ticket_id`; the source timeline stores `linked_ticket_id` and `linked_ticket_public_id`, while the child ticket stores `custom_fields.linked_ticket_type=handoff_child`, `source_ticket_id`, and `handoff_id` with the same full case context in its private timeline.
- Handoff-forward SMTP messages carry `X-Omni-Handoff-ID`, source-ticket, linked-ticket, and reply-target headers. IMAP replies that reference the outbound `Message-ID`, contain Omni thread headers, or preserve a ticket public ID are appended to the existing ticket thread instead of opening a duplicate ticket. For handoff forwards, team replies append privately to the linked internal ticket and add an internal note on the source ticket.

SLA policies:

- `GET /sla-policies` lists market-scoped SLA policies ordered by active state, priority, `position`, and name.
- `POST /sla-policies` creates an admin-managed policy with `name`, `priority=low|normal|high|urgent`, optional `channels`, `first_response_minutes`, `resolution_minutes`, `business_hours`, `position`, and `active`.
- `PATCH /sla-policies/{policy_id}` updates policy metadata and active state. Policy names are unique per market.
- `POST /tickets` resolves the first active matching policy by market, priority, and channel when setting `sla.first_response_due_at` and `sla.resolution_due_at`; if no policy matches, the backend falls back to the default priority SLA.
- Priority naming note: the backend stores `normal`, while the frontend labels that priority as `medium`.
- `GET /frontend/snapshot` includes `sla_policies`, and Setup exposes the catalog under Automation > SLA policies. Writes create `sla_policy.create` / `sla_policy.update` audit events.

Ticket fields:

- `GET /ticket-fields?active_only=true&channel=whatsapp` lists market-scoped custom ticket fields ordered by `position` and label. Channel filtering includes fields available to all channels and fields explicitly assigned to the requested channel.
- `POST /ticket-fields` creates an admin-managed field with `key`, `label`, `field_type`, optional `options`, optional `channel_ids`, `required`, `active`, and `position`.
- `PATCH /ticket-fields/{field_id}` updates field metadata and active/required state. Field keys remain immutable once created.
- Supported field types are `text`, `textarea`, `select`, `multiselect`, `checkbox`, `number`, and `date`.
- `POST /tickets` and `PATCH /tickets/{ticket_id}` accept `custom_fields`. Required active fields applying to the ticket channel are enforced, select/multiselect values are normalized against configured options, checkboxes are stored as booleans, numbers as numbers, and dates as ISO dates.
- Tickets and ticket contexts return `custom_fields`, and `GET /frontend/snapshot` includes `ticket_fields` so the frontend can render the Setup field builder, quick ticket form, and ticket property panel without extra reads.

Public customer portal:

- `GET /portal/{market_code}/answers?q=payment&limit=5` is unauthenticated and returns customer-safe published answers plus active portal ticket fields for the market. The response shape is `{ market_id, market_code, query, suggestions, ticket_fields }`.
- Public answer suggestions expose only `article_id`, `title`, `body`, `language`, `tags`, `score`, `reasons`, `matched_terms`, and `updated_at`. Draft/review/private article state is not exposed.
- `POST /portal/{market_code}/tickets` is unauthenticated and creates or reuses the portal customer, persists portal contact points, validates active portal ticket fields, creates a normal backend ticket with `channel=portal`, writes `ticket.create` audit history with `actor=customer-portal`, and returns `{ ticket_id, public_id, status, priority, created_at, article_suggestions }`.
- Portal submissions accept `name`, `email`, optional `phone`, `subject`, `description`, optional `priority=low|normal|high|urgent`, `custom_fields`, and optional `search_query`.
- `GET /portal/{market_code}/tickets/{public_id}?email={customer_email}` is unauthenticated and returns customer-safe ticket metadata, customer-facing status, next step, public timeline events only, and customer-safe answer suggestions. Ticket ownership is checked by public ticket ID plus requester email; wrong email returns the same `404 Ticket not found` response as an unknown ticket.
- `POST /portal/{market_code}/tickets/{public_id}/reply` accepts `{ email, body }`, verifies the same public ID/email ownership pair, adds a public portal inbound timeline event, writes `ticket.portal_reply` audit history, and moves the ticket back to `open` when the previous status was `pending`, `waiting`, `solved`, or `closed`.
- `POST /portal/{market_code}/tickets/{public_id}/attachments?email={customer_email}&filename={filename}` accepts a raw file body from the verified ticket requester. Clean files are scanned, stored, attached to the ticket, and shown in portal ticket detail as sanitized metadata; blocked files are retained as metadata only. The response does not expose storage keys.
- Portal routes use the client IP, market, public ID, and submitted email for fixed-window rate limiting. Runtime settings: `OMNI_PORTAL_RATE_LIMIT_ATTEMPTS` and `OMNI_PORTAL_RATE_LIMIT_WINDOW_SECONDS`.
- The frontend public route is `/?screen=portal`. It does not require staff login and uses the same API base URL as the authenticated SPA.

Production list controls:

- `GET /customers` supports optional `q`, `sentiment`, `company_id`, `sort_by=name|email|sentiment|created_at|updated_at`, `sort_order=asc|desc`, `limit`, and `offset`.
- `GET /tickets` supports optional `q`, `status`, `channel`, `priority`, `customer_id`, `assignee_id`, `team`, `sort_by=updated_at|created_at|public_id|subject|status|priority|channel`, `sort_order=asc|desc`, `limit`, and `offset`.
- List responses remain JSON arrays for existing clients. Production metadata is returned in `X-Total-Count`, `X-Returned-Count`, `X-Limit`, `X-Offset`, and `X-Sort` headers.
- All list queries remain scoped to the authenticated `X-Omni-Market`.

Optimistic concurrency:

- `POST /companies`, `PATCH /companies/{company_id}`, `POST /customers`, `GET /customers/{customer_id}`, `PATCH /customers/{customer_id}`, `POST /tickets`, `GET /tickets/{ticket_id}`, and `PATCH /tickets/{ticket_id}` return an `ETag` header derived from the resource update timestamp.
- Clients can send `If-Match: <etag>` on company, customer, and ticket `PATCH` requests. If the resource changed since that ETag was issued, the API returns `412 Precondition Failed` with `Resource has changed; refresh before retrying.`
- `If-Match` is optional so existing frontend write-through calls continue to work; production clients should use it for edit forms and bulk/admin workflows.

Attachments:

- `GET /tickets/{ticket_id}/attachments`
- `POST /tickets/{ticket_id}/attachments`
- `POST /tickets/{ticket_id}/attachments/binary`
- `DELETE /tickets/{ticket_id}/attachments/{attachment_id}`
- `POST /tickets/{ticket_id}/attachments/{attachment_id}/download-link`
- `GET /tickets/{ticket_id}/attachments/{attachment_id}/download`
- `GET /tickets/{ticket_id}/attachments/{attachment_id}/download/signed`
- `GET /attachments/provider-config`
- `GET /attachments/retention`
- `POST /attachments/retention/prune`

Attachment governance:

- Attachments now carry `lifecycle_status=active|deleted|purged`, `retained_until`, deletion metadata, and `purged_at`.
- `DELETE /tickets/{ticket_id}/attachments/{attachment_id}` is supervisor/admin-only. It marks metadata deleted and can immediately purge stored bytes with `{"purge_storage": true}`.
- Downloads and signed links only serve `active` and `clean` attachments; deleted or purged metadata remains visible for audit/history but cannot be downloaded.
- Signed download links include an expiring HMAC token with market, ticket, attachment, token ID, and creator identity. Link creation and signed download audit events carry the same token ID, and download responses set no-store/nosniff headers.
- Handoff-forward emails use the same signed download path for clean active attachments. `OMNI_PUBLIC_APP_URL` controls the absolute URL used in email bodies, and `OMNI_HANDOFF_ATTACHMENT_DOWNLOAD_TTL_MINUTES` controls the handoff email link lifetime.
- `GET /attachments/provider-config` is supervisor/admin-only and returns sanitized storage/scanner readiness. It never exposes S3 access keys, scanner tokens, bucket secrets, or scanner endpoint secrets.
- `OMNI_ATTACHMENT_STORAGE_BACKEND=s3` enables S3-compatible object storage through `OMNI_ATTACHMENT_S3_*`; the default `local` backend remains active for the isolated VM/demo path.
- `OMNI_ATTACHMENT_SCANNER_ADAPTER=http` enables an external scanner service for binary uploads. Binary uploads are scanned before bytes are persisted; blocked or failed scans create audit-visible metadata but do not write the binary into storage.
- `GET /attachments/retention` returns configured active/deleted retention windows, cutoff dates, active/deleted/purged counts, purgeable count, and prune limit for the authenticated market.
- `POST /attachments/retention/prune` is admin-only. It purges stored bytes for active/deleted attachments past policy and records `attachment.retention_prune`; the worker also runs this policy as `attachment_retention`.

Knowledge, automation, analytics, and audit:

- `GET /knowledge`
- `POST /knowledge`
- `PATCH /knowledge/{article_id}`
- `GET /macros`
- `POST /macros`
- `PATCH /macros/{macro_id}`
- `POST /macros/{macro_id}/use`
- `GET /automation-rules`
- `POST /automation-rules`
- `PATCH /automation-rules/{rule_id}`
- `GET /analytics/summary`
- `GET /analytics/overview`
- `GET /analytics/rollups`
- `GET /alerts`
- `GET /alerts/deliveries`
- `GET /alerts/delivery-config`
- `PATCH /alerts/{alert_id}`
- `GET /audit`
- `GET /audit/export`
- `GET /audit/retention`
- `POST /audit/retention/prune`
- `GET /tracker`

Audit governance:

- `GET /audit` accepts optional `actor`, `action`, `entity_type`, `entity_id`, `since`, `until`, and `limit` filters. Results are scoped to global audit events plus the authenticated market.
- `GET /audit/export?format=csv|json` returns filtered audit rows for audit readers. Each export writes an `audit.export` audit event after selecting rows.
- `GET /audit/retention` returns the active `OMNI_AUDIT_RETENTION_DAYS` cutoff, prunable count, retained count, and `OMNI_AUDIT_EXPORT_MAX_ROWS`.
- `POST /audit/retention/prune` is admin-only. It removes global/current-market audit rows older than the configured cutoff, records `audit.retention_prune`, and the worker also runs the same pruning path as `worker.audit_retention`.

Operational alerts:

- `GET /alerts` and `PATCH /alerts/{alert_id}` are supervisor/admin routes.
- `GET /alerts/deliveries` returns external alert delivery attempts for the current market.
- `GET /alerts/delivery-config` returns sanitized delivery configuration status. It never returns webhook URLs or secrets.
- `GET /frontend/snapshot` includes `operational_alerts`, `alert_deliveries`, and real `alert_delivery_config` only for supervisors/admins; agent, auditor, and service-account snapshots return empty alert/delivery lists with neutral config.
- Supported alert statuses: `open`, `acknowledged`, `resolved`.
- Current alert sources include outbound delivery failures, dead-lettered messages, worker exceptions, and SLA supervisor notifications.
- External webhook delivery is inactive until an admin saves an alert webhook URL in Setup -> Connectors -> Production credentials, or `OMNI_ALERT_WEBHOOK_URL` is set as a runtime fallback. Optional signing uses a write-only saved secret or `OMNI_ALERT_WEBHOOK_SECRET`; webhook requests include `X-Omni-Alert-Timestamp` and, when configured, `X-Omni-Alert-Signature`.

Connectors and provider webhooks:

- `GET /connectors/providers`
- `GET /connectors/accounts`
- `POST /connectors/accounts`
- `PATCH /connectors/accounts/{account_id}`
- `GET /connectors/events`
- `POST /connectors/inbound`
- `POST /webhooks/{provider}/{market_code}`
- `GET /inbound/provider-config`
- `GET /outbound/messages`
- `GET /outbound/provider-config`
- `POST /outbound/messages/{message_id}/retry`
- `GET /integration-credentials/settings`
- `PATCH /integration-credentials/settings`
- `GET /production/account-requests`
- `POST /production/account-requests/email`
- `GET /production/account-references`
- `POST /production/account-references`
- `PATCH /production/account-references/{reference_id}`
- `GET /production/account-references/docs`
- `GET /production/readiness-checklist`

`GET /integration-credentials/settings` returns sanitized market production credentials for supervisors/admins. `PATCH /integration-credentials/settings` is admin-only and saves AI, alert webhook, SMS, voice, WhatsApp, Facebook, and Instagram credentials. Secret inputs are write-only; responses expose only `*_configured` booleans.
`GET /production/account-requests` returns a sanitized provider activation pack for `gbolahans@wakanow.com`, including missing account fields, callback URLs, setup locations, credential reference names, and a mailto-ready request body. It does not expose raw passwords, API keys, access tokens, private keys, or webhook secrets.
`POST /production/account-requests/email` is admin-only and queues the sanitized activation pack to `gbolahans@wakanow.com` through the durable email outbound queue. The backend creates a searchable internal production-readiness ticket, attaches the pack as an internal timeline note, records audit history, and returns the queued outbound message. The endpoint is idempotent for the current pack fingerprint, so repeat clicks return the already queued message instead of creating duplicates.
`GET/POST/PATCH /production/account-references` tracks non-secret provider account metadata after accounts are requested or provisioned. References include provider, area, account name, external account identifier, status, owner email, credential reference, API_DOCS reference, callback URLs, and notes. Admins mutate references; supervisors/admins can read them.
`GET /production/account-references/docs` returns a Markdown table snippet operators can copy into this file. It never contains raw provider secrets unless an operator manually enters a secret-like value into a non-secret reference field, which is not allowed by operating policy.
`GET /production/readiness-checklist` returns a supervisor/admin launch gate that combines live migration state, queued account-request email evidence, non-secret account references, secret-hygiene checks, provider credential readiness, storage/scanner readiness, SSO readiness, alert delivery readiness, and observability next actions. It is intentionally sanitized and never returns raw credentials.

## Signed Provider Webhooks

External providers should call:

```http
POST /api/v1/webhooks/{provider}/{market_code}
```

Required headers:

- `X-Omni-Timestamp`: Unix timestamp within the configured tolerance.
- `X-Omni-Signature`: `sha256=<hmac>` over `{timestamp}.{raw_body}`.
- `X-Omni-Delivery`: provider delivery identifier for replay protection.

The connector account must be enabled, webhook-verified, and configured with a secret reference before provider webhooks are accepted.

### SMS Provider Callbacks

- Signed SMS webhooks now support inbound text payloads and outbound delivery receipts on `POST /api/v1/webhooks/sms/{market_code}`.
- Inbound SMS payloads can use `event_type=inbound_message`, `from`, `text` or `body`, and `message_id`; the backend creates/reuses an SMS customer contact point and opens a ticket through the shared connector intake path.
- Delivery receipts can use `event_type=delivery_receipt`, `status`, and one of `outbound_message_id`, `idempotency_key`, or provider `message_id`; the backend updates the durable outbound message payload, writes a connector receipt timeline event, records a connector event for replay protection, and writes `outbound.delivery_receipt` audit history.
- SMS webhook secrets belong in the runtime secret store or provider dashboard. Track only the credential reference here.

### WhatsApp Business Callbacks

- Signed WhatsApp webhooks now support Meta Cloud API-shaped inbound message and status payloads on `POST /api/v1/webhooks/whatsapp/{market_code}`.
- Inbound message payloads can use nested `entry[].changes[].value.messages[]` with `from`, `id`, `type=text`, and `text.body`; the backend creates/reuses a WhatsApp customer contact point and opens a ticket through the shared connector intake path.
- Status receipts can use nested `entry[].changes[].value.statuses[]` with `id` and `status`; the backend matches the provider `wamid` to the durable outbound message, updates the payload, writes a connector receipt timeline event, records a connector event for replay protection, and writes `outbound.delivery_receipt` audit history.
- WhatsApp webhook secrets and Meta access tokens belong in the runtime secret store or provider dashboard. Track only the credential reference here.

### Facebook Messenger Callbacks

- Signed Facebook Messenger webhooks now support Meta page-shaped inbound message, postback, delivery, and read payloads on `POST /api/v1/webhooks/facebook/{market_code}`.
- Inbound payloads can use `object=page` with nested `entry[].messaging[]`, `sender.id`, `recipient.id`, and either `message.mid`/`message.text` or `postback.title`/`postback.payload`; the backend creates/reuses a Facebook customer contact point and opens a ticket through the shared connector intake path.
- Delivery receipts can use nested `entry[].messaging[].delivery.mids[]`; the backend matches the provider message ID to the durable outbound message, updates the payload, writes a connector receipt timeline event, records a connector event for replay protection, and writes `outbound.delivery_receipt` audit history.
- Facebook page access tokens and webhook secrets belong in the runtime secret store or provider dashboard. Track only the credential reference here.

### Instagram DM Callbacks

- Signed Instagram DM webhooks now support Meta Instagram-shaped inbound message, postback, delivery, and read payloads on `POST /api/v1/webhooks/instagram/{market_code}`.
- Inbound payloads can use `object=instagram` with nested `entry[].messaging[]`, `sender.id`, `recipient.id`, and either `message.mid`/`message.text` or `postback.title`/`postback.payload`; the backend creates/reuses an Instagram customer contact point and opens a ticket through the shared connector intake path.
- Delivery/read receipts can use nested `entry[].messaging[].delivery.mids[]`, `read.mid`, `seen.mid`, or flat receipt payloads; the backend matches the provider message ID to the durable outbound message, updates the payload, writes a connector receipt timeline event, records a connector event for replay protection, and writes `outbound.delivery_receipt` audit history.
- Instagram access tokens and webhook secrets belong in the runtime secret store or provider dashboard. Track only the credential reference here.

### Voice Provider Callbacks

- Signed voice webhooks now support provider-shaped callback requests, call logs, missed calls, voicemail summaries, and outbound call-status receipts on `POST /api/v1/webhooks/voice/{market_code}`.
- Inbound voice payloads can use `event_type=callback_request`, `inbound_call`, `call_log`, `missed_call`, or `voicemail` with `call_id`, `from`, `caller_name`, `summary`, `transcript`, `recording_url`, and duration fields; the backend creates/reuses a voice customer contact point and opens a ticket through the shared connector intake path.
- Call-status receipts can use `event_type=call_status`, `status`, and one of `outbound_message_id`, `idempotency_key`, or provider `call_id`; the backend updates the durable outbound message payload, writes a connector receipt timeline event, records a connector event for replay protection, and writes `outbound.delivery_receipt` audit history.
- Voice API tokens, caller IDs, recording access policies, and webhook secrets belong in the runtime secret store or provider dashboard. Track only the credential reference here.

## Inbound Email Intake

- Email inbound now has an IMAP polling adapter. The worker polls unread messages when market email settings have inbound enabled plus IMAP host, username, and password. Runtime env values (`OMNI_EMAIL_IMAP_*`) remain a fallback when no market settings record exists.
- `GET /email/settings` and `PATCH /email/settings` let supervisors/admins read sanitized mailbox setup and let admins save IMAP/SMTP settings from Setup. Passwords are write-only: the API returns only `*_password_configured` booleans.
- `GET /inbound/provider-config` shows sanitized inbound-adapter readiness for supervisors/admins. It does not expose IMAP passwords or provider secrets.
- Polled email messages are converted into the existing connector intake path, so customer creation/reuse, ticket creation, connector events, automation, timeline receipts, idempotency, audit history, and worker alerts remain shared with other provider intake.
- IMAP attachments are scanned through the existing attachment policy before persistence. Clean attachments are stored on the ticket and can be downloaded through the normal attachment path; blocked attachments are retained as blocked metadata with no stored bytes. Duplicate IMAP events do not duplicate attachment records.
- Customer replies that preserve an Omni outbound `Message-ID`, Omni thread headers, or a ticket public ID in the subject append to the existing ticket instead of creating a duplicate case. Public customer replies reopen non-open tickets, add `customer-replied` and `thread-reply` tags, and write connector/audit history. Handoff team replies stay private on the linked internal team ticket and add a source-ticket note.
- The adapter uses Message-ID when present, otherwise `imap:{mailbox}:{uid}`, as the connector external id. `OMNI_EMAIL_IMAP_MARK_SEEN=true` marks processed messages seen after successful ingestion.
- IMAP secret values can be saved through Setup for the current isolated VM path. Move them into managed secret storage when that service is selected.

## Outbound Provider Delivery

- Public replies are queued durably before provider dispatch.
- Email outbound now has a production SMTP adapter. It activates when market email settings have outbound enabled plus SMTP host, or falls back to `OMNI_EMAIL_SMTP_HOST` when no saved market settings exist. The default sender remains `jimb@wakanow.com`.
- Handoff forwards use the same durable email queue but send to the receiving support group's `team_email` instead of the requester customer.
- WhatsApp outbound now has a configurable Cloud API adapter. It activates when the current market has saved WhatsApp phone-number ID/access token settings, or runtime `OMNI_WHATSAPP_*` fallback values exist, sends text replies to the customer's WhatsApp contact point through `/{Phone-Number-ID}/messages`, and records provider `wamid` status payloads without returning the access token. Delivery receipts return through the signed WhatsApp webhook path above.
- Facebook Messenger outbound now has a configurable Graph API adapter. It activates when the current market has saved Facebook page ID/page-token settings, or runtime `OMNI_FACEBOOK_*` fallback values exist, sends text replies to the customer's Facebook PSID contact point through `/{Page-ID}/messages`, and records provider message IDs/status payloads without returning the page token. Delivery receipts return through the signed Facebook webhook path above.
- Instagram DM outbound now has a configurable Graph API adapter. It activates when the current market has saved Instagram business-account ID/access-token settings, or runtime `OMNI_INSTAGRAM_*` fallback values exist, sends text replies to the customer's Instagram-scoped user ID through `/{IG-User-ID}/messages`, and records provider message IDs/status payloads without returning the access token. Delivery receipts return through the signed Instagram webhook path above.
- SMS outbound now has a configurable HTTP provider adapter. It activates when the current market has saved SMS endpoint/token/sender settings, or runtime `OMNI_SMS_HTTP_*` fallback values exist, sends customer SMS contact-point replies through the durable outbound queue, and records provider message IDs/status payloads without returning the API token. Delivery receipts return through the signed SMS webhook path above.
- Voice outbound now has a configurable HTTP provider adapter. It activates when the current market has saved voice endpoint/token/caller-ID settings, or runtime `OMNI_VOICE_HTTP_*` fallback values exist, sends callback-request payloads for customer voice contact points through the durable outbound queue, and records provider call IDs/status payloads without returning the API token. Call-status receipts return through the signed voice webhook path above.
- `GET /outbound/provider-config` shows sanitized provider-adapter readiness for supervisors/admins. It does not expose SMTP passwords or webhook secrets.
- `OMNI_OUTBOUND_LOCAL_ADAPTER_ENABLED` keeps the local-dev adapter available for demo/pulse operation. Set it to `false` in staging/production after live provider adapters are configured.
- SMTP, WhatsApp, Facebook, Instagram, SMS, voice, alert, and Anthropic secret values are accepted only as write-only admin settings or runtime fallbacks. Do not commit them to git.

## Analytics And Dashboards

- `GET /analytics/summary` and `GET /analytics/overview` return the current live market snapshot.
- `GET /analytics/rollups?limit=24` returns recent durable hourly rollups written by the worker.
- `/frontend/snapshot` includes `analytics_rollups` and `csat_feedback` so the Insights screen can render persisted backend dashboard history and recent customer ratings without an additional request.

## CSAT Feedback

- `POST /tickets/{ticket_id}/csat` records one market-scoped satisfaction record per ticket. Ratings are integers from `1` to `5`; posting again updates the existing ticket feedback.
- `GET /csat/feedback?ticket_id={ticket_id}&limit=100` lists recent feedback for supervisors/admins, optionally filtered to a ticket.
- CSAT submissions add a ticket timeline note, write audit events for `csat.create` or `csat.update`, and feed `avg_csat` in `GET /analytics/summary` plus worker-written analytics rollups.

## Retention Runtime Settings

- `OMNI_ATTACHMENT_STORAGE_BACKEND` controls attachment storage. Use `local` for VM/demo or `s3` for managed object storage.
- `OMNI_ATTACHMENT_S3_BUCKET`, `OMNI_ATTACHMENT_S3_PREFIX`, `OMNI_ATTACHMENT_S3_REGION`, `OMNI_ATTACHMENT_S3_ENDPOINT_URL`, `OMNI_ATTACHMENT_S3_ACCESS_KEY_ID`, `OMNI_ATTACHMENT_S3_SECRET_ACCESS_KEY`, and `OMNI_ATTACHMENT_S3_SERVER_SIDE_ENCRYPTION` configure the S3-compatible storage adapter.
- `OMNI_ATTACHMENT_SCANNER_ADAPTER` controls scan mode. Use `local` for metadata policy scanning or `http` for an external malware scanning service.
- `OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT`, `OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_TOKEN`, `OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_HEADER`, `OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_SCHEME`, and `OMNI_ATTACHMENT_SCANNER_HTTP_TIMEOUT_SECONDS` configure the HTTP scanner adapter.
- `OMNI_ATTACHMENT_RETENTION_DAYS` controls active attachment retention before purge eligibility. Default: `365`.
- `OMNI_ATTACHMENT_DELETED_RETENTION_DAYS` controls how long deleted attachment metadata/bytes stay recoverable before purge eligibility. Default: `30`.
- `OMNI_ATTACHMENT_RETENTION_PRUNE_LIMIT` caps one prune pass. Default: `250`.
- `OMNI_AUDIT_RETENTION_DAYS` and `OMNI_AUDIT_EXPORT_MAX_ROWS` continue to govern audit retention and export size.

## External Accounts Needed

When account details are available, email them to `gbolahans@wakanow.com` and add the non-secret tracking reference to this file. Do not commit raw passwords, access tokens, private keys, app secrets, OAuth client secrets, webhook secrets, or API keys.

Admins and supervisors can call `GET /api/v1/production/account-requests` or use Setup -> Connectors -> Account requests to generate the current action list and email draft for `gbolahans@wakanow.com`. Admins can also queue the same sanitized pack through `POST /api/v1/production/account-requests/email`; delivery uses the existing outbound email queue and will send through SMTP once the mailbox credentials are configured.

Admins can record non-secret provisioned account metadata in Setup -> Connectors -> Account references or through `POST /api/v1/production/account-references`. Use `GET /api/v1/production/account-references/docs` to generate a copy-ready Markdown table for the account reference subsection below. Store only account IDs, provider names, owner emails, callback URLs, docs anchors, and secret-location references such as `vault://...`; never store raw passwords, API keys, access tokens, private keys, app secrets, OAuth client secrets, or webhook secrets.

Use `GET /api/v1/production/readiness-checklist` or Setup -> Connectors -> Production readiness as the launch gate. Treat `blocked` items as external-account or runtime-configuration dependencies, and keep this file updated with non-secret references as each account is provisioned.

| Area | Account Or Credential Needed | Backend Use | Status |
| --- | --- | --- | --- |
| Email inbound/outbound | Mailbox provider, OAuth app or IMAP/SMTP/API credentials for `jimb@wakanow.com`, sender identity, webhook/callback URL | Email tickets, replies, attachments, delivery state | Started; IMAP inbound and SMTP outbound adapters built, Setup can save mailbox settings, provider credentials pending |
| WhatsApp Business | Meta Business Manager, WhatsApp Business Account, phone number ID, Cloud API access token, templates, webhook secret | WhatsApp intake, replies, media, receipts | Started; Cloud API text outbound plus signed inbound/status callbacks built, Meta credentials pending |
| Facebook Messenger | Meta app, Facebook page ID, page access token with `pages_messaging`, page webhook subscription, app/webhook secret | Messenger intake, replies, private reply flow | Started; Graph API text outbound plus signed inbound/delivery callbacks built, Meta page credentials pending |
| Instagram DM | Meta app, Instagram professional account ID, Instagram access token with messaging permissions, webhook subscription, app/webhook secret | Instagram DM intake, replies, receipts, media | Started; Graph API text outbound plus signed inbound/read callbacks built, Meta Instagram credentials pending |
| SMS | SMS provider account, sender ID, HTTP send endpoint, API token, webhook signing secret | SMS outbound through HTTP adapter, inbound texts, delivery receipts | Started; outbound HTTP adapter plus signed inbound/receipt callbacks built, provider credentials pending |
| Voice | Voice/telephony provider account, HTTP callback endpoint, API token, caller ID, webhook signing secret, recording access policy | Voice call logs, callbacks, voicemail summaries, call-status receipts | Started; outbound HTTP callback adapter plus signed inbound/status callbacks built, provider credentials pending |
| Anthropic AI | Anthropic API key in `AI_Key` or `OMNI_ANTHROPIC_API_KEY`, model access for `OMNI_ANTHROPIC_MODEL` | Production AI summaries, recommended next actions, decision model metadata | Active on isolated Omni VM; Anthropic Messages adapter live-smoked against `claude-sonnet-4-6`, managed secret storage pending |
| Identity | SSO/OIDC provider, OAuth/OIDC client, redirect URLs, future enterprise lifecycle hooks | Production login, user lifecycle, external identity federation | Started; OIDC PKCE boundary, one-time callback state, existing-user linking, guarded provisioning, local TOTP MFA, and custom permission profiles are built; external SSO/OIDC client credentials pending |
| Object storage | S3-compatible bucket, access policy, KMS/encryption config, optional endpoint URL, credential reference | Production attachment storage | Started; S3-compatible adapter and sanitized readiness are built, managed bucket credentials pending |
| Malware scanning | Antivirus/scanning provider or scanning service endpoint plus optional auth token reference | Attachment clearance before storage/download | Started; HTTP scanner adapter and pre-storage block path are built, scanning provider account pending |
| Observability | Log drain/APM/alerting destination, optional alert webhook URL, optional alert webhook signing secret | API, worker, SLA, connector, and queue alerts | Started; durable alert delivery is built, external destination pending |

## Account Detail Intake Format

Use this shape when adding non-secret account references to this file:

```text
Provider:
Purpose:
Market(s):
Account owner:
Credential reference name:
Webhook URL:
Callback/redirect URL:
Secret storage location:
Operational notes:
```

Secrets should live in the VM runtime environment, a future secret manager, the provider dashboard, or the backend database for user-specific MFA shared secrets until managed secret storage is provisioned. This file should only contain enough metadata for operators and engineers to know which account is connected and where the real secret is stored.

## Current Production Verification

Latest public smoke checks:

```bash
curl -fsSI https://omni.wakanow.com/
curl -fsS https://omni.wakanow.com/api/v1/health
```

Expected API health response:

```json
{"status":"ok"}
```
