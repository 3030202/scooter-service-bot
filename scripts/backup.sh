#!/usr/bin/env bash
set -euo pipefail

# Scooter Service Bot Automated Backup Script
# Performs PostgreSQL database dump and storage directory backup with retention management.

BACKUP_DIR="${BACKUP_DIR:-/var/backups/scooter-service-bot}"
PROJECT_DIR="${PROJECT_DIR:-/opt/scooter-service-bot}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DATE_DAY="$(date +%Y%m%d)"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"

mkdir -p "${BACKUP_DIR}/daily"
mkdir -p "${BACKUP_DIR}/weekly"

echo "[$(date -Iseconds)] Starting backup process..."

# 1. PostgreSQL Backup
DB_BACKUP_FILE="${BACKUP_DIR}/daily/postgres_${TIMESTAMP}.sql.gz"
if docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T postgres pg_dump -U "${POSTGRES_USER:-scooter_user}" "${POSTGRES_DB:-scooter_service}" | gzip > "${DB_BACKUP_FILE}"; then
    echo "[$(date -Iseconds)] Database backup created: ${DB_BACKUP_FILE}"
else
    echo "[$(date -Iseconds)] ERROR: Database backup failed!" >&2
    exit 1
fi

# 2. Storage Directory Backup
STORAGE_BACKUP_FILE="${BACKUP_DIR}/daily/storage_${TIMESTAMP}.tar.gz"
if [ -d "${PROJECT_DIR}/storage" ]; then
    tar -czf "${STORAGE_BACKUP_FILE}" -C "${PROJECT_DIR}" storage
    echo "[$(date -Iseconds)] Storage backup created: ${STORAGE_BACKUP_FILE}"
fi

# 3. Weekly Promotion (on Sunday)
if [ "$(date +%u)" -eq 7 ]; then
    cp "${DB_BACKUP_FILE}" "${BACKUP_DIR}/weekly/postgres_weekly_${DATE_DAY}.sql.gz"
    if [ -f "${STORAGE_BACKUP_FILE}" ]; then
        cp "${STORAGE_BACKUP_FILE}" "${BACKUP_DIR}/weekly/storage_weekly_${DATE_DAY}.tar.gz"
    fi
    echo "[$(date -Iseconds)] Weekly backup archived."
fi

# 4. Cleanup old daily backups
find "${BACKUP_DIR}/daily" -type f -mtime +"${RETENTION_DAYS}" -delete
echo "[$(date -Iseconds)] Cleaned daily backups older than ${RETENTION_DAYS} days."

# 5. Cleanup old weekly backups
find "${BACKUP_DIR}/weekly" -type f -mtime +"$((RETENTION_WEEKS * 7))" -delete
echo "[$(date -Iseconds)] Cleaned weekly backups older than ${RETENTION_WEEKS} weeks."

echo "[$(date -Iseconds)] Backup complete."
