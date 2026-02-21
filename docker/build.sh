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
REGISTRY="${REGISTRY:-}"   # e.g. ghcr.io/poppopjmp/

for arg in "$@"; do
    case $arg in
        --push) PUSH=true ;;
        --tag) TAG="$2" ;;
        --registry) REGISTRY="$2" ;;
    esac
done

cd "$PROJECT_ROOT"

echo "=== Building SpiderFoot microservice images (tag: $TAG) ==="

# 1. Base image
echo "[1/5] Building base image..."
docker build \
    -f docker/Dockerfile.base \
    -t ${REGISTRY}spiderfoot-base:latest \
    -t ${REGISTRY}spiderfoot-base:$TAG \
    .

# 2. Scanner
echo "[2/5] Building scanner image..."
docker build \
    -f docker/Dockerfile.scanner \
    -t ${REGISTRY}spiderfoot-scanner:latest \
    -t ${REGISTRY}spiderfoot-scanner:$TAG \
    .

# 3. API
echo "[3/5] Building API image..."
docker build \
    -f docker/Dockerfile.api \
    -t ${REGISTRY}spiderfoot-api:latest \
    -t ${REGISTRY}spiderfoot-api:$TAG \
    .

# 4. WebUI
echo "[4/5] Building WebUI image..."
docker build \
    -f docker/Dockerfile.webui \
    -t ${REGISTRY}spiderfoot-webui:latest \
    -t ${REGISTRY}spiderfoot-webui:$TAG \
    .

# 5. Active Worker
echo "[5/5] Building active-worker image..."
docker build \
    -f Dockerfile.active-worker \
    -t ${REGISTRY}spiderfoot-active-worker:latest \
    -t ${REGISTRY}spiderfoot-active-worker:$TAG \
    .

echo ""
echo "=== Build complete ==="
echo "Images:"
docker images --filter "reference=spiderfoot-*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"

if [ "$PUSH" = true ]; then
    echo ""
    echo "=== Pushing images ==="
    for svc in base scanner api webui active-worker; do
        docker push ${REGISTRY}spiderfoot-$svc:$TAG
        docker push ${REGISTRY}spiderfoot-$svc:latest
    done
fi
