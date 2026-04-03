#!/usr/bin/env bash

set -e

FILE="$1"

if [ -z "$FILE" ]; then
  echo "Usage: $0 <backup.sql or backup.sql.gz>"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "[restore] file not found: $FILE"
  exit 1
fi

echo "[restore] stopping app services..."
docker compose stop api celery_worker celery_beat tg_bot || true

echo "[restore] terminating active connections..."
docker compose exec -T db psql -U bakhrushin -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'bakhrushin' AND pid <> pg_backend_pid();
"

echo "[restore] recreating database..."
docker compose exec -T db psql -U bakhrushin -d postgres -c "DROP DATABASE IF EXISTS bakhrushin;"
docker compose exec -T db psql -U bakhrushin -d postgres -c "CREATE DATABASE bakhrushin;"

echo "[restore] restoring from $FILE..."

if [[ "$FILE" == *.gz ]]; then
  gunzip -c "$FILE" | docker compose exec -T db psql -U bakhrushin -d bakhrushin
else
  cat "$FILE" | docker compose exec -T db psql -U bakhrushin -d bakhrushin
fi

echo "[restore] starting services..."
docker compose up -d

echo "[restore] done ✅"