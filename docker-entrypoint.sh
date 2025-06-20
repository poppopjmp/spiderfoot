#!/bin/bash
# SpiderFoot Docker startup script

# Ensure the correct database and logs directory structure
mkdir -p /home/spiderfoot/.spiderfoot/logs
mkdir -p /home/spiderfoot/logs
mkdir -p /var/lib/spiderfoot/log
mkdir -p /var/lib/spiderfoot/cache

# Remove any database files from the application directory if they exist
if [ -f "/home/spiderfoot/spiderfoot.db" ]; then
    echo "Warning: Found spiderfoot.db in application directory. Removing it..."
    rm -f /home/spiderfoot/spiderfoot.db
fi

if [ -f "/home/spiderfoot/data/spiderfoot.db" ]; then
    echo "Warning: Found spiderfoot.db in data directory. Removing it..."
    rm -f /home/spiderfoot/data/spiderfoot.db
fi

# Ensure proper permissions
# Clean up any existing log files that might have wrong ownership
if [ -d "/home/spiderfoot/logs" ]; then
    echo "Cleaning up existing log files..."
    rm -rf /home/spiderfoot/logs/*
fi

chown -R spiderfoot:spiderfoot /home/spiderfoot/.spiderfoot
chown -R spiderfoot:spiderfoot /home/spiderfoot/logs
chown -R spiderfoot:spiderfoot /var/lib/spiderfoot
chmod -R 755 /home/spiderfoot/logs

echo "Database will be created at: /home/spiderfoot/.spiderfoot/spiderfoot.db"
echo "Starting SpiderFoot..."

# Execute the original command
exec "$@"
