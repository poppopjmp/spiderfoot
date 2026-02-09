"""
Tests for Cycle 21 — Scan Event Bridge.

Validates the ScanEventBridge that routes live scan events from
the scanner's waitForThreads() loop to the EventRelay for
real-time WebSocket delivery.
"""
import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from spiderfoot.scan_event_bridge import (
    ScanEventBridge,
    create_scan_bridge,
    get_scan_bridge,
    teardown_scan_bridge,
    list_active_bridges,
    reset_bridges,
)
from spiderfoot.event_relay import EventRelay, reset_event_relay


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

class FakeEvent:
    """Minimal SpiderFootEvent mock."""
    def __init__(self, event_type="IP_ADDRESS", data="1.2.3.4",
                 module="sfp_test", confidence=100, visibility=100,
                 risk=0, generated=0):
        self.eventType = event_type
        self.data = data
        self.module = module
        self.confidence = confidence
        self.visibility = visibility
        self.risk = risk
        self.generated = generated or time.time()
        self.sourceEvent = None
        self.sourceEventHash = "ROOT"


def _fresh_relay():
    """Create a fresh EventRelay instance."""
    return EventRelay(max_queue_size=100)


# =====================================================================
# ScanEventBridge unit tests
# =====================================================================

class TestScanEventBridgeLifecycle:

    def test_start(self):
        relay = _fresh_relay()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start(target="example.com")
        assert bridge._started is True

    def test_start_idempotent(self):
        relay = _fresh_relay()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.start()  # should not raise
        assert bridge._started is True

    def test_stop(self):
        relay = _fresh_relay()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.stop("FINISHED")
        assert bridge._stopped is True

    def test_stop_idempotent(self):
        relay = _fresh_relay()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.stop("FINISHED")
        bridge.stop("FINISHED")  # should not raise
        assert bridge._stopped is True

    def test_stop_pushes_completion(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start(target="example.com")
        bridge.stop("FINISHED")
        # Should have called push_scan_started, push_scan_completed, push_event(stats)
        assert relay.push_scan_started.called
        assert relay.push_scan_completed.called
        # At least 3 relay calls: started + completed + stats
        assert relay.push_event.call_count >= 1


class TestScanEventBridgeForwarding:

    def test_forward_event(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        event = FakeEvent()
        result = bridge.forward(event)
        assert result is True
        relay.push_event.assert_called()

    def test_forward_increments_counter(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        bridge.forward(FakeEvent(event_type="DOMAIN_NAME"))
        assert bridge._events_forwarded == 2
        assert bridge._events_by_type["IP_ADDRESS"] == 1
        assert bridge._events_by_type["DOMAIN_NAME"] == 1

    def test_forward_after_stop_returns_false(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.stop()
        result = bridge.forward(FakeEvent())
        assert result is False

    def test_throttling(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=500)
        bridge.start()
        # First event should go through
        result1 = bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        # Second same-type event within 500ms should be throttled
        result2 = bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        assert result1 is True
        assert result2 is False
        assert bridge._events_throttled == 1

    def test_throttle_different_types(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=500)
        bridge.start()
        result1 = bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        result2 = bridge.forward(FakeEvent(event_type="DOMAIN_NAME"))
        # Different event types shouldn't throttle each other
        assert result1 is True
        assert result2 is True

    def test_throttle_zero_disables(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        result1 = bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        result2 = bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        assert result1 is True
        assert result2 is True

    def test_push_status(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.push_status("RUNNING", event_count=5)
        relay.push_status_update.assert_called_with("scan-1", "RUNNING", 5)

    def test_push_status_after_stop(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
        bridge.start()
        bridge.stop()
        relay.push_status_update.reset_mock()
        bridge.push_status("RUNNING")
        relay.push_status_update.assert_not_called()


class TestScanEventBridgeSerialization:

    def test_serialize_basic_event(self):
        event = FakeEvent(
            event_type="IP_ADDRESS",
            data="1.2.3.4",
            module="sfp_dns",
            confidence=90,
            risk=20,
        )
        result = ScanEventBridge._serialize_event(event)
        assert result["event_type"] == "IP_ADDRESS"
        assert result["data"] == "1.2.3.4"
        assert result["module"] == "sfp_dns"
        assert result["confidence"] == 90
        assert result["risk"] == 20

    def test_serialize_truncates_large_data(self):
        event = FakeEvent(data="x" * 10000)
        result = ScanEventBridge._serialize_event(event)
        assert len(result["data"]) < 5000
        assert "[truncated]" in result["data"]

    def test_serialize_no_source_event(self):
        event = FakeEvent()
        event.sourceEvent = None
        result = ScanEventBridge._serialize_event(event)
        assert result["source_event"] is None

    def test_serialize_with_source_event(self):
        parent = FakeEvent(event_type="ROOT")
        event = FakeEvent()
        event.sourceEvent = parent
        result = ScanEventBridge._serialize_event(event)
        assert result["source_event"] == "ROOT"


class TestScanEventBridgeStats:

    def test_stats_initial(self):
        bridge = ScanEventBridge("scan-1", relay=MagicMock(), throttle_ms=0)
        stats = bridge.stats
        assert stats["scan_id"] == "scan-1"
        assert stats["started"] is False
        assert stats["stopped"] is False
        assert stats["events_forwarded"] == 0
        assert stats["events_throttled"] == 0

    def test_stats_after_events(self):
        bridge = ScanEventBridge("scan-1", relay=MagicMock(), throttle_ms=0)
        bridge.start()
        bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        bridge.forward(FakeEvent(event_type="IP_ADDRESS"))
        bridge.forward(FakeEvent(event_type="DOMAIN_NAME"))
        stats = bridge.stats
        assert stats["events_forwarded"] == 3
        assert stats["events_by_type"]["IP_ADDRESS"] == 2
        assert stats["events_by_type"]["DOMAIN_NAME"] == 1
        assert stats["duration"] >= 0


# =====================================================================
# Bridge registry
# =====================================================================

class TestBridgeRegistry:

    def setup_method(self):
        reset_bridges()

    def teardown_method(self):
        reset_bridges()

    def test_create_scan_bridge(self):
        bridge = create_scan_bridge("scan-1", relay=MagicMock())
        assert bridge is not None
        assert bridge.scan_id == "scan-1"

    def test_create_scan_bridge_idempotent(self):
        b1 = create_scan_bridge("scan-1", relay=MagicMock())
        b2 = create_scan_bridge("scan-1", relay=MagicMock())
        assert b1 is b2

    def test_get_scan_bridge(self):
        create_scan_bridge("scan-1", relay=MagicMock())
        bridge = get_scan_bridge("scan-1")
        assert bridge is not None
        assert bridge.scan_id == "scan-1"

    def test_get_scan_bridge_none(self):
        assert get_scan_bridge("nonexistent") is None

    def test_teardown_scan_bridge(self):
        relay = MagicMock()
        bridge = create_scan_bridge("scan-1", relay=relay)
        bridge.start()
        teardown_scan_bridge("scan-1", status="FINISHED")
        assert get_scan_bridge("scan-1") is None
        assert bridge._stopped is True

    def test_teardown_nonexistent(self):
        # Should not raise
        teardown_scan_bridge("nonexistent")

    def test_list_active_bridges(self):
        create_scan_bridge("scan-1", relay=MagicMock())
        create_scan_bridge("scan-2", relay=MagicMock())
        active = list_active_bridges()
        assert "scan-1" in active
        assert "scan-2" in active

    def test_reset_bridges(self):
        create_scan_bridge("scan-1", relay=MagicMock())
        reset_bridges()
        assert list_active_bridges() == []


# =====================================================================
# Integration with EventRelay
# =====================================================================

class TestBridgeRelayIntegration:

    def test_forward_reaches_relay_consumer(self):
        import asyncio

        async def _test():
            relay = EventRelay(max_queue_size=100)
            q = relay.register_consumer("scan-1")

            bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
            bridge.start(target="example.com")

            # scan_started should be in queue
            event = await asyncio.wait_for(q.get(), timeout=1)
            assert event["type"] == "scan_started"

            # Forward an event
            bridge.forward(FakeEvent(event_type="IP_ADDRESS", data="10.0.0.1"))

            event = await asyncio.wait_for(q.get(), timeout=1)
            assert event["type"] == "new_event"
            assert event["data"]["event_type"] == "IP_ADDRESS"
            assert event["data"]["data"] == "10.0.0.1"

            relay.unregister_consumer("scan-1", q)

        asyncio.run(_test())

    def test_stop_sends_completion_to_consumer(self):
        import asyncio

        async def _test():
            relay = EventRelay(max_queue_size=100)
            q = relay.register_consumer("scan-1")

            bridge = ScanEventBridge("scan-1", relay=relay, throttle_ms=0)
            bridge.start()

            # Drain scan_started
            await asyncio.wait_for(q.get(), timeout=1)

            bridge.stop("FINISHED")

            # Should get scan_completed and scan_stats
            events = []
            try:
                while True:
                    ev = await asyncio.wait_for(q.get(), timeout=1)
                    events.append(ev)
            except (asyncio.TimeoutError, Exception):
                pass

            types = [e["type"] for e in events]
            assert "scan_completed" in types
            assert "scan_stats" in types

            relay.unregister_consumer("scan-1", q)

        asyncio.run(_test())

    def test_no_consumers_no_error(self):
        """If no consumers are registered, forwarding still works."""
        relay = EventRelay(max_queue_size=100)
        bridge = ScanEventBridge("scan-no-consumers", relay=relay, throttle_ms=0)
        bridge.start()
        result = bridge.forward(FakeEvent())
        # Should not raise, just deliver to 0 consumers
        assert result is True
        bridge.stop()


# =====================================================================
# Service integration wiring
# =====================================================================

class TestServiceIntegrationWiring:

    def test_wire_scan_event_bridge(self):
        from spiderfoot.service_integration import _wire_scan_event_bridge
        reset_bridges()

        scanner = MagicMock()
        scanner._SpiderFootScanner__targetValue = "example.com"
        _wire_scan_event_bridge(scanner, "scan-test-123")

        # Bridge should be attached to scanner
        assert hasattr(scanner, '_event_bridge')
        bridge = scanner._event_bridge
        assert bridge.scan_id == "scan-test-123"
        assert bridge._started is True

        # Cleanup
        teardown_scan_bridge("scan-test-123")
        reset_bridges()

    def test_complete_scan_services_tears_down_bridge(self):
        from spiderfoot.service_integration import complete_scan_services
        reset_bridges()

        relay = MagicMock()
        bridge = create_scan_bridge("scan-teardown", relay=relay)
        bridge.start()

        # complete_scan_services should teardown the bridge
        complete_scan_services("scan-teardown", status="FINISHED", duration=10.0)

        assert get_scan_bridge("scan-teardown") is None
        assert bridge._stopped is True

        reset_bridges()


# =====================================================================
# Thread safety
# =====================================================================

class TestBridgeThreadSafety:

    def test_concurrent_forwarding(self):
        relay = MagicMock()
        bridge = ScanEventBridge("scan-thread", relay=relay, throttle_ms=0)
        bridge.start()

        errors = []

        def forward_events(n):
            try:
                for _ in range(n):
                    bridge.forward(FakeEvent())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=forward_events, args=(50,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert bridge._events_forwarded == 200
        bridge.stop()
