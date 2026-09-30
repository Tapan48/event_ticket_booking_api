#!/bin/sh
# Run from cron as root; dumps contain user data and must never enter Git/images.
set -eu
umask 077
DEPLOY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKUP_DIR="$DEPLOY_ROOT/backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/ticketing-$(date -u +%Y%m%dT%H%M%SZ).dump"
trap 'rm -f "$BACKUP_FILE.partial"' EXIT HUP INT TERM
sh "$DEPLOY_ROOT/deploy/compose.sh" exec -T db \
  pg_dump -U ticketing -d ticketing --format=custom > "$BACKUP_FILE.partial"
test -s "$BACKUP_FILE.partial"
mv "$BACKUP_FILE.partial" "$BACKUP_FILE"
find "$BACKUP_DIR" -type f -name 'ticketing-*.dump' -mtime +6 -delete
printf 'Backup created: %s\n' "$BACKUP_FILE"
