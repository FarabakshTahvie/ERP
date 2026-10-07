#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/farabakhsh/app"
VENV_DIR="/var/www/farabakhsh/venv"

echo "=== Starting Farabakhsh Update Script ==="

cd "$APP_DIR"

# Ensure git safe.directory for www-data and root
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
sudo -u www-data git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

# Check uncommitted changes
UNCOMMITTED=$(sudo -u www-data git status --porcelain 2>/dev/null || git status --porcelain || true)
if [ -n "$UNCOMMITTED" ]; then
    echo "ERROR: Uncommitted changes detected on server:"
    echo "$UNCOMMITTED"
    echo "Aborting update to prevent data loss."
    exit 1
fi

# Get PREV commit hash
PREV=$(sudo -u www-data git rev-parse HEAD 2>/dev/null || git rev-parse HEAD)
echo "PREV Commit: $PREV"

echo "=== Fetching and Resetting to origin/main ==="
sudo -u www-data git fetch origin main
sudo -u www-data git reset --hard origin/main

NEW=$(sudo -u www-data git rev-parse HEAD 2>/dev/null || git rev-parse HEAD)
echo "NEW Commit:  $NEW"

echo "=== Installing Python dependencies ==="
sudo -u www-data "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u www-data "$VENV_DIR/bin/pip" install -r requirements.txt

echo "=== Building frontend assets with pnpm ==="
sudo -u www-data pnpm install --frozen-lockfile
sudo -u www-data pnpm run build

echo "=== Collecting static files ==="
sudo -u www-data "$VENV_DIR/bin/python" manage.py collectstatic --noinput

echo "=== Running Database Migrations ==="
sudo -u www-data "$VENV_DIR/bin/python" manage.py migrate --noinput

echo "=== Restarting Farabakhsh Service ==="
systemctl restart farabakhsh

echo "=== Installing and restarting Celery services ==="
install -m 644 "$APP_DIR/deploy/farabakhsh-celery.service" /etc/systemd/system/farabakhsh-celery.service
install -m 644 "$APP_DIR/deploy/farabakhsh-celerybeat.service" /etc/systemd/system/farabakhsh-celerybeat.service
systemctl daemon-reload
systemctl enable farabakhsh-celery farabakhsh-celerybeat >/dev/null 2>&1
systemctl restart farabakhsh-celery farabakhsh-celerybeat

CELERY_OK=0
for i in {1..10}; do
    if systemctl is-active --quiet farabakhsh-celery && systemctl is-active --quiet farabakhsh-celerybeat \
       && sudo -u www-data "$VENV_DIR/bin/celery" -A config inspect ping --timeout 5 >/dev/null 2>&1; then
        CELERY_OK=1
        break
    fi
    echo "Celery check attempt $i/10 not ready yet"
    sleep 3
done
if [ "$CELERY_OK" -ne 1 ]; then
    echo "ERROR: Celery worker/beat is not healthy (the website itself is up)."
    systemctl --no-pager status farabakhsh-celery farabakhsh-celerybeat | tail -n 40 || true
    exit 1
fi

echo "=== Running Health Check ==="
HEALTH_PASS=0
for i in {1..10}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: farabakhshtahvieh.com" http://127.0.0.1:8000/accounts/login/ || echo "000")
    echo "Health check attempt $i/10: HTTP $HTTP_CODE"
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTH_PASS=1
        break
    fi
    sleep 2
done

if [ "$HEALTH_PASS" -ne 1 ]; then
    echo "ERROR: Health check failed! (HTTP $HTTP_CODE)"
    echo "PREV Commit: $PREV"
    echo "NEW Commit:  $NEW"
    echo "برای برگشت کد: cd $APP_DIR && sudo -u www-data git reset --hard $PREV && systemctl restart farabakhsh"
    exit 1
fi

echo "=== Update Completed Successfully! ==="
