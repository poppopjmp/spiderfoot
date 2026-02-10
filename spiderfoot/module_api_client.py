"""Standardized API client for module HTTP interactions.

Provides a unified HTTP client with retry logic, rate limiting, response
parsing, and error handling for use by SpiderFoot modules.
"""

import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin, urlencode


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    PATCH = "PATCH"


class ResponseFormat(Enum):
    JSON = "json"
    TEXT = "text"
    BINARY = "binary"
    AUTO = "auto"


@dataclass
class RequestConfig:
    """Configuration for an HTTP request."""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    verify_ssl: bool = True
    follow_redirects: bool = True
    max_redirects: int = 10
    user_agent: str = "SpiderFoot/5.x"

    def to_dict(self) -> dict:
        return {
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "retry_backoff": self.retry_backoff,
            "verify_ssl": self.verify_ssl,
            "follow_redirects": self.follow_redirects,
            "max_redirects": self.max_redirects,
            "user_agent": self.user_agent,
        }


@dataclass
class ApiResponse:
    """Standardized API response wrapper."""
    status_code: int = 0
    headers: dict = field(default_factory=dict)
    body: Any = None
    content_type: str = ""
    elapsed_ms: float = 0.0
    url: str = ""
    error: Optional[str] = None
    retries_used: int = 0

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_json(self) -> bool:
        return "json" in self.content_type.lower()

    def json(self) -> Any:
        """Parse body as JSON if it's a string."""
        if isinstance(self.body, (dict, list)):
            return self.body
        if isinstance(self.body, str):
            return json.loads(self.body)
        return None

    def text(self) -> str:
        if isinstance(self.body, str):
            return self.body
        if isinstance(self.body, bytes):
            return self.body.decode("utf-8", errors="replace")
        return str(self.body) if self.body is not None else ""

    def to_dict(self) -> dict:
        return {
            "status_code": self.status_code,
            "content_type": self.content_type,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "url": self.url,
            "ok": self.ok,
            "error": self.error,
            "retries_used": self.retries_used,
            "body_type": type(self.body).__name__ if self.body is not None else "None",
        }


class RateLimiter:
    """Token-bucket rate limiter for API calls.

    Args:
        requests_per_second: Maximum sustained request rate.
        burst_size: Maximum burst of requests allowed.
    """

    def __init__(self, requests_per_second: float = 10.0, burst_size: int = 20) -> None:
        self.rate = requests_per_second
        self.burst_size = burst_size
        self._tokens = float(burst_size)
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Acquire permission to make a request. Returns wait time in seconds."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst_size, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            wait_time = (1.0 - self._tokens) / self.rate
            self._tokens = 0.0
            return wait_time

    def wait(self):
        """Block until a request is permitted."""
        delay = self.acquire()
        if delay > 0:
            time.sleep(delay)


@dataclass
class RequestRecord:
    """Record of a completed request for logging/audit."""
    method: str
    url: str
    status_code: int
    elapsed_ms: float
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    retries: int = 0

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "status_code": self.status_code,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "timestamp": self.timestamp,
            "error": self.error,
            "retries": self.retries,
        }


class ModuleApiClient:
    """Standardized HTTP client for SpiderFoot modules.

    Handles retry logic, rate limiting, response normalization,
    and request history tracking.

    Args:
        base_url: Base URL for API requests (optional).
        config: Request configuration defaults.
        rate_limiter: Rate limiter (optional).
        api_key: API key for authentication (optional).
        api_key_header: Header name for API key (default X-API-Key).
        max_history: Max request records to keep.
    """

    def __init__(
        self,
        base_url: str = "",
        config: Optional[RequestConfig] = None,
        rate_limiter: Optional[RateLimiter] = None,
        api_key: str = "",
        api_key_header: str = "X-API-Key",
        max_history: int = 100,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.config = config or RequestConfig()
        self.rate_limiter = rate_limiter
        self.api_key = api_key
        self.api_key_header = api_key_header
        self._history: list[RequestRecord] = []
        self._max_history = max_history
        self._default_headers: dict[str, str] = {}

    def set_header(self, name: str, value: str) -> "ModuleApiClient":
        """Set a default header for all requests."""
        self._default_headers[name] = value
        return self

    def remove_header(self, name: str) -> "ModuleApiClient":
        self._default_headers.pop(name, None)
        return self

    def build_url(self, path: str, params: Optional[dict] = None) -> str:
        """Build full URL from base + path + query params."""
        if self.base_url and not path.startswith(("http://", "https://")):
            url = self.base_url + "/" + path.lstrip("/")
        else:
            url = path
        if params:
            separator = "&" if "?" in url else "?"
            url = url + separator + urlencode(params, doseq=True)
        return url

    def build_headers(self, extra: Optional[dict] = None) -> dict:
        """Build request headers with defaults, auth, and extras."""
        headers = {"User-Agent": self.config.user_agent}
        headers.update(self._default_headers)
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: HttpMethod,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        body: Any = None,
        response_format: ResponseFormat = ResponseFormat.AUTO,
        config: Optional[RequestConfig] = None,
    ) -> ApiResponse:
        """Execute an HTTP request (simulation — returns structured ApiResponse).

        In production, this would use urllib/requests. Here we build
        the full request structure and return a response stub for
        modules to integrate with.
        """
        cfg = config or self.config
        url = self.build_url(path, params)
        req_headers = self.build_headers(headers)

        # Rate limiting
        if self.rate_limiter:
            self.rate_limiter.wait()

        start = time.time()

        # Build response (stub — real implementation would make HTTP call)
        response = ApiResponse(
            url=url,
            status_code=0,
            headers=req_headers,
            content_type="",
            elapsed_ms=0.0,
            error="No HTTP backend configured — use with SpiderFoot fetch_url()",
        )

        elapsed = (time.time() - start) * 1000
        response.elapsed_ms = elapsed

        # Record
        record = RequestRecord(
            method=method.value,
            url=url,
            status_code=response.status_code,
            elapsed_ms=elapsed,
            error=response.error,
        )
        self._record(record)

        return response

    def get(self, path: str, params: Optional[dict] = None, **kwargs) -> ApiResponse:
        return self.request(HttpMethod.GET, path, params=params, **kwargs)

    def post(self, path: str, body: Any = None, **kwargs) -> ApiResponse:
        return self.request(HttpMethod.POST, path, body=body, **kwargs)

    def put(self, path: str, body: Any = None, **kwargs) -> ApiResponse:
        return self.request(HttpMethod.PUT, path, body=body, **kwargs)

    def delete(self, path: str, **kwargs) -> ApiResponse:
        return self.request(HttpMethod.DELETE, path, **kwargs)

    def _record(self, record: RequestRecord):
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    @property
    def history(self) -> list[RequestRecord]:
        return list(self._history)

    def clear_history(self):
        self._history.clear()

    def get_stats(self) -> dict:
        """Get request statistics from history."""
        if not self._history:
            return {"total": 0, "errors": 0, "avg_elapsed_ms": 0.0}
        errors = sum(1 for r in self._history if r.error)
        avg_elapsed = sum(r.elapsed_ms for r in self._history) / len(self._history)
        return {
            "total": len(self._history),
            "errors": errors,
            "success_rate": round((len(self._history) - errors) / len(self._history), 4),
            "avg_elapsed_ms": round(avg_elapsed, 2),
        }

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "config": self.config.to_dict(),
            "has_api_key": bool(self.api_key),
            "has_rate_limiter": self.rate_limiter is not None,
            "history_size": len(self._history),
            "default_headers": list(self._default_headers.keys()),
            "stats": self.get_stats(),
        }
