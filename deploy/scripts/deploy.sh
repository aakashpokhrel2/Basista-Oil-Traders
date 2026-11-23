#!/usr/bin/env bash
# ==============================================================================
# Production Deployment Script
# Application: Basista Oil Traders Petrol Station Management System
# Target Path: /var/www/basista_oil
# ==============================================================================
set -euo pipefail

# Configuration
APP_DIR="/var/www/basista_oil"
VENV_DIR="${APP_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
GIT_BRANCH="${1:-main}"

echo "=================================================================="
echo " Starting Production Deployment: Basista Oil Traders"
echo " Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo " Target Directory: ${APP_DIR}"
echo " Git Branch: ${GIT_BRANCH}"
echo "=================================================================="

# 1. Verify Application Directory and Environment
if [ ! -d "${APP_DIR}" ]; then
    echo "ERROR: Application directory ${APP_DIR} does not exist!" >&2
    exit 1
fi

cd "${APP_DIR}"

if [ ! -f ".env" ]; then
    echo "ERROR: Production .env file not found at ${APP_DIR}/.env!" >&2
    echo "Please create .env using .env.production.example before deploying." >&2
    exit 1
fi

# Ensure log and run directories exist
sudo mkdir -p /var/log/gunicorn /run/gunicorn "${APP_DIR}/logs" "${APP_DIR}/media" "${APP_DIR}/staticfiles"
sudo chown -R www-data:www-data /var/log/gunicorn /run/gunicorn "${APP_DIR}/logs" "${APP_DIR}/media" "${APP_DIR}/staticfiles"

# 2. Pull Latest Git Code
echo ""
echo "[Step 1/8] Pulling latest changes from branch '${GIT_BRANCH}'..."
git fetch --all --prune
CURRENT_COMMIT=$(git rev-parse HEAD)
git checkout "${GIT_BRANCH}"
git pull origin "${GIT_BRANCH}"
NEW_COMMIT=$(git rev-parse HEAD)
echo "Updated from commit ${CURRENT_COMMIT:0:8} to ${NEW_COMMIT:0:8}"

# Save deployment state for rollback reference
echo "${CURRENT_COMMIT}" > "${APP_DIR}/.previous_deployment_commit"

# 3. Virtual Environment Check & Dependencies
echo ""
echo "[Step 2/8] Ensuring virtual environment and upgrading dependencies..."
if [ ! -f "${PYTHON_BIN}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi

"${PIP_BIN}" install --quiet --upgrade pip setuptools wheel
"${PIP_BIN}" install --quiet -r requirements.txt

# 4. Database Migrations
echo ""
echo "[Step 3/8] Applying PostgreSQL database migrations..."
"${PYTHON_BIN}" manage.py migrate --noinput

# 5. Compile Bilingual Translation Catalogs
echo ""
echo "[Step 4/8] Compiling bilingual gettext messages (en / ne)..."
"${PYTHON_BIN}" manage.py compilemessages || {
    echo "WARNING: compilemessages returned non-zero. Check gettext tools."
}

# 6. Collect Static Assets
echo ""
echo "[Step 5/8] Collecting static files into ${APP_DIR}/staticfiles..."
"${PYTHON_BIN}" manage.py collectstatic --noinput --clear

# Ensure proper permissions for www-data
sudo chown -R www-data:www-data "${APP_DIR}/staticfiles" "${APP_DIR}/media"

# 7. Django Production Security & Health Check
echo ""
echo "[Step 6/8] Running Django deployment security check..."
"${PYTHON_BIN}" manage.py check --deploy

# 8. Reload Gunicorn and Nginx
echo ""
echo "[Step 7/8] Restarting application services..."
sudo systemctl restart gunicorn.socket gunicorn.service
sudo systemctl status gunicorn.service --no-pager -l

echo "Testing Nginx configuration syntax..."
sudo nginx -t
sudo systemctl reload nginx

# 9. Smoke Test Health Check
echo ""
echo "[Step 8/8] Performing local endpoint smoke test..."
sleep 2

# Check via UNIX socket or local HTTP
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: petrol.basistaoil.com.np" http://127.0.0.1/login/ || true)
if [ "${HTTP_STATUS}" = "200" ] || [ "${HTTP_STATUS}" = "302" ]; then
    echo "Smoke check PASSED: Received HTTP ${HTTP_STATUS}"
else
    echo "WARNING: Smoke check received unexpected HTTP status: ${HTTP_STATUS} (Check /var/log/gunicorn/error.log)"
fi

echo ""
echo "=================================================================="
echo " SUCCESS: Production Deployment Finished!"
echo " Commit: ${NEW_COMMIT:0:8}"
echo " Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=================================================================="
