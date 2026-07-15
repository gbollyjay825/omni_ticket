# Pulse VM Deploy Runbook (omni.wakanow.com)

Authoritative, **observed** description of how Omni Ticket runs in production on the
`pulse-prod` VM, plus a reproducible release procedure. The architecture below was
captured by read-only inspection of the running VM on 2026-06-07; the helper scripts
(`infra/scripts/deploy-pulse.sh`, `infra/scripts/rollback-pulse.sh`) encode the same steps.

> The VM previously had **no committed deploy tooling** — releases were cut manually.
> This runbook + scripts close that gap. Review the scripts before first use.

## Topology

- **Host:** `pulse-prod` (SSH alias) — user `amechi`, GCP VM.
- **Public URL:** `https://omni.wakanow.com` (Nginx site `omni-ticket`, wildcard Wakanow TLS).
  - `/api/*` → `http://127.0.0.1:8090` (API)
  - everything else → `http://127.0.0.1:8088` (frontend static server)
- **Base dir:** `/home/amechi/omni-ticket/`
  - `releases/<ref>-<UTCstamp>/` — immutable release snapshots (not git checkouts)
  - `current` → symlink to the active release
  - `runtime/env.sh` — sourced by every process (contains DB URL, session secret, provider
    keys; **never commit or print its values**)
  - `attachments/`, `backups/`, `logs/`
- **Database:** local PostgreSQL `omni_ticket` (`OMNI_DATABASE_URL` in `runtime/env.sh`).
- **Runtimes (on VM):** Node `v22.x`, Python `3.14` (backend venv at
  `releases/<rel>/backend/.venv`).

## Process model (PM2, fork mode)

All three are `bash -lc` wrappers that `cd` into the current release, `source runtime/env.sh`,
and run from the release's own venv / node:

| PM2 process | Command (observed) | Port |
| --- | --- | --- |
| `omni-ticket-api` | `cd current/backend && source ../../runtime/env.sh && . .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8090` | 8090 |
| `omni-ticket-worker` | `cd current/backend && source ../../runtime/env.sh && . .venv/bin/activate && python -m app.worker --interval-seconds 60 --outbound-limit 50` | — |
| `omni-ticket-frontend` | `cd current && source ../runtime/env.sh && node infra/scripts/pulse-static-server.mjs` | 8088 |

The frontend static server (`infra/scripts/pulse-static-server.mjs`) serves `frontend/dist/` with SPA
fallback and proxies `/api/*` to `OMNI_API_PROXY_TARGET` (`127.0.0.1:8090`). It reads
`OMNI_FRONTEND_PORT` (8088) and `OMNI_FRONTEND_DIST` (default `frontend/dist`).

Guardrails: in staging/production the API/worker refuse to start unless
`OMNI_INITIALIZE_DATABASE=false`, `OMNI_DATABASE_URL` is non-SQLite, `OMNI_SESSION_SECRET`
is not the dev default, and `OMNI_ALLOWED_ORIGINS` is explicit (no `*`). See
`backend/docs/DEPLOYMENT.md`.

## Release procedure (what `infra/scripts/deploy-pulse.sh` automates)

Run on the VM. Given a git `REF` (branch/tag/sha):

1. **Snapshot** the ref into a new `releases/<ref>-<UTCstamp>/` (git export, `.git` stripped).
2. **Build frontend:** run `npm ci && VITE_OMNI_API_BASE_URL=/api/v1 npm run build` in
   `frontend/` to produce `frontend/dist/`,
   then drop `node_modules` to keep the release lean.
3. **Build backend venv:** `python3 -m venv .venv && .venv/bin/pip install -e .` in
   `backend/`.
4. **Carry secrets:** keep `AI_Key` in `/home/amechi/omni-ticket/runtime/AI_Key` and
   symlink it into each release backend (`OMNI_ANTHROPIC_API_KEY_FILE=AI_Key`).
   `runtime/env.sh` and all provider secrets are shared, protected runtime files.
5. **Migrate:** `source runtime/env.sh && .venv/bin/alembic upgrade head` (idempotent).
6. **Activate atomically:** `ln -sfn releases/<new> current`.
7. **Reload:** apply `infra/pm2/ecosystem.config.cjs` with `pm2 startOrReload`. The
   definition owns only `omni-ticket-api`, `omni-ticket-worker`, and
   `omni-ticket-frontend`; Pulse processes are not selected or modified.
8. **Health-gate:** curl `127.0.0.1:8090/api/v1/health` and `127.0.0.1:8088/`. On failure,
   **auto-rollback** (repoint `current` to the prior release, restart) and exit non-zero.
9. **Prune** old releases, keeping the most recent N (default 10).

### Invoke

```bash
# From a workstation with SSH access (recommended): stream the script to the VM.
ssh pulse-prod 'bash -s -- Claude' < infra/scripts/deploy-pulse.sh

# Or copy it once and run on the VM:
scp infra/scripts/deploy-pulse.sh pulse-prod:/home/amechi/omni-ticket/deploy-pulse.sh
ssh pulse-prod 'bash /home/amechi/omni-ticket/deploy-pulse.sh Claude'
```

`REPO_URL`, `BASE`, and `KEEP_RELEASES` can be overridden via env vars (see script header).

## Rollback

Releases are immutable, so rollback is just repointing the symlink:

```bash
# Roll back to the immediately previous release and restart:
ssh pulse-prod 'bash -s' < infra/scripts/rollback-pulse.sh

# Or to a specific release:
ssh pulse-prod 'bash -s -- claude-20260607085917' < infra/scripts/rollback-pulse.sh
```

## Verify

```bash
ssh pulse-prod 'curl -fsS http://127.0.0.1:8090/api/v1/health'        # {"status":"ok"}
ssh pulse-prod 'curl -fsSI http://127.0.0.1:8088/ | head -1'          # HTTP/1.1 200 OK
ssh pulse-prod 'pm2 status | grep omni-ticket'                        # all online
curl -fsS https://omni.wakanow.com/api/v1/health                     # public
```

Check the live release commit by inspecting a marker only present at the intended tip,
e.g. `grep -c C-110 /home/amechi/omni-ticket/current/docs/project-tracker.md`.
