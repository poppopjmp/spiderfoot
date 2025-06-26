# Configuration Guide

SpiderFoot offers extensive configuration options to customize behavior, performance, and integration with external services. This guide covers all configuration methods and options available in SpiderFoot 5.2.9.

## Configuration Methods

### 1. Web Interface Configuration (Recommended)

The easiest way to configure SpiderFoot is through the web interface:

1. **Access Settings**: Navigate to http://127.0.0.1:5001 → Settings
2. **Global Settings**: Configure core system behavior
3. **Module Settings**: Set API keys and module-specific options
4. **Scan Settings**: Default scanning parameters

### 2. Configuration File

The primary configuration file is `spiderfoot.conf` in the SpiderFoot root directory:

```ini
# spiderfoot.conf - Main configuration file
[global]
# Web server configuration
__webaddr = 127.0.0.1
__webport = 5001
__logfile = 
__database = spiderfoot.db
__logstdout = True

# Workflow configuration  
__max_concurrent_scans = 5
__scan_timeout = 3600
__correlation_enabled = True
__auto_correlation = True

# Performance settings
__maxthreads = 3
__timeout = 30
__fetchtimeout = 5

# Security settings
__api_enabled = True
__api_key = 
__debug = False

[workflow]
# Workspace settings
max_targets_per_workspace = 100
default_scan_modules = sfp_dnsresolve,sfp_whois,sfp_sslcert
correlation_rules_enabled = True

[mcp]
# MCP integration for CTI reports
enabled = True
server_url = http://localhost:8000
api_key = your_mcp_api_key
timeout = 300
```

### 3. Environment Variables

Override any configuration using environment variables:

```bash
# Core server settings
export SPIDERFOOT_WEB_ADDR="0.0.0.0"
export SPIDERFOOT_WEB_PORT="5001"
export SPIDERFOOT_DATABASE="/path/to/custom/database.db"
export SPIDERFOOT_DEBUG="True"

# Performance tuning
export SPIDERFOOT_MAX_THREADS="5"
export SPIDERFOOT_SCAN_TIMEOUT="7200"
export SPIDERFOOT_MAX_CONCURRENT_SCANS="3"

# API keys (preferred method for security)
export SPIDERFOOT_VIRUSTOTAL_API_KEY="your_virustotal_key"
export SPIDERFOOT_SHODAN_API_KEY="your_shodan_key"  
export SPIDERFOOT_HUNTER_API_KEY="your_hunter_key"
export SPIDERFOOT_SECURITYTRAILS_API_KEY="your_securitytrails_key"
```

# Workflow settings
export SPIDERFOOT_MAX_CONCURRENT_SCANS="3"
export SPIDERFOOT_SCAN_TIMEOUT="7200"
```

### 3. Command Line Arguments

Override settings via command line:

```bash
# Start with custom settings
python sf.py -l 0.0.0.0:8080 -d /custom/database.db

# Workflow with custom options
python sfworkflow.py multi-scan ws_123 \
  --options '{"_maxthreads": 2, "_timeout": 600}'
```

### 4. Web Interface

Configure settings through the web interface:
1. Navigate to **Settings** → **Global Settings**
2. Modify configuration values
3. Click **Save Changes**
4. Restart SpiderFoot if required

## Core Configuration Options

### Web Server Settings

```ini
[global]
# Bind address (127.0.0.1 for localhost only, 0.0.0.0 for all interfaces)
__webaddr = 127.0.0.1

# Port number
__webport = 5001

# Enable HTTPS
__sslcert = /path/to/cert.pem
__sslkey = /path/to/key.pem

# Session timeout (seconds)
__sessionsettings = 3600

# Enable authentication
__authentication = true
__username = admin
__password = spiderfoot
```

### Database Configuration

```ini
[global]
# SQLite database path
__database = spiderfoot.db

# Database connection timeout
__dbtimeout = 30

# Enable database optimization
__dboptimize = true

# Maximum database size (MB)
__dbmaxsize = 1000
```

### Logging Configuration

```ini
[global]
# Log file path (empty for console output)
__logfile = spiderfoot.log

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
__loglevel = INFO

# Log format
__logformat = %(asctime)s [%(levelname)s] %(name)s: %(message)s

# Enable module logging
__modulelogging = true
```

## Module Configuration

### API Key Configuration

Many modules require API keys for external services:

```ini
[modules]
# VirusTotal
sfp_virustotal.api_key = your_virustotal_api_key
sfp_virustotal.verify = true

# Shodan
sfp_shodan.api_key = your_shodan_api_key
sfp_shodan.verify = true

