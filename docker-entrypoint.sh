#!/bin/bash
# SpiderFoot Docker startup script

# Ensure the correct database and logs directory structure
mkdir -p /home/spiderfoot/.spiderfoot/logs
mkdir -p /home/spiderfoot/logs
mkdir -p /home/spiderfoot/cache
mkdir -p /home/spiderfoot/data

# Remove any database files from the application directory if they exist
if [ -f "/home/spiderfoot/data/spiderfoot.db" ]; then
    echo "Warning: Found spiderfoot.db in data directory. Removing it..."
    rm -f /home/spiderfoot/data/spiderfoot.db
fi

# Remove any database files from the application directory if they exist
if [ -f "/home/spiderfoot/spiderfoot.db" ]; then
    echo "Warning: Found spiderfoot.db in application directory. Removing it..."
    rm -f /home/spiderfoot/spiderfoot.db
fi

# Ensure proper permissions
# Clean up any existing log files that might have wrong ownership
if [ -d "/home/spiderfoot/logs" ]; then
    echo "Cleaning up existing log files..."
    rm -rf /home/spiderfoot/logs/*
fi

chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot
chown -R spiderfoot:spiderfoot /home/spiderfoot/logs
chown -R spiderfoot:spiderfoot /home/spiderfoot/cache
chown -R spiderfoot:spiderfoot /home/spiderfoot/data
chmod -R 755 /home/spiderfoot/logs

echo "Database will be created at: /home/spiderfoot/data/spiderfoot.db"
echo "Starting SpiderFoot..."

# ── Microservice deployment support ──
# Auto-detect service role from SF_SERVICE_ROLE or command arguments
if [ -z "${SF_SERVICE_ROLE}" ]; then
    case "$1" in
        *sfapi*|*api*)     export SF_SERVICE_ROLE="api" ;;
        *scanner*|*sf.py*) export SF_SERVICE_ROLE="scanner" ;;
        *webui*|*sfwebui*) export SF_SERVICE_ROLE="webui" ;;
        *)                 export SF_SERVICE_ROLE="standalone" ;;
    esac
fi

echo "Service role: ${SF_SERVICE_ROLE}"
echo "Deployment mode: ${SF_DEPLOYMENT_MODE:-monolith}"

# Execute the original command
exec "$@"
