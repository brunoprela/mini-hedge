#!/usr/bin/env bash
# Restore PostgreSQL database from a backup file.
# Usage: ./scripts/restore.sh <backup_file>
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup_file.dump.gz>"
  echo ""
  echo "Available backups:"
  ls -1t backups/minihedge_*.dump.gz 2>/dev/null || echo "  (none found in ./backups/)"
  exit 1
fi

BACKUP_FILE="$1"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_USER="${DB_USER:-minihedge}"
DB_NAME="${DB_NAME:-minihedge}"

if [[ "$BACKUP_FILE" == *.gz ]]; then
  echo "Decompressing ${BACKUP_FILE} ..."
  TEMP_FILE="${BACKUP_FILE%.gz}"
  gunzip -k "$BACKUP_FILE"
  BACKUP_FILE="$TEMP_FILE"
  CLEANUP_TEMP=true
else
  CLEANUP_TEMP=false
fi

echo "Restoring ${DB_NAME} from ${BACKUP_FILE} ..."

PGPASSWORD="${DB_PASSWORD:-minihedge}" pg_restore \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --clean \
  --if-exists \
  --no-owner \
  "$BACKUP_FILE"

if [ "$CLEANUP_TEMP" = true ]; then
  rm -f "$BACKUP_FILE"
fi

echo "Restore complete."
