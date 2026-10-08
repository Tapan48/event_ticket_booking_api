#!/bin/sh
# Images must already be built/loaded with this immutable release tag.
set -eu
DEPLOY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RELEASE_TAG=${1:?Usage: sh deploy/release.sh COMMIT_SHA}
case "$RELEASE_TAG" in *[!a-f0-9]*|'') echo 'Expected a hexadecimal commit SHA' >&2; exit 1;; esac
export RELEASE_TAG
compose() { sh "$DEPLOY_ROOT/deploy/compose.sh" "$@"; }
docker image inspect "ticket-booking-app:$RELEASE_TAG" >/dev/null
docker image inspect "ticket-booking-proxy:$RELEASE_TAG" >/dev/null
compose config --quiet
sh "$DEPLOY_ROOT/deploy/ensure-edge-network.sh"
if test -n "$(compose ps -q --status running web)"; then
  sh "$DEPLOY_ROOT/deploy/backup.sh"
fi
compose up -d --wait db redis
compose run --rm --no-deps web python manage.py migrate --noinput
compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
compose up -d --no-build --wait --wait-timeout 180 web worker beat proxy
# Persist the tag only after the containers pass health checks. Keep all secrets private.
python3 - "$DEPLOY_ROOT/.env.prod" "$RELEASE_TAG" <<'PY'
import os
import sys
from pathlib import Path

path, tag = Path(sys.argv[1]), sys.argv[2]
lines = [line for line in path.read_text().splitlines() if not line.startswith("RELEASE_TAG=")]
temporary = path.with_suffix(".prod.tmp")
with open(temporary, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
    stream.write("\n".join([f"RELEASE_TAG={tag}", *lines]) + "\n")
temporary.replace(path)
PY
printf 'Healthy release started: %s. Verify the public HTTPS endpoint next.\n' "$RELEASE_TAG"
