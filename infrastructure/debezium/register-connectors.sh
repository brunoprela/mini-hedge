#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONNECTOR_CONFIG="$SCRIPT_DIR/minihedge-connector.json"
CONNECTOR_NAME="minihedge-cdc"

# Wait for Kafka Connect REST API to be available
echo "Waiting for Kafka Connect at $CONNECT_URL ..."
elapsed=0
until curl -sf "$CONNECT_URL/" > /dev/null 2>&1; do
  if [ "$elapsed" -ge 60 ]; then
    echo "ERROR: Kafka Connect not available after 60 seconds"
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
echo "Kafka Connect is ready."

# Check if the connector already exists
if curl -sf "$CONNECT_URL/connectors/$CONNECTOR_NAME" > /dev/null 2>&1; then
  echo "Connector '$CONNECTOR_NAME' already exists."
  curl -s "$CONNECT_URL/connectors/$CONNECTOR_NAME/status" | python3 -m json.tool 2>/dev/null || true
else
  echo "Registering connector '$CONNECTOR_NAME' ..."
  curl -sf -X POST "$CONNECT_URL/connectors" \
    -H "Content-Type: application/json" \
    -d @"$CONNECTOR_CONFIG"
  echo ""
  echo "Connector '$CONNECTOR_NAME' registered successfully."
fi

# Print final status
echo ""
echo "Current connectors:"
curl -s "$CONNECT_URL/connectors" | python3 -m json.tool 2>/dev/null || true