# Hunter.io
sfp_hunter.api_key = your_hunter_api_key

# SecurityTrails
sfp_securitytrails.api_key = your_securitytrails_api_key

# PassiveTotal
sfp_passivetotal.api_key = your_passivetotal_api_key
sfp_passivetotal.secret = your_passivetotal_secret

# Recorded Future
sfp_recordedfuture.api_key = your_recordedfuture_api_key
```

### Module-Specific Settings

```ini
[modules]
# DNS resolution
sfp_dnsresolve.timeout = 30
sfp_dnsresolve.servers = 8.8.8.8,1.1.1.1

# Port scanning
sfp_portscan_tcp.timeout = 5
sfp_portscan_tcp.maxports = 1000
sfp_portscan_tcp.randomize = true

# Web crawling
sfp_spider.maxpages = 100
sfp_spider.maxdirs = 50
sfp_spider.timeout = 30

# SSL certificate analysis
sfp_ssl.timeout = 30
sfp_ssl.verify_chains = true
```

## Workflow Configuration

### Multi-Target Scanning

```ini
[workflow]
# Maximum concurrent scans
max_concurrent_scans = 5

# Default scan timeout (seconds)
scan_timeout = 3600

# Enable progress monitoring
progress_monitoring = true

# Scan result retention (days)
result_retention = 90
```

### Correlation Settings

```ini
[correlation]
# Enable automatic correlation
auto_correlation = true

# Correlation confidence threshold (0-100)
confidence_threshold = 75

# Maximum correlation results per rule
max_results_per_rule = 100

# Enable parallel processing
parallel_processing = true

# Custom correlation rules directory
custom_rules_dir = /path/to/custom/rules
```

### CTI Report Configuration

```ini
[cti]
# MCP server configuration
mcp_server_url = http://localhost:8000
mcp_api_key = your_mcp_api_key
mcp_timeout = 300

# Default report format
default_format = json

# Report template directory
template_dir = /path/to/templates

# Enable report caching
cache_reports = true
```

## Performance Configuration

### Scanning Performance

```ini
[performance]
# Global thread limits
max_threads = 10
max_concurrent_modules = 50

# Request timeouts
http_timeout = 30
dns_timeout = 10

# Rate limiting
requests_per_second = 10
delay_between_requests = 0.1

# Memory management
max_memory_usage = 1024  # MB
garbage_collection_interval = 3600  # seconds
```

### Database Performance

```ini
[database]
# Enable WAL mode for better concurrency
wal_mode = true

# Database cache size (KB)
cache_size = 10000

# Synchronous mode (OFF, NORMAL, FULL)
synchronous = NORMAL

# Journal mode (DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF)
journal_mode = WAL

# Enable foreign keys
foreign_keys = true
```

## Network Configuration

### Proxy Settings

```ini
[network]
# HTTP proxy
http_proxy = http://proxy.example.com:8080

# HTTPS proxy
https_proxy = http://proxy.example.com:8080

# SOCKS proxy
socks_proxy = socks5://proxy.example.com:1080

# No proxy for these hosts
no_proxy = localhost,127.0.0.1,.internal.com

# Proxy authentication
proxy_username = username
proxy_password = password
```

### DNS Configuration

```ini
[network]
# Custom DNS servers
dns_servers = 8.8.8.8,1.1.1.1,9.9.9.9

# DNS timeout
dns_timeout = 10

# Enable DNS over HTTPS
dns_over_https = true
dns_over_https_url = https://cloudflare-dns.com/dns-query

# DNS cache TTL
dns_cache_ttl = 300
```

### User Agent Configuration

```ini
[network]
# Default user agent
user_agent = Mozilla/5.0 (compatible; SpiderFoot/5.0; +https://spiderfoot.net)

# Rotate user agents
rotate_user_agents = true

# Custom user agent list
user_agents = Mozilla/5.0 (Windows NT 10.0; Win64; x64),Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)
```

## Security Configuration

### Authentication Settings

```ini
[security]
# Enable web authentication
authentication_enabled = true

# Default credentials
default_username = admin
default_password = spiderfoot

# Session settings
session_timeout = 3600
session_secure = true
session_httponly = true

# Password policy
min_password_length = 8
require_special_chars = true
```

### API Security

```ini
[api]
# Enable API authentication
api_auth_enabled = true

# API key
api_key = your_secure_api_key

# Rate limiting
api_rate_limit = 100  # requests per minute
api_burst_limit = 20

