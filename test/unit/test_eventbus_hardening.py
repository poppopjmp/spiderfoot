"""Tests for spiderfoot.eventbus_hardening — Cycle 11."""
from __future__ import annotations

import asyncio
import os
import sys
import time
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope
from spiderfoot.eventbus_hardening import (
    AsyncCircuitBreaker,
    AsyncDeadLetterQueue,
    CircuitState,
    DeadLetterEntry,
    EventBusMetrics,
    HealthCheckResult,
    HealthStatus,
    ResilientConfig,
    ResilientEventBus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(topic="sf.scan1.IP_ADDRESS", data="1.2.3.4"):
    return EventEnvelope(
        topic=topic,
        scan_id="scan1",
        event_type="IP_ADDRESS",
        module="sfp_test",
        data=data,
    )


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


class FakeEventBus(EventBus):
    """Minimal in-memory EventBus for testing."""

    def __init__(self, *, fail_publish=False, config=None):
        super().__init__(config)
        self.published = []
        self.subscribers = {}
        self.fail_publish = fail_publish

    async def connect(self):
        self._running = True

    async def disconnect(self):
        self._running = False

    async def publish(self, envelope):
        if self.fail_publish:
            raise ConnectionError("Backend unavailable")
        self.published.append(envelope)
        return True

    async def subscribe(self, topic, callback):
        sub_id = f"sub-{len(self.subscribers)}"
        self.subscribers[sub_id] = (topic, callback)
        return sub_id

    async def unsubscribe(self, subscription_id):
        self.subscribers.pop(subscription_id, None)


# ---------------------------------------------------------------------------
# AsyncCircuitBreaker
# ---------------------------------------------------------------------------


class TestAsyncCircuitBreaker(unittest.TestCase):

    def test_initial_state_closed(self):
        cb = AsyncCircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_allow_request_when_closed(self):
        cb = AsyncCircuitBreaker()
        self.assertTrue(_run(cb.allow_request()))

    def test_opens_after_threshold(self):
        cb = AsyncCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            _run(cb.record_failure())
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_does_not_open_below_threshold(self):
        cb = AsyncCircuitBreaker(failure_threshold=5)
        for _ in range(4):
            _run(cb.record_failure())
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_rejects_when_open(self):
        cb = AsyncCircuitBreaker(failure_threshold=1)
        _run(cb.record_failure())
        self.assertFalse(_run(cb.allow_request()))

    def test_transitions_to_half_open(self):
        cb = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        _run(cb.record_failure())
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(0.15)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_closes_on_success_from_half_open(self):
        cb = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
        _run(cb.record_failure())
        time.sleep(0.1)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        _run(cb.record_success())
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_reopens_on_failure_from_half_open(self):
        cb = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
        _run(cb.record_failure())
        time.sleep(0.1)
        _run(cb.allow_request())  # enter half_open
        _run(cb.record_failure())
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_success_resets_failure_count(self):
        cb = AsyncCircuitBreaker(failure_threshold=5)
        _run(cb.record_failure())
        _run(cb.record_failure())
        _run(cb.record_success())   # resets count while still CLOSED
        # After success, failure count is 0 — need 5 more to open
        _run(cb.record_failure())
        _run(cb.record_failure())
        _run(cb.record_failure())
        # Only 3 failures after reset, not enough to open (threshold=5)
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_to_dict(self):
        cb = AsyncCircuitBreaker(failure_threshold=5)
        d = cb.to_dict()
        self.assertEqual(d["state"], "closed")
        self.assertEqual(d["failure_threshold"], 5)
        self.assertEqual(d["failure_count"], 0)

    def test_reset(self):
        cb = AsyncCircuitBreaker(failure_threshold=1)
        _run(cb.record_failure())
        self.assertEqual(cb.state, CircuitState.OPEN)
        cb.reset()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_state_change_callback(self):
        changes = []

        async def on_change(old, new):
            changes.append((old.value, new.value))

        cb = AsyncCircuitBreaker(failure_threshold=1)
        cb.on_state_change(on_change)
        _run(cb.record_failure())
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], ("closed", "open"))

    def test_half_open_limit(self):
        cb = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=0.05, half_open_max=1
        )
        _run(cb.record_failure())
        time.sleep(0.1)
        self.assertTrue(_run(cb.allow_request()))   # First probe allowed
        self.assertFalse(_run(cb.allow_request()))  # Second blocked


