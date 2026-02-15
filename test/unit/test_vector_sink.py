"""Tests for the Vector.dev integration sink."""
from __future__ import annotations

import json
import logging
import pytest
from unittest.mock import patch, MagicMock

from spiderfoot.vector_sink import VectorConfig, VectorSink, VectorLogHandler


class TestVectorConfig:
    """Tests for VectorConfig."""

    def test_default_config(self):
        config = VectorConfig()
        assert config.enabled is False
        assert config.endpoint == "http://localhost:8686"
        assert config.batch_size == 50

    def test_from_sf_config(self):
        sf_config = {
            "_vector_enabled": True,
            "_vector_endpoint": "http://vector:8686",
            "_vector_batch_size": 100,
        }
        config = VectorConfig.from_sf_config(sf_config)
        assert config.enabled is True
        assert config.endpoint == "http://vector:8686"
        assert config.batch_size == 100

    def test_from_sf_config_defaults(self):
        config = VectorConfig.from_sf_config({})
        assert config.enabled is False
        assert config.environment == "development"


class TestVectorSink:
    """Tests for VectorSink."""

    def test_disabled_sink(self):
        config = VectorConfig(enabled=False)
        sink = VectorSink(config)
        sink.start()
        assert sink._running is False

    def test_emit_event_when_disabled(self):
        config = VectorConfig(enabled=False)
        sink = VectorSink(config)
        sink.emit_event("test", {"key": "value"})
        assert sink._buffer.qsize() == 0

    def test_emit_scan_event(self):
        config = VectorConfig(enabled=True)
        sink = VectorSink(config)
        sink._running = True  # Simulate started without thread
        
        sink.emit_scan_event(
            scan_id="scan1",
            event_type="IP_ADDRESS",
            module="sfp_dns",
            data="1.2.3.4",
            confidence=95,
            risk=20,
        )
        
        assert sink._buffer.qsize() == 1
        event = sink._buffer.get_nowait()
        assert event["scan_id"] == "scan1"
        assert event["event_type"] == "IP_ADDRESS"
        assert event["type"] == "scan_event"

    def test_emit_scan_status(self):
        config = VectorConfig(enabled=True)
        sink = VectorSink(config)
        sink._running = True
        
        sink.emit_scan_status(
            scan_id="scan1",
            status="RUNNING",
            target="example.com",
            progress=50.0,
        )
        
        event = sink._buffer.get_nowait()
        assert event["status"] == "RUNNING"
        assert event["type"] == "scan_status"

    def test_emit_metric(self):
        config = VectorConfig(enabled=True)
        sink = VectorSink(config)
        sink._running = True
        
        sink.emit_metric("events_per_second", 42.5, {"scan_id": "s1"})
        
        event = sink._buffer.get_nowait()
        assert event["metric_name"] == "events_per_second"
        assert event["metric_value"] == 42.5
        assert event["type"] == "metric"

    def test_stats(self):
        config = VectorConfig(enabled=True)
        sink = VectorSink(config)
        stats = sink.stats
        assert stats["events_sent"] == 0
        assert stats["events_dropped"] == 0


class TestVectorLogHandler:
    """Tests for VectorLogHandler."""

    def test_handler_emits_to_sink(self):
        config = VectorConfig(enabled=True)
        sink = VectorSink(config)
        sink._running = True
        
        handler = VectorLogHandler(sink)
        logger = logging.getLogger("test.vector.handler")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        logger.info("Test message")
        
        assert sink._buffer.qsize() == 1
        event = sink._buffer.get_nowait()
        assert event["type"] == "log"
        assert event["message"] == "Test message"
        assert event["level"] == "INFO"
        
        logger.removeHandler(handler)
