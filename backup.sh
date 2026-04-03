#!/usr/bin/env bash

set -e

PROJECT_NAME="bakhrushin"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%dT%H%M%S")
FILE="${BACKUP_DIR}/pgdump_${PROJECT_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] creating dump: $FILE"

docker compose exec -T db pg_dump -U bakhrushin -d bakhrushin \
  | gzip > "$FILE"

echo "[backup] done: $FILE"