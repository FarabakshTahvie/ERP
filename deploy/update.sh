#!/usr/bin/env bash
set -e

PROJECT_DIR="/var/www/farabakhsh/app"
VENV_DIR="/var/www/farabakhsh/venv"

echo "=== Pulling latest changes from Git ==="
cd "$PROJECT_DIR"
git pull origin main

echo "=== Installing Python dependencies ==="
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "=== Building frontend assets with pnpm ==="
pnpm install --frozen-lockfile
pnpm run build

echo "=== Collecting static files ==="
"$VENV_DIR/bin/python" manage.py collectstatic --noinput

echo "=== Applying database migrations ==="
"$VENV_DIR/bin/python" manage.py migrate --noinput

echo "=== Restarting Gunicorn service ==="
systemctl restart farabakhsh

echo "=== Update completed successfully! ==="
