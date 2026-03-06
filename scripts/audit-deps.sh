#!/usr/bin/env bash
# -------------------------------------------------------------------------------
# Dependency Vulnerability Audit Script
#
# Scans Python and frontend dependencies for known CVEs.
# Designed for CI pipelines and local developer use.
#
# Exit codes:
#   0 — No vulnerabilities found
#   1 — Vulnerabilities found
#   2 — Tool installation/configuration error
# -------------------------------------------------------------------------------
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== SpiderFoot Dependency Vulnerability Audit ==="
echo ""

ISSUES=0

# ── Python dependencies ─────────────────────────────────────────────
echo -e "${YELLOW}[1/3] Python dependency audit (pip-audit)${NC}"
if command -v pip-audit &>/dev/null; then
    if pip-audit -r "$PROJECT_ROOT/requirements.txt" --strict --desc 2>&1; then
        echo -e "${GREEN}  ✓ No Python vulnerabilities found${NC}"
    else
        echo -e "${RED}  ✗ Python vulnerabilities detected${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "${YELLOW}  ⚠ pip-audit not installed (pip install pip-audit)${NC}"
fi

echo ""

# ── Frontend dependencies ───────────────────────────────────────────
echo -e "${YELLOW}[2/3] Frontend dependency audit (npm audit)${NC}"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
if [ -f "$FRONTEND_DIR/package-lock.json" ]; then
    cd "$FRONTEND_DIR"
    if npm audit --omit=dev 2>&1; then
        echo -e "${GREEN}  ✓ No frontend vulnerabilities found${NC}"
    else
        echo -e "${RED}  ✗ Frontend vulnerabilities detected${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    cd "$PROJECT_ROOT"
elif [ -f "$FRONTEND_DIR/package.json" ]; then
    echo -e "${YELLOW}  ⚠ No package-lock.json — run 'npm install' first${NC}"
else
    echo "  (no frontend directory found, skipping)"
fi

echo ""

# ── Docker image scanning ───────────────────────────────────────────
echo -e "${YELLOW}[3/3] Docker image scan (trivy)${NC}"
if command -v trivy &>/dev/null; then
    echo "  Scanning spiderfoot API image..."
    if docker image inspect spiderfoot-api:latest &>/dev/null 2>&1; then
        trivy image --severity HIGH,CRITICAL --exit-code 1 spiderfoot-api:latest 2>&1 || {
            echo -e "${RED}  ✗ API image has HIGH/CRITICAL vulnerabilities${NC}"
            ISSUES=$((ISSUES + 1))
        }
    else
        echo "  (spiderfoot-api:latest not built, skipping)"
    fi

    echo "  Scanning spiderfoot frontend image..."
    if docker image inspect spiderfoot-frontend:latest &>/dev/null 2>&1; then
        trivy image --severity HIGH,CRITICAL --exit-code 1 spiderfoot-frontend:latest 2>&1 || {
            echo -e "${RED}  ✗ Frontend image has HIGH/CRITICAL vulnerabilities${NC}"
            ISSUES=$((ISSUES + 1))
        }
    else
        echo "  (spiderfoot-frontend:latest not built, skipping)"
    fi
else
    echo -e "${YELLOW}  ⚠ trivy not installed (https://trivy.dev)${NC}"
fi

echo ""
echo "================================================================"
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}All checks passed — no known vulnerabilities.${NC}"
    exit 0
else
    echo -e "${RED}$ISSUES check(s) found vulnerabilities. Review above.${NC}"
    exit 1
fi
