# -------------------------------------------------------------------------------
# Name:         async_network
# Purpose:      Native async HTTP and DNS utilities for SpiderFoot.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-01
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Native async HTTP and DNS client for SpiderFoot.

Wraps :mod:`aiohttp` for non-blocking HTTP requests and :mod:`aiodns`
for non-blocking DNS resolution.  Designed to be consumed by
:class:`~spiderfoot.plugins.async_plugin.SpiderFootAsyncPlugin` instead
of the legacy ``loop.run_in_executor()`` shim pattern.

Session lifecycle
-----------------
Call :func:`get_session` to obtain a module-scoped ``aiohttp.ClientSession``.
Sessions are cached per ``(module_name, loop)`` key so each plugin reuses one
connection pool.  Call :func:`close_all_sessions` at scan shutdown.

DNS resolver
------------
A single ``aiodns.DNSResolver`` is lazily created per event-loop and cached
in :data:`_resolvers`.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from typing import Any

import aiohttp

log = logging.getLogger("spiderfoot.sflib.async_network")

# ---------------------------------------------------------------------------
# Session pool keyed by (module_name, id(loop))
# ---------------------------------------------------------------------------

_sessions: dict[tuple[str, int], aiohttp.ClientSession] = {}

# Default connection limits per session (host / total)
_DEFAULT_LIMIT_PER_HOST = 10
_DEFAULT_LIMIT_TOTAL = 30

# Default timeouts (seconds)
_DEFAULT_CONNECT_TIMEOUT = 15
_DEFAULT_TOTAL_TIMEOUT = 60


async def get_session(
    module_name: str = "__global__",
    *,
    limit_per_host: int = _DEFAULT_LIMIT_PER_HOST,
    limit_total: int = _DEFAULT_LIMIT_TOTAL,
    connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
    total_timeout: float = _DEFAULT_TOTAL_TIMEOUT,
    verify_ssl: bool = True,
) -> aiohttp.ClientSession:
    """Return (or create) an ``aiohttp.ClientSession`` for *module_name*.

    Sessions are keyed by ``(module_name, id(loop))`` so each asyncio
    event-loop gets its own connection pool.
    """
    loop = asyncio.get_running_loop()
    key = (module_name, id(loop))

    session = _sessions.get(key)
    if session is not None and not session.closed:
        return session

    connector_kwargs: dict[str, Any] = {
        "limit": limit_total,
        "limit_per_host": limit_per_host,
        "enable_cleanup_closed": True,
    }
    if not verify_ssl:
        connector_kwargs["ssl"] = False

    # Try to use aiodns resolver for non-blocking DNS
    try:
        import aiodns  # noqa: F401
        from aiohttp.resolver import AsyncResolver
        connector_kwargs["resolver"] = AsyncResolver()
    except ImportError:
        log.debug("aiodns not installed – falling back to threaded DNS resolver")

    connector = aiohttp.TCPConnector(**connector_kwargs)

    timeout = aiohttp.ClientTimeout(
        total=total_timeout,
        connect=connect_timeout,
    )

    session = aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers={"User-Agent": "SpiderFoot"},
    )
    _sessions[key] = session
    return session


async def close_session(module_name: str = "__global__") -> None:
    """Gracefully close the session(s) for *module_name*."""
    to_close = [k for k in _sessions if k[0] == module_name]
    for key in to_close:
        session = _sessions.pop(key, None)
        if session and not session.closed:
            await session.close()


async def close_all_sessions() -> None:
    """Close **every** cached session – call at scan shutdown."""
    for key in list(_sessions):
        session = _sessions.pop(key, None)
        if session and not session.closed:
            await session.close()


# ---------------------------------------------------------------------------
# Async HTTP fetch
# ---------------------------------------------------------------------------


