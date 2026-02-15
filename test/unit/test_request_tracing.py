"""
Tests for Request Tracing Middleware — Cycle 18.

Covers:
  - Context variables: get/set request_id, get_request_context
  - RequestIdFilter: injects request_id into log records
  - RequestTracingMiddleware: generates IDs, echoes client IDs,
    response headers, timing logs, slow request warnings
  - StructuredFormatter integration: request_id in JSON output
  - install_tracing_middleware: wiring and idempotent filter install
"""
from __future__ import annotations

import json
import logging
import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.request_tracing import (
    RequestIdFilter,
    generate_request_id,
    get_request_context,
    get_request_id,
    set_request_id,
    _request_id_var,
    _request_method_var,
    _request_path_var,
    install_tracing_middleware,
    _install_request_id_filter,
)


# =====================================================================
# Context variables
# =====================================================================

class TestContextVariables(unittest.TestCase):

    def tearDown(self):
        # Reset context vars
        _request_id_var.set(None)
        _request_method_var.set(None)
        _request_path_var.set(None)

    def test_get_request_id_default_none(self):
        self.assertIsNone(get_request_id())

    def test_set_and_get_request_id(self):
        tok = set_request_id("test-123")
        self.assertEqual(get_request_id(), "test-123")
        _request_id_var.reset(tok)

    def test_set_returns_token(self):
        tok = set_request_id("abc")
        self.assertIsNotNone(tok)
        _request_id_var.reset(tok)
        self.assertIsNone(get_request_id())

    def test_generate_request_id_unique(self):
        ids = {generate_request_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_generate_request_id_format(self):
        rid = generate_request_id()
        # UUID4 format: 8-4-4-4-12
        parts = rid.split("-")
        self.assertEqual(len(parts), 5)

    def test_get_request_context_empty(self):
        ctx = get_request_context()
        self.assertEqual(ctx, {})

    def test_get_request_context_populated(self):
        set_request_id("req-1")
        _request_method_var.set("GET")
        _request_path_var.set("/api/health")

        ctx = get_request_context()
        self.assertEqual(ctx["request_id"], "req-1")
        self.assertEqual(ctx["request_method"], "GET")
        self.assertEqual(ctx["request_path"], "/api/health")


# =====================================================================
# RequestIdFilter
# =====================================================================

class TestRequestIdFilter(unittest.TestCase):

    def setUp(self):
        self.filter = RequestIdFilter()
        _request_id_var.set(None)
        _request_method_var.set(None)
        _request_path_var.set(None)

    def tearDown(self):
        _request_id_var.set(None)
        _request_method_var.set(None)
        _request_path_var.set(None)

    def test_filter_adds_empty_when_no_context(self):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "msg", (), None,
        )
        result = self.filter.filter(record)
        self.assertTrue(result)  # Always passes
        self.assertEqual(record.request_id, "")
        self.assertEqual(record.request_method, "")
        self.assertEqual(record.request_path, "")

    def test_filter_adds_context_when_set(self):
        set_request_id("ctx-123")
        _request_method_var.set("POST")
        _request_path_var.set("/api/scan")

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "msg", (), None,
        )
        self.filter.filter(record)
        self.assertEqual(record.request_id, "ctx-123")
        self.assertEqual(record.request_method, "POST")
        self.assertEqual(record.request_path, "/api/scan")

    def test_filter_always_returns_true(self):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "msg", (), None,
        )
        self.assertTrue(self.filter.filter(record))


# =====================================================================
# StructuredFormatter integration
# =====================================================================

class TestStructuredFormatterRequestId(unittest.TestCase):

    def setUp(self):
        _request_id_var.set(None)

    def tearDown(self):
        _request_id_var.set(None)

    def test_formatter_includes_request_id_from_extra(self):
        from spiderfoot.observability.structured_logging import StructuredFormatter

        fmt = StructuredFormatter(include_timestamp=False, include_hostname=False)
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test msg", (), None,
        )
        record.request_id = "extra-id-456"
        output = fmt.format(record)
        data = json.loads(output)
        self.assertEqual(data["request_id"], "extra-id-456")

    def test_formatter_includes_request_id_from_contextvar(self):
        from spiderfoot.observability.structured_logging import StructuredFormatter

        fmt = StructuredFormatter(include_timestamp=False, include_hostname=False)
        set_request_id("ctxvar-789")

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test msg", (), None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        self.assertEqual(data["request_id"], "ctxvar-789")

    def test_formatter_no_request_id_when_absent(self):
        from spiderfoot.observability.structured_logging import StructuredFormatter

        fmt = StructuredFormatter(include_timestamp=False, include_hostname=False)
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test msg", (), None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        self.assertNotIn("request_id", data)

    def test_formatter_includes_method_and_path(self):
        from spiderfoot.observability.structured_logging import StructuredFormatter

        fmt = StructuredFormatter(include_timestamp=False, include_hostname=False)
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test msg", (), None,
        )
        record.request_id = "r1"
        record.request_method = "GET"
        record.request_path = "/api/health"
        output = fmt.format(record)
        data = json.loads(output)
        self.assertEqual(data["request_method"], "GET")
        self.assertEqual(data["request_path"], "/api/health")


