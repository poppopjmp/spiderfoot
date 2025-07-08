# Configuration

*Author: poppopjmp*

SpiderFoot can be configured via the web UI, configuration file, and environment variables. Proper configuration ensures you get the most out of all modules and integrations, and helps tailor SpiderFoot to your environment and use case.

---

## API Keys

Many modules require API keys for external services. Configure these in the web UI:

- Go to **Settings → Module Settings**
- Enter your API keys for services such as:
  - VirusTotal
  - Shodan
  - Hunter.io
  - SecurityTrails
  - Have I Been Pwned
  - ...and more

> **Tip:** Modules that require API keys will show a warning if not configured. You can run scans without API keys, but results may be limited.

---

## Configuration File

Advanced options can be set in `spiderfoot.conf` (or `spiderfoot.cfg`):

```ini
[webui]
host = 127.0.0.1
port = 5001

[database]
path = spiderfoot.db

[security]
# CSRF Protection
csrf_enabled = True
csrf_secret_key = your-strong-secret-key
csrf_timeout = 3600

# Rate Limiting
rate_limiting_enabled = True
rate_limiting_storage = memory
rate_limiting_api_requests_per_minute = 60
rate_limiting_web_requests_per_minute = 120

# Input Validation
input_validation_enabled = True
input_validation_max_input_length = 10000
input_validation_strict_mode = False

# Session Security
session_security_enabled = True
session_security_storage = memory
session_security_session_timeout = 3600
session_security_max_sessions_per_user = 5

# API Security
api_security_enabled = True
api_security_jwt_secret = your-jwt-secret-key
api_security_jwt_expiry = 3600
api_security_api_key_length = 32

# Security Logging
security_logging_enabled = True
security_logging_log_file = security.log
security_logging_log_level = INFO

# Security Headers
security_headers_enabled = True
```

- You can change the web UI port, database location, logging options, security features, and more.
- For production, consider moving the database to a persistent storage location.
- **Security:** Always use strong, unique secret keys for CSRF and JWT tokens.

---

## Environment Variables

You can override some settings using environment variables (useful for Docker and CI/CD):

### General Configuration
- `SPIDERFOOT_DB_PATH` – Path to the database file
- `SPIDERFOOT_WEBUI_PORT` – Port for the web UI
- `SPIDERFOOT_WEBUI_HOST` – Host address for the web UI

### Security Configuration
- `SPIDERFOOT_CSRF_SECRET` – CSRF protection secret key
- `SPIDERFOOT_JWT_SECRET` – JWT token secret key
- `SPIDERFOOT_RATE_LIMIT_STORAGE` – Rate limiting storage backend (memory/redis)
- `SPIDERFOOT_REDIS_HOST` – Redis server host (if using Redis storage)
- `SPIDERFOOT_REDIS_PORT` – Redis server port
- `SPIDERFOOT_SECURITY_LOG_FILE` – Path to security log file
- `SPIDERFOOT_SESSION_TIMEOUT` – Session timeout in seconds

### API Key Environment Variables
- `VIRUSTOTAL_API_KEY` – VirusTotal API key
- `SHODAN_API_KEY` – Shodan API key
- `HUNTER_API_KEY` – Hunter.io API key
- `SECURITYTRAILS_API_KEY` – SecurityTrails API key
- `HIBP_API_KEY` – Have I Been Pwned API key
- `SPIDERFOOT_LOG_LEVEL` – Logging verbosity (e.g., INFO, DEBUG)

---

## Best Practices

- Always keep your API keys secure and never share them publicly.
- Use a dedicated config file for production deployments.
- Regularly review and update your API keys and module settings.
- For Docker, use environment variables or mount a config file for persistent configuration.

---

## Troubleshooting

- If a module fails, check if its API key is set and valid.
- For config file errors, ensure correct INI syntax and file permissions.
- For Docker, use environment variables or mount a config file.
- See the [Troubleshooting Guide](troubleshooting.md) for more help.

---

## Database Backend Support (2025+)

SpiderFoot supports both SQLite and PostgreSQL as database backends. The backend is auto-detected based on configuration and connection string.

- **SQLite** is the default and is suitable for most single-user or small deployments.
- **PostgreSQL** is recommended for large-scale, multi-user, or production deployments.

### Switching Backends

- To use PostgreSQL, set the database connection string in your config file or environment variable (e.g., `SPIDERFOOT_DB_TYPE=postgresql` and `SPIDERFOOT_DB_PATH=postgresql://user:pass@host/dbname`).
- For SQLite, use a file path (e.g., `spiderfoot.db`).
- The backend is detected automatically based on the connection string or file extension.

### Schema Management

