#!/bin/sh
# Seeds Vault with development secrets on first run.
# Idempotent — safe to run multiple times.
#
# Usage: docker compose exec vault sh /vault/config/vault-init.sh

set -e

export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="minihedge-dev-root-token"

echo "Waiting for Vault to be ready..."
until vault status > /dev/null 2>&1; do
    sleep 1
done

echo "Enabling KV v2 secrets engine (if not already enabled)..."
vault secrets enable -path=secret kv-v2 2>/dev/null || true

echo "Seeding secrets..."
vault kv put secret/minihedge \
    jwt_secret="minihedge-vault-managed-jwt-secret" \
    database_url="postgresql+asyncpg://minihedge:minihedge@postgres:5432/minihedge" \
    database_password="minihedge" \
    redis_password="" \
    kafka_sasl_username="" \
    kafka_sasl_password="" \
    keycloak_admin_password="admin"

echo "Vault secrets seeded successfully."
vault kv get secret/minihedge
