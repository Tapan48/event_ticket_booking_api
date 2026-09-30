#!/bin/sh
# Restore into a fresh disposable database. Never accepts a live database name.
set -eu
DEPLOY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKUP_FILE=${1:?Usage: sh deploy/verify-restore.sh /path/to/backup.dump}
test -s "$BACKUP_FILE"
RESTORE_DB="ticketing_restore_check_$(date +%s)_$$"
compose() { sh "$DEPLOY_ROOT/deploy/compose.sh" "$@"; }
cleanup() { compose exec -T db dropdb -U ticketing --if-exists "$RESTORE_DB"; }
trap cleanup EXIT HUP INT TERM
compose exec -T db createdb -U ticketing "$RESTORE_DB"
compose exec -T db pg_restore -U ticketing -d "$RESTORE_DB" \
  --exit-on-error --no-owner < "$BACKUP_FILE"
compose exec -T db psql -U ticketing -d "$RESTORE_DB" -v ON_ERROR_STOP=1 \
  -c 'SELECT count(*) AS restored_migrations FROM django_migrations;' \
  -c 'SELECT count(*) AS restored_events FROM events_event;'
printf 'Restore verification succeeded in disposable database.\n'
