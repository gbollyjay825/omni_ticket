# Freshworks migration

The importer uses a full historical export followed by incremental API sync. This is
deliberate: Freshdesk caps a ticket list window at 30,000 records, and Freshchat does not
document an unfiltered tenant-wide user or conversation feed.

## Safety properties

- Run `alembic upgrade head` before any import.
- Every run is visible through `/api/v1/imports/runs` and stores source/next cursors.
- Source IDs map idempotently through `external_id_mappings`; repeated records are hashed.
- Files stream record by record and checkpoint by resource. JSON, JSONL/NDJSON, CSV, and
  gzip-compressed variants are supported.
- Dry runs validate and count all records inside a rolled-back savepoint.
- Bulk history suppresses per-record realtime events and emits one completion event.
- Active Freshdesk/Freshchat work for the same customer joins the customer's single active
  case. Closed history retains independent closed cases.
- Credentials come only from `OMNI_FRESHDESK_*` and `OMNI_FRESHCHAT_*` runtime variables.

## Sequence

```bash
cd backend
source .venv/bin/activate
alembic upgrade head

# Validate exports without retaining domain records.
python -m scripts.import_freshworks freshdesk-export --market-id market-ng \
  --contacts /secure/export/contacts.jsonl.gz \
  --tickets /secure/export/tickets.jsonl.gz \
  --conversations /secure/export/conversations.jsonl.gz --dry-run

python -m scripts.import_freshworks freshchat-export --market-id market-ng \
  --users /secure/export/users.jsonl.gz \
  --conversations /secure/export/conversations.jsonl.gz \
  --messages /secure/export/messages.jsonl.gz --dry-run

# Repeat without --dry-run after reconciliation succeeds.
# Then run the incremental deltas from the stored cursor.
python -m scripts.import_freshworks freshdesk-api --market-id market-ng
python -m scripts.import_freshworks freshchat-api --market-id market-ng \
  --user-ids-file /secure/export/freshchat-user-ids.json
```

The export rows must retain source `id` values. Freshdesk conversations must include
`ticket_id`; Freshchat conversations must identify their user, and messages must include
`conversation_id`. A mismatched reference stops the run instead of dropping data.

Before cutover, compare each provider/entity count from `/api/v1/imports/reconciliation`
with the source export, then sample timestamps, authorship, message ordering, and attachment
checksums. Attachment binary transfer remains a separate gated cutover step and must finish
before the migration can be declared reconciled.
