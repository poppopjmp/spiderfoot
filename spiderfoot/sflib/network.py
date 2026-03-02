# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot SFLib Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
"""Network, DNS, and HTTP utilities for SpiderFoot.

Provides mixin methods for DNS resolution, SSL/TLS certificate inspection,
HTTP content fetching, proxy support, and socket-level operations used by
the core :class:`SpiderFoot` object.
"""
# Network, DNS, IP, socket, proxy, fetch, etc. utilities
from __future__ import annotations

import socket
import ssl
import requests
import OpenSSL
import cryptography
import urllib.parse
import random
from collections.abc import Callable
from cryptography.hazmat.backends.openssl import backend
from .helpers import validIP, validIP6

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

import logging
log = logging.getLogger("spiderfoot.sflib.network")
from datetime import datetime, timezone

def resolveHost(host: str) -> list:
    """Return a normalised IPv4 resolution of a hostname.

    Uses dnspython (``dns.resolver``) for reliable, non-blocking-friendly
    DNS resolution.  Falls back to ``socket.gethostbyname_ex`` only when
    dnspython is unavailable.
    """
    import socket
    from .helpers import normalizeDNS
    if not host:
        return []
    try:
        import dns.resolver
        answers = dns.resolver.resolve(host, "A")
        addrs = [rdata.address for rdata in answers]
    except ImportError:
        # dnspython not installed — fall back to socket
        try:
            addrs = normalizeDNS(socket.gethostbyname_ex(host))
        except (socket.gaierror, socket.herror, OSError):
            return []
    except Exception:
        return []
    if not addrs:
        return []
    return list(set(addrs))

def resolveIP(ipaddr: str) -> list:
    """Return a normalised resolution of an IPv4 or IPv6 address as a flat list (not a tuple)."""
    import socket
    from .helpers import normalizeDNS, validIP, validIP6
    if not validIP(ipaddr) and not validIP6(ipaddr):
        return []
    try:
        addrs = normalizeDNS(socket.gethostbyaddr(ipaddr))
    except (socket.herror, socket.gaierror, OSError):
        return []
    if not addrs:
        return []
    return list(set(addrs))

def resolveHost6(hostname: str) -> list:
    """Return a normalised IPv6 resolution of a hostname."""
    if not hostname:
        return []
    addrs = list()
    try:
        for r in socket.getaddrinfo(hostname, None, socket.AF_INET6):
            addrs.append(r[4][0])
    except (socket.gaierror, OSError):
        return []
    if not addrs:
        return []
    return list(set(addrs))

def validateIP(host: str, ip: str) -> bool:
    """Validate that an IP address resolves to the given host."""
    if not host:
        return False
    addrs = []
    if validIP(ip):
        addrs = resolveHost(host)
    elif validIP6(ip):
        addrs = resolveHost6(host)
    else:
        return False
    if not addrs:
        return False
    return any(str(addr) == ip for addr in addrs)

