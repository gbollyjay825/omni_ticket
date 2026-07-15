#!/usr/bin/env bash
#
# deploy-pulse.sh — release-snapshot deploy for the Omni Ticket Pulse VM.
#
# Reconstructed from the OBSERVED production release model on pulse-prod
# (omni.wakanow.com) as of 2026-06-07. It mirrors the running topology documented
# in docs/DEPLOY_RUNBOOK.md. Review before first production use.
#
# Runs ON the VM. Builds a new immutable release from a git ref, runs migrations,
# switches the `current` symlink atomically, restarts PM2, health-gates, and
# auto-rolls-back on failure.
#
# Usage:
#   bash deploy-pulse.sh <git-ref>            # e.g. Claude, main, v1.2.3, <sha>
#   ssh pulse-prod 'bash -s -- Claude' < infra/scripts/deploy-pulse.sh
#
# Overridable via env:
#   REPO_URL        git remote to fetch from        (default: origin of repo, see below)
#   BASE            deploy base dir                  (default: /home/amechi/omni-ticket)
#   KEEP_RELEASES   how many releases to retain      (default: 10)
#   API_PORT        backend health port             (default: 8090)
#   FRONTEND_PORT   frontend health port            (default: 8088)
#
set -euo pipefail

REF="${1:-Claude}"
BASE="${BASE:-/home/amechi/omni-ticket}"
REPO_URL="${REPO_URL:-https://github.com/gbollyjay825/omni_ticket.git}"
KEEP_RELEASES="${KEEP_RELEASES:-10}"
API_PORT="${API_PORT:-8090}"
FRONTEND_PORT="${FRONTEND_PORT:-8088}"

RELEASES_DIR="$BASE/releases"
CURRENT_LINK="$BASE/current"
ENV_FILE="$BASE/runtime/env.sh"
STAMP="$(date -u +%Y%m%d%H%M%S)"
SAFE_REF="${REF//[^A-Za-z0-9._-]/-}"
REL_DIR="$RELEASES_DIR/${SAFE_REF}-${STAMP}"

log() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "runtime env not found at $ENV_FILE"
command -v node >/dev/null || die "node not found on VM"
command -v npm  >/dev/null || die "npm not found on VM"
command -v python3 >/dev/null || die "python3 not found on VM"
command -v pm2  >/dev/null || die "pm2 not found on VM"

PREV_RELEASE=""
if [ -L "$CURRENT_LINK" ]; then PREV_RELEASE="$(readlink -f "$CURRENT_LINK")"; fi

log "Deploying ref '$REF' -> $REL_DIR (previous: ${PREV_RELEASE:-none})"

# 1) Snapshot the ref (shallow), strip .git to match the immutable-snapshot model.
mkdir -p "$RELEASES_DIR"
git clone --depth 1 --branch "$REF" "$REPO_URL" "$REL_DIR" \
  || die "git clone of ref '$REF' failed"
rm -rf "$REL_DIR/.git"

# 2) Build the frontend (same base URL Nginx expects), then drop node_modules.
log "Building frontend"
( cd "$REL_DIR/frontend" && npm ci && VITE_OMNI_API_BASE_URL=/api/v1 npm run build )
[ -d "$REL_DIR/frontend/dist" ] || die "frontend build produced no frontend/dist/"
rm -rf "$REL_DIR/frontend/node_modules"

# 3) Build the backend venv from pyproject.
log "Building backend venv"
BACKEND="$REL_DIR/backend"
( cd "$BACKEND" \
  && python3 -m venv .venv \
  && ./.venv/bin/pip install --upgrade pip \
  && ./.venv/bin/pip install -e . )

# 4) Keep Anthropic secret material outside immutable release directories.
RUNTIME_AI_KEY="$BASE/runtime/AI_Key"
if [ ! -f "$RUNTIME_AI_KEY" ] && [ -n "$PREV_RELEASE" ]; then
  for previous_key in "$PREV_RELEASE/backend/AI_Key" "$PREV_RELEASE/services/omni-ticket-backend/AI_Key"; do
    if [ -f "$previous_key" ]; then
      install -m 600 "$previous_key" "$RUNTIME_AI_KEY"
      log "Migrated AI_Key into the protected runtime directory"
      break
    fi
  done
fi
if [ -f "$RUNTIME_AI_KEY" ]; then
  ln -s "$RUNTIME_AI_KEY" "$BACKEND/AI_Key"
fi

# 5) Run migrations (idempotent) with the shared runtime env.
log "Running database migrations (alembic upgrade head)"
(
  cd "$BACKEND"
  set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a
  ./.venv/bin/alembic upgrade head
) || die "alembic migration failed — NOT switching traffic"

# 6) Activate atomically.
log "Switching 'current' symlink"
ln -sfn "$REL_DIR" "$CURRENT_LINK"

# 7) Reload only Omni's PM2 processes from the versioned process definition.
PM2_CONFIG="$CURRENT_LINK/infra/pm2/ecosystem.config.cjs"
log "Reloading Omni PM2 processes"
OMNI_DEPLOY_BASE="$BASE" pm2 startOrReload "$PM2_CONFIG" --update-env \
  || die "pm2 reload failed"
pm2 save --force >/dev/null

# 8) Health-gate, auto-rollback on failure.
log "Health check"
ok=0
for i in $(seq 1 15); do
  if curl -fsS --max-time 5 "http://127.0.0.1:${API_PORT}/api/v1/health" >/dev/null 2>&1 \
     && curl -fsSI --max-time 5 "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 2
done

if [ "$ok" -ne 1 ]; then
  printf '\n\033[1;31mHealth check failed.\033[0m\n'
  if [ -n "$PREV_RELEASE" ] && [ -d "$PREV_RELEASE" ]; then
    log "AUTO-ROLLBACK -> $PREV_RELEASE"
    ln -sfn "$PREV_RELEASE" "$CURRENT_LINK"
    OMNI_DEPLOY_BASE="$BASE" pm2 startOrReload \
      "$CURRENT_LINK/infra/pm2/ecosystem.config.cjs" --update-env || true
  fi
  die "deploy rolled back (or left on previous release)"
fi

# 9) Prune old releases, keeping the newest KEEP_RELEASES (never the active one).
log "Pruning old releases (keep $KEEP_RELEASES)"
ACTIVE="$(basename "$(readlink -f "$CURRENT_LINK")")"
# shellcheck disable=SC2012
ls -1t "$RELEASES_DIR" | grep -vx "$ACTIVE" | tail -n +"$KEEP_RELEASES" | while read -r old; do
  [ -n "$old" ] && rm -rf "${RELEASES_DIR:?}/$old"
done

log "Deploy complete: $(basename "$REL_DIR") is live and healthy."
