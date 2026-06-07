#!/usr/bin/env bash
#
# rollback-pulse.sh — repoint the Omni Ticket Pulse VM to a previous release.
#
# Releases are immutable snapshots, so rollback is just switching the `current`
# symlink and restarting PM2. Mirrors docs/DEPLOY_RUNBOOK.md. Runs ON the VM.
#
# Usage:
#   bash rollback-pulse.sh                 # roll back to the immediately previous release
#   bash rollback-pulse.sh <release-name>  # roll back to a specific release dir name
#   ssh pulse-prod 'bash -s' < scripts/rollback-pulse.sh
#
# NOTE: This does NOT reverse database migrations. Alembic upgrades are forward-only
# here; if a release introduced a destructive migration, restore the DB from backups/
# separately. The schema is additive across these releases, so an app-only rollback
# to a recent release is safe.
#
set -euo pipefail

BASE="${BASE:-/home/amechi/omni-ticket}"
API_PORT="${API_PORT:-8090}"
FRONTEND_PORT="${FRONTEND_PORT:-8088}"
RELEASES_DIR="$BASE/releases"
CURRENT_LINK="$BASE/current"
TARGET_NAME="${1:-}"

log() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -L "$CURRENT_LINK" ] || die "no current symlink at $CURRENT_LINK"
ACTIVE="$(basename "$(readlink -f "$CURRENT_LINK")")"

if [ -z "$TARGET_NAME" ]; then
  # newest release that is not the active one
  TARGET_NAME="$(ls -1t "$RELEASES_DIR" | grep -vx "$ACTIVE" | head -1 || true)"
  [ -n "$TARGET_NAME" ] || die "no previous release found to roll back to"
fi

TARGET_DIR="$RELEASES_DIR/$TARGET_NAME"
[ -d "$TARGET_DIR" ] || die "release '$TARGET_NAME' does not exist"
[ "$TARGET_NAME" = "$ACTIVE" ] && die "release '$TARGET_NAME' is already active"

log "Rolling back: $ACTIVE -> $TARGET_NAME"
ln -sfn "$TARGET_DIR" "$CURRENT_LINK"
pm2 restart omni-ticket-api omni-ticket-worker omni-ticket-frontend --update-env \
  || die "pm2 restart failed (symlink already repointed)"

log "Health check"
ok=0
for i in $(seq 1 15); do
  if curl -fsS --max-time 5 "http://127.0.0.1:${API_PORT}/api/v1/health" >/dev/null 2>&1 \
     && curl -fsSI --max-time 5 "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 2
done
[ "$ok" -eq 1 ] || die "rolled back to $TARGET_NAME but health check still failing — investigate"

log "Rollback complete: $TARGET_NAME is live and healthy."
