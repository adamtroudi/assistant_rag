#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python -m alembic upgrade head
fi

if [ "${RAG_INGEST_ON_STARTUP:-false}" = "true" ]; then
  python -m app.cli ingest
fi

exec "$@"

