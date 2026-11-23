#!/usr/bin/env bash
# ==============================================================================
# Automated Daily Backup & Off-Site Synchronization Cron Script
# Project: Basista Oil Traders Petrol Station Management System
# Schedule: Run daily at 02:00 AM via cron
# ==============================================================================
set -euo pipefail

APP_DIR="/var/www/basista_oil"
VENV_DIR="${APP_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
BACKUP_DIR="${APP_DIR}/backups"
LOG_FILE="/var/log/petrol_station_backup.log"

# Optional Remote Off-site Configuration (e.g. Remote storage server or mounted NAS)
REMOTE_OFFSITE_DIR="${OFFSITE_BACKUP_DIR:-/mnt/offsite_backups/basista_oil}"
REMOTE_SSH_TARGET="${OFFSITE_SSH_TARGET:-}" # e.g. "backup_user@nas.example.com:/backups/basista_oil"

mkdir -p "${BACKUP_DIR}" "$(dirname "${LOG_FILE}")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "${LOG_FILE}"
}

log "=================================================================="
log "Starting automated petrol station database backup..."

cd "${APP_DIR}"

# 1. Run Django Backup Management Command (PostgreSQL native or compressed JSON)
# - Generates SHA-256 checksum and manifest
# - Automatically prunes backups older than 30 days
# - Records immutable AuditLog event
if "${PYTHON_BIN}" manage.py backup_database --keep-days 30 --offsite-dir "${REMOTE_OFFSITE_DIR}" >> "${LOG_FILE}" 2>&1; then
    log "Django backup management command completed successfully."
else
    log "ERROR: Django backup command failed!"
    exit 1
fi

# 2. Remote Off-site Synchronization (via rsync over SSH if configured)
if [ -n "${REMOTE_SSH_TARGET}" ]; then
    log "Synchronizing backup directory to remote offsite target: ${REMOTE_SSH_TARGET}..."
    if rsync -avz --delete -e "ssh -o StrictHostKeyChecking=accept-new" "${BACKUP_DIR}/" "${REMOTE_SSH_TARGET}/" >> "${LOG_FILE}" 2>&1; then
        log "Offsite rsync replication succeeded."
    else
        log "WARNING: Offsite rsync replication encountered an error. Check network and SSH keys."
    fi
fi

# 3. Summary of stored backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "*.sql.gz" -o -name "*.json.gz" | wc -l)
log "Daily backup cycle finished. Total stored backups: ${BACKUP_COUNT}"
log "=================================================================="
