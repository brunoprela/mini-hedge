#!/usr/bin/env bash
# Backup PostgreSQL database to a timestamped gzip file.
# Usage: ./scripts/backup.sh [BACKUP_DIR]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/minihedge_${TIMESTAMP}.dump"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_USER="${DB_USER:-minihedge}"
DB_NAME="${DB_NAME:-minihedge}"

mkdir -p "$BACKUP_DIR"

echo "Backing up ${DB_NAME} to ${BACKUP_FILE}.gz ..."

PGPASSWORD="${DB_PASSWORD:-minihedge}" pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --format=custom \
  --file="$BACKUP_FILE"

gzip "$BACKUP_FILE"

echo "Backup complete: ${BACKUP_FILE}.gz ($(du -h "${BACKUP_FILE}.gz" | cut -f1))"

# Retain only the last N backups (default: 10)
RETAIN="${BACKUP_RETAIN:-10}"
cd "$BACKUP_DIR"
# shellcheck disable=SC2012
ls -1t minihedge_*.dump.gz 2>/dev/null | tail -n +$((RETAIN + 1)) | xargs -r rm -f
echo "Retained last ${RETAIN} backups."
