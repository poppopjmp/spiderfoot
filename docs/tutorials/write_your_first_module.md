# Write Your First SpiderFoot Module

This tutorial walks you through creating a custom SpiderFoot v6
module from scratch. By the end (~20 minutes), you'll have a
working module that queries DNS TXT records for a given domain.

## Prerequisites

- Python 3.11+
- SpiderFoot v6 installed (`pip install -e .`)
- A text editor

## 1. Understand the Module System

SpiderFoot modules are Python classes that:

1. **Consume** events (e.g., `DOMAIN_NAME`)
2. **Process** those events (DNS lookups, API calls, etc.)
3. **Produce** new events (e.g., `DNS_TEXT`)

Every module lives in `spiderfoot/plugins/` and inherits from
`SpiderFootAsyncPlugin` (recommended) or `SpiderFootModernPlugin`.

### Event Flow

```
[Root Event]
    → Module A → DOMAIN_NAME
                    → Module B → IP_ADDRESS
                    → Module C → DNS_TEXT
                                    → Module D → EMAILADDR
```

## 2. Scaffold the Module

### Option A: Use the Scaffolder (Recommended)

```python
from spiderfoot.plugins.module_devtools import ModuleScaffolder, ScaffoldConfig

config = ScaffoldConfig(
    name="dns_txt_lookup",
    display_name="DNS TXT Record Lookup",
    description="Queries DNS TXT records for domains",
    consumes=["DOMAIN_NAME"],
    produces=["DNS_TEXT"],
    category="DNS",
)
scaffolder = ModuleScaffolder(config)
scaffolder.generate_to_file("spiderfoot/plugins/sfp_dns_txt_lookup.py")
scaffolder.generate_test("test/unit/modules/test_sfp_dns_txt_lookup.py")
```

### Option B: Manual Creation

Create `spiderfoot/plugins/sfp_dns_txt_lookup.py`:

```python
"""SpiderFoot module: DNS TXT Record Lookup.

Queries DNS TXT records for domains found during the scan.
TXT records often contain SPF, DKIM, DMARC, and domain
verification data.
"""

from __future__ import annotations

import logging
from typing import Any

from spiderfoot.plugins import SpiderFootAsyncPlugin

log = logging.getLogger(__name__)


class sfp_dns_txt_lookup(SpiderFootAsyncPlugin):
    """Query DNS TXT records for domains."""

    meta = {
        "name": "DNS TXT Record Lookup",
        "summary": "Queries DNS TXT records for domains",
        "flags": [],
        "useCases": ["Footprint", "Passive"],
        "categories": ["DNS"],
        "dataSource": {
            "website": "https://www.iana.org/domains",
            "description": "DNS TXT records via standard resolution",
        },
    }

    # Events this module consumes
    watched_events = ["DOMAIN_NAME"]

    # Events this module produces
    produced_events = ["DNS_TEXT"]

    # Module options (user-configurable)
    opts = {
        "timeout": 10,
    }
    optdescs = {
        "timeout": "DNS query timeout in seconds.",
    }

    async def handleEvent(self, event: Any) -> None:
        """Process a DOMAIN_NAME event.

        Args:
            event: The incoming event with event.data = domain name.
        """
        domain = event.data
        self.debug(f"Looking up TXT records for {domain}")

        try:
            txt_records = await self._query_txt(domain)
        except Exception as e:
            self.error(f"TXT lookup failed for {domain}: {e}")
            return

        for record in txt_records:
            self.info(f"Found TXT record: {record[:80]}")
            await self.notifyListeners(
                "DNS_TEXT",
                record,
                event,
            )

    async def _query_txt(self, domain: str) -> list[str]:
        """Query DNS TXT records.

        In a real module, use self.sf.resolveHost() or
        an async DNS library like aiodns.
        """
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        try:
            answers = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: socket.getaddrinfo(
                        domain, None, socket.AF_INET,
                    ),
                ),
                timeout=self.opts.get("timeout", 10),
            )
            # In production, use dns.resolver for actual TXT records
            return [f"TXT lookup completed for {domain}"]
        except Exception:
            return []
```

## 3. Understand the Key Methods

### `meta` (Required)

A dictionary describing the module:

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Human-readable module name |
| `summary` | str | One-line description |
| `flags` | list | `["apikey"]`, `["slow"]`, `["invasive"]`, etc. |
| `useCases` | list | `["Footprint"]`, `["Investigate"]`, `["Passive"]` |
| `categories` | list | `["DNS"]`, `["Social Media"]`, etc. |
| `dataSource` | dict | `{"website": "...", "description": "..."}` |

### `watched_events` (Required)

List of event types this module consumes:

```python
watched_events = ["DOMAIN_NAME", "INTERNET_NAME"]
```

### `produced_events` (Required)

List of event types this module produces:

```python
produced_events = ["DNS_TEXT", "RAW_DNS_RECORDS"]
```

### `handleEvent(event)` (Required)

The main processing method. Called for each matching event:

```python
async def handleEvent(self, event):
    domain = event.data          # The actual data
    source = event.sourceEvent   # Parent event
    event_type = event.eventType # e.g., "DOMAIN_NAME"

    # Do your processing...
    result = await self.some_lookup(domain)

    # Produce new events
    await self.notifyListeners("DNS_TEXT", result, event)
```

