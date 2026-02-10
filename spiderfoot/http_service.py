"""
HttpService — Standalone HTTP client service.

Extracted from the SpiderFoot god object (core.py + network.py) to provide
a clean, injectable HTTP client for modules and services.

Handles fetching, proxy configuration, session management, and
search-engine iteration (Google/Bing APIs).
"""

import json
import logging
import ssl
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

log = logging.getLogger("spiderfoot.http_service")


@dataclass
class HttpServiceConfig:
    """Configuration for the HTTP service.

    Attributes:
        proxy_type: SOCKS proxy type ('', 'HTTP', 'SOCKS4', 'SOCKS5')
        proxy_host: Proxy hostname
        proxy_port: Proxy port
        proxy_username: Proxy auth username
        proxy_password: Proxy auth password
        proxy_dns: Route DNS through proxy
        user_agent: Default User-Agent header
        timeout: Default request timeout in seconds
        ssl_verify: Verify SSL certificates
        size_limit: Default response size limit (bytes), 0=unlimited
        fetch_max_retries: Max retry attempts for failed fetches
        google_api_key: Google Custom Search API key
        google_cse_id: Google Custom Search Engine ID
        bing_api_key: Bing Web Search API key
    """
    proxy_type: str = ""
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_username: str = ""
    proxy_password: str = ""
    proxy_dns: bool = True
    user_agent: str = "SpiderFoot"
    timeout: int = 30
    ssl_verify: bool = True
    size_limit: int = 10_000_000  # 10MB default
    fetch_max_retries: int = 1
    google_api_key: str = ""
    google_cse_id: str = ""
    bing_api_key: str = ""

    @classmethod
    def from_sf_config(cls, opts: dict[str, Any]) -> "HttpServiceConfig":
        """Create config from SpiderFoot options dict.

        Maps legacy _socks* and _fetchtimeout keys.
        """
        return cls(
            proxy_type=opts.get("_socks1type", ""),
            proxy_host=opts.get("_socks2addr", ""),
            proxy_port=int(opts.get("_socks3port", 0)),
            proxy_username=opts.get("_socks4user", ""),
            proxy_password=opts.get("_socks5pwd", ""),
            proxy_dns=opts.get("_socks6dns", True),
            timeout=int(opts.get("_fetchtimeout", 30)),
            size_limit=int(opts.get("_fetchsizelimit", 10_000_000)),
            google_api_key=opts.get("_googlecseapi", ""),
            google_cse_id=opts.get("_googlecseid", ""),
            bing_api_key=opts.get("_bingkey", ""),
        )


