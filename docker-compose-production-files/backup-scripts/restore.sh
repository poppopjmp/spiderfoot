#!/bin/bash

# SpiderFoot Database Restore Script
# Usage: ./restore.sh <backup_file>

set -e

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <backup_file>"
    echo "Available backups:"
    ls -la /backups/spiderfoot_backup_*.sql.gz* 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-spiderfoot_prod}"
POSTGRES_USER="${POSTGRES_USER:-spiderfoot}"

# Check if backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file '$BACKUP_FILE' not found!"
    exit 1
fi

echo "Starting database restore from: $BACKUP_FILE"
echo "WARNING: This will replace all data in database '$POSTGRES_DB'"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Determine backup format
if [[ "$BACKUP_FILE" == *.custom ]]; then
    echo "Restoring from custom format backup..."
    PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
        --host="$POSTGRES_HOST" \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --no-password \
        --clean \
        --if-exists \
        --verbose \
        "$BACKUP_FILE"
elif [[ "$BACKUP_FILE" == *.sql.gz ]]; then
    echo "Restoring from compressed SQL backup..."
    gunzip -c "$BACKUP_FILE" | PGPASSWORD="$POSTGRES_PASSWORD" psql \
        --host="$POSTGRES_HOST" \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --no-password
else
    echo "Restoring from plain SQL backup..."
    PGPASSWORD="$POSTGRES_PASSWORD" psql \
        --host="$POSTGRES_HOST" \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --no-password \
        --file="$BACKUP_FILE"
fi

echo "Database restore completed successfully!"
echo "You may want to restart the SpiderFoot application to ensure proper operation."
