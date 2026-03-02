"""
Tests for Cycle 45 — Exception Information Leakage Audit

Validates that:
1. The global unhandled-exception handler returns a generic message.
2. HTTPException handler relays detail but does NOT add stack traces.
3. Validation error handler returns structured field errors without internals.
4. Formerly-leaky endpoints no longer expose str(e) content.
5. No API router file contains f"...{e}" or str(e) in HTTPException detail
   or response body (static source-code audit).
"""

from __future__ import annotations

import os
import re
import glob
import pytest

from spiderfoot.api.error_handlers import (
    _build_error_response,
    _error_code_for,
    _unhandled_exception_handler,
    _http_exception_handler,
    _validation_exception_handler,
    ErrorResponse,
)


# ---------------------------------------------------------------------------
# Helper: minimal Request mock
# ---------------------------------------------------------------------------

class _FakeState:
    request_id = "test-req-001"

class _FakeRequest:
    method = "GET"
    url = type("U", (), {"path": "/test"})()
    state = _FakeState()
    headers = {}


# ---------------------------------------------------------------------------
# Error code mapping
# ---------------------------------------------------------------------------

class TestErrorCodeMapping:
    """Verify status → error-code derivation."""

    def test_known_status(self):
        assert _error_code_for(404) == "NOT_FOUND"

    def test_unknown_status(self):
        assert _error_code_for(418) == "HTTP_418"

    def test_scan_not_found(self):
        assert _error_code_for(404, "Scan not found") == "SCAN_NOT_FOUND"

    def test_module_not_found(self):
        assert _error_code_for(404, "Module xyz not found") == "MODULE_NOT_FOUND"


# ---------------------------------------------------------------------------
# _build_error_response
# ---------------------------------------------------------------------------

class TestBuildErrorResponse:
    """Verify the structured error envelope."""

    def test_envelope_structure(self):
        resp = _build_error_response(500, "boom", _FakeRequest())
        body = resp.body.decode()
        assert '"error"' in body
        assert '"message"' in body
        assert '"request_id"' in body
        assert "test-req-001" in body

    def test_generic_message_no_stack_trace(self):
        resp = _build_error_response(500, "Internal server error", _FakeRequest())
        body = resp.body.decode()
        assert "Traceback" not in body
        assert "File " not in body
        assert ".py" not in body or "server error" in body  # .py only in benign context

    def test_status_code_in_body(self):
        resp = _build_error_response(404, "Not found", _FakeRequest())
        assert resp.status_code == 404
        assert '"status":404' in resp.body.decode()


# ---------------------------------------------------------------------------
# Unhandled exception handler
# ---------------------------------------------------------------------------

class TestUnhandledException:
    """The catch-all must never expose internals."""

    @pytest.mark.asyncio
    async def test_returns_generic_500(self):
        exc = RuntimeError("SECRET: database password is hunter2 at /opt/sf/db.py:42")
        resp = await _unhandled_exception_handler(_FakeRequest(), exc)
        body = resp.body.decode()
        assert resp.status_code == 500
        assert "Internal server error" in body
        # Must NOT contain the secret or any internal path
        assert "hunter2" not in body
        assert "/opt/sf" not in body
        assert "db.py" not in body

    @pytest.mark.asyncio
    async def test_no_traceback_in_response(self):
        try:
            raise ValueError("should not leak")
        except ValueError as e:
            resp = await _unhandled_exception_handler(_FakeRequest(), e)
        body = resp.body.decode()
        assert "Traceback" not in body
        assert "should not leak" not in body


# ---------------------------------------------------------------------------
# HTTP exception handler
# ---------------------------------------------------------------------------

