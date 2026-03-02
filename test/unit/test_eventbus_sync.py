"""Tests for EventBus.publish_sync() thread safety — Cycle 15.

Validates that the persistent background event loop does not leak threads
and that concurrent publish_sync calls from multiple threads work correctly.
"""
from __future__ import annotations

import asyncio
import threading
import time
import unittest

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope
from spiderfoot.eventbus.memory import InMemoryEventBus


def _make_envelope(topic="sf.scan1.IP_ADDRESS", data="1.2.3.4"):
    return EventEnvelope(
        topic=topic,
        scan_id="scan1",
        event_type="IP_ADDRESS",
        module="sfp_test",
        data=data,
    )


class TestPublishSyncBasic(unittest.TestCase):
    """Basic correctness of publish_sync."""

    def setUp(self):
        self.bus = InMemoryEventBus()
        asyncio.run(self.bus.connect())

    def tearDown(self):
        asyncio.run(self.bus.disconnect())

    def test_publish_sync_no_subscribers_returns_false(self):
        """publish returns False when no subscriber matched (correct behavior)."""
        result = self.bus.publish_sync(_make_envelope())
        self.assertFalse(result)

    def test_publish_sync_with_subscriber_returns_true(self):
        """publish returns True when at least one subscriber receives the event."""
        received = []

        async def handler(env):
            received.append(env)

        # Subscribe first, then publish
        sub_id = self.bus.subscribe_sync("sf.scan1.IP_ADDRESS", handler)
        result = self.bus.publish_sync(_make_envelope())
        self.assertTrue(result)

    def test_publish_sync_returns_false_when_disconnected(self):
        asyncio.run(self.bus.disconnect())
        result = self.bus.publish_sync(_make_envelope())
        self.assertFalse(result)


class TestBgLoopReuse(unittest.TestCase):
    """The background event loop must be created once and reused."""

    def test_bg_loop_is_reused_across_calls(self):
        loop1 = EventBus._get_bg_loop()
        loop2 = EventBus._get_bg_loop()
        self.assertIs(loop1, loop2)

    def test_bg_loop_thread_is_daemon(self):
        EventBus._get_bg_loop()
        self.assertTrue(EventBus._bg_thread.daemon)
        self.assertEqual(EventBus._bg_thread.name, "eventbus-bg-loop")

    def test_bg_loop_is_running(self):
        loop = EventBus._get_bg_loop()
        self.assertTrue(loop.is_running())


class TestPublishSyncConcurrency(unittest.TestCase):
    """Concurrent publish_sync from multiple threads must not leak threads."""

    def setUp(self):
        self.bus = InMemoryEventBus()
        asyncio.run(self.bus.connect())

    def tearDown(self):
        asyncio.run(self.bus.disconnect())

    def test_concurrent_publish_sync(self):
        """10 threads each publish 5 events — all 50 should succeed."""
        received = []
        results = []
        errors = []

        async def handler(env):
            received.append(env)

        # Subscribe so publish returns True
        self.bus.subscribe_sync("sf.scan1.IP_ADDRESS", handler)

        def worker(thread_id):
            try:
                for i in range(5):
                    env = _make_envelope(data=f"thread-{thread_id}-{i}")
                    r = self.bus.publish_sync(env)
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(len(errors), 0, f"Errors in worker threads: {errors}")
        self.assertEqual(len(results), 50)
        self.assertTrue(all(results), "Some publish_sync calls returned False")

    def test_no_thread_leak(self):
        """Thread count should not grow with repeated publish_sync calls."""
        baseline = threading.active_count()

        for i in range(20):
            self.bus.publish_sync(_make_envelope(data=f"leak-test-{i}"))

        # Allow a small margin (bg loop thread + test framework)
        current = threading.active_count()
        self.assertLessEqual(
            current, baseline + 2,
            f"Thread leak detected: {current} active (baseline was {baseline})"
        )


class TestSubscribeSyncBasic(unittest.TestCase):
    """Basic correctness of subscribe_sync."""

    def setUp(self):
        self.bus = InMemoryEventBus()
        asyncio.run(self.bus.connect())

    def tearDown(self):
        asyncio.run(self.bus.disconnect())

    def test_subscribe_sync_returns_id(self):
        async def handler(env):
            pass
        sub_id = self.bus.subscribe_sync("sf.scan1.IP_ADDRESS", handler)
        self.assertIsInstance(sub_id, str)
        self.assertTrue(len(sub_id) > 0)


if __name__ == "__main__":
    unittest.main()