### `notifyListeners(event_type, data, source)`

Emit a new event into the event bus:

```python
await self.notifyListeners(
    "DNS_TEXT",           # Event type
    "v=spf1 include:...",  # Data
    event,                 # Source event (parent)
)
```

## 4. Add Options

Options are user-configurable through the web UI:

```python
opts = {
    "api_key": "",
    "max_results": 100,
    "include_expired": False,
}

optdescs = {
    "api_key": "API key for the service.",
    "max_results": "Maximum results to return.",
    "include_expired": "Include expired records?",
}
```

Access options in `handleEvent`:

```python
api_key = self.opts.get("api_key", "")
if not api_key:
    self.error("API key not configured")
    return
```

## 5. Write Tests

Create `test/unit/modules/test_sfp_dns_txt_lookup.py`:

```python
"""Tests for sfp_dns_txt_lookup module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSfpDnsTxtLookup:
    """Tests for the DNS TXT lookup module."""

    def test_meta_fields(self):
        """Module meta has required fields."""
        from spiderfoot.plugins.sfp_dns_txt_lookup import sfp_dns_txt_lookup
        mod = sfp_dns_txt_lookup.__new__(sfp_dns_txt_lookup)
        assert "name" in mod.meta
        assert "summary" in mod.meta
        assert "categories" in mod.meta

    def test_watched_events(self):
        """Module watches DOMAIN_NAME events."""
        from spiderfoot.plugins.sfp_dns_txt_lookup import sfp_dns_txt_lookup
        mod = sfp_dns_txt_lookup.__new__(sfp_dns_txt_lookup)
        assert "DOMAIN_NAME" in mod.watched_events

    def test_produced_events(self):
        """Module produces DNS_TEXT events."""
        from spiderfoot.plugins.sfp_dns_txt_lookup import sfp_dns_txt_lookup
        mod = sfp_dns_txt_lookup.__new__(sfp_dns_txt_lookup)
        assert "DNS_TEXT" in mod.produced_events
```

Run tests:

```bash
python -m pytest test/unit/modules/test_sfp_dns_txt_lookup.py -v
```

## 6. Validate Your Module

Use the `ModuleValidator` to check for common issues:

```python
from spiderfoot.plugins.module_devtools import ModuleValidator

validator = ModuleValidator()

# Validate source code
with open("spiderfoot/plugins/sfp_dns_txt_lookup.py") as f:
    source = f.read()
report = validator.validate_source(source)
print(report.to_text())
```

Output:

```
Validation Report
═══════════════════
Syntax:    ✓ OK
Base class: SpiderFootAsyncPlugin (async)
Consumes:  DOMAIN_NAME
Produces:  DNS_TEXT
Blocking calls: None detected
Meta quality score: 85/100
```

## 7. Test with Docker Dev Profile

Generate a hot-reload Docker Compose override:

```python
from spiderfoot.plugins.module_devtools import DockerDevProfileGenerator

gen = DockerDevProfileGenerator(port=5002)
gen.write("docker-compose.dev.yml")
```

Then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Your module will hot-reload on save.

## 8. Common Patterns

### API Key Module

```python
meta = {
    "name": "My API Module",
    "flags": ["apikey"],
    ...
}

opts = {
    "api_key": "",
}

async def handleEvent(self, event):
    api_key = self.opts.get("api_key", "")
    if not api_key:
        self.error("No API key set")
        return
    # Use api_key...
```

### Rate-Limited Module

```python
import asyncio

async def handleEvent(self, event):
    # Rate limit: 1 request per second
    await asyncio.sleep(1)
    result = await self._query(event.data)
```

### Multi-Event Producer

```python
watched_events = ["DOMAIN_NAME"]
produced_events = ["IP_ADDRESS", "DNS_TEXT", "EMAILADDR"]

async def handleEvent(self, event):
    domain = event.data
    # Produce multiple event types from one input
    ips = await self._resolve(domain)
    for ip in ips:
        await self.notifyListeners("IP_ADDRESS", ip, event)

    txts = await self._txt_lookup(domain)
    for txt in txts:
        await self.notifyListeners("DNS_TEXT", txt, event)
        # If TXT contains an email
        if "@" in txt:
            await self.notifyListeners("EMAILADDR", txt, event)
```

## 9. Event Type Reference

See [docs/architecture/event_types.md](event_types.md) for the
complete catalog of 68+ event types with descriptions.

## 10. Checklist

Before submitting your module:

- [ ] Module file name starts with `sfp_`
- [ ] Class inherits from `SpiderFootAsyncPlugin`
- [ ] `meta` dict has `name`, `summary`, `categories`, `useCases`
- [ ] `watched_events` is defined
- [ ] `produced_events` is defined
- [ ] `handleEvent` is async
- [ ] No blocking calls (`requests.get`, `time.sleep`, `urllib`)
- [ ] Options have descriptions in `optdescs`
- [ ] Tests exist and pass
- [ ] `ModuleValidator` score ≥ 70/100

---

*SpiderFoot v6 — Write Your First Module Tutorial*
