#!/bin/sh
# =============================================================================
# Generate self-signed TLS certificates for Traefik
# =============================================================================
# Creates a self-signed cert valid for 365 days, suitable for local dev.
# For production, use Let's Encrypt (see infra/traefik/traefik.yml).
#
# Usage:
#   chmod +x scripts/generate-traefik-certs.sh
#   ./scripts/generate-traefik-certs.sh
# =============================================================================

set -e

CERT_DIR="$(dirname "$0")/../infra/traefik/certs"
mkdir -p "$CERT_DIR"

CERT_FILE="$CERT_DIR/spiderfoot.crt"
KEY_FILE="$CERT_DIR/spiderfoot.key"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "Certificates already exist in $CERT_DIR"
  echo "  $CERT_FILE"
  echo "  $KEY_FILE"
  echo "Delete them first if you want to regenerate."
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "Error: openssl not found in \$PATH"
  exit 1
fi

echo "Generating self-signed TLS certificate..."

openssl req -new -newkey rsa:4096 -sha256 -x509 -days 365 -nodes \
  -out "$CERT_FILE" \
  -keyout "$KEY_FILE" \
  -subj "/CN=localhost/O=SpiderFoot/OU=Dev" \
  -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1"

chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo ""
echo "Certificates generated:"
echo "  Certificate: $CERT_FILE"
echo "  Private key: $KEY_FILE"
echo ""
echo "These are self-signed — your browser will show a security warning."
echo "For production, configure Let's Encrypt in infra/traefik/traefik.yml"
