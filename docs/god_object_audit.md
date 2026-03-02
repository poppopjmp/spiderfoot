# God Object Audit — Cycle 27

## Summary

`spiderfoot/sflib/core.py` (SpiderFoot class, ~690 lines) acts as a "god object"
facade. It holds 27 thin wrapper methods that simply forward to module-level
helper functions already importable from `spiderfoot.sflib.helpers` and
`spiderfoot.sflib.network`.

### Impact

| Metric | Value |
|--------|-------|
| Thin wrapper methods | 27 |
| Lines spent on wrappers | ~120 (lines 172–292) |
| Total core.py lines | ~690 |
| Wrapper % of core.py | ~17% |

### Wrapper Inventory

| # | Method | Delegates to | Module |
|---|--------|-------------|--------|
| 1 | `hashstring(s)` | `hashstring(s)` | helpers |
| 2 | `cachePut(label, data)` | `cachePut(label, data)` | helpers |
| 3 | `cacheGet(label, hrs)` | `cacheGet(label, hrs)` | helpers |
| 4 | `removeUrlCreds(url)` | `removeUrlCreds(url)` | helpers |
| 5 | `isValidLocalOrLoopbackIp(ip)` | `isValidLocalOrLoopbackIp(ip)` | helpers |
| 6 | `domainKeyword(domain, tlds)` | `domainKeyword(domain, tlds)` | helpers |
| 7 | `domainKeywords(domains, tlds)` | `domainKeywords(domains, tlds)` | helpers |
| 8 | `hostDomain(hostname, tlds)` | `hostDomain(hostname, tlds)` | helpers |
| 9 | `validHost(hostname, tlds)` | `validHost(hostname, tlds)` | helpers |
| 10 | `isDomain(hostname, tlds)` | `isDomain(hostname, tlds)` | helpers |
| 11 | `validIP(addr)` | `validIP(addr)` | helpers |
| 12 | `validIP6(addr)` | `validIP6(addr)` | helpers |
| 13 | `validIpNetwork(cidr)` | `validIpNetwork(cidr)` | helpers |
| 14 | `isPublicIpAddress(ip)` | `isPublicIpAddress(ip)` | helpers |
| 15 | `normalizeDNS(res)` | `normalizeDNS(res)` | helpers |
| 16 | `resolveHost(host)` | `resolveHost(host)` | network |
| 17 | `resolveIP(ip)` | `resolveIP(ip)` | network |
| 18 | `resolveHost6(hostname)` | `resolveHost6(hostname)` | network |
| 19 | `validateIP(host, ip)` | `validateIP(host, ip)` | network |
| 20 | `safeSocket(host, port, t)` | `safeSocket(host, port, t)` | network |
| 21 | `safeSSLSocket(host, port, t)` | `safeSSLSocket(host, port, t)` | network |
| 22 | `parseCert(rawcert, fqdn, d)` | `parseCert(rawcert, fqdn, d)` | network |
| 23 | `getSession()` | `getSession()` | network |
| 24 | `useProxyForUrl(url)` | `useProxyForUrl(url, opts, ...)` | network |
| 25 | `fetchUrl(...)` | `fetchUrl(...)` | network |
| 26 | `checkDnsWildcard(target)` | `checkDnsWildcard(target)` | network |
| 27 | `urlFQDN(url)` | `urlFQDN(url)` | helpers |

### Recommendation

**Phase 2 action:** Replace the 27 wrappers with a `__getattr__` delegation to
a lookup table, reducing ~120 lines to ~15. Modules can then call either:
- `sf.validIP(addr)` (backward-compatible via `__getattr__`)
- `from spiderfoot.sflib.helpers import validIP` (direct, preferred for new code)

The wrapper for `useProxyForUrl` (#24) is the only one that passes `self`-derived
values (`self.opts`, `self.urlFQDN`), so it cannot be a simple pass-through. It
should remain as an explicit method or be refactored to accept opts explicitly.

### Non-wrapper methods that remain essential

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__` | ~60 | SSL contexts, option defaults |
| `info/error/debug` | ~20 | Scan-scoped logging |
| `cveInfo` | ~80 | CIRCL + NIST CVE resolution |
| `loadModules` | ~100 | importlib dynamic module loading |
| `modulesProducing/Consuming` | ~40 | DAG traversal for module graph |
| `optValueToData` | ~30 | Option deserialization |
| `targetType` | ~20 | Input classification |

These ~350 lines represent the irreducible core of the facade.
