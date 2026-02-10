"""Tests for the SpiderFoot structured logging module."""
from __future__ import annotations

import json
import logging
import io
import pytest

from spiderfoot.structured_logging import (
    StructuredFormatter,
    StructuredLogHandler,
    EventLogEmitter,
    setup_structured_logging,
)


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    def test_basic_format(self):
        formatter = StructuredFormatter(include_hostname=False)
        record = logging.LogRecord(
            name="spiderfoot.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "spiderfoot.test"
        assert parsed["message"] == "Test message"
        assert parsed["service"] == "spiderfoot"
        assert "timestamp" in parsed

    def test_scan_id_extra(self):
        formatter = StructuredFormatter(include_hostname=False)
        record = logging.LogRecord(
            name="spiderfoot.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Scanning",
            args=None,
            exc_info=None,
        )
        record.scanId = "abc123"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["scan_id"] == "abc123"

    def test_exception_format(self):
        formatter = StructuredFormatter(include_hostname=False)
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="spiderfoot.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=None,
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"

    def test_caller_info(self):
        formatter = StructuredFormatter(include_caller=True, include_hostname=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/src/test.py",
            lineno=42,
            msg="test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "caller" in parsed
        assert parsed["caller"]["line"] == 42

    def test_extra_fields(self):
        formatter = StructuredFormatter(
            include_hostname=False,
            extra_fields={"version": "5.4.1", "cluster": "us-east"}
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["version"] == "5.4.1"
        assert parsed["cluster"] == "us-east"


class TestStructuredLogHandler:
    """Tests for StructuredLogHandler."""

    def test_handler_writes_json(self):
        stream = io.StringIO()
        handler = StructuredLogHandler(stream=stream, include_hostname=False)
        
        logger = logging.getLogger("test.structured.handler")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        logger.info("Test message from handler")
        
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["message"] == "Test message from handler"
        
        logger.removeHandler(handler)


class TestEventLogEmitter:
    """Tests for EventLogEmitter."""

    def test_emit_scan_event(self):
        stream = io.StringIO()
        handler = StructuredLogHandler(stream=stream, include_hostname=False)
        
        log = logging.getLogger("spiderfoot.events")
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        
        emitter = EventLogEmitter()
        emitter.emit_scan_event(
            scan_id="scan123",
            event_type="IP_ADDRESS",
            module="sfp_dnsresolve",
            data="1.2.3.4",
            confidence=95,
            risk=20,
        )
        
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        
        assert parsed["scan_id"] == "scan123"
        assert parsed["event_type"] == "IP_ADDRESS"
        assert parsed["sf_module"] == "sfp_dnsresolve"
        assert parsed["log_type"] == "scan_event"
        
        log.removeHandler(handler)

    def test_emit_scan_status(self):
        stream = io.StringIO()
        handler = StructuredLogHandler(stream=stream, include_hostname=False)
        
        log = logging.getLogger("spiderfoot.events")
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        
        emitter = EventLogEmitter()
        emitter.emit_scan_status(
            scan_id="scan123",
            status="RUNNING",
            target="example.com",
            modules_count=50,
            events_count=1000,
        )
        
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        
        assert parsed["scan_status"] == "RUNNING"
        assert parsed["log_type"] == "scan_status"
        
        log.removeHandler(handler)
