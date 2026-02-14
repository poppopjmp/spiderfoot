#!/bin/bash
# Create a separate database for LiteLLM so its Prisma migrations
# don't interfere with SpiderFoot's tables.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE litellm OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
EOSQL