# ---------------------------------------------------------------------------
# AsyncDeadLetterQueue
# ---------------------------------------------------------------------------


class TestAsyncDeadLetterQueue(unittest.TestCase):

    def test_add_and_size(self):
        dlq = AsyncDeadLetterQueue(max_size=10)
        _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(), error="err")))
        self.assertEqual(dlq.size, 1)
        self.assertEqual(dlq.total_added, 1)

    def test_pop(self):
        dlq = AsyncDeadLetterQueue()
        env = _make_envelope()
        _run(dlq.add(DeadLetterEntry(envelope=env, error="x")))
        entry = _run(dlq.pop())
        self.assertIsNotNone(entry)
        self.assertEqual(entry.envelope.data, "1.2.3.4")
        self.assertEqual(dlq.size, 0)

    def test_pop_empty(self):
        dlq = AsyncDeadLetterQueue()
        self.assertIsNone(_run(dlq.pop()))

    def test_peek(self):
        dlq = AsyncDeadLetterQueue()
        for i in range(5):
            _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(data=str(i)), error="e")))
        peeked = _run(dlq.peek(3))
        self.assertEqual(len(peeked), 3)
        self.assertEqual(dlq.size, 5)  # peek doesn't remove

    def test_clear(self):
        dlq = AsyncDeadLetterQueue()
        for _ in range(3):
            _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(), error="e")))
        cleared = _run(dlq.clear())
        self.assertEqual(cleared, 3)
        self.assertEqual(dlq.size, 0)

    def test_max_size_evicts_oldest(self):
        dlq = AsyncDeadLetterQueue(max_size=2)
        for i in range(3):
            _run(dlq.add(DeadLetterEntry(
                envelope=_make_envelope(data=str(i)), error="e"
            )))
        self.assertEqual(dlq.size, 2)
        self.assertEqual(dlq.total_added, 3)
        entry = _run(dlq.pop())
        self.assertEqual(entry.envelope.data, "1")  # oldest (0) was evicted

    def test_replay_success(self):
        dlq = AsyncDeadLetterQueue()
        _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(), error="e")))

        async def fake_publish(env):
            return True

        replayed = _run(dlq.replay(fake_publish))
        self.assertEqual(replayed, 1)
        self.assertEqual(dlq.size, 0)

    def test_replay_partial_failure(self):
        dlq = AsyncDeadLetterQueue()
        _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(data="a"), error="e")))
        _run(dlq.add(DeadLetterEntry(envelope=_make_envelope(data="b"), error="e")))

        call_count = 0

        async def flaky_publish(env):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            raise ConnectionError("fail")

        replayed = _run(dlq.replay(flaky_publish))
        self.assertEqual(replayed, 1)
        self.assertEqual(dlq.size, 1)  # one still in DLQ


# ---------------------------------------------------------------------------
# EventBusMetrics
# ---------------------------------------------------------------------------


class TestEventBusMetrics(unittest.TestCase):

    def test_initial_state(self):
        m = EventBusMetrics()
        snap = m.snapshot()
        self.assertEqual(snap["published"], 0)
        self.assertEqual(snap["publish_failed"], 0)
        self.assertIn("uptime_seconds", snap)

    def test_increment(self):
        m = EventBusMetrics()
        m.inc("published", 5)
        m.inc("published")
        self.assertEqual(m.snapshot()["published"], 6)

    def test_topic_counts(self):
        m = EventBusMetrics()
        m.inc_topic("sf.scan1.IP_ADDRESS")
        m.inc_topic("sf.scan1.IP_ADDRESS")
        m.inc_topic("sf.scan1.DNS")
        snap = m.snapshot()
        self.assertEqual(snap["top_topics"]["sf.scan1.IP_ADDRESS"], 2)

    def test_reset(self):
        m = EventBusMetrics()
        m.inc("published", 10)
        m.reset()
        self.assertEqual(m.snapshot()["published"], 0)

    def test_thread_safety(self):
        m = EventBusMetrics()
        errors = []

        def bumper():
            try:
                for _ in range(100):
                    m.inc("published")
                    m.inc_topic("t")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=bumper) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(m.snapshot()["published"], 500)


# ---------------------------------------------------------------------------
# HealthCheckResult
# ---------------------------------------------------------------------------


