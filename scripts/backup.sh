#!/usr/bin/env bash
# Nexus automated database backup with rotation.
#
# Usage: ./scripts/backup.sh [/path/to/backup_dir]
#
# Default backup dir:  ~/.nexus/backups/
# Rotation:            keep 7 daily, 4 weekly, 12 monthly
# Encryption:          gpg (set NEXUS_BACKUP_GPG_KEY to enable)

set -euo pipefail

BACKUP_DIR="${1:-$HOME/.nexus/backups}"
LOG_FILE="$BACKUP_DIR/backup.log"

# ── Config (overridable via environment) ────────────────────────────────

: "${NEXUS_DB_NAME:=nexus_db}"
: "${NEXUS_DB_USER:=bot}"
: "${NEXUS_DB_HOST:=localhost}"
: "${NEXUS_DB_PORT:=5432}"
: "${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD must be set}"
: "${DOCKER_CONTAINER:=finance-bot-db}"

# ── Helpers ─────────────────────────────────────────────────────────────

log()  { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE"; }
die() { log "FATAL: $*"; exit 1; }

# ── Prepare ─────────────────────────────────────────────────────────────

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/nexus_${TIMESTAMP}.sql.gz"
BACKUP_TMP=$(mktemp)

trap 'rm -f "$BACKUP_TMP"' EXIT

log "Starting backup → $BACKUP_FILE"

# ── Dump (via Docker if container is running, else direct pg_dump) ──────

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$DOCKER_CONTAINER"; then
    log "Dumping via Docker container '$DOCKER_CONTAINER'..."
    docker exec "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
        pg_dump -U "$NEXUS_DB_USER" -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
        --format=plain --no-owner --no-acl "$NEXUS_DB_NAME" > "$BACKUP_TMP" \
        || die "pg_dump (Docker) failed"
else
    log "Dumping via local pg_dump..."
    PGPASSWORD="$NEXUS_DB_PASSWORD" pg_dump \
        -U "$NEXUS_DB_USER" -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
        --format=plain --no-owner --no-acl "$NEXUS_DB_NAME" > "$BACKUP_TMP" \
        || die "pg_dump (local) failed"
fi

# ── Compress ────────────────────────────────────────────────────────────

gzip -c "$BACKUP_TMP" > "$BACKUP_FILE"
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup compressed: $BACKUP_SIZE"

# ── Encrypt (optional) ──────────────────────────────────────────────────

if [[ -n "${NEXUS_BACKUP_GPG_KEY:-}" ]]; then
    gpg --encrypt --recipient "$NEXUS_BACKUP_GPG_KEY" \
        --batch --yes --output "${BACKUP_FILE}.gpg" "$BACKUP_FILE"
    rm "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gpg"
    log "Backup encrypted with GPG key $NEXUS_BACKUP_GPG_KEY"
fi

# ── Rotation ────────────────────────────────────────────────────────────

rotate_keep() {
    # Keep last $1 files matching $2, delete the rest.
    local keep="$1" pattern="$2"
    local -a files
    readarray -t files < <(ls -1t $pattern 2>/dev/null || true)
    local total=${#files[@]}
    for ((i = keep; i < total; i++)); do
        rm -f "${files[$i]}"
        log "Rotated out: ${files[$i]}"
    done
}

# Daily: keep last 7
rotate_keep 7 "$BACKUP_DIR/nexus_*.sql.gz"*
# Weekly: keep every 7th file (Sunday dump), max 4
weekly_files=$(ls -1t "$BACKUP_DIR"/nexus_*.sql.gz* 2>/dev/null | awk 'NR % 7 == 1' || true)
if [[ -n "$weekly_files" ]]; then
    keep=4
    for f in $weekly_files; do
        if ((keep <= 0)); then rm -f "$f"; fi
        ((keep--)) || true
    done
fi
# Monthly: keep every 30th file, max 12
monthly_files=$(ls -1t "$BACKUP_DIR"/nexus_*.sql.gz* 2>/dev/null | awk 'NR % 30 == 1' || true)
if [[ -n "$monthly_files" ]]; then
    keep=12
    for f in $monthly_files; do
        if ((keep <= 0)); then rm -f "$f"; fi
        ((keep--)) || true
    done
fi

log "Backup complete: $BACKUP_FILE"
log "Directory: $(ls "$BACKUP_DIR" | wc -l) backups on disk"
