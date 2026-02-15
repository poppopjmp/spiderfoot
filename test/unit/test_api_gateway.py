"""Unit tests for spiderfoot.api_gateway."""
from __future__ import annotations

import time
import unittest

from spiderfoot.api_gateway import (
    APIGateway,
    CircuitBreaker,
    CircuitState,
    GatewayError,
    RateLimiter,
)


class TestCircuitBreaker(unittest.TestCase):
    """Tests for the CircuitBreaker class."""

    def test_starts_closed(self):
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.allow_request())

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.allow_request())

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # Should still be closed
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.allow_request())

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(0.06)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        self.assertTrue(cb.allow_request())

    def test_half_open_limits_calls(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01,
                            half_open_max=1)
        cb.record_failure()
        time.sleep(0.02)
        self.assertTrue(cb.allow_request())
        self.assertFalse(cb.allow_request())

    def test_to_dict(self):
        cb = CircuitBreaker()
        d = cb.to_dict()
        self.assertIn("state", d)
        self.assertIn("failure_count", d)


class TestRateLimiter(unittest.TestCase):
    """Tests for the RateLimiter class."""

    def test_allows_within_burst(self):
        rl = RateLimiter(rate=10, burst=5)
        for _ in range(5):
            self.assertTrue(rl.allow("client1"))

    def test_rejects_over_burst(self):
        rl = RateLimiter(rate=0.001, burst=2)
        self.assertTrue(rl.allow("client1"))
        self.assertTrue(rl.allow("client1"))
        self.assertFalse(rl.allow("client1"))

    def test_separate_clients(self):
        rl = RateLimiter(rate=10, burst=1)
        self.assertTrue(rl.allow("client1"))
        self.assertTrue(rl.allow("client2"))

    def test_cleanup(self):
        rl = RateLimiter()
        rl.allow("test_client")
        rl.cleanup(max_age=0)
        self.assertEqual(len(rl._clients), 0)


class TestAPIGateway(unittest.TestCase):
    """Tests for the APIGateway class."""

    def test_monolith_routing(self):
        gw = APIGateway(mode="monolith")
        gw.register_local_handler("scanner", "Ping",
                                  lambda p: {"pong": True})
        result = gw.route("scanner", "Ping")
        self.assertEqual(result, {"pong": True})

    def test_missing_handler_raises(self):
        gw = APIGateway(mode="monolith")
        with self.assertRaises(GatewayError):
            gw.route("scanner", "Missing")

    def test_missing_service_raises(self):
        gw = APIGateway(mode="monolith")
        with self.assertRaises(GatewayError):
            gw.route("nonexistent", "Method")

    def test_rate_limit_enforced(self):
        gw = APIGateway(mode="monolith")
        gw._rate_limiter = RateLimiter(rate=0.001, burst=1)
        gw.register_local_handler("svc", "m",
                                  lambda p: {"ok": True})
        gw.route("svc", "m", client_id="c1")
        with self.assertRaises(GatewayError) as ctx:
            gw.route("svc", "m", client_id="c1")
        self.assertEqual(ctx.exception.status, 429)

    def test_circuit_breaker_on_failure(self):
        gw = APIGateway(mode="monolith")
        gw._circuit_breakers["svc"] = CircuitBreaker(failure_threshold=1)

        def fail_handler(p):
            raise RuntimeError("boom")

        gw.register_local_handler("svc", "fail", fail_handler)

        with self.assertRaises(GatewayError):
            gw.route("svc", "fail")

        # Circuit should be open now
        with self.assertRaises(GatewayError) as ctx:
            gw.route("svc", "fail")
        self.assertEqual(ctx.exception.status, 503)

    def test_stats(self):
        gw = APIGateway(mode="monolith")
        gw.register_local_handler("scanner", "Ping",
                                  lambda p: {"ok": True})
        s = gw.stats()
        self.assertEqual(s["mode"], "monolith")
        self.assertIn("scanner", s["registered_services"])

    def test_handler_receives_payload(self):
        gw = APIGateway(mode="monolith")
        received = {}

        def handler(p):
            received.update(p)
            return {"ok": True}

        gw.register_local_handler("svc", "Do", handler)
        gw.route("svc", "Do", {"key": "value"})
        self.assertEqual(received, {"key": "value"})

    def test_gateway_error_status(self):
        e = GatewayError("test", status=418)
        self.assertEqual(e.status, 418)
        self.assertEqual(str(e), "test")


if __name__ == "__main__":
    unittest.main()
