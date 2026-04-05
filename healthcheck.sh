#!/usr/bin/env bash

set -e

SERVICE="api"

echo "[healthcheck] running AI healthcheck..."

docker compose exec -T $SERVICE python ai_healthcheck.py "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[healthcheck] ✅ ALL OK"
else
  echo "[healthcheck] ❌ FAILED"
fi

exit $EXIT_CODE