# Module Migration Guide: SpiderFootPlugin → SpiderFootModernPlugin

This guide explains how to migrate existing SpiderFoot modules from the legacy
`SpiderFootPlugin` base class to `SpiderFootModernPlugin`, which provides direct
access to the extracted service layer (HttpService, DnsService, CacheService, etc.).

## Why Migrate?

| Feature | Legacy (`SpiderFootPlugin`) | Modern (`SpiderFootModernPlugin`) |
|---|---|---|
| HTTP requests | `self.sf.fetchUrl()` | `self.fetch_url()` → HttpService |
| DNS resolution | `self.sf.resolveHost()` | `self.resolve_host()` → DnsService |
| Caching | Manual / none | `self.cache_get()` / `self.cache_put()` → CacheService |
| Metrics | None | Automatic Prometheus metrics |
| Event publishing | `self.notifyListeners()` | `self.notifyListeners()` + `self.publish_event()` |
| Connection pooling | No | Yes (via HttpService) |
| Service discovery | Coupled to `self.sf` god object | Decoupled via ServiceRegistry |

## Migration Steps

### Step 1: Change the import and base class

```python
# BEFORE
from spiderfoot import SpiderFootPlugin

class sfp_example(SpiderFootPlugin):
    ...

# AFTER
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_example(SpiderFootModernPlugin):
    ...
```

### Step 2: Update setup()

```python
# BEFORE
def setup(self, sfc, userOpts=dict()):
    self.sf = sfc
    self.results = self.tempStorage()
    for opt in list(userOpts.keys()):
        self.opts[opt] = userOpts[opt]

# AFTER
def setup(self, sfc, userOpts=None):
    super().setup(sfc, userOpts or {})
    self.results = self.tempStorage()
    # Services (self.http, self.dns, self.cache) are now available
```

**Key point**: Always call `super().setup(sfc, userOpts)` — this wires both
the legacy `self.sf` and the modern services.

### Step 3: Replace self.sf.fetchUrl() with self.fetch_url()

```python
# BEFORE
res = self.sf.fetchUrl(
    url,
    timeout=self.opts['_fetchtimeout'],
    useragent=self.opts['_useragent'],
    headers=headers,
)

# AFTER
res = self.fetch_url(
    url,
    timeout=self.opts.get('_fetchtimeout', 15),
    headers=headers,
)
```

The response format is the same dict with keys: `content`, `code`, `headers`,
`realurl`, `status`.

### Step 4: Replace self.sf.resolveHost() with self.resolve_host()

```python
# BEFORE
addrs = self.sf.resolveHost(hostname)
addrs6 = self.sf.resolveHost6(hostname)

# AFTER
addrs = self.resolve_host(hostname)
addrs6 = self.resolve_host6(hostname)
```

### Step 5: Add caching (optional, new capability)

```python
# Check cache before API call
cached = self.cache_get(f"mymodule:{query}")
if cached is not None:
    return cached

# After API call, store result
self.cache_put(f"mymodule:{query}", result, ttl=3600)
```

### Step 6: Publish events to EventBus (optional, new capability)

```python
# After notifyListeners (for legacy compat), also publish to EventBus
self.notifyListeners(evt)
self.publish_event("scan.event.new", {
    "type": evt.eventType,
    "data": evt.data,
    "module": self.__name__,
})
```

## Complete Example

See the migrated modules for real-world examples:

- **`modules/sfp_ipapico_modern.py`** — Simplest migration (HTTP only, no API key)
- **`modules/sfp_ipinfo_modern.py`** — Migration with API key auth + response caching

## Backward Compatibility

- `self.sf` still works exactly as before
- `self.notifyListeners()` is unchanged
- `self.tempStorage()` is unchanged
- All legacy module methods are inherited
- If ServiceRegistry is not configured, modern methods silently fall back to `self.sf`
- You can mix legacy and modern calls in the same module

## Testing

Migrated modules can be tested the same way as legacy modules. The services
are lazily resolved, so unit tests that mock `self.sf` still work:

```python
def test_handleEvent(self):
    mod = sfp_example()
    mod.sf = MockSpiderFoot()  # Legacy mock still works
    mod.setup(mod.sf, {})
    # ... test as before
```

## Checklist

- [ ] Change base class to `SpiderFootModernPlugin`
- [ ] Update `setup()` to call `super().setup()`
- [ ] Replace `self.sf.fetchUrl()` → `self.fetch_url()`
- [ ] Replace `self.sf.resolveHost()` → `self.resolve_host()` (if applicable)
- [ ] Add response caching via `self.cache_get()`/`self.cache_put()` (optional)
- [ ] Add type hints (optional but recommended)
- [ ] Run existing tests to verify backward compatibility
- [ ] Test with ServiceRegistry enabled to verify modern path
