# API Reference

*Author: poppopjmp*

SpiderFoot provides both a REST API and a Python API for integration, automation, and advanced workflows. Use the API to automate scans, retrieve results, and integrate SpiderFoot with other tools and platforms. The enhanced SpiderFoot v5.3.3 includes 277 modules with advanced capabilities for TikTok OSINT, blockchain analytics, performance optimization, and AI-powered analysis.

---

## REST API

The REST API allows you to manage scans, retrieve results, and interact with SpiderFoot programmatically.

### Core Endpoints

- **List scans:**
  - `GET /api/scans` — Returns a list of all scans.
- **Start a scan:**
  - `POST /api/scans` — Start a new scan. JSON body: `{ "target": "example.com", "type": "DOMAIN_NAME", "modules": ["sfp_dnsresolve", "sfp_ssl"] }`
- **Get scan results:**
  - `GET /api/scans/{scanId}/results` — Retrieve results for a specific scan.
- **Delete a scan:**
  - `DELETE /api/scans/{scanId}` — Remove a scan and its results.

### Enhanced API Endpoints

- **Performance metrics:**
  - `GET /api/performance/stats` — Get performance optimization statistics
  - `GET /api/performance/cache/stats` — Get cache performance metrics
- **Correlation data:**
  - `GET /api/correlation/entities` — Get correlated entity relationships
  - `GET /api/correlation/patterns` — Get detected patterns and anomalies
- **Blockchain analytics:**
  - `GET /api/blockchain/address/{address}` — Get blockchain address analysis
  - `GET /api/blockchain/risk/{address}` — Get risk assessment for address
- **AI analysis:**
  - `GET /api/ai/summary/{scanId}` — Get AI-generated threat intelligence summary
  - `POST /api/ai/analyze` — Request AI analysis of specific events

### Authentication

- By default, the API is open on localhost. For production, use a reverse proxy or firewall to restrict access.
- API keys and authentication can be configured in the web UI (see [Configuration](configuration.md)).
- JWT tokens are supported for enhanced security with configurable expiry times.
- Rate limiting is automatically applied to prevent API abuse.
- Always secure your API endpoints in production environments.

### Example: Start a Enhanced Scan (cURL)

```sh
# Basic scan with new modules
curl -X POST http://127.0.0.1:5001/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "type": "DOMAIN_NAME", "modules": ["sfp_dnsresolve", "sfp_ssl", "sfp_performance_optimizer"]}'

# TikTok OSINT scan
curl -X POST http://127.0.0.1:5001/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "@username", "type": "SOCIAL_MEDIA", "modules": ["sfp_tiktok_osint", "sfp_advanced_correlation"]}'

# Blockchain investigation
curl -X POST http://127.0.0.1:5001/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "type": "BITCOIN_ADDRESS", "modules": ["sfp_blockchain_analytics"]}'
```

---

## Python API Example

You can also use SpiderFoot as a Python library for custom automation:

```python
from spiderfoot.sflib import SpiderFoot
from spiderfoot.scan_service.scanner import startSpiderFootScanner

# Basic scan setup
sf = SpiderFoot()
scanner = startSpiderFootScanner(
    target="example.com",
    targetType="DOMAIN_NAME",
    modules=["sfp_dnsresolve", "sfp_ssl", "sfp_performance_optimizer"]
)

# Enhanced TikTok OSINT
tiktok_scanner = startSpiderFootScanner(
    target="@username",
    targetType="SOCIAL_MEDIA",
    modules=["sfp_tiktok_osint", "sfp_advanced_correlation"]
)

# Blockchain analytics
blockchain_scanner = startSpiderFootScanner(
    target="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    targetType="BITCOIN_ADDRESS", 
    modules=["sfp_blockchain_analytics"]
)

# Performance monitoring
from modules.sfp_performance_optimizer import sfp_performance_optimizer
optimizer = sfp_performance_optimizer()
cache_stats = optimizer.get_cache_stats()
performance_metrics = optimizer.get_performance_stats()

# Advanced correlation
from modules.sfp_advanced_correlation import sfp_advanced_correlation
correlator = sfp_advanced_correlation()
entity_relationships = correlator.get_entity_relationships()
```

## Available Module Categories

SpiderFoot v5.3.3 includes 277 modules organized into the following categories:

### Core Categories

- **DNS/Network Analysis**: 45+ modules for network reconnaissance
- **Threat Intelligence**: 35+ modules for threat data correlation
- **Social Media**: 25+ modules including TikTok, Twitter, LinkedIn
- **Search Engines**: 20+ modules for web intelligence gathering
- **Email/Communication**: 18+ modules for email investigation
- **Cryptocurrency/Blockchain**: 12+ modules for financial investigation

### Enhanced Categories (New in v5.3.3)

- **AI-Powered Analysis**: Machine learning and AI summarization
- **Performance Optimization**: Caching and resource management
- **Advanced Correlation**: Cross-platform entity resolution
- **Behavioral Analytics**: Pattern detection and anomaly identification

### Security and Compliance

- **Input Validation**: Comprehensive sanitization and validation
- **Rate Limiting**: Adaptive throttling and abuse prevention
- **Audit Logging**: Security event tracking and compliance
- **CSRF Protection**: Cross-site request forgery prevention

---

For detailed information about individual modules, see the [Modules Guide](modules.md).

## Python API Advanced Usage

```python
# See the source code and docstrings for more advanced usage.
# The Python API is ideal for integrating SpiderFoot into custom scripts and pipelines.
```

---

## Best Practices

- Always restrict API access in production.
- Use API keys or authentication for automation and integrations.
- Monitor API usage and logs for errors or unauthorized access.
- Refer to the webapp for the latest API endpoints and documentation.

---
