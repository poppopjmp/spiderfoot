#!/bin/bash
# =============================================================================
# Build all SpiderFoot microservice Docker images
#
# Image hierarchy:
#   spiderfoot-base           ← shared Python + SpiderFoot code
#   ├─ spiderfoot-api         ← FastAPI REST API
#   ├─ spiderfoot-scanner     ← Celery worker (passive queues)
#   └─ spiderfoot-active-scanner ← Celery worker + recon tools (scan queue)
#   spiderfoot-frontend       ← React SPA (Nginx)
#
# Usage:
#   ./docker/build.sh                          # build all, tag :latest
#   ./docker/build.sh --tag v6.0.0             # build all, tag :v6.0.0
#   ./docker/build.sh --push --tag v6.0.0      # build + push to registry
#   REGISTRY=ghcr.io/org/ ./docker/build.sh    # custom registry prefix
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TAG="latest"
PUSH=false
REGISTRY="${REGISTRY:-}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)    PUSH=true; shift ;;
        --tag)     TAG="$2"; shift 2 ;;
        --registry) REGISTRY="$2"; shift 2 ;;
        *)         shift ;;
    esac
done

cd "$PROJECT_ROOT"

echo "=== Building SpiderFoot microservice images (tag: $TAG) ==="
echo ""

# 1. Base image
echo "[1/5] Building base image..."
docker build \
    -f docker/Dockerfile.base \
    -t "${REGISTRY}spiderfoot-base:latest" \
    -t "${REGISTRY}spiderfoot-base:$TAG" \
    .

# 2. API
echo "[2/5] Building API image..."
docker build \
    -f docker/Dockerfile.api \
    --build-arg "BASE_IMAGE=${REGISTRY}spiderfoot-base:$TAG" \
    -t "${REGISTRY}spiderfoot-api:latest" \
    -t "${REGISTRY}spiderfoot-api:$TAG" \
    .

# 3. Scanner (passive worker)
echo "[3/5] Building scanner image..."
docker build \
    -f docker/Dockerfile.scanner \
    --build-arg "BASE_IMAGE=${REGISTRY}spiderfoot-base:$TAG" \
    -t "${REGISTRY}spiderfoot-scanner:latest" \
    -t "${REGISTRY}spiderfoot-scanner:$TAG" \
    .

# 4. Active scanner (scan worker + recon tools)
echo "[4/5] Building active-scanner image..."
docker build \
    -f docker/Dockerfile.active-scanner \
    --build-arg "BASE_IMAGE=${REGISTRY}spiderfoot-base:$TAG" \
    -t "${REGISTRY}spiderfoot-active-scanner:latest" \
    -t "${REGISTRY}spiderfoot-active-scanner:$TAG" \
    .

# 5. Frontend
echo "[5/5] Building frontend image..."
docker build \
    -f frontend/Dockerfile \
    -t "${REGISTRY}spiderfoot-frontend:latest" \
    -t "${REGISTRY}spiderfoot-frontend:$TAG" \
    frontend/

echo ""
echo "=== Build complete ==="
docker images --filter "reference=*spiderfoot-*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"

if [ "$PUSH" = true ]; then
    echo ""
    echo "=== Pushing images ==="
    for svc in base api scanner active-scanner frontend; do
        docker push "${REGISTRY}spiderfoot-$svc:$TAG"
        docker push "${REGISTRY}spiderfoot-$svc:latest"
    done
fi