# CORS settings
cors_enabled = true
cors_origins = http://localhost:3000,https://yourdomain.com
```

### Data Protection

```ini
[security]
# Encrypt sensitive data
encrypt_database = true
encryption_key = your_encryption_key

# Data anonymization
anonymize_ips = false
anonymize_domains = false

# Audit logging
audit_logging = true
audit_log_file = audit.log
```

## Module-Specific Configuration Examples

### VirusTotal Configuration

```ini
[modules]
sfp_virustotal.api_key = your_api_key
sfp_virustotal.verify = true
sfp_virustotal.timeout = 30
sfp_virustotal.delay = 15  # Rate limiting delay
sfp_virustotal.cohostsamedomain = false
```

### Shodan Configuration

```ini
[modules]
sfp_shodan.api_key = your_api_key
sfp_shodan.verify = true
sfp_shodan.timeout = 30
sfp_shodan.maxpages = 10
```

### Port Scanner Configuration

```ini
[modules]
sfp_portscan_tcp.timeout = 5
sfp_portscan_tcp.maxports = 1000
sfp_portscan_tcp.randomize = true
sfp_portscan_tcp.source_port = 0
sfp_portscan_tcp.interface = 
```

## Environment-Specific Configurations

### Development Environment

```ini
[global]
__loglevel = DEBUG
__modulelogging = true
__webaddr = 127.0.0.1

[workflow]
max_concurrent_scans = 2
scan_timeout = 1800

[performance]
max_threads = 3
```

### Production Environment

```ini
[global]
__loglevel = WARNING
__webaddr = 0.0.0.0
__sslcert = /etc/ssl/certs/spiderfoot.pem
__sslkey = /etc/ssl/private/spiderfoot.key

[workflow]
max_concurrent_scans = 10
scan_timeout = 7200

[performance]
max_threads = 20
max_memory_usage = 4096
```

### High-Performance Environment

```ini
[global]
__database = /fast/storage/spiderfoot.db

[workflow]
max_concurrent_scans = 20

[performance]
max_threads = 50
max_concurrent_modules = 100

[database]
cache_size = 50000
wal_mode = true
```

## Configuration Validation

### Validate Configuration

```bash
# Validate configuration file
python sf.py --validate-config

# Test database connection
python sf.py --test-database

# Verify module configuration
python sf.py --test-modules
```

### Configuration Debugging

```python
# Python script to debug configuration
from spiderfoot import SpiderFootConfig

config = SpiderFootConfig()
print("Current configuration:")
for key, value in config.get_all().items():
    print(f"{key}: {value}")
```

## Best Practices

### Security Best Practices

1. **Change default credentials** for web interface
2. **Use HTTPS** in production environments
3. **Restrict web interface access** to trusted networks
4. **Rotate API keys** regularly
5. **Enable audit logging** for compliance

### Performance Best Practices

1. **Adjust thread limits** based on system resources
2. **Use appropriate timeouts** to prevent hanging
3. **Monitor memory usage** during large scans
4. **Enable database optimization** for better performance
5. **Use rate limiting** to avoid being blocked

### Operational Best Practices

1. **Regular backups** of configuration and database
2. **Monitor log files** for errors and warnings
3. **Update modules** regularly for latest features
4. **Test configuration changes** in development first
5. **Document customizations** for team knowledge

## Troubleshooting Configuration Issues

### Common Issues

```bash
# Configuration file not found
ls -la spiderfoot.conf
# Create default configuration if missing

# Permission issues
chmod 644 spiderfoot.conf
chown spiderfoot:spiderfoot spiderfoot.conf

# Invalid configuration values
python sf.py --validate-config

# Module configuration errors
python sf.py -M  # List all modules and their status
```

### Debugging Tips

```bash
# Enable debug logging
export SPIDERFOOT_LOG_LEVEL=DEBUG

# Check effective configuration
python -c "from spiderfoot import SpiderFootConfig; print(SpiderFootConfig().get_all())"

# Test specific module configuration
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v
```

## Migration and Backup

### Configuration Backup

```bash
# Backup configuration
cp spiderfoot.conf spiderfoot.conf.backup.$(date +%Y%m%d)

# Backup entire configuration directory
tar czf spiderfoot-config-backup.tar.gz spiderfoot.conf *.key *.pem
```

### Migration Between Versions

```bash
# Compare configurations
diff spiderfoot.conf.old spiderfoot.conf.new

# Merge custom settings
python migrate_config.py --old spiderfoot.conf.old --new spiderfoot.conf.new
```

For more advanced configuration topics, see the [Advanced Configuration Guide](advanced/performance_tuning.md).