class TestHealthCheckResult(unittest.TestCase):

    def test_to_dict(self):
        hc = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            backend="memory",
            connected=True,
            circuit_state="closed",
            dlq_size=0,
        )
        d = hc.to_dict()
        self.assertEqual(d["status"], "healthy")
        self.assertTrue(d["connected"])


# ---------------------------------------------------------------------------
# ResilientEventBus
# ---------------------------------------------------------------------------


class TestResilientEventBus(unittest.TestCase):

    def test_connect_disconnect(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())
        self.assertTrue(bus.is_connected)
        _run(bus.disconnect())
        self.assertFalse(bus.is_connected)

    def test_successful_publish(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())
        env = _make_envelope()
        result = _run(bus.publish(env))
        self.assertTrue(result)
        self.assertEqual(len(inner.published), 1)
        self.assertEqual(bus.get_metrics()["published"], 1)
        _run(bus.disconnect())

    def test_publish_failure_goes_to_dlq(self):
        inner = FakeEventBus(fail_publish=True)
        bus = ResilientEventBus(
            inner,
            ResilientConfig(
                max_publish_retries=2,
                retry_backoff_base=0.01,
                health_check_interval=0,
            ),
        )
        _run(bus.connect())
        result = _run(bus.publish(_make_envelope()))
        self.assertFalse(result)
        self.assertEqual(bus.dlq.size, 1)
        self.assertEqual(bus.get_metrics()["publish_failed"], 1)
        self.assertEqual(bus.get_metrics()["dlq_added"], 1)
        _run(bus.disconnect())

    def test_publish_retries(self):
        attempt_count = 0

        inner = FakeEventBus()
        original_publish = inner.publish

        async def flaky_publish(env):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("fail")
            return await original_publish(env)

        inner.publish = flaky_publish
        bus = ResilientEventBus(
            inner,
            ResilientConfig(
                max_publish_retries=3,
                retry_backoff_base=0.01,
                health_check_interval=0,
            ),
        )
        _run(bus.connect())
        result = _run(bus.publish(_make_envelope()))
        self.assertTrue(result)
        self.assertEqual(attempt_count, 3)
        self.assertEqual(bus.get_metrics()["retries"], 2)
        _run(bus.disconnect())

    def test_circuit_breaker_blocks_publish(self):
        inner = FakeEventBus(fail_publish=True)
        config = ResilientConfig(
            max_publish_retries=1,
            retry_backoff_base=0.01,
            circuit_failure_threshold=2,
            health_check_interval=0,
        )
        bus = ResilientEventBus(inner, config)
        _run(bus.connect())

        # Trigger failures to open circuit
        _run(bus.publish(_make_envelope()))
        _run(bus.publish(_make_envelope()))

        # Circuit should now be open
        self.assertEqual(bus.circuit.state, CircuitState.OPEN)

        # Next publish should be circuit-rejected (not even attempted)
        result = _run(bus.publish(_make_envelope()))
        self.assertFalse(result)
        self.assertEqual(bus.dlq.size, 3)  # All three sent to DLQ
        _run(bus.disconnect())

    def test_subscribe_with_metrics(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        received = []

        async def handler(env):
            received.append(env)

        sub_id = _run(bus.subscribe("topic", handler))
        self.assertIsNotNone(sub_id)

        # Simulate a call to the instrumented callback
        _, wrapped_cb = inner.subscribers[sub_id]
        env = _make_envelope()
        _run(wrapped_cb(env))
        self.assertEqual(len(received), 1)
        self.assertEqual(bus.get_metrics()["consumed"], 1)
        _run(bus.disconnect())

    def test_subscribe_sync_callback(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        received = []

        def sync_handler(env):
            received.append(env)

        sub_id = _run(bus.subscribe("topic", sync_handler))
        _, wrapped_cb = inner.subscribers[sub_id]
        _run(wrapped_cb(_make_envelope()))
        self.assertEqual(len(received), 1)
        _run(bus.disconnect())

    def test_subscribe_error_counted(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        async def bad_handler(env):
            raise ValueError("boom")

        sub_id = _run(bus.subscribe("topic", bad_handler))
        _, wrapped_cb = inner.subscribers[sub_id]

        with self.assertRaises(ValueError):
            _run(wrapped_cb(_make_envelope()))
        self.assertEqual(bus.get_metrics()["consume_errors"], 1)
        _run(bus.disconnect())

    def test_unsubscribe(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        sub_id = _run(bus.subscribe("topic", lambda e: None))
        _run(bus.unsubscribe(sub_id))
        self.assertEqual(len(inner.subscribers), 0)
        _run(bus.disconnect())

    def test_health_check(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        hc = _run(bus.health_check())
        self.assertEqual(hc.status, HealthStatus.HEALTHY)
        self.assertTrue(hc.connected)
        self.assertEqual(hc.circuit_state, "closed")
        self.assertEqual(hc.dlq_size, 0)

        cached = bus.health_status()
        self.assertIsNotNone(cached)
        _run(bus.disconnect())

    def test_health_check_unhealthy_when_disconnected(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        # Don't connect — bus is not running
        hc = _run(bus.health_check())
        self.assertEqual(hc.status, HealthStatus.UNHEALTHY)

    def test_health_check_degraded_when_dlq_large(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())

        # Fill DLQ with >100 entries
        for i in range(101):
            _run(bus.dlq.add(DeadLetterEntry(
                envelope=_make_envelope(data=str(i)), error="e"
            )))

        hc = _run(bus.health_check())
        self.assertEqual(hc.status, HealthStatus.DEGRADED)
        _run(bus.disconnect())

    def test_replay_dlq(self):
        inner = FakeEventBus(fail_publish=True)
        bus = ResilientEventBus(
            inner,
            ResilientConfig(
                max_publish_retries=1,
                retry_backoff_base=0.01,
                health_check_interval=0,
            ),
        )
        _run(bus.connect())
        _run(bus.publish(_make_envelope()))  # fails, goes to DLQ
        self.assertEqual(bus.dlq.size, 1)

        # Fix the backend
        inner.fail_publish = False
        replayed = _run(bus.replay_dlq())
        self.assertEqual(replayed, 1)
        self.assertEqual(bus.dlq.size, 0)
        self.assertEqual(bus.get_metrics()["dlq_replayed"], 1)
        _run(bus.disconnect())

    def test_repr(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        r = repr(bus)
        self.assertIn("ResilientEventBus", r)
        self.assertIn("FakeEventBus", r)
        self.assertIn("closed", r)

    def test_inner_property(self):
        inner = FakeEventBus()
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        self.assertIs(bus.inner, inner)

    def test_circuit_opened_counted(self):
        inner = FakeEventBus(fail_publish=True)
        bus = ResilientEventBus(
            inner,
            ResilientConfig(
                max_publish_retries=1,
                retry_backoff_base=0.01,
                circuit_failure_threshold=1,
                health_check_interval=0,
            ),
        )
        _run(bus.connect())
        _run(bus.publish(_make_envelope()))
        self.assertEqual(bus.get_metrics()["circuit_opened"], 1)
        _run(bus.disconnect())

    def test_publish_returns_false_no_subscribers(self):
        """If inner.publish returns False (no subscribers), it's not a
        failure — metrics should count it as published, not failed."""
        inner = FakeEventBus()

        async def no_sub_publish(env):
            return False

        inner.publish = no_sub_publish
        bus = ResilientEventBus(inner, ResilientConfig(health_check_interval=0))
        _run(bus.connect())
        result = _run(bus.publish(_make_envelope()))
        self.assertFalse(result)
        self.assertEqual(bus.get_metrics()["published"], 1)  # counted
        self.assertEqual(bus.get_metrics()["publish_failed"], 0)  # not a failure
        self.assertEqual(bus.dlq.size, 0)
        _run(bus.disconnect())


# ---------------------------------------------------------------------------
# ResilientConfig
# ---------------------------------------------------------------------------


class TestResilientConfig(unittest.TestCase):

    def test_defaults(self):
        c = ResilientConfig()
        self.assertEqual(c.max_publish_retries, 3)
        self.assertEqual(c.circuit_failure_threshold, 5)
        self.assertEqual(c.dlq_max_size, 1000)

    def test_custom(self):
        c = ResilientConfig(
            max_publish_retries=5,
            circuit_failure_threshold=10,
            dlq_max_size=500,
        )
        self.assertEqual(c.max_publish_retries, 5)
        self.assertEqual(c.dlq_max_size, 500)


if __name__ == "__main__":
    unittest.main()