class HttpService:
    """HTTP client service for web requests.

    Provides a clean interface for making HTTP requests with
    proxy support, session management, and search engine APIs.

    Usage:
        http = HttpService(config)
        result = http.fetch_url("https://example.com")
        print(result["content"])
    """

    def __init__(self, config: Optional[HttpServiceConfig] = None):
        self.config = config or HttpServiceConfig()
        self.log = logging.getLogger("spiderfoot.http_service")
        self._session_count = 0

    # --- Session Management ---

    def get_session(self) -> "requests.Session":
        """Create a new requests session.

        Returns:
            A fresh requests.Session
        """
        if not HAS_REQUESTS:
            raise RuntimeError("'requests' package is required for HttpService")

        session = requests.Session()
        self._session_count += 1
        return session

    # --- Proxy Configuration ---

    def _should_use_proxy(self, url: str) -> bool:
        """Determine if a URL should be routed through the proxy.

        Local/loopback addresses bypass the proxy.

        Args:
            url: URL to check

        Returns:
            True if proxy should be used
        """
        if not self.config.proxy_type:
            return False

        # Extract hostname from URL
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
        except Exception:
            return True

        # Skip proxy for localhost/loopback
        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Check for private IP ranges
        try:
            import netaddr
            ip = netaddr.IPAddress(host)
            if ip.is_loopback() or ip.is_private() or ip.is_reserved():
                return False
        except (netaddr.AddrFormatError, ValueError):
            pass  # Not an IP, it's a hostname — route through proxy

        return True

    def _get_proxy_dict(self) -> dict[str, str]:
        """Build the proxy dict for requests.

        Returns:
            Proxy configuration dict for requests library
        """
        if not self.config.proxy_type:
            return {}

        proxy_type = self.config.proxy_type.lower()
        auth = ""
        if self.config.proxy_username:
            auth = f"{self.config.proxy_username}"
            if self.config.proxy_password:
                auth += f":{self.config.proxy_password}"
            auth += "@"

        proxy_url = f"{proxy_type}://{auth}{self.config.proxy_host}:{self.config.proxy_port}"

        return {
            "http": proxy_url,
            "https": proxy_url,
        }

    # --- HTTP Fetch ---

    def fetch_url(
        self,
        url: str,
        cookies: Optional[str] = None,
        timeout: Optional[int] = None,
        useragent: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        post_data: Optional[str] = None,
        disable_content_encoding: bool = False,
        size_limit: Optional[int] = None,
        head_only: bool = False,
        verify: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Fetch a URL and return the response.

        Args:
            url: URL to fetch
            cookies: Cookie string
            timeout: Request timeout (overrides config)
            useragent: User-Agent header
            headers: Additional headers
            post_data: POST body (switches to POST method)
            disable_content_encoding: Disable Accept-Encoding
            size_limit: Max response size in bytes
            head_only: Use HEAD method
            verify: SSL verification (overrides config)

        Returns:
            Dict with keys: code, status, content, headers, realurl, url
        """
        result = {
            "code": None,
            "status": None,
            "content": None,
            "headers": None,
            "realurl": url,
            "url": url,
        }

        if not HAS_REQUESTS:
            self.log.error("'requests' package unavailable")
            return result

        _timeout = timeout or self.config.timeout
        _useragent = useragent or self.config.user_agent
        _verify = verify if verify is not None else self.config.ssl_verify
        _size_limit = size_limit if size_limit is not None else self.config.size_limit

        request_headers = {
            "User-Agent": _useragent,
        }
        if cookies:
            request_headers["Cookie"] = cookies
        if disable_content_encoding:
            request_headers["Accept-Encoding"] = "identity"
        if headers:
            request_headers.update(headers)

        session = self.get_session()

        # Configure proxy
        proxies = {}
        if self._should_use_proxy(url):
            proxies = self._get_proxy_dict()

        try:
            if head_only:
                resp = session.head(
                    url, headers=request_headers, timeout=_timeout,
                    verify=_verify, proxies=proxies, allow_redirects=True
                )
            elif post_data:
                resp = session.post(
                    url, data=post_data, headers=request_headers,
                    timeout=_timeout, verify=_verify, proxies=proxies,
                    allow_redirects=True
                )
            else:
                resp = session.get(
                    url, headers=request_headers, timeout=_timeout,
                    verify=_verify, proxies=proxies, allow_redirects=True,
                    stream=True
                )

            result["code"] = str(resp.status_code)
            result["status"] = resp.reason
            result["headers"] = dict(resp.headers)
            result["realurl"] = str(resp.url)

            if not head_only:
                # Respect size limit
                if _size_limit and _size_limit > 0:
                    content_length = resp.headers.get("Content-Length")
                    if content_length and int(content_length) > _size_limit:
                        self.log.warning(
                            f"Response too large ({content_length} > {_size_limit}): {url}"
                        )
                        result["content"] = ""
                        return result

                result["content"] = resp.text

        except requests.exceptions.Timeout:
            self.log.warning("Timeout fetching %s", url)
            result["status"] = "Timeout"
        except requests.exceptions.ConnectionError as e:
            self.log.warning("Connection error fetching %s: %s", url, e)
            result["status"] = "Connection Error"
        except requests.exceptions.RequestException as e:
            self.log.warning("Request error fetching %s: %s", url, e)
            result["status"] = str(e)
        except Exception as e:
            self.log.error("Unexpected error fetching %s: %s", url, e)
            result["status"] = str(e)
        finally:
            session.close()

        return result

    # --- Search Engine APIs ---

    def google_iterate(
        self,
        search_string: str,
        opts: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Search Google Custom Search API.

        Args:
            search_string: Search query
            opts: Override options (google_api_key, google_cse_id, pages)

        Returns:
            Dict with 'urls' list and 'webSearchUrl' string
        """
        result = {"urls": [], "webSearchUrl": ""}

        api_key = (opts or {}).get("google_api_key", self.config.google_api_key)
        cse_id = (opts or {}).get("google_cse_id", self.config.google_cse_id)
        pages = int((opts or {}).get("pages", 1))

        if not api_key or not cse_id:
            self.log.warning("Google API key or CSE ID not configured")
            return result

        for page in range(pages):
            start = page * 10 + 1
            params = urllib.parse.urlencode({
                "key": api_key,
                "cx": cse_id,
                "q": search_string,
                "start": start,
            })
            google_url = f"https://www.googleapis.com/customsearch/v1?{params}"

            resp = self.fetch_url(google_url)
            if not resp["content"]:
                break

            try:
                data = json.loads(resp["content"])
            except (json.JSONDecodeError, TypeError):
                break

            if "items" in data:
                for item in data["items"]:
                    if "link" in item:
                        result["urls"].append(item["link"])

            # Capture web search URL from first page
            if page == 0 and "url" in data:
                result["webSearchUrl"] = data["url"]

            if "queries" not in data or "nextPage" not in data.get("queries", {}):
                break

        return result

    def bing_iterate(
        self,
        search_string: str,
        opts: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Search Bing Web Search API.

        Args:
            search_string: Search query
            opts: Override options (bing_api_key, pages)

        Returns:
            Dict with 'urls' list and 'webSearchUrl' string
        """
        result = {"urls": [], "webSearchUrl": ""}

        api_key = (opts or {}).get("bing_api_key", self.config.bing_api_key)
        pages = int((opts or {}).get("pages", 1))

        if not api_key:
            self.log.warning("Bing API key not configured")
            return result

        for page in range(pages):
            offset = page * 10
            params = urllib.parse.urlencode({
                "q": search_string,
                "count": 10,
                "offset": offset,
            })
            bing_url = f"https://api.bing.microsoft.com/v7.0/search?{params}"

            resp = self.fetch_url(
                bing_url,
                headers={"Ocp-Apim-Subscription-Key": api_key},
            )
            if not resp["content"]:
                break

            try:
                data = json.loads(resp["content"])
            except (json.JSONDecodeError, TypeError):
                break

            if "webPages" in data and "value" in data["webPages"]:
                for item in data["webPages"]["value"]:
                    if "url" in item:
                        result["urls"].append(item["url"])

                if page == 0:
                    result["webSearchUrl"] = data["webPages"].get("webSearchUrl", "")

            if "webPages" not in data:
                break

        return result

    # --- SSL/TLS Utilities ---

    def safe_socket(self, host: str, port: int, timeout: int = 10) -> socket.socket:
        """Create a plain TCP socket connection.

        Args:
            host: Target hostname
            port: Target port
            timeout: Connection timeout

        Returns:
            Connected socket
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    def safe_ssl_socket(
        self, host: str, port: int, timeout: int = 10
    ) -> ssl.SSLSocket:
        """Create a TLS socket connection.

        Args:
            host: Target hostname
            port: Target port
            timeout: Connection timeout

        Returns:
            Connected SSL socket
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        ssl_sock = context.wrap_socket(sock, server_hostname=host)
        ssl_sock.connect((host, port))
        return ssl_sock

    def parse_cert(
        self,
        raw_cert: str,
        fqdn: Optional[str] = None,
        expiring_days: int = 30,
    ) -> dict[str, Any]:
        """Parse a PEM certificate and extract details.

        Args:
            raw_cert: PEM-encoded certificate string
            fqdn: FQDN to check for hostname match
            expiring_days: Days threshold for expiry warning

        Returns:
            Dict with issuer, subject, SANs, expiry info, etc.
        """
        result = {
            "issuer": "",
            "subject": "",
            "sans": [],
            "expired": False,
            "expiring_soon": False,
            "not_before": None,
            "not_after": None,
            "hostname_match": True,
            "self_signed": False,
        }

        if not HAS_CRYPTO:
            self.log.warning("cryptography package not available for cert parsing")
            return result

        try:
            cert = x509.load_pem_x509_certificate(
                raw_cert.encode() if isinstance(raw_cert, str) else raw_cert,
                default_backend()
            )

            result["issuer"] = cert.issuer.rfc4514_string()
            result["subject"] = cert.subject.rfc4514_string()
            result["not_before"] = cert.not_valid_before_utc.isoformat()
            result["not_after"] = cert.not_valid_after_utc.isoformat()
            result["self_signed"] = (cert.issuer == cert.subject)

            # Check expiry
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            result["expired"] = now > cert.not_valid_after_utc
            expiry_threshold = now + datetime.timedelta(days=expiring_days)
            result["expiring_soon"] = (
                not result["expired"] and expiry_threshold > cert.not_valid_after_utc
            )

            # Extract SANs
            try:
                san_ext = cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName
                )
                result["sans"] = san_ext.value.get_values_for_type(x509.DNSName)
            except x509.ExtensionNotFound:
                pass

            # Hostname match
            if fqdn:
                all_names = [result["subject"]] + result["sans"]
                result["hostname_match"] = any(
                    fqdn.lower() == name.lower() or
                    (name.startswith("*.") and fqdn.lower().endswith(name.lower()[1:]))
                    for name in all_names
                )

        except Exception as e:
            self.log.error("Certificate parsing failed: %s", e)

        return result

    # --- URL Utilities ---

    @staticmethod
    def url_fqdn(url: str) -> str:
        """Extract the FQDN from a URL.

        Args:
            url: Full URL

        Returns:
            Hostname without port
        """
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.hostname or ""
        except Exception:
            return ""

    @staticmethod
    def url_base(url: str) -> str:
        """Extract scheme://hostname from a URL.

        Args:
            url: Full URL

        Returns:
            Base URL (scheme + host)
        """
        try:
            parsed = urllib.parse.urlparse(url)
            return f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            return url

    # --- Metrics ---

    def stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dict with session_count, proxy_configured, etc.
        """
        return {
            "session_count": self._session_count,
            "proxy_configured": bool(self.config.proxy_type),
            "proxy_type": self.config.proxy_type,
            "timeout": self.config.timeout,
        }
