#!/usr/bin/env bash
# ==============================================================================
# Database Backup & S3 Synchronization script
# ==============================================================================
set -euo pipefail

# Configuration parameters
DB_PATH="/app/data/network_noc.db"
BACKUP_DIR="/app/data/backups"
S3_BUCKET="s3://noc-ai-production-backups/database"
DATE_TAG=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/noc_db_backup_${DATE_TAG}.db"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

echo "[$(date)] Initiating database backup sweep..."

# Create local backup directory if missing
mkdir -p "${BACKUP_DIR}"

# 1. Execute online hot-backup using SQLite CLI
if [ ! -f "${DB_PATH}" ]; then
    echo "ERROR: Source database not found at ${DB_PATH}" >&2
    exit 1
fi

sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"
echo "SQLite online backup file created successfully: ${BACKUP_FILE}"

# 2. Compress backup to minimize network transmission costs
gzip -9 "${BACKUP_FILE}"
echo "Backup compressed: ${COMPRESSED_FILE}"

# 3. Synchronize backup to S3 storage bucket
if command -v aws &> /dev/null; then
    aws s3 cp "${COMPRESSED_FILE}" "${S3_BUCKET}/noc_db_backup_${DATE_TAG}.db.gz"
    echo "Backup uploaded to S3 storage successfully."
else
    echo "WARNING: AWS CLI not found. Skipping S3 upload sync. Backup stored locally."
fi

# 4. Prune local backups older than 7 days
find "${BACKUP_DIR}" -type f -name "noc_db_backup_*.db.gz" -mtime +7 -delete
echo "Local pruning complete. Backups older than 7 days deleted."

echo "[$(date)] Database backup routine completed."
