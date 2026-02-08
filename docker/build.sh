#!/bin/bash
# =============================================================================
# Build all SpiderFoot microservice Docker images
# Usage:  ./docker/build.sh [--push] [--tag v5.7.0]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TAG="${2:-latest}"
PUSH=false

for arg in "$@"; do
    case $arg in
        --push) PUSH=true ;;
        --tag) TAG="$2" ;;
    esac
done

cd "$PROJECT_ROOT"

echo "=== Building SpiderFoot microservice images (tag: $TAG) ==="

# 1. Base image
echo "[1/4] Building base image..."
docker build \
    -f docker/Dockerfile.base \
    -t spiderfoot-base:latest \
    -t spiderfoot-base:$TAG \
    .

# 2. Scanner
echo "[2/4] Building scanner image..."
docker build \
    -f docker/Dockerfile.scanner \
    -t spiderfoot-scanner:latest \
    -t spiderfoot-scanner:$TAG \
    .

# 3. API
echo "[3/4] Building API image..."
docker build \
    -f docker/Dockerfile.api \
    -t spiderfoot-api:latest \
    -t spiderfoot-api:$TAG \
    .

# 4. WebUI
echo "[4/4] Building WebUI image..."
docker build \
    -f docker/Dockerfile.webui \
    -t spiderfoot-webui:latest \
    -t spiderfoot-webui:$TAG \
    .

echo ""
echo "=== Build complete ==="
echo "Images:"
docker images --filter "reference=spiderfoot-*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"

if [ "$PUSH" = true ]; then
    echo ""
    echo "=== Pushing images ==="
    for svc in base scanner api webui; do
        docker push spiderfoot-$svc:$TAG
        docker push spiderfoot-$svc:latest
    done
fi
