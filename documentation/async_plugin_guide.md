# Async Plugin Guide

This guide covers writing SpiderFoot modules that use native async I/O for high-throughput HTTP and DNS operations.

---

## Overview

SpiderFoot v6.0.0 introduces `SpiderFootAsyncPlugin`, a base class that provides native `aiohttp` HTTP requests and `aiodns` DNS resolution — no `run_in_executor` wrapping needed. Sync modules using `SpiderFootPlugin` are unaffected.

### When to Use Async

Use `SpiderFootAsyncPlugin` when your module:

- Makes **many HTTP requests** per event (e.g., API pagination, bulk lookups)
- Performs **concurrent DNS resolution** (e.g., subdomain brute-force)
- Benefits from **connection pooling** across calls

For simple modules with 1–2 HTTP calls, the standard sync `SpiderFootPlugin` is sufficient.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│              SpiderFootPlugin (sync)              │
│         threadWorker() → handleEvent()            │
├──────────────────────────────────────────────────┤
│          SpiderFootAsyncPlugin (async)            │
│  threadWorker() → _asyncDispatch() → handleEvent()│
│                      ↓                            │
│        async_network.async_fetch_url()            │
│        async_network.async_resolve_host()         │
│                      ↓                            │
│          aiohttp.ClientSession (pooled)           │
│          aiodns.DNSResolver                       │
└──────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `async_network` | `spiderfoot/sflib/async_network.py` | Session pool, HTTP fetch, DNS resolve |
| `SpiderFootAsyncPlugin` | `spiderfoot/plugins/async_plugin.py` | Base class for async modules |
| `plugin.py` dispatcher | `spiderfoot/plugins/plugin.py` | Detects async `handleEvent` and routes via `_asyncDispatch()` |

---

## Writing an Async Module

### 1. Subclass `SpiderFootAsyncPlugin`

```python
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

class sfp_example_async(SpiderFootAsyncPlugin):
    """Example async module."""

    meta = {
        'name': "Example Async Module",
        'summary': "Demonstrates async HTTP and DNS lookups.",
        'flags': [],
        'useCases': ["Investigate"],
        'categories': ["Search Engines"],
    }

    # Declare watched/produced event types as usual
    watchedEvents = ["DOMAIN_NAME"]
    producedEvents = ["RAW_RIR_DATA"]

    async def handleEvent(self, event):
        """Handle an event asynchronously."""
        domain = event.data

        # Native async HTTP — no executor wrapping
        result = await self.async_fetch_url(f"https://api.example.com/lookup/{domain}")
        if result['code'] == "200":
            self.produce_event(result['content'], "RAW_RIR_DATA", event)

        # Native async DNS
        ips = await self.async_resolve_host(domain)
        for ip in ips:
            self.produce_event(ip, "IP_ADDRESS", event)
```

### 2. Key Differences from Sync Modules

| Feature | Sync (`SpiderFootPlugin`) | Async (`SpiderFootAsyncPlugin`) |
|---------|--------------------------|--------------------------------|
| `handleEvent` | Regular method | `async def handleEvent` |
| HTTP requests | `self.sf.fetchUrl()` | `await self.async_fetch_url()` |
| DNS lookups | `self.sf.resolveHost()` | `await self.async_resolve_host()` |
| Connection pooling | Per-call | Per-module session (pooled) |
| Dispatcher | `poolExecute()` | `_asyncDispatch()` via `run_coroutine_threadsafe()` |

### 3. Available Async Methods

From `SpiderFootAsyncPlugin`:

```python
# HTTP
result = await self.async_fetch_url(url, headers=None, timeout=30)
# Returns: {'code': str, 'status': str, 'content': str, 'headers': dict, 'realurl': str}

# DNS A records
ips = await self.async_resolve_host(hostname)

# DNS AAAA records
ipv6s = await self.async_resolve_host6(hostname)

# Reverse DNS
hostnames = await self.async_reverse_resolve(ip_address)

# DNS wildcard check
is_wildcard = await self.async_check_dns_wildcard(domain)
```

From `async_network` (lower-level):

```python
from spiderfoot.sflib.async_network import (
    async_fetch_url,
    async_resolve_host,
    async_resolve_host6,
    async_reverse_resolve,
    async_check_dns_wildcard,
    get_session,
    close_session,
    close_all_sessions,
)
```

---

## Session Lifecycle

aiohttp sessions are **cached per `(module_name, event_loop)` tuple**:

1. **First call**: Session is created and cached
2. **Subsequent calls**: Reuses the cached session (connection pooling)
3. **Module finish**: `finished()` calls `close_session()` for the module
4. **Scan end**: `shutdown_event_loop()` calls `close_all_sessions()`

You typically don't need to manage sessions manually — the base class handles it.

---

## Detection and Dispatch

The `plugin.py` base class automatically detects async modules:

```python
# In plugin.py threadWorker():
self._is_async_handler = inspect.iscoroutinefunction(self.handleEvent)

if self._is_async_handler:
    self._asyncDispatch(self.handleEvent, event)
else:
    self.poolExecute(self.handleEvent, event)
```

`_asyncDispatch()` uses `asyncio.run_coroutine_threadsafe()` to submit the coroutine to the shared event loop with a 300-second timeout.

---

## Dependencies

The async engine requires:

```
aiohttp>=3.9.0,<4.0.0    # Already in requirements.txt
aiodns>=3.0.0,<4.0.0     # Already in requirements.txt
```

`aiodns` is optional — if not installed, DNS resolution falls back to `loop.getaddrinfo()`.

---

## Performance Characteristics

| Metric | Sync Plugin | Async Plugin |
|--------|-------------|--------------|
| HTTP connections | New per call | Pooled per module |
| DNS resolution | Blocking | Non-blocking (aiodns) |
| Concurrent I/O | Thread-limited | Event loop native |
| Memory overhead | Thread stack per call | Coroutine (~2KB) |

Async modules are especially beneficial for:
- Modules making 50+ HTTP calls per event
- Subdomain brute-force modules
- Bulk API pagination
