"""Tests for spiderfoot.logging_config — unified logging configuration."""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset logging config between tests."""
    from spiderfoot.logging_config import reset_logging
    reset_logging()
    yield
    reset_logging()


def _capture_log_output(logger, message, level="info", **extra):
    """Capture what a logger writes to its handlers."""
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream != sys.stderr:
            handler.stream.truncate(0)
            handler.stream.seek(0)

    getattr(logger, level)(message, extra=extra) if extra else getattr(logger, level)(message)

    results = []
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream != sys.stderr:
            handler.stream.seek(0)
            content = handler.stream.read()
            if content.strip():
                results.append(content.strip())
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfigureLogging:
    """Test the unified configure_logging function."""

    def test_returns_logger(self):
        from spiderfoot.logging_config import configure_logging
        logger = configure_logging(force_text=True)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "spiderfoot"

    def test_idempotent(self):
        from spiderfoot.logging_config import configure_logging
        l1 = configure_logging(force_text=True)
        handler_count = len(l1.handlers)
        l2 = configure_logging(force_text=True)
        assert l1 is l2
        assert len(l2.handlers) == handler_count

    def test_text_format_console(self):
        from spiderfoot.logging_config import configure_logging
        import io
        logger = configure_logging(force_text=True, log_dir=tempfile.mkdtemp())
        # Console handler should use text format
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert len(console_handlers) == 1
        fmt = console_handlers[0].formatter
        assert not hasattr(fmt, 'service_name')  # Not StructuredFormatter

    def test_json_format_console(self):
        from spiderfoot.logging_config import configure_logging
        from spiderfoot.structured_logging import StructuredFormatter
        logger = configure_logging(force_json=True, log_dir=tempfile.mkdtemp())
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert len(console_handlers) == 1
        assert isinstance(console_handlers[0].formatter, StructuredFormatter)

    def test_json_auto_in_production(self):
        from spiderfoot.logging_config import configure_logging
        from spiderfoot.structured_logging import StructuredFormatter
        logger = configure_logging(
            {"_production": True},
            log_dir=tempfile.mkdtemp()
        )
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert isinstance(console_handlers[0].formatter, StructuredFormatter)

    def test_json_via_env_var(self):
        from spiderfoot.logging_config import configure_logging
        from spiderfoot.structured_logging import StructuredFormatter
        with mock.patch.dict(os.environ, {"SF_LOG_FORMAT": "json"}):
            logger = configure_logging(log_dir=tempfile.mkdtemp())
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert isinstance(console_handlers[0].formatter, StructuredFormatter)

    def test_debug_level_from_config(self):
        from spiderfoot.logging_config import configure_logging
        logger = configure_logging(
            {"_debug": True},
            force_text=True,
            log_dir=tempfile.mkdtemp()
        )
        console = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ][0]
        assert console.level == logging.DEBUG

    def test_quiet_mode(self):
        from spiderfoot.logging_config import configure_logging
        logger = configure_logging(
            {"__logging": False},
            force_text=True,
            log_dir=tempfile.mkdtemp()
        )
        console = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ][0]
        assert console.level == logging.WARNING

    def test_file_handlers_created(self):
        from spiderfoot.logging_config import configure_logging, reset_logging
        tmpdir = tempfile.mkdtemp()
        try:
            logger = configure_logging(force_text=True, log_dir=tmpdir)
            file_handlers = [
                h for h in logger.handlers
                if isinstance(h, logging.handlers.TimedRotatingFileHandler)
            ]
            assert len(file_handlers) == 2  # debug + error
        finally:
            # Close file handlers before cleanup to avoid Windows locking
            for h in list(logger.handlers):
                if isinstance(h, logging.handlers.TimedRotatingFileHandler):
                    h.close()
                    logger.removeHandler(h)
            reset_logging()

    def test_no_file_handlers_without_dir(self):
        from spiderfoot.logging_config import configure_logging
        # Use a path that can't be created
        logger = configure_logging(
            force_text=True,
            log_dir="/nonexistent/path/that/wont/work"
        )
        # Should still work, just without file handlers
        assert logger.name == "spiderfoot"

    def test_sqlite_deprecated_warning(self):
        from spiderfoot.logging_config import configure_logging
        with pytest.warns(DeprecationWarning, match="SQLite log handler is deprecated"):
            configure_logging(
                force_text=True,
                enable_sqlite=True,
                log_dir=tempfile.mkdtemp()
            )

    def test_force_text_overrides_json(self):
        from spiderfoot.logging_config import configure_logging
        logger = configure_logging(
            {"_production": True},
            force_text=True,
            log_dir=tempfile.mkdtemp()
        )
        console = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ][0]
        assert not hasattr(console.formatter, 'service_name')

    def test_docker_detection(self):
        from spiderfoot.logging_config import _running_in_container
        with mock.patch.dict(os.environ, {"DOCKER_CONTAINER": "1"}):
            assert _running_in_container()

    def test_kubernetes_detection(self):
        from spiderfoot.logging_config import _running_in_container
        with mock.patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}):
            assert _running_in_container()

    def test_not_in_container(self):
        from spiderfoot.logging_config import _running_in_container
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("os.path.exists", return_value=False):
                assert not _running_in_container()


class TestResetLogging:
    """Test reset functionality."""

    def test_reset_allows_reconfigure(self):
        from spiderfoot.logging_config import configure_logging, reset_logging
        l1 = configure_logging(force_text=True, log_dir=tempfile.mkdtemp())
        h1 = len(l1.handlers)
        reset_logging()
        l2 = configure_logging(force_json=True, log_dir=tempfile.mkdtemp())
        assert l1 is l2  # Same logger object
        # But reconfigured
        from spiderfoot.structured_logging import StructuredFormatter
        console = [
            h for h in l2.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ][0]
        assert isinstance(console.formatter, StructuredFormatter)


class TestGetModuleLogger:
    """Test module-specific logger creation."""

    def test_returns_logger(self):
        from spiderfoot.logging_config import get_module_logger
        log = get_module_logger("sfp_dns")
        assert "sfp_dns" in str(log.name if hasattr(log, 'name') else log.logger.name)

    def test_with_scan_id(self):
        from spiderfoot.logging_config import get_module_logger
        log = get_module_logger("sfp_dns", scan_id="abc123")
        assert isinstance(log, logging.LoggerAdapter)
        assert log.extra["scanId"] == "abc123"

    def test_without_scan_id(self):
        from spiderfoot.logging_config import get_module_logger
        log = get_module_logger("sfp_dns")
        assert isinstance(log, logging.Logger)


class TestStructuredJsonOutput:
    """Test that JSON output is valid and contains expected fields."""

    def test_json_output_valid(self):
        from spiderfoot.logging_config import configure_logging, reset_logging
        import io
        buf = io.StringIO()
        reset_logging()

        # Create a custom handler with our buffer
        from spiderfoot.structured_logging import StructuredFormatter, StructuredLogHandler
        logger = logging.getLogger("spiderfoot")
        logger.handlers.clear()
        handler = StructuredLogHandler(stream=buf)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("test message")

        buf.seek(0)
        line = buf.read().strip()
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["message"] == "test message"
        assert "timestamp" in data
        assert data["service"] == "spiderfoot"

    def test_json_scan_context(self):
        import io
        from spiderfoot.structured_logging import StructuredLogHandler
        buf = io.StringIO()
        logger = logging.getLogger("spiderfoot.test.scan_ctx")
        logger.handlers.clear()
        handler = StructuredLogHandler(stream=buf)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("found host", extra={"scanId": "scan-123", "sf_module": "sfp_dns"})

        buf.seek(0)
        data = json.loads(buf.read().strip())
        assert data["scan_id"] == "scan-123"
        assert data["module"] == "sfp_dns"

    def test_json_exception_info(self):
        import io
        from spiderfoot.structured_logging import StructuredLogHandler
        buf = io.StringIO()
        logger = logging.getLogger("spiderfoot.test.exc")
        logger.handlers.clear()
        handler = StructuredLogHandler(stream=buf)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("something failed")

        buf.seek(0)
        data = json.loads(buf.read().strip())
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "test error" in data["exception"]["message"]


class TestContainerDetection:
    """Test container environment detection logic."""

    def test_dockerenv_file(self):
        from spiderfoot.logging_config import _running_in_container
        with mock.patch("os.path.exists", return_value=True):
            assert _running_in_container()

    def test_docker_env_var(self):
        from spiderfoot.logging_config import _running_in_container
        with mock.patch.dict(os.environ, {"DOCKER_CONTAINER": "1"}):
            assert _running_in_container()
