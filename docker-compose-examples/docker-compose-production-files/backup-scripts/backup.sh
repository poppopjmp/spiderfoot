#!/bin/bash

# SpiderFoot Production Database Backup Script
# This script creates compressed backups of the PostgreSQL database

set -e

# Configuration
BACKUP_DIR="/backups"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-spiderfoot_prod}"
POSTGRES_USER="${POSTGRES_USER:-spiderfoot}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp for backup file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="spiderfoot_backup_${TIMESTAMP}.sql.gz"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

echo "Starting database backup at $(date)"
echo "Backup file: $BACKUP_PATH"

# Create the backup
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host="$POSTGRES_HOST" \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --no-password \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="$BACKUP_PATH.custom"

# Also create a plain SQL backup for easier restore
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host="$POSTGRES_HOST" \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --no-password \
    --format=plain \
    --verbose | gzip > "$BACKUP_PATH"

# Verify backup was created
if [[ -f "$BACKUP_PATH" && -f "$BACKUP_PATH.custom" ]]; then
    BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    CUSTOM_SIZE=$(du -h "$BACKUP_PATH.custom" | cut -f1)
    echo "Backup completed successfully!"
    echo "SQL backup size: $BACKUP_SIZE"
    echo "Custom backup size: $CUSTOM_SIZE"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups (keep only last N days)
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "spiderfoot_backup_*.sql.gz*" -type f -mtime +$RETENTION_DAYS -delete

# List current backups
echo "Current backups:"
ls -lh "$BACKUP_DIR"/spiderfoot_backup_*.sql.gz* | tail -10

# Optional: Upload to S3 if configured
if [[ "${S3_BACKUP_ENABLED}" == "true" ]]; then
    echo "Uploading backup to S3..."
    if command -v aws >/dev/null 2>&1; then
        aws s3 cp "$BACKUP_PATH" "s3://${S3_BUCKET}/database/" --region="${S3_REGION}"
        aws s3 cp "$BACKUP_PATH.custom" "s3://${S3_BUCKET}/database/" --region="${S3_REGION}"
        echo "Backup uploaded to S3 successfully"
    else
        echo "WARNING: AWS CLI not found, skipping S3 upload"
    fi
fi

echo "Backup process completed at $(date)"