def safeSocket(host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
    """Create a plain TCP socket connection with a timeout."""
    sock = socket.create_connection((host, int(port)), int(timeout))
    sock.settimeout(int(timeout))
    return sock

def safeSSLSocket(host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
    """Create a TLS-wrapped socket connection with a timeout."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    s = socket.socket()
    s.settimeout(int(timeout))
    s.connect((host, int(port)))
    sock = context.wrap_socket(s, server_hostname=host)
    sock.do_handshake()
    return sock

def parseCert(rawcert: str, fqdn: str | None = None, expiringdays: int = 30) -> dict:
    """Parse a PEM certificate and return its metadata."""
    if not rawcert:
        return {}
    ret = dict()
    if '\r' in rawcert:
        rawcert = rawcert.replace('\r', '')
    if isinstance(rawcert, str):
        rawcert = rawcert.encode('utf-8')
    cert = cryptography.x509.load_pem_x509_certificate(rawcert, backend)
    sslcert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, rawcert)
    sslcert_dump = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_TEXT, sslcert)
    ret['text'] = sslcert_dump.decode('utf-8', errors='replace')
    ret['issuer'] = str(cert.issuer)
    ret['altnames'] = list()
    ret['expired'] = False
    ret['expiring'] = False
    ret['mismatch'] = False
    ret['certerror'] = False
    ret['issued'] = str(cert.subject)
    # Expiry info
    try:
        not_after = cert.not_valid_after
        now = datetime.now(timezone.utc)
        if not_after < now:
            ret['expired'] = True
        elif (not_after - now).days < expiringdays:
            ret['expiring'] = True
    except Exception as e:
        log.debug("Failed to check cert not_valid_after: %s", e)
    # SANs
    try:
        ext = cert.extensions.get_extension_for_class(cryptography.x509.SubjectAlternativeName)
        ret['altnames'] = ext.value.get_values_for_type(cryptography.x509.DNSName)
    except Exception as e:
        log.debug("Failed to extract SubjectAlternativeName from cert: %s", e)
    certhosts = list()
    try:
        certhosts.append(cert.subject.get_attributes_for_oid(cryptography.x509.NameOID.COMMON_NAME)[0].value)
        certhosts.extend(ret['altnames'])
    except Exception as e:
        log.debug("Failed to extract CommonName from cert: %s", e)
    # Check for mismatch
    if fqdn and ret['issued']:
        if fqdn not in certhosts:
            ret['mismatch'] = True
    return ret

import threading
from requests.adapters import HTTPAdapter

_session_local = threading.local()


def getSession() -> 'requests.sessions.Session':
    """Return a thread-local HTTP session with connection pooling.

    Reuses TCP connections across multiple fetchUrl() calls within the
    same thread, avoiding the overhead of a fresh session + TCP handshake
    per request.
    """
    if not hasattr(_session_local, 'session') or _session_local.session is None:
        session = requests.session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # retries handled by caller
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        _session_local.session = session
    return _session_local.session


def closeSession() -> None:
    """Close and discard the thread-local HTTP session.

    Should be called when a worker thread is about to exit so that the
    underlying TCP connection pool is released instead of leaking until
    the thread object is garbage-collected.
    """
    session = getattr(_session_local, 'session', None)
    if session is not None:
        try:
            session.close()
        except Exception:
            pass
        _session_local.session = None


# ---------------------------------------------------------------------------
# httpx-based internal HTTP client (Cycles 54-55)
# ---------------------------------------------------------------------------

_httpx_client: httpx.Client | None = None
_httpx_client_lock = __import__("threading").Lock()


def get_internal_http_client(
    *,
    max_connections: int = 100,
    max_keepalive_connections: int = 20,
    connect_timeout: float = 10.0,
    total_timeout: float = 30.0,
) -> "httpx.Client":
    """Return a process-scoped ``httpx.Client`` with connection pooling.

    Intended for **internal service calls** (Redis, MinIO, Keycloak, etc.)
    — NOT for scan-time URL fetching which still uses ``requests`` for
    module compatibility.

    The client is created once and reused across all threads.

    Raises:
        ImportError: If ``httpx`` is not installed.
    """
    global _httpx_client
    if not HAS_HTTPX:
        raise ImportError("httpx is required for internal HTTP client")

    if _httpx_client is not None and not _httpx_client.is_closed:
        return _httpx_client

    with _httpx_client_lock:
        # Double-check after acquiring lock
        if _httpx_client is not None and not _httpx_client.is_closed:
            return _httpx_client

        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=total_timeout,
            write=total_timeout,
            pool=total_timeout,
        )
        _httpx_client = httpx.Client(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "SpiderFoot-Internal/1.0"},
        )
        return _httpx_client


def close_internal_http_client() -> None:
    """Close the process-scoped httpx client."""
    global _httpx_client
    with _httpx_client_lock:
        if _httpx_client is not None:
            try:
                _httpx_client.close()
            except Exception:
                pass
            _httpx_client = None


def internal_fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    json: dict | None = None,
    data: str | bytes | None = None,
    timeout: float | None = None,
) -> dict:
    """Fetch using httpx for internal service calls (Cycle 55).

    Returns a dict matching the ``fetchUrl`` return shape::

        {"code": "200", "status": "OK", "content": "...",
         "headers": {...}, "realurl": "..."}
    """
    result = {
        "code": None,
        "status": None,
        "content": None,
        "headers": None,
        "realurl": url,
    }
    if not url:
        return result

    try:
        client = get_internal_http_client()
    except ImportError:
        log.warning("httpx not available, falling back to requests for %s", url)
        return fetchUrl(url, timeout=int(timeout or 30), headers=headers)

    req_kwargs: dict = {}
    if headers:
        req_kwargs["headers"] = headers
    if json is not None:
        req_kwargs["json"] = json
    elif data is not None:
        req_kwargs["content"] = data
    if timeout is not None:
        req_kwargs["timeout"] = timeout

    try:
        resp = client.request(method.upper(), url, **req_kwargs)
        result["code"] = str(resp.status_code)
        result["status"] = resp.reason_phrase
        result["content"] = resp.text
        result["headers"] = dict(resp.headers)
        result["realurl"] = str(resp.url)
    except Exception as exc:
        log.debug("Internal HTTP request failed for %s: %s", url, exc)

    return result


def useProxyForUrl(
    url: str,
    opts: dict | None = None,
    urlFQDN: Callable | None = None,
    isValidLocalOrLoopbackIp: Callable | None = None,
) -> bool:
    """Determine whether a proxy should be used for the given URL."""
    if opts is None:
        return False
    if urlFQDN is None:
        urlFQDN = lambda u: u
    if isValidLocalOrLoopbackIp is None:
        isValidLocalOrLoopbackIp = lambda ip: False
    host = urlFQDN(url).lower()
    if not opts.get('_socks1type'):
        return False
    proxy_host = opts.get('_socks2addr')
    if not proxy_host:
        return False
    proxy_port = opts.get('_socks3port')
    if not proxy_port:
        return False
    if host == proxy_host.lower():
        return False
    # Localhost and private IPs should not use proxy
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if isValidLocalOrLoopbackIp(host):
        return False
    if validIP(host):
        # If it's a valid IP, check if it's local/private
        if isValidLocalOrLoopbackIp(host):
            return False
    return True

def fetchUrl(
    url: str, cookies: str | None = None, timeout: int = 30,
    useragent: str = "SpiderFoot", headers: dict | None = None,
    noLog: bool = False, postData: str | None = None,
    disableContentEncoding: bool = False,
    sizeLimit: int | None = None, headOnly: bool = False,
    verify: bool = True,
    stealth_engine: object | None = None,
) -> dict:
    """Fetch content from a URL and return response details.

    Args:
        stealth_engine: Optional :class:`~spiderfoot.recon.stealth_engine.StealthEngine`
            instance.  When provided, the engine applies request jitter,
            randomised headers, and proxy rotation transparently before
            the outbound HTTP call.
    """
    if not isinstance(url, str):
        return None
    if not url or not url.strip():
        return None
    url = url.strip()
    try:
        parsed_url = urllib.parse.urlparse(url)
    except ValueError:
        return None
    if parsed_url.scheme not in ['http', 'https']:
        return None
    result = {
        'code': None,
        'status': None,
        'content': None,
        'headers': None,
        'realurl': url
    }
    url = url.strip()
    try:
        parsed_url = urllib.parse.urlparse(url)
    except ValueError:
        return result
    if parsed_url.scheme not in ['http', 'https']:
        return result

    # ── Stealth pre-request hook ──────────────────────────────────────
    proxies = None
    if stealth_engine is not None:
        try:
            # 1) Timing jitter — slows the request rate to look human
            stealth_engine.apply_jitter()

            # 2) Stealth-enhanced headers (UA rotation + randomised extras)
            stealth_headers = stealth_engine.prepare_headers(
                target_url=url,
                extra_headers=headers,
            )
            # Override caller-supplied headers with the stealth set
            headers = stealth_headers

            # 3) Proxy rotation (returns requests-compatible dict or None)
            proxies = stealth_engine.get_proxy()

            # 4) Track request count for circuit renewal / stats
            stealth_engine.increment_request_counter()
        except Exception as exc:
            log.warning("Stealth engine pre-request hook failed: %s", exc)
            # Fall through — make the request without stealth rather
            # than silently aborting the fetch.
    # ──────────────────────────────────────────────────────────────────

    session = getSession()
    try:
        kwargs: dict = dict(timeout=timeout, headers=headers, verify=verify)
        if proxies:
            kwargs["proxies"] = proxies

        if headOnly:
            resp = session.head(url, **kwargs)
        elif postData:
            resp = session.post(url, data=postData, **kwargs)
        else:
            resp = session.get(url, **kwargs)
        result['code'] = str(resp.status_code)
        result['status'] = resp.reason
        result['content'] = resp.content.decode('utf-8', errors='replace')
        result['headers'] = dict(resp.headers)
        result['realurl'] = resp.url
    except Exception as e:
        log.debug("HTTP request failed for %s: %s", url, e)
    return result


# Per-process wildcard cache (Cycle 57)
_wildcard_cache: dict[str, bool] = {}


def checkDnsWildcard(target: str) -> bool:
    """Check if a domain has a DNS wildcard entry.

    Results are cached per-domain within the process to avoid
    redundant live DNS queries.
    """
    if not target:
        return False
    if target in _wildcard_cache:
        return _wildcard_cache[target]
    randpool = 'bcdfghjklmnpqrstvwxyz3456789'
    randhost = ''.join([random.SystemRandom().choice(randpool) for _ in range(10)])
    result = bool(resolveHost(randhost + "." + target))
    _wildcard_cache[target] = result
    return result