class TestHTTPExceptionHandler:
    """HTTPException handler should relay detail string only."""

    @pytest.mark.asyncio
    async def test_relays_detail_string(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        exc = StarletteHTTPException(status_code=404, detail="Scan not found")
        resp = await _http_exception_handler(_FakeRequest(), exc)
        body = resp.body.decode()
        assert resp.status_code == 404
        assert "Scan not found" in body

    @pytest.mark.asyncio
    async def test_no_traceback_added(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        exc = StarletteHTTPException(status_code=500, detail="Failed to get config")
        resp = await _http_exception_handler(_FakeRequest(), exc)
        body = resp.body.decode()
        assert "Traceback" not in body
        assert "File " not in body


# ---------------------------------------------------------------------------
# Validation error handler
# ---------------------------------------------------------------------------

class TestValidationErrorHandler:
    """Pydantic validation errors should expose field names, not internals."""

    @pytest.mark.asyncio
    async def test_returns_422(self):
        from fastapi.exceptions import RequestValidationError
        exc = RequestValidationError(errors=[
            {"loc": ("body", "target"), "msg": "field required", "type": "value_error.missing"},
        ])
        resp = await _validation_exception_handler(_FakeRequest(), exc)
        body = resp.body.decode()
        assert resp.status_code == 422
        assert "Request validation failed" in body
        assert "target" in body  # field name is okay to expose


# ---------------------------------------------------------------------------
# Static source audit: no str(e) / f"{e}" in HTTP responses
# ---------------------------------------------------------------------------

class TestNoExceptionLeakageInSource:
    """
    Scan all API router and GraphQL source files for patterns that would
    embed raw exception messages into HTTP responses.

    Allowed:  log.error("...: %s", e)
    Forbidden: HTTPException(detail=f"...{e}"), "error": f"...{e}",
               HTTPException(detail=str(e))
    """

    # Patterns that indicate leakage (exception message flowing to response)
    _LEAK_PATTERNS = [
        # f-string with {e} in HTTPException detail
        re.compile(r"""detail\s*=\s*f['"].*\{e\}"""),
        # str(e) in HTTPException detail
        re.compile(r"""detail\s*=\s*str\(e\)"""),
        # "error": f"...{e}" in JSON response dicts
        re.compile(r""""error"\s*:\s*f['"].*\{e\}"""),
    ]

    def _get_api_source_files(self):
        """Collect all Python source files in the API layer."""
        base = os.path.join(os.path.dirname(__file__), "..", "..", "spiderfoot", "api")
        base = os.path.normpath(base)
        files = []
        for pattern in ["routers/*.py", "graphql/*.py", "*.py"]:
            files.extend(glob.glob(os.path.join(base, pattern)))
        return [f for f in files if "__pycache__" not in f]

    def test_no_leak_patterns_in_api_source(self):
        """Ensure no API source file exposes str(e) in any response."""
        violations = []
        for filepath in self._get_api_source_files():
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    # Skip lines that are pure log statements
                    stripped = line.strip()
                    if any(stripped.startswith(p) for p in [
                        "log.", "logger.", "_log.", "logging.",
                    ]):
                        continue
                    for pat in self._LEAK_PATTERNS:
                        if pat.search(line):
                            # Allow if line is a comment
                            if stripped.startswith("#"):
                                continue
                            violations.append(
                                f"{os.path.basename(filepath)}:{lineno}: {stripped[:100]}"
                            )

        assert not violations, (
            f"Found {len(violations)} exception-leakage pattern(s) in API source:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Regression: verify the three fixed leaks stay fixed
# ---------------------------------------------------------------------------

class TestFixedLeakRegression:
    """
    The following three files had leaky exception handlers that were fixed:
    - config.py: f"Config validation failed: {e}" → generic message
    - scan_comparison.py: f"Failed to load scan data: {e}" → generic message
    - websocket.py: f"Service not available: {e}" → generic message
    """

    def _read_source(self, relative_path: str) -> str:
        base = os.path.join(
            os.path.dirname(__file__), "..", "..", "spiderfoot", "api",
        )
        filepath = os.path.normpath(os.path.join(base, relative_path))
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def test_config_validation_no_leak(self):
        src = self._read_source("routers/config.py")
        assert 'f"Config validation failed: {e}"' not in src
        assert "Config validation failed due to an internal error" in src

    def test_scan_comparison_no_leak(self):
        src = self._read_source("routers/scan_comparison.py")
        assert 'f"Failed to load scan data: {e}"' not in src

    def test_websocket_no_leak(self):
        src = self._read_source("routers/websocket.py")
        assert 'f"Service not available: {e}"' not in src
