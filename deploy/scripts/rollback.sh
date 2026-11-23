#!/usr/bin/env bash
# ==============================================================================
# Production Rollback Script
# Application: Basista Oil Traders Petrol Station Management System
# Target Path: /var/www/basista_oil
# ==============================================================================
set -euo pipefail

APP_DIR="/var/www/basista_oil"
VENV_DIR="${APP_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

echo "=================================================================="
echo " Emergency Production Rollback: Basista Oil Traders"
echo " Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=================================================================="

cd "${APP_DIR}"

# Determine target commit to roll back to
TARGET_COMMIT="${1:-}"

if [ -z "${TARGET_COMMIT}" ]; then
    if [ -f "${APP_DIR}/.previous_deployment_commit" ]; then
        TARGET_COMMIT=$(cat "${APP_DIR}/.previous_deployment_commit")
        echo "Auto-detected previous deployment commit: ${TARGET_COMMIT}"
    else
        echo "ERROR: No target commit specified and .previous_deployment_commit not found." >&2
        echo "Usage: $0 <commit-hash-or-git-tag>" >&2
        exit 1
    fi
fi

echo "Rolling back to commit: ${TARGET_COMMIT}..."
git checkout "${TARGET_COMMIT}"

# Collect static assets for reverted code
echo "Re-collecting static assets..."
"${PYTHON_BIN}" manage.py collectstatic --noinput --clear
sudo chown -R www-data:www-data "${APP_DIR}/staticfiles"

# Restart Gunicorn application server
echo "Restarting Gunicorn and Nginx..."
sudo systemctl restart gunicorn.service
sudo systemctl reload nginx

echo ""
echo "=================================================================="
echo " SUCCESS: Rollback completed to commit ${TARGET_COMMIT}!"
echo " Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=================================================================="
