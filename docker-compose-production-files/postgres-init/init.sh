#!/bin/bash
set -e

echo "Starting SpiderFoot PostgreSQL database initialization..."

# Create additional databases and users if needed
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create extensions for better performance and functionality
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS btree_gin;
    CREATE EXTENSION IF NOT EXISTS unaccent;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS uuid-ossp;
    
    -- Create performance monitoring extensions
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    
    -- Grant necessary permissions to main user
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON SCHEMA public TO $POSTGRES_USER;
    
    -- Create a read-only user for analytics/reporting
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'spiderfoot_readonly') THEN
            CREATE USER spiderfoot_readonly WITH PASSWORD '${READONLY_PASSWORD:-readonly_password}';
        END IF;
    END
    \$\$;
    
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO spiderfoot_readonly;
    GRANT USAGE ON SCHEMA public TO spiderfoot_readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO spiderfoot_readonly;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO spiderfoot_readonly;
    
    -- Create a monitoring user for metrics collection
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'spiderfoot_monitor') THEN
            CREATE USER spiderfoot_monitor WITH PASSWORD '${MONITOR_PASSWORD:-monitor_password}';
        END IF;
    END
    \$\$;
    
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO spiderfoot_monitor;
    GRANT USAGE ON SCHEMA public TO spiderfoot_monitor;
    GRANT SELECT ON pg_stat_database TO spiderfoot_monitor;
    GRANT SELECT ON pg_stat_user_tables TO spiderfoot_monitor;
    GRANT SELECT ON pg_stat_user_indexes TO spiderfoot_monitor;
    GRANT SELECT ON pg_stat_activity TO spiderfoot_monitor;
    GRANT SELECT ON pg_stat_statements TO spiderfoot_monitor;
    
    -- Configure some performance settings
    ALTER DATABASE $POSTGRES_DB SET shared_preload_libraries = 'pg_stat_statements';
    ALTER DATABASE $POSTGRES_DB SET pg_stat_statements.max = 10000;
    ALTER DATABASE $POSTGRES_DB SET pg_stat_statements.track = all;
    
    -- Create performance monitoring view
    CREATE OR REPLACE VIEW pg_stat_statements_summary AS
    SELECT 
        query,
        calls,
        total_time,
        mean_time,
        rows,
        100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
    FROM pg_stat_statements
    ORDER BY total_time DESC;
    
    GRANT SELECT ON pg_stat_statements_summary TO spiderfoot_monitor;
    
    -- Log the initialization
    SELECT 'SpiderFoot PostgreSQL database initialized successfully' as status,
           current_timestamp as initialized_at;
EOSQL

echo "PostgreSQL initialization completed for SpiderFoot production environment"
echo "Database: $POSTGRES_DB"
echo "Main user: $POSTGRES_USER"
echo "Read-only user: spiderfoot_readonly"
echo "Monitor user: spiderfoot_monitor"
