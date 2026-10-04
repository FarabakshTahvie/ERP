#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/farabakhsh/app"
BACKUP_DIR="/var/backups/farabakhsh"
KEEP_DAYS=14
STAMP=$(date +%Y%m%d-%H%M)

mkdir -p "$BACKUP_DIR"
DB_NAME=$(grep -E '^DB_NAME=' "$APP_DIR/.env" | cut -d= -f2- | tr -d '"' || true)
DB_NAME=${DB_NAME:-FaraBakhsh}

runuser -u postgres -- pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/db-$STAMP.dump"
if [ -d "$APP_DIR/media" ]; then
    tar -czf "$BACKUP_DIR/media-$STAMP.tgz" -C "$APP_DIR" media
fi
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete
chmod 600 "$BACKUP_DIR"/*
echo "backup ok: $STAMP"
