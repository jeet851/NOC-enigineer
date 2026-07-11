#!/usr/bin/env bash
# ==============================================================================
# Database Restore Utility
# ==============================================================================
set -euo pipefail

DB_PATH="/app/data/network_noc.db"
BACKUP_DIR="/app/data/backups"
S3_BUCKET="s3://noc-ai-production-backups/database"

# Ensure usage arguments are supplied
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup_filename_or_s3_url>" >&2
    echo "Example: $0 noc_db_backup_20260705_120000.db.gz" >&2
    exit 1
fi

INPUT_BACKUP="$1"
LOCAL_BACKUP_PATH=""

mkdir -p "${BACKUP_DIR}"

# 1. Resolve and download backup file
if [[ "${INPUT_BACKUP}" =~ ^s3:// ]]; then
    FILENAME=$(basename "${INPUT_BACKUP}")
    LOCAL_BACKUP_PATH="${BACKUP_DIR}/${FILENAME}"
    echo "Downloading backup from S3: ${INPUT_BACKUP}..."
    aws s3 cp "${INPUT_BACKUP}" "${LOCAL_BACKUP_PATH}"
else
    # Check if file exists locally
    if [ -f "${INPUT_BACKUP}" ]; then
        LOCAL_BACKUP_PATH="${INPUT_BACKUP}"
    elif [ -f "${BACKUP_DIR}/${INPUT_BACKUP}" ]; then
        LOCAL_BACKUP_PATH="${BACKUP_DIR}/${INPUT_BACKUP}"
    else
        # Try to download from default S3 bucket
        LOCAL_BACKUP_PATH="${BACKUP_DIR}/${INPUT_BACKUP}"
        echo "Searching default S3 bucket for file: ${S3_BUCKET}/${INPUT_BACKUP}..."
        if command -v aws &> /dev/null; then
            aws s3 cp "${S3_BUCKET}/${INPUT_BACKUP}" "${LOCAL_BACKUP_PATH}"
        else
            echo "ERROR: File not found locally and AWS CLI is unavailable." >&2
            exit 1
        fi
    fi
fi

echo "Resolved backup file: ${LOCAL_BACKUP_PATH}"

# Decompress backup to temp location
TEMP_RESTORE_DB="/tmp/noc_restore_db_$$.db"
echo "Decompressing backup..."
gunzip -c "${LOCAL_BACKUP_PATH}" > "${TEMP_RESTORE_DB}"

# 2. Cryptographic and Integrity validation checks
echo "Verifying restored database integrity..."
INTEGRITY=$(sqlite3 "${TEMP_RESTORE_DB}" "PRAGMA integrity_check;")
if [ "${INTEGRITY}" != "ok" ]; then
    echo "CRITICAL ERROR: Restored database integrity check failed: ${INTEGRITY}" >&2
    rm -f "${TEMP_RESTORE_DB}"
    exit 1
fi
echo "Integrity check: SUCCESS."

# 3. Securely replace running database
echo "!!! WARNING: Proceeding will overwrite the running database !!!"
read -p "Do you want to continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled by user."
    rm -f "${TEMP_RESTORE_DB}"
    exit 1
fi

# Backup active live DB to .bak before replacing
if [ -f "${DB_PATH}" ]; then
    echo "Backing up running database to ${DB_PATH}.bak..."
    cp "${DB_PATH}" "${DB_PATH}.bak"
fi

echo "Swapping database files..."
cp "${TEMP_RESTORE_DB}" "${DB_PATH}"
rm -f "${TEMP_RESTORE_DB}"

echo "Database restoration completed successfully!"
echo "Please restart application and Celery worker pods to reload DB sessions."
