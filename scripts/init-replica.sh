#!/usr/bin/env bash
# Entrypoint for the PostgreSQL read replica.
# Performs pg_basebackup from the primary, then starts as a hot standby.
set -e

PGDATA="/var/lib/postgresql/data"
PRIMARY_HOST="${PRIMARY_HOST:-postgres}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
REPLICATION_USER="${REPLICATION_USER:-replicator}"
REPLICATION_PASSWORD="${REPLICATION_PASSWORD:-minihedge}"

# Ensure PGDATA is owned by postgres with correct permissions (entrypoint runs as root)
chown postgres:postgres "$PGDATA"
chmod 0700 "$PGDATA"

# If PGDATA is empty, bootstrap from primary
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "replica: no data directory found, running pg_basebackup..."
    gosu postgres env PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
        -h "$PRIMARY_HOST" \
        -p "$PRIMARY_PORT" \
        -U "$REPLICATION_USER" \
        -D "$PGDATA" \
        -Fp -Xs -P -R

    # -R flag creates standby.signal and sets primary_conninfo in postgresql.auto.conf
    # Override hot_standby to ensure read-only queries work
    echo "hot_standby = on" >> "$PGDATA/postgresql.auto.conf"
    chown postgres:postgres "$PGDATA/postgresql.auto.conf"

    echo "replica: base backup complete, starting as hot standby"
else
    echo "replica: data directory exists, starting as hot standby"
fi

# Start PostgreSQL as the postgres user (postgres refuses to run as root)
exec gosu postgres postgres \
    -c hot_standby=on \
    -c max_connections=100
