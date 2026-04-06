#!/usr/bin/env bash
# Appends replication entry to pg_hba.conf after initdb runs.
# Mounted as a docker-entrypoint-initdb.d script on the primary.
set -e

PG_HBA="$PGDATA/pg_hba.conf"

# Allow replication connections from any Docker network host
echo "host replication replicator all scram-sha-256" >> "$PG_HBA"

echo "pg-hba: added replication entry for replicator role"
