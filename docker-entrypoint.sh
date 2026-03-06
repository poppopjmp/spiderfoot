#!/bin/bash
# SpiderFoot Docker startup script — Microservice mode (PostgreSQL only)
#
# Service roles (set via SF_SERVICE_ROLE env var):
#   api              → FastAPI REST API
#   scanner          → Celery worker (passive queues)
#   active-scanner   → Celery worker (scan queue + recon tools)
#   celery-beat      → Celery periodic scheduler
#   agents           → AI analysis agents
#
# If SF_SERVICE_ROLE is not set, auto-detects from the command arguments.

set -e

# Ensure runtime directories exist and are writable
for dir in logs cache data .spiderfoot/logs; do
    mkdir -p "/home/spiderfoot/$dir"
done

# Clean stale logs on start
rm -rf /home/spiderfoot/logs/*

# Fix ownership (only if running as root — skipped in rootless containers)
if [ "$(id -u)" = "0" ]; then
    chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot \
        /home/spiderfoot/logs /home/spiderfoot/cache /home/spiderfoot/data
    chmod -R 755 /home/spiderfoot/logs
fi

# Auto-detect service role from command arguments if not explicitly set
if [ -z "${SF_SERVICE_ROLE:-}" ]; then
    case "$*" in
        *sfapi*|*"service api"*|*"--service api"*)  export SF_SERVICE_ROLE="api" ;;
        *"--queues=scan"*)                           export SF_SERVICE_ROLE="active-scanner" ;;
        *celery*worker*)                             export SF_SERVICE_ROLE="scanner" ;;
        *celery*beat*)                               export SF_SERVICE_ROLE="celery-beat" ;;
        *celery*flower*)                             export SF_SERVICE_ROLE="flower" ;;
        *agents*)                                    export SF_SERVICE_ROLE="agents" ;;
        *)                                           export SF_SERVICE_ROLE="api" ;;
    esac
fi

echo "SpiderFoot starting — role=${SF_SERVICE_ROLE} mode=${SF_DEPLOYMENT_MODE:-microservice}"

# Validate PostgreSQL connectivity
if [ -n "${SF_POSTGRES_DSN:-}" ]; then
    echo "PostgreSQL DSN configured"
else
    echo "WARNING: SF_POSTGRES_DSN not set — database operations will fail"
fi

exec "$@"
