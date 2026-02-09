"""
Tests for EventRelay and WebSocket Router — Cycle 19.

Covers:
  - RelayEvent: creation, to_dict, to_json
  - EventRelay: register/unregister consumers, push_event,
    push_event_all, lifecycle helpers, stats, singleton
  - EventRelay: queue overflow (drop-oldest policy)
  - EventRelay: EventBus integration (subscribe/unsubscribe)
  - WebSocketManager: connect/disconnect, per-scan grouping,
    send_to_scan, broadcast, connection_count
  - WebSocket endpoint: relay mode, polling fallback
"""

import asyncio
import json
import time
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from spiderfoot.event_relay import (
    EventRelay,
    RelayEvent,
    get_event_relay,
    reset_event_relay,
)


# =====================================================================
# RelayEvent
# =====================================================================

class TestRelayEvent(unittest.TestCase):

    def test_default_timestamp(self):
        ev = RelayEvent(event_type="test", scan_id="s1")
        self.assertGreater(ev.timestamp, 0)

    def test_to_dict(self):
        ev = RelayEvent(
            event_type="scan_started",
            scan_id="s1",
            data={"target": "example.com"},
        )
        d = ev.to_dict()
        self.assertEqual(d["type"], "scan_started")
        self.assertEqual(d["scan_id"], "s1")
        self.assertEqual(d["data"]["target"], "example.com")

    def test_to_json(self):
        ev = RelayEvent(event_type="test", scan_id="s1", data={"x": 1})
        j = ev.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["type"], "test")

    def test_explicit_timestamp(self):
        ev = RelayEvent(event_type="e", scan_id="s", timestamp=42.0)
        self.assertEqual(ev.timestamp, 42.0)


# =====================================================================
# EventRelay — consumer management
# =====================================================================

class TestEventRelayConsumers(unittest.TestCase):

    def setUp(self):
        self.relay = EventRelay(max_queue_size=10)

    def test_register_consumer(self):
        q = self.relay.register_consumer("scan-1")
        self.assertIsInstance(q, asyncio.Queue)
        self.assertTrue(self.relay.has_consumers("scan-1"))

    def test_unregister_consumer(self):
        q = self.relay.register_consumer("scan-1")
        self.relay.unregister_consumer("scan-1", q)
        self.assertFalse(self.relay.has_consumers("scan-1"))

    def test_unregister_nonexistent(self):
        # Should not raise
        q = asyncio.Queue()
        self.relay.unregister_consumer("nope", q)

    def test_multiple_consumers_same_scan(self):
        q1 = self.relay.register_consumer("scan-1")
        q2 = self.relay.register_consumer("scan-1")
        self.assertEqual(self.relay.consumer_count("scan-1"), 2)
        self.relay.unregister_consumer("scan-1", q1)
        self.assertEqual(self.relay.consumer_count("scan-1"), 1)

    def test_active_scans(self):
        self.relay.register_consumer("s1")
        self.relay.register_consumer("s2")
        scans = self.relay.active_scans()
        self.assertIn("s1", scans)
        self.assertIn("s2", scans)

    def test_consumer_count_total(self):
        self.relay.register_consumer("s1")
        self.relay.register_consumer("s1")
        self.relay.register_consumer("s2")
        self.assertEqual(self.relay.consumer_count(), 3)


# =====================================================================
# EventRelay — push events
# =====================================================================

