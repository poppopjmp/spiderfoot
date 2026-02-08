"""Tests for spiderfoot.module_api_client."""

import time
import pytest
from spiderfoot.module_api_client import (
    HttpMethod,
    ResponseFormat,
    RequestConfig,
    ApiResponse,
    RateLimiter,
    RequestRecord,
    ModuleApiClient,
)


class TestRequestConfig:
    def test_defaults(self):
        c = RequestConfig()
        assert c.timeout == 30.0
        assert c.max_retries == 3
        assert c.verify_ssl is True
        assert c.user_agent == "SpiderFoot/5.x"

    def test_to_dict(self):
        c = RequestConfig(timeout=10)
        d = c.to_dict()
        assert d["timeout"] == 10
        assert "max_retries" in d


class TestApiResponse:
    def test_ok(self):
        r = ApiResponse(status_code=200)
        assert r.ok
        r2 = ApiResponse(status_code=404)
        assert not r2.ok

    def test_is_json(self):
        r = ApiResponse(content_type="application/json")
        assert r.is_json
        r2 = ApiResponse(content_type="text/html")
        assert not r2.is_json

    def test_json_from_dict(self):
        r = ApiResponse(body={"key": "val"})
        assert r.json() == {"key": "val"}

    def test_json_from_string(self):
        r = ApiResponse(body='{"key": "val"}')
        assert r.json() == {"key": "val"}

    def test_text_from_string(self):
        r = ApiResponse(body="hello")
        assert r.text() == "hello"

    def test_text_from_bytes(self):
        r = ApiResponse(body=b"bytes")
        assert r.text() == "bytes"

    def test_text_from_none(self):
        r = ApiResponse(body=None)
        assert r.text() == ""

    def test_to_dict(self):
        r = ApiResponse(status_code=200, url="http://example.com", elapsed_ms=5.5)
        d = r.to_dict()
        assert d["status_code"] == 200
        assert d["ok"] is True
        assert d["elapsed_ms"] == 5.5


class TestRateLimiter:
    def test_acquire_within_burst(self):
        rl = RateLimiter(requests_per_second=10, burst_size=5)
        wait = rl.acquire()
        assert wait == 0.0

    def test_acquire_exhausted(self):
        rl = RateLimiter(requests_per_second=10, burst_size=2)
        rl.acquire()
        rl.acquire()
        wait = rl.acquire()
        assert wait > 0.0

    def test_wait_does_not_crash(self):
        rl = RateLimiter(requests_per_second=1000, burst_size=100)
        rl.wait()  # should return immediately


class TestRequestRecord:
    def test_to_dict(self):
        r = RequestRecord(
            method="GET",
            url="http://example.com",
            status_code=200,
            elapsed_ms=12.345,
        )
        d = r.to_dict()
        assert d["method"] == "GET"
        assert d["elapsed_ms"] == 12.35


class TestModuleApiClient:
    def test_defaults(self):
        c = ModuleApiClient()
        assert c.base_url == ""
        assert c.api_key == ""
        assert isinstance(c.config, RequestConfig)

    def test_build_url_with_base(self):
        c = ModuleApiClient(base_url="https://api.example.com")
        assert c.build_url("/users") == "https://api.example.com/users"

    def test_build_url_absolute(self):
        c = ModuleApiClient(base_url="https://api.example.com")
        url = c.build_url("https://other.com/path")
        assert url == "https://other.com/path"

    def test_build_url_with_params(self):
        c = ModuleApiClient()
        url = c.build_url("https://api.example.com/search", {"q": "test", "page": "1"})
        assert "q=test" in url
        assert "page=1" in url

    def test_build_headers_with_api_key(self):
        c = ModuleApiClient(api_key="secret123")
        h = c.build_headers()
        assert h["X-API-Key"] == "secret123"
        assert "User-Agent" in h

    def test_build_headers_custom_key_header(self):
        c = ModuleApiClient(api_key="key", api_key_header="Authorization")
        h = c.build_headers()
        assert h["Authorization"] == "key"

    def test_set_header(self):
        c = ModuleApiClient()
        result = c.set_header("Accept", "application/json")
        assert result is c  # chainable
        h = c.build_headers()
        assert h["Accept"] == "application/json"

    def test_remove_header(self):
        c = ModuleApiClient()
        c.set_header("X-Custom", "val")
        c.remove_header("X-Custom")
        h = c.build_headers()
        assert "X-Custom" not in h

    def test_get_request(self):
        c = ModuleApiClient(base_url="https://api.example.com")
        resp = c.get("/test")
        assert isinstance(resp, ApiResponse)
        assert "api.example.com/test" in resp.url

    def test_post_request(self):
        c = ModuleApiClient()
        resp = c.post("https://api.example.com/data", body={"key": "val"})
        assert isinstance(resp, ApiResponse)

    def test_history_tracking(self):
        c = ModuleApiClient()
        c.get("https://example.com/a")
        c.get("https://example.com/b")
        assert len(c.history) == 2
        assert c.history[0].method == "GET"

    def test_clear_history(self):
        c = ModuleApiClient()
        c.get("https://example.com")
        c.clear_history()
        assert len(c.history) == 0

    def test_history_max_size(self):
        c = ModuleApiClient(max_history=3)
        for i in range(5):
            c.get(f"https://example.com/{i}")
        assert len(c.history) == 3

    def test_get_stats_empty(self):
        c = ModuleApiClient()
        s = c.get_stats()
        assert s["total"] == 0

    def test_get_stats_with_requests(self):
        c = ModuleApiClient()
        c.get("https://example.com")
        c.get("https://example.com")
        s = c.get_stats()
        assert s["total"] == 2

    def test_to_dict(self):
        c = ModuleApiClient(base_url="https://api.example.com", api_key="secret")
        d = c.to_dict()
        assert d["base_url"] == "https://api.example.com"
        assert d["has_api_key"] is True
        assert "config" in d
        assert "stats" in d

    def test_with_rate_limiter(self):
        rl = RateLimiter(requests_per_second=1000, burst_size=100)
        c = ModuleApiClient(rate_limiter=rl)
        resp = c.get("https://example.com")
        assert isinstance(resp, ApiResponse)
        assert c.to_dict()["has_rate_limiter"] is True

    def test_build_headers_extra(self):
        c = ModuleApiClient()
        h = c.build_headers({"X-Extra": "val"})
        assert h["X-Extra"] == "val"
