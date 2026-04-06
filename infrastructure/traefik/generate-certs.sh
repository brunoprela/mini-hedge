#!/bin/sh
# Generate self-signed TLS certificates for local development.
# Run once: ./infrastructure/traefik/generate-certs.sh

set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/local.crt" ]; then
    echo "Certificates already exist. Delete $CERT_DIR/local.crt to regenerate."
    exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$CERT_DIR/local.key" \
    -out "$CERT_DIR/local.crt" \
    -days 365 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"

echo "Self-signed certificates generated in $CERT_DIR/"