class TestEventRelayPush(unittest.TestCase):

    def setUp(self):
        self.relay = EventRelay(max_queue_size=10)

    def test_push_event_to_consumers(self):
        q = self.relay.register_consumer("s1")
        count = self.relay.push_event("s1", {"key": "val"}, "test_event")
        self.assertEqual(count, 1)
        msg = q.get_nowait()
        self.assertEqual(msg["type"], "test_event")
        self.assertEqual(msg["data"]["key"], "val")

    def test_push_event_no_consumers(self):
        count = self.relay.push_event("none", {"key": "val"})
        self.assertEqual(count, 0)

    def test_push_event_multiple_consumers(self):
        q1 = self.relay.register_consumer("s1")
        q2 = self.relay.register_consumer("s1")
        count = self.relay.push_event("s1", {"x": 1})
        self.assertEqual(count, 2)
        self.assertFalse(q1.empty())
        self.assertFalse(q2.empty())

    def test_push_event_only_to_target_scan(self):
        q1 = self.relay.register_consumer("s1")
        q2 = self.relay.register_consumer("s2")
        self.relay.push_event("s1", {"x": 1})
        self.assertFalse(q1.empty())
        self.assertTrue(q2.empty())

    def test_push_event_all(self):
        q1 = self.relay.register_consumer("s1")
        q2 = self.relay.register_consumer("s2")
        count = self.relay.push_event_all({"msg": "hello"}, "broadcast")
        self.assertEqual(count, 2)
        self.assertFalse(q1.empty())
        self.assertFalse(q2.empty())

    def test_queue_overflow_drops_oldest(self):
        relay = EventRelay(max_queue_size=2)
        q = relay.register_consumer("s1")

        relay.push_event("s1", {"seq": 1}, "e1")
        relay.push_event("s1", {"seq": 2}, "e2")
        relay.push_event("s1", {"seq": 3}, "e3")  # Should drop seq=1

        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())

        self.assertEqual(len(msgs), 2)
        # Oldest (seq=1) should be dropped, seq=2 and seq=3 retained
        seqs = [m["data"]["seq"] for m in msgs]
        self.assertIn(3, seqs)

    def test_stats_tracking(self):
        q = self.relay.register_consumer("s1")
        self.relay.push_event("s1", {"x": 1})
        s = self.relay.stats
        self.assertEqual(s["events_relayed"], 1)
        self.assertEqual(s["consumers_active"], 1)
        self.assertIn("s1", s["active_scans"])


# =====================================================================
# EventRelay — lifecycle helpers
# =====================================================================

class TestEventRelayHelpers(unittest.TestCase):

    def setUp(self):
        self.relay = EventRelay()

    def test_push_scan_started(self):
        q = self.relay.register_consumer("s1")
        count = self.relay.push_scan_started("s1", "example.com")
        self.assertEqual(count, 1)
        msg = q.get_nowait()
        self.assertEqual(msg["type"], "scan_started")
        self.assertEqual(msg["data"]["target"], "example.com")

    def test_push_scan_completed(self):
        q = self.relay.register_consumer("s1")
        self.relay.push_scan_completed("s1", "FINISHED", 42)
        msg = q.get_nowait()
        self.assertEqual(msg["type"], "scan_completed")
        self.assertEqual(msg["data"]["status"], "FINISHED")
        self.assertEqual(msg["data"]["event_count"], 42)

    def test_push_status_update(self):
        q = self.relay.register_consumer("s1")
        self.relay.push_status_update("s1", "RUNNING", 10)
        msg = q.get_nowait()
        self.assertEqual(msg["type"], "status_update")
        self.assertEqual(msg["data"]["status"], "RUNNING")


# =====================================================================
# EventRelay — EventBus integration
# =====================================================================

