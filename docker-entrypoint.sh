#!/bin/bash
# SpiderFoot Docker startup script — Microservice mode (PostgreSQL only)

set -e

# Ensure runtime directories exist
mkdir -p /home/spiderfoot/.spiderfoot/logs
mkdir -p /home/spiderfoot/logs
mkdir -p /home/spiderfoot/cache
mkdir -p /home/spiderfoot/data

# Ensure proper permissions
if [ -d "/home/spiderfoot/logs" ]; then
    rm -rf /home/spiderfoot/logs/*
fi

chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot
chown -R spiderfoot:spiderfoot /home/spiderfoot/logs
chown -R spiderfoot:spiderfoot /home/spiderfoot/cache
chown -R spiderfoot:spiderfoot /home/spiderfoot/data
chmod -R 755 /home/spiderfoot/logs

echo "Starting SpiderFoot..."

# ── Microservice deployment support ──
# Auto-detect service role from SF_SERVICE_ROLE or command arguments
if [ -z "${SF_SERVICE_ROLE}" ]; then
    case "$1" in
        *sfapi*|*api*)     export SF_SERVICE_ROLE="api" ;;
        *scanner*)         export SF_SERVICE_ROLE="scanner" ;;
        *)                 export SF_SERVICE_ROLE="api" ;;
    esac
fi

echo "Service role: ${SF_SERVICE_ROLE}"
echo "Deployment mode: ${SF_DEPLOYMENT_MODE:-microservice}"

# Validate PostgreSQL connectivity
if [ -n "${SF_POSTGRES_DSN}" ]; then
    echo "PostgreSQL DSN configured"
else
    echo "WARNING: SF_POSTGRES_DSN not set — database operations will fail"
fi

# Execute the original command
exec "$@"
