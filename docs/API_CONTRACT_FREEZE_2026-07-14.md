# Omni Primary Contract Freeze

**Freeze date:** 2026-07-14

**Schema revision:** `20260714_0054`

**OpenAPI artifact:** `frontend/src/api/openapi.json`
**SHA-256:** `92930aec95b6aa24d09d4278dcf77ff939eabc67a83848b7dd647053435d6a90`

## Purpose

This freeze is the branch point between the primary product implementation and the
separate live-data migration workstream. It covers the canonical customer case, customer
identity, ticket, conversation, participant, assignment, message, receipt, attachment,
topic, saved-view, feature-capability, and ticket-workspace contracts.

The primary workstream may continue to add backward-compatible product APIs. Any breaking
change to a frozen aggregate requires a new Alembic revision, regenerated OpenAPI artifact,
an updated checksum in this document, and a migration adapter compatibility test.

## Frozen Interfaces

- `/api/v1/conversations` and cursor-paginated conversation list, search, and filtering
- `/api/v1/conversation-views` and `/api/v1/conversation-topics`
- conversation messages, assignment, status, receipts, context, and linked-ticket resources
- `/api/v1/tickets/{id}/workspace`
- `/api/v1/ticket-views` and ticket queue search, customer, age, tag, assignment, group,
  status, priority, source, sorting, and pagination filters
- version-aware ticket and conversation mutations
- `/api/v1/realtime` conversation lifecycle events
- authenticated feature-capability responses and rollout flags

The generated TypeScript definitions in `frontend/src/api/schema.d.ts` are part of the
published contract and must be regenerated from the same OpenAPI artifact.

## Migration Ownership

The migration workstream branches from this revision and owns import artifacts, jobs,
manifests, reconciliation evidence, incremental cursors, final-delta approval, cutover,
and rollback endpoints. It must use isolated staging storage and may not import live
Freshworks data into a developer database.

Migration validation must reconcile counts, source IDs, timestamps, authorship, identity
links, attachments, transcripts, ticket links, and the one-active-case-per-customer-and-
market constraint. Missing Freshworks credentials, exports, or provider limitations block
migration cutover only; they do not block the primary product workstream.

## Current Evidence

- Alembic reports `20260714_0054 (head)` on the local validation database.
- The OpenAPI artifact checksum above was verified after route generation.
- Backend domain, RBAC, realtime, failure, and migration-fixture tests pass with synthetic
  data.
- No live Wakanow Freshdesk or Freshchat tenant data was imported during this freeze.