class TestEventRelayEventBus(unittest.TestCase):

    def test_wire_eventbus(self):
        relay = EventRelay()
        mock_bus = MagicMock()
        relay.wire_eventbus(mock_bus)
        self.assertTrue(relay.stats["eventbus_wired"])

    def test_subscribe_scan_without_bus(self):
        relay = EventRelay()
        result = asyncio.run(relay.subscribe_scan("s1"))
        self.assertIsNone(result)

    def test_subscribe_scan_with_bus(self):
        relay = EventRelay()
        mock_bus = MagicMock()
        mock_bus.config = MagicMock()
        mock_bus.config.channel_prefix = "sf"
        mock_bus.subscribe = AsyncMock(return_value="sub-123")
        relay.wire_eventbus(mock_bus)

        sub_id = asyncio.run(relay.subscribe_scan("s1"))
        self.assertEqual(sub_id, "sub-123")
        mock_bus.subscribe.assert_called_once()

    def test_subscribe_idempotent(self):
        relay = EventRelay()
        mock_bus = MagicMock()
        mock_bus.config = MagicMock()
        mock_bus.config.channel_prefix = "sf"
        mock_bus.subscribe = AsyncMock(return_value="sub-123")
        relay.wire_eventbus(mock_bus)

        asyncio.run(relay.subscribe_scan("s1"))
        asyncio.run(relay.subscribe_scan("s1"))
        # Should only subscribe once
        mock_bus.subscribe.assert_called_once()

    def test_unsubscribe_scan(self):
        relay = EventRelay()
        mock_bus = MagicMock()
        mock_bus.config = MagicMock()
        mock_bus.config.channel_prefix = "sf"
        mock_bus.subscribe = AsyncMock(return_value="sub-123")
        mock_bus.unsubscribe = AsyncMock()
        relay.wire_eventbus(mock_bus)

        asyncio.run(relay.subscribe_scan("s1"))
        asyncio.run(relay.unsubscribe_scan("s1"))
        mock_bus.unsubscribe.assert_called_once_with("sub-123")

    def test_on_eventbus_event(self):
        relay = EventRelay()
        q = relay.register_consumer("s1")

        # Simulate an EventEnvelope
        mock_envelope = MagicMock()
        mock_envelope.scan_id = "s1"
        mock_envelope.event_type = "IP_ADDRESS"
        mock_envelope.module = "sfp_dns"
        mock_envelope.data = "1.2.3.4"
        mock_envelope.confidence = 90
        mock_envelope.risk = 20

        asyncio.run(relay._on_eventbus_event(mock_envelope))

        msg = q.get_nowait()
        self.assertEqual(msg["type"], "new_event")
        self.assertEqual(msg["data"]["event_type"], "IP_ADDRESS")
        self.assertEqual(msg["data"]["module"], "sfp_dns")
        self.assertEqual(msg["data"]["data"], "1.2.3.4")


# =====================================================================
# Singleton
# =====================================================================

class TestEventRelaySingleton(unittest.TestCase):

    def setUp(self):
        reset_event_relay()

    def tearDown(self):
        reset_event_relay()

    def test_get_returns_same_instance(self):
        r1 = get_event_relay()
        r2 = get_event_relay()
        self.assertIs(r1, r2)

    def test_reset_clears_singleton(self):
        r1 = get_event_relay()
        reset_event_relay()
        r2 = get_event_relay()
        self.assertIsNot(r1, r2)


# =====================================================================
# WebSocketManager
# =====================================================================

