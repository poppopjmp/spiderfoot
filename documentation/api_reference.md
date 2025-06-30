# API Reference

*Author: poppopjmp*

SpiderFoot provides both a REST API and a Python API for integration, automation, and advanced workflows. Use the API to automate scans, retrieve results, and integrate SpiderFoot with other tools and platforms.

---

## REST API

The REST API allows you to manage scans, retrieve results, and interact with SpiderFoot programmatically.

- **List scans:**
  - `GET /api/scans` — Returns a list of all scans.
- **Start a scan:**
  - `POST /api/scans` — Start a new scan. JSON body: `{ "target": "example.com", "type": "DOMAIN_NAME", "modules": ["sfp_dnsresolve", "sfp_ssl"] }`
- **Get scan results:**
  - `GET /api/scans/{scanId}/results` — Retrieve results for a specific scan.
- **Delete a scan:**
  - `DELETE /api/scans/{scanId}` — Remove a scan and its results.

### Authentication

- By default, the API is open on localhost. For production, use a reverse proxy or firewall to restrict access.
- API keys and authentication can be configured in the web UI (see [Configuration](configuration.md)).
- Always secure your API endpoints in production environments.

### Example: Start a Scan (cURL)

```sh
curl -X POST http://127.0.0.1:5001/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "type": "DOMAIN_NAME", "modules": ["sfp_dnsresolve", "sfp_ssl"]}'
```

---

## Python API Example

You can also use SpiderFoot as a Python library for custom automation:

```python
from spiderfoot.sflib import SpiderFoot
from spiderfoot.scan_service.scanner import startSpiderFootScanner

sf = SpiderFoot()
scanner = startSpiderFootScanner(
    target="example.com",
    targetType="DOMAIN_NAME",
    modules=["sfp_dnsresolve", "sfp_ssl"]
)
```

- See the source code and docstrings for more advanced usage.
- The Python API is ideal for integrating SpiderFoot into custom scripts and pipelines.

---

## Best Practices

- Always restrict API access in production.
- Use API keys or authentication for automation and integrations.
- Monitor API usage and logs for errors or unauthorized access.
- Refer to the webapp for the latest API endpoints and documentation.

---