async def async_fetch_url(
    url: str,
    *,
    method: str = "GET",
    timeout: float | None = None,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    post_data: str | bytes | dict | None = None,
    head_only: bool = False,
    size_limit: int | None = None,
    verify_ssl: bool = True,
    useragent: str = "SpiderFoot",
    module_name: str = "__global__",
) -> dict[str, Any]:
    """Non-blocking HTTP fetch mirroring the return shape of ``network.fetchUrl``.

    Returns a dict with keys:
        ``code``   – HTTP status as a *str* (e.g. ``"200"``).
        ``status`` – reason phrase.
        ``content`` – decoded body text (UTF-8, errors replaced).
        ``headers`` – dict of response headers.
        ``realurl`` – final URL after redirects.
    """
    result: dict[str, Any] = {
        "code": None,
        "status": None,
        "content": None,
        "headers": None,
        "realurl": url,
    }

    if not url or not isinstance(url, str):
        return result

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return result

    session = await get_session(
        module_name,
        verify_ssl=verify_ssl,
    )

    req_headers = {"User-Agent": useragent}
    if headers:
        req_headers.update(headers)

    req_timeout = (
        aiohttp.ClientTimeout(total=timeout) if timeout else None
    )

    try:
        effective_method = "HEAD" if head_only else method.upper()
        kwargs: dict[str, Any] = {
            "headers": req_headers,
            "allow_redirects": True,
        }
        if req_timeout:
            kwargs["timeout"] = req_timeout
        if cookies:
            kwargs["cookies"] = cookies
        if post_data and effective_method in ("POST", "PUT", "PATCH"):
            if isinstance(post_data, dict):
                kwargs["json"] = post_data
            else:
                kwargs["data"] = post_data

        ssl_ctx: ssl.SSLContext | bool = True
        if not verify_ssl:
            ssl_ctx = False
        kwargs["ssl"] = ssl_ctx

        async with session.request(effective_method, url, **kwargs) as resp:
            result["code"] = str(resp.status)
            result["status"] = resp.reason or ""
            result["realurl"] = str(resp.url)
            result["headers"] = dict(resp.headers)

            if not head_only:
                if size_limit:
                    raw = await resp.content.read(size_limit)
                else:
                    raw = await resp.read()
                result["content"] = raw.decode("utf-8", errors="replace")

    except asyncio.TimeoutError:
        log.debug("Async HTTP timeout for %s", url)
    except aiohttp.ClientError as exc:
        log.debug("Async HTTP error for %s: %s", url, exc)
    except Exception as exc:
        log.debug("Unexpected error fetching %s: %s", url, exc)

    return result


# ---------------------------------------------------------------------------
# Async DNS resolution
# ---------------------------------------------------------------------------

_resolvers: dict[int, Any] = {}


def _get_resolver() -> Any:
    """Return a cached ``aiodns.DNSResolver`` for the running loop.

    Falls back to ``None`` if aiodns is not installed, in which case callers
    should use :func:`asyncio.get_running_loop().getaddrinfo()`.
    """
    loop = asyncio.get_running_loop()
    key = id(loop)
    resolver = _resolvers.get(key)
    if resolver is not None:
        return resolver
    try:
        import aiodns
        resolver = aiodns.DNSResolver(loop=loop)
        _resolvers[key] = resolver
        return resolver
    except ImportError:
        return None


async def async_resolve_host(hostname: str) -> list[str]:
    """Resolve *hostname* to a list of IPv4 addresses (non-blocking).

    Uses ``aiodns`` when available; otherwise falls back to the loop's
    threaded ``getaddrinfo``.
    """
    if not hostname:
        return []

    resolver = _get_resolver()
    if resolver is not None:
        try:
            answers = await resolver.query(hostname, "A")
            return list({r.host for r in answers})
        except Exception:
            return []

    # Fallback: threaded getaddrinfo
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None, family=2)  # AF_INET
        return list({info[4][0] for info in infos})
    except Exception:
        return []


async def async_resolve_host6(hostname: str) -> list[str]:
    """Resolve *hostname* to a list of IPv6 addresses (non-blocking)."""
    if not hostname:
        return []

    resolver = _get_resolver()
    if resolver is not None:
        try:
            answers = await resolver.query(hostname, "AAAA")
            return list({r.host for r in answers})
        except Exception:
            return []

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None, family=10)  # AF_INET6
        return list({info[4][0] for info in infos})
    except Exception:
        return []


async def async_reverse_resolve(ip_address: str) -> list[str]:
    """Reverse-resolve an IP address to hostnames (non-blocking)."""
    if not ip_address:
        return []

    resolver = _get_resolver()
    if resolver is not None:
        # Build the PTR query name
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip_address)
            ptr_name = addr.reverse_pointer
            answers = await resolver.query(ptr_name, "PTR")
            return list({r.host.rstrip(".") for r in answers})
        except Exception:
            return []

    loop = asyncio.get_running_loop()
    try:
        result = await loop.getnameinfo((ip_address, 0), 0)
        return [result[0]] if result[0] != ip_address else []
    except Exception:
        return []


async def async_check_dns_wildcard(target: str) -> bool:
    """Check if *target* has a DNS wildcard entry (non-blocking)."""
    if not target:
        return False
    import random
    randpool = "bcdfghjklmnpqrstvwxyz3456789"
    randhost = "".join(random.SystemRandom().choice(randpool) for _ in range(10))
    addrs = await async_resolve_host(f"{randhost}.{target}")
    return len(addrs) > 0