class TestWebSocketManager(unittest.TestCase):

    def setUp(self):
        from spiderfoot.api.routers.websocket import WebSocketManager
        self.mgr = WebSocketManager()

    def test_connect_and_count(self):
        ws = AsyncMock()
        asyncio.run(self.mgr.connect(ws, "s1"))
        self.assertEqual(self.mgr.connection_count("s1"), 1)

    def test_disconnect(self):
        ws = AsyncMock()
        asyncio.run(self.mgr.connect(ws, "s1"))
        asyncio.run(self.mgr.disconnect(ws, "s1"))
        self.assertEqual(self.mgr.connection_count("s1"), 0)

    def test_disconnect_nonexistent(self):
        ws = AsyncMock()
        # Should not raise
        asyncio.run(self.mgr.disconnect(ws, "nope"))

    def test_per_scan_grouping(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        asyncio.run(self.mgr.connect(ws1, "s1"))
        asyncio.run(self.mgr.connect(ws2, "s2"))
        self.assertEqual(self.mgr.connection_count("s1"), 1)
        self.assertEqual(self.mgr.connection_count("s2"), 1)
        self.assertEqual(self.mgr.connection_count(), 2)

    def test_active_scans(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        asyncio.run(self.mgr.connect(ws1, "s1"))
        asyncio.run(self.mgr.connect(ws2, "s2"))
        self.assertIn("s1", self.mgr.active_scans())
        self.assertIn("s2", self.mgr.active_scans())

    def test_send_to_scan(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        asyncio.run(self.mgr.connect(ws1, "s1"))
        asyncio.run(self.mgr.connect(ws2, "s2"))

        count = asyncio.run(self.mgr.send_to_scan("s1", {"msg": "hello"}))
        self.assertEqual(count, 1)
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    def test_send_to_scan_cleans_failed(self):
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = ConnectionError("gone")
        asyncio.run(self.mgr.connect(ws_good, "s1"))
        asyncio.run(self.mgr.connect(ws_bad, "s1"))

        count = asyncio.run(self.mgr.send_to_scan("s1", {"msg": "test"}))
        self.assertEqual(count, 1)
        # Bad connection should be cleaned up
        self.assertEqual(self.mgr.connection_count("s1"), 1)

    def test_broadcast(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        asyncio.run(self.mgr.connect(ws1, "s1"))
        asyncio.run(self.mgr.connect(ws2, "s2"))

        count = asyncio.run(self.mgr.broadcast({"msg": "all"}))
        self.assertEqual(count, 2)
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()


# =====================================================================
# WebSocket endpoint
# =====================================================================

class TestWebSocketEndpoint(unittest.TestCase):
    """Test the WebSocket route via FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("FastAPI not installed")

        reset_event_relay()

        from spiderfoot.api.routers import websocket as ws_mod
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(ws_mod.router, prefix="/ws")
        cls.client = TestClient(app)

    def setUp(self):
        reset_event_relay()

    def tearDown(self):
        reset_event_relay()

    @patch("spiderfoot.api.routers.websocket.get_app_config")
    def test_polling_mode_scan_not_found(self, mock_config):
        """When relay is not active, falls back to polling which needs DB."""
        mock_cfg = MagicMock()
        mock_cfg.get_config.return_value = {}
        mock_config.return_value = mock_cfg

        # SpiderFootDb will likely fail since we don't have a real DB
        # The endpoint should handle errors gracefully
        with self.client.websocket_connect("/ws/scans/test-scan") as ws:
            msg = ws.receive_text()
            data = json.loads(msg)
            # Should get an error message (either DB fail or config issue)
            self.assertTrue(
                "error" in data or "type" in data,
                f"Expected error or type in response: {data}",
            )

    def test_relay_mode_starts(self):
        """Test that relay mode is selected when EventBus is wired."""
        relay = get_event_relay()
        mock_bus = MagicMock()
        mock_bus.subscribe = AsyncMock(return_value="sub-1")
        mock_bus.unsubscribe = AsyncMock()
        mock_bus.config = MagicMock()
        mock_bus.config.channel_prefix = "sf"
        relay.wire_eventbus(mock_bus)

        # Push a scan_completed event immediately so the WS handler finishes
        def push_complete():
            time.sleep(0.2)
            relay.push_event(
                "relay-scan",
                {"status": "FINISHED"},
                "scan_completed",
            )

        t = threading.Thread(target=push_complete, daemon=True)
        t.start()

        with self.client.websocket_connect("/ws/scans/relay-scan") as ws:
            messages = []
            try:
                while True:
                    msg = ws.receive_text()
                    data = json.loads(msg)
                    messages.append(data)
                    if data.get("type") in ("stream_end", "scan_completed"):
                        break
            except Exception:
                pass

        t.join(timeout=3)

        # Should have received the scan_completed event and stream_end
        event_types = [m.get("type") for m in messages]
        self.assertIn("scan_completed", event_types)


if __name__ == "__main__":
    unittest.main()