- Schema creation and migrations are backend-aware and idempotent. You can safely run SpiderFoot with an existing database file or PostgreSQL schema.
- All upsert/replace operations use backend-agnostic helpers, ensuring correct behavior for both SQLite and PostgreSQL. This prevents data loss and ensures atomic updates.
- Composite keys and unique constraints are enforced where required for upsert support. For example, `tbl_scan_config` uses a unique constraint on `(scan_instance_id, component, opt)`.
- Schema versioning is automatic. The schema version is tracked in the `tbl_schema_version` table, and migrations are applied as needed.

### Error Handling

- All database operations use granular exception handling and retry logic for transient errors (e.g., connection drops, deadlocks).
- Errors are logged with context, including the backend type, query, and parameters.
- If a schema or migration error occurs, SpiderFoot will log the error and abort startup to prevent data corruption.

### Best Practices

- For SQLite, foreign key enforcement is enabled automatically (`PRAGMA foreign_keys=ON`).
- For PostgreSQL, connection pooling is recommended for high concurrency (e.g., using `psycopg2.pool`).
- Always back up your database before upgrading SpiderFoot or changing the backend.
- For Docker deployments, mount the database file or use a managed PostgreSQL service for persistence.

### Advanced: Backend Differences

- **Placeholders:** SQL parameter placeholders are adapted automatically (`?` for SQLite, `%s` for PostgreSQL).
- **Upserts:** All upserts use `ON CONFLICT` for both backends, with the correct conflict target and update columns.
- **Type Mapping:** Data types are mapped to the appropriate backend types (e.g., `TEXT` for SQLite, `VARCHAR`/`TEXT` for PostgreSQL).
- **Indexes:** All indexes are created with `IF NOT EXISTS` to ensure idempotency.
- **Foreign Keys:** Enforced in both backends, but SQLite requires explicit enabling.

### Troubleshooting Database Issues

- If you see errors about missing tables or constraints, ensure your database is not corrupted and that SpiderFoot has permission to create/modify tables.
- For PostgreSQL, check that your user has the necessary privileges (CREATE, INSERT, UPDATE, etc.).
- For SQLite, ensure the database file is writable and not locked by another process.
- Use the `drop_all_tables` and `dump_schema` helpers (see developer guide) for test isolation and debugging.

---

## Security Configuration Best Practices

### Production Security Setup

When deploying SpiderFoot in production, follow these security configuration guidelines:

**1. Strong Secret Keys**
```bash
# Generate cryptographically secure keys
SPIDERFOOT_CSRF_SECRET=$(openssl rand -hex 32)
SPIDERFOOT_JWT_SECRET=$(openssl rand -hex 32)
```

**2. Rate Limiting Configuration**
```ini
[security]
rate_limiting_enabled = True
rate_limiting_storage = redis  # Use Redis for distributed setups
rate_limiting_api_requests_per_minute = 60
rate_limiting_web_requests_per_minute = 120
```

**3. Session Security**
```ini
[security]
session_security_enabled = True
session_security_session_timeout = 1800  # 30 minutes
session_security_max_sessions_per_user = 3
```

**4. Input Validation**
```ini
[security]
input_validation_enabled = True
input_validation_strict_mode = True  # Enable for production
input_validation_max_input_length = 5000
```

### Security Monitoring

Enable comprehensive security logging:

```ini
[security]
security_logging_enabled = True
security_logging_log_file = /var/log/spiderfoot/security.log
security_logging_log_level = INFO
```

Monitor these security events:
- Authentication failures
- Rate limit violations
- Input validation failures
- Session anomalies
- API abuse attempts

### Environment-Specific Configuration

**Development Environment:**
```bash
export SPIDERFOOT_CSRF_SECRET=dev-csrf-secret
export SPIDERFOOT_JWT_SECRET=dev-jwt-secret
export SPIDERFOOT_SECURITY_LOG_LEVEL=DEBUG
```

**Production Environment:**
```bash
export SPIDERFOOT_CSRF_SECRET=your-production-csrf-secret
export SPIDERFOOT_JWT_SECRET=your-production-jwt-secret
export SPIDERFOOT_RATE_LIMIT_STORAGE=redis
export SPIDERFOOT_REDIS_HOST=redis.production.local
export SPIDERFOOT_SECURITY_LOG_FILE=/var/log/spiderfoot/security.log
```

### Security Validation

Validate your security configuration:

```bash
cd spiderfoot
python security_validator.py /path/to/spiderfoot
```

This will check:
- Security module availability
- Configuration validity
- Security feature functionality
- Performance impact assessment

---

See the [User Guide](user_guide.md) for more usage details and advanced configuration options.
