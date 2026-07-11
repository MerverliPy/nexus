#!/usr/bin/env bash
# Restore a Nexus backup and verify it with a health check.
#
# Usage: ./scripts/test-restore.sh <backup_file.sql.gz[.gpg]>
#
# Restores to a temporary database (nexus_restore_test) and runs a few
# sanity queries. Does NOT touch the production database.

set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup_file.sql.gz[.gpg]>}"
RESTORE_DB="nexus_restore_test"

: "${NEXUS_DB_USER:=bot}"
: "${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD must be set}"
: "${DOCKER_CONTAINER:=finance-bot-db}"

log()  { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }
die()  { log "FATAL: $*"; exit 1; }

log "Restore test: $BACKUP_FILE → $RESTORE_DB"

# ── Determine if encrypted ──────────────────────────────────────────────

if [[ "$BACKUP_FILE" == *.gpg ]]; then
    if [[ -z "${NEXUS_BACKUP_GPG_KEY:-}" ]]; then
        die "Backup is encrypted but NEXUS_BACKUP_GPG_KEY is not set"
    fi
    log "Decrypting with GPG..."
    DECRYPTED=$(mktemp)
    gpg --decrypt --recipient "$NEXUS_BACKUP_GPG_KEY" \
        --batch --yes --output "$DECRYPTED" "$BACKUP_FILE"
    SOURCE_FILE="$DECRYPTED"
else
    SOURCE_FILE="$BACKUP_FILE"
fi

# ── Decompress if needed ────────────────────────────────────────────────

SQL_TMP=$(mktemp)
if [[ "$SOURCE_FILE" == *.gz ]]; then
    gunzip -c "$SOURCE_FILE" > "$SQL_TMP"
else
    cp "$SOURCE_FILE" "$SQL_TMP"
fi
rm -f "$DECRYPTED"

# ── Restore to temporary DB ─────────────────────────────────────────────

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$DOCKER_CONTAINER"; then
    log "Restoring via Docker container '$DOCKER_CONTAINER'..."

    # Drop + recreate the test DB
    docker exec "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
        psql -U "$NEXUS_DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $RESTORE_DB;" 2>/dev/null || true
    docker exec "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
        psql -U "$NEXUS_DB_USER" -d postgres -c "CREATE DATABASE $RESTORE_DB;" || die "CREATE DATABASE failed"

    # Restore
    docker exec -i "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
        psql -U "$NEXUS_DB_USER" -d "$RESTORE_DB" < "$SQL_TMP" \
        || die "Restore failed"

    # Health-check queries
    for q in \
        "SELECT count(*) FROM users;" \
        "SELECT count(*) FROM transactions;" \
        "SELECT count(*) FROM tasks;"; do
        result=$(docker exec "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
            psql -U "$NEXUS_DB_USER" -d "$RESTORE_DB" -tAc "$q" 2>/dev/null || echo "QUERY FAILED")
        log "  $q → $result"
    done

    # Cleanup
    docker exec "$DOCKER_CONTAINER" env PGPASSWORD="$NEXUS_DB_PASSWORD" \
        psql -U "$NEXUS_DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $RESTORE_DB;" 2>/dev/null || true
else
    # Local Postgres
    set +e
    PGPASSWORD="$NEXUS_DB_PASSWORD" dropdb -U "$NEXUS_DB_USER" "$RESTORE_DB" 2>/dev/null
    set -e
    PGPASSWORD="$NEXUS_DB_PASSWORD" createdb -U "$NEXUS_DB_USER" "$RESTORE_DB" || die "createdb failed"
    PGPASSWORD="$NEXUS_DB_PASSWORD" psql -U "$NEXUS_DB_USER" -d "$RESTORE_DB" < "$SQL_TMP" || die "Restore failed"

    for q in \
        "SELECT count(*) FROM users;" \
        "SELECT count(*) FROM transactions;" \
        "SELECT count(*) FROM tasks;"; do
        result=$(PGPASSWORD="$NEXUS_DB_PASSWORD" psql -U "$NEXUS_DB_USER" -d "$RESTORE_DB" -tAc "$q" 2>/dev/null || echo "QUERY FAILED")
        log "  $q → $result"
    done

    PGPASSWORD="$NEXUS_DB_PASSWORD" dropdb -U "$NEXUS_DB_USER" "$RESTORE_DB" 2>/dev/null || true
fi

rm -f "$SQL_TMP"
log "Restore test PASSED"