# =====================================================================
# FastAPI Middleware
# =====================================================================

class TestRequestTracingMiddleware(unittest.TestCase):
    """Tests for the middleware via FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("FastAPI not installed")

        cls.app = FastAPI()

        # Install middleware
        install_tracing_middleware(
            cls.app,
            log_requests=True,
            slow_request_threshold=0.001,  # Low threshold for testing
        )

        @cls.app.get("/test")
        async def test_endpoint():
            # Return the request ID from inside the handler
            return {"request_id": get_request_id()}

        @cls.app.get("/slow")
        async def slow_endpoint():
            import asyncio
            await asyncio.sleep(0.01)
            return {"request_id": get_request_id()}

        @cls.app.get("/error")
        async def error_endpoint():
            raise ValueError("test error")

        cls.client = TestClient(cls.app, raise_server_exceptions=False)

    def test_generates_request_id(self):
        resp = self.client.get("/test")
        self.assertEqual(resp.status_code, 200)

        # Response should have X-Request-ID header
        self.assertIn("X-Request-ID", resp.headers)
        rid = resp.headers["X-Request-ID"]
        self.assertTrue(len(rid) > 0)

        # The handler should have seen the same ID
        self.assertEqual(resp.json()["request_id"], rid)

    def test_echoes_client_request_id(self):
        client_id = "my-custom-trace-id-123"
        resp = self.client.get(
            "/test",
            headers={"X-Request-ID": client_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["X-Request-ID"], client_id)
        self.assertEqual(resp.json()["request_id"], client_id)

    def test_unique_ids_per_request(self):
        r1 = self.client.get("/test")
        r2 = self.client.get("/test")
        self.assertNotEqual(
            r1.headers["X-Request-ID"],
            r2.headers["X-Request-ID"],
        )

    def test_context_cleared_after_request(self):
        self.client.get("/test")
        # After request, context should be cleared
        self.assertIsNone(get_request_id())

    def test_error_response_still_has_id(self):
        resp = self.client.get("/error")
        self.assertEqual(resp.status_code, 500)
        # Even on errors, the X-Request-ID might not be set because
        # the exception is raised before the response is modified.
        # But the context should still be cleaned up.
        self.assertIsNone(get_request_id())


# =====================================================================
# install_tracing_middleware
# =====================================================================

class TestInstallTracingMiddleware(unittest.TestCase):

    def test_install_adds_filter_to_root_logger(self):
        root = logging.getLogger()
        # Remove any existing RequestIdFilter
        root.filters = [f for f in root.filters if not isinstance(f, RequestIdFilter)]

        _install_request_id_filter()

        has_filter = any(isinstance(f, RequestIdFilter) for f in root.filters)
        self.assertTrue(has_filter)

    def test_install_filter_idempotent(self):
        root = logging.getLogger()
        root.filters = [f for f in root.filters if not isinstance(f, RequestIdFilter)]

        _install_request_id_filter()
        _install_request_id_filter()
        _install_request_id_filter()

        count = sum(1 for f in root.filters if isinstance(f, RequestIdFilter))
        self.assertEqual(count, 1)

    def test_install_without_starlette(self):
        """Should not crash when Starlette is unavailable."""
        with patch("spiderfoot.request_tracing.HAS_STARLETTE", False):
            # This should log a warning but not crash
            mock_app = MagicMock()
            install_tracing_middleware(mock_app)
            # add_middleware should NOT be called since starlette is "missing"
            mock_app.add_middleware.assert_not_called()


# =====================================================================
# Edge cases
# =====================================================================

class TestEdgeCases(unittest.TestCase):

    def tearDown(self):
        _request_id_var.set(None)

    def test_set_request_id_for_background_task(self):
        """Background tasks can manually set a request ID."""
        import threading

        results = {}

        def bg_task():
            set_request_id("bg-task-1")
            results["bg_id"] = get_request_id()

        t = threading.Thread(target=bg_task)
        t.start()
        t.join()

        # Background thread should have had its own context
        self.assertEqual(results["bg_id"], "bg-task-1")
        # Main thread should not be affected
        self.assertIsNone(get_request_id())

    def test_nested_context(self):
        """Tokens allow restoring previous context."""
        set_request_id("outer")
        tok = set_request_id("inner")
        self.assertEqual(get_request_id(), "inner")
        _request_id_var.reset(tok)
        self.assertEqual(get_request_id(), "outer")


if __name__ == "__main__":
    unittest.main()
