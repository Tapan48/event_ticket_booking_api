#!/bin/sh
set -eu
DEPLOY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec docker compose --project-name ticket-booking \
  --env-file "$DEPLOY_ROOT/.env.prod" \
  -f "$DEPLOY_ROOT/docker-compose.prod.yml" "$@"
