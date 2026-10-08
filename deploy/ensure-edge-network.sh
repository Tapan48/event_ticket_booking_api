#!/bin/sh
# Shared only by the RAG frontend proxy and ticket proxy; never by databases.
set -eu
if ! docker network inspect ticket-edge >/dev/null 2>&1; then
  docker network create --driver bridge --internal ticket-edge >/dev/null
fi
properties=$(docker network inspect ticket-edge --format '{{.Driver}} {{.Internal}}')
if [ "$properties" != 'bridge true' ]; then
  echo 'ticket-edge must be an internal bridge; inspect it before proceeding.' >&2
  exit 1
fi
