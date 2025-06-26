# API Reference

## REST API

- List scans: `GET /api/scans`
- Start scan: `POST /api/scans`
- Get results: `GET /api/scans/{scanId}/results`

## Python API Example

```python
from sflib import SpiderFoot
from sfscan import startSpiderFootScanner

sf = SpiderFoot()
scanner = startSpiderFootScanner(
    target="example.com",
    targetType="DOMAIN_NAME",
    modules=["sfp_dnsresolve", "sfp_ssl"]
)
```

See the webapp for the latest API endpoints.
