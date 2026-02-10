"""Tests for spiderfoot.rate_limiter."""
from __future__ import annotations

import time
import threading

import pytest

from spiderfoot.rate_limiter import (
    Algorithm,
    RateLimit,
    RateLimiterService,
    RateLimitResult,
    get_rate_limiter,
)


@pytest.fixture
def limiter():
    return RateLimiterService()


class TestRateLimit:
    def test_defaults(self):
        rl = RateLimit()
        assert rl.requests == 30
        assert rl.window == 60.0
        assert rl.effective_burst == 30

    def test_custom_burst(self):
        rl = RateLimit(requests=10, window=10.0, burst=20)
        assert rl.effective_burst == 20
        assert rl.rate == 1.0

    def test_rate(self):
        rl = RateLimit(requests=60, window=60.0)
        assert rl.rate == 1.0

    def test_zero_window(self):
        rl = RateLimit(requests=10, window=0.0)
        assert rl.rate == float("inf")


class TestTokenBucket:
    def test_allow_within_limit(self, limiter):
        limiter.set_limit("test", RateLimit(requests=5, window=1.0))
        for _ in range(5):
            assert limiter.allow("test") is True

    def test_deny_over_limit(self, limiter):
        limiter.set_limit("test", RateLimit(requests=3, window=10.0))
        for _ in range(3):
            assert limiter.allow("test") is True
        assert limiter.allow("test") is False

    def test_refill(self, limiter):
        limiter.set_limit("test", RateLimit(requests=10, window=1.0))
        for _ in range(10):
            limiter.allow("test")

        assert limiter.allow("test") is False
        time.sleep(0.15)
        assert limiter.allow("test") is True

    def test_burst(self, limiter):
        limiter.set_limit("test", RateLimit(
            requests=1, window=1.0, burst=5))
        # Should allow burst
        for _ in range(5):
            assert limiter.allow("test") is True
        assert limiter.allow("test") is False


class TestSlidingWindow:
    def test_allow_within_limit(self, limiter):
        limiter.set_limit("sw", RateLimit(
            requests=3, window=1.0,
            algorithm=Algorithm.SLIDING_WINDOW))

        for _ in range(3):
            assert limiter.allow("sw") is True
        assert limiter.allow("sw") is False

    def test_window_slides(self, limiter):
        limiter.set_limit("sw", RateLimit(
            requests=2, window=0.2,
            algorithm=Algorithm.SLIDING_WINDOW))

        assert limiter.allow("sw") is True
        assert limiter.allow("sw") is True
        assert limiter.allow("sw") is False

        time.sleep(0.25)
        assert limiter.allow("sw") is True


class TestFixedWindow:
    def test_allow_within_limit(self, limiter):
        limiter.set_limit("fw", RateLimit(
            requests=3, window=10.0,
            algorithm=Algorithm.FIXED_WINDOW))

        for _ in range(3):
            assert limiter.allow("fw") is True
        assert limiter.allow("fw") is False

    def test_window_resets(self, limiter):
        limiter.set_limit("fw", RateLimit(
            requests=2, window=0.15,
            algorithm=Algorithm.FIXED_WINDOW))

        assert limiter.allow("fw") is True
        assert limiter.allow("fw") is True
        assert limiter.allow("fw") is False

        time.sleep(0.2)
        assert limiter.allow("fw") is True


class TestRateLimiterService:
    def test_default_limit(self, limiter):
        # Uses default (60 req/60s)
        for _ in range(60):
            assert limiter.allow("any_key") is True
        assert limiter.allow("any_key") is False

    def test_check_returns_result(self, limiter):
        limiter.set_limit("k", RateLimit(requests=2, window=10.0))
        r = limiter.check("k")
        assert isinstance(r, RateLimitResult)
        assert r.allowed is True
        assert r.remaining == 1
        assert r.limit == 2

    def test_check_denied_has_retry_after(self, limiter):
        limiter.set_limit("k", RateLimit(requests=1, window=10.0))
        limiter.allow("k")
        r = limiter.check("k")
        assert r.allowed is False
        assert r.retry_after > 0

    def test_remove_limit(self, limiter):
        limiter.set_limit("rm", RateLimit(requests=1, window=10.0))
        assert limiter.remove_limit("rm") is True
        assert limiter.remove_limit("rm") is False

    def test_reset(self, limiter):
        limiter.set_limit("res", RateLimit(requests=1, window=10.0))
        limiter.allow("res")
        assert limiter.allow("res") is False

        limiter.reset("res")
        assert limiter.allow("res") is True

    def test_reset_all(self, limiter):
        limiter.set_limit("a", RateLimit(requests=1, window=10.0))
        limiter.set_limit("b", RateLimit(requests=1, window=10.0))
        limiter.allow("a")
        limiter.allow("b")
        limiter.reset_all()
        assert limiter.allow("a") is True
        assert limiter.allow("b") is True

    def test_disabled(self, limiter):
        limiter.set_limit("dis", RateLimit(requests=1, window=10.0))
        limiter.allow("dis")

        limiter.enabled = False
        assert limiter.allow("dis") is True  # Bypassed

        limiter.enabled = True
        assert limiter.allow("dis") is False

    def test_get_stats(self, limiter):
        limiter.set_limit("st", RateLimit(requests=2, window=10.0))
        limiter.allow("st")
        limiter.allow("st")
        limiter.allow("st")

        stats = limiter.get_stats("st")
        assert stats["allowed"] == 2
        assert stats["denied"] == 1
        assert stats["limit"] == 2

    def test_all_stats(self, limiter):
        limiter.set_limit("x", RateLimit(requests=5, window=1.0))
        limiter.set_limit("y", RateLimit(requests=5, window=1.0))
        limiter.allow("x")
        limiter.allow("y")

        stats = limiter.all_stats
        keys = [s["key"] for s in stats]
        assert "x" in keys
        assert "y" in keys

    def test_allow_all(self, limiter):
        limiter.set_limit("a", RateLimit(requests=5, window=10.0))
        limiter.set_limit("b", RateLimit(requests=5, window=10.0))
        assert limiter.allow_all(["a", "b"]) is True

    def test_allow_all_one_denied(self, limiter):
        limiter.set_limit("a", RateLimit(requests=5, window=10.0))
        limiter.set_limit("b", RateLimit(requests=1, window=10.0))
        limiter.allow("b")
        assert limiter.allow_all(["a", "b"]) is False

    def test_retry_after(self, limiter):
        limiter.set_limit("rt", RateLimit(requests=1, window=10.0))
        limiter.allow("rt")
        wait = limiter.retry_after("rt")
        assert wait > 0

    def test_retry_after_no_state(self, limiter):
        assert limiter.retry_after("no_key") == 0.0

    def test_retry_after_sliding(self, limiter):
        limiter.set_limit("sw_rt", RateLimit(
            requests=1, window=1.0,
            algorithm=Algorithm.SLIDING_WINDOW))
        limiter.allow("sw_rt")
        wait = limiter.retry_after("sw_rt")
        assert wait >= 0

    def test_retry_after_fixed(self, limiter):
        limiter.set_limit("fw_rt", RateLimit(
            requests=1, window=1.0,
            algorithm=Algorithm.FIXED_WINDOW))
        limiter.allow("fw_rt")
        wait = limiter.retry_after("fw_rt")
        assert wait >= 0

    def test_acquire_context_manager(self, limiter):
        limiter.set_limit("ctx", RateLimit(requests=5, window=1.0))

        with limiter.acquire("ctx") as ctx:
            assert ctx.waited >= 0

    def test_configure_from_dict(self, limiter):
        config = {
            "api:shodan": {"requests": 1, "window": 1.0},
            "api:vt": {
                "requests": 4, "window": 60.0,
                "algorithm": "sliding_window",
            },
        }
        count = limiter.configure_from_dict(config)
        assert count == 2
        assert limiter.get_limit("api:shodan").requests == 1
        assert limiter.get_limit("api:vt").algorithm == Algorithm.SLIDING_WINDOW

    def test_configure_from_dict_invalid(self, limiter):
        config = {"bad": {"algorithm": "nope"}}
        count = limiter.configure_from_dict(config)
        assert count == 0

    def test_cleanup(self, limiter):
        limiter.set_limit("cl", RateLimit(requests=5, window=0.1))
        limiter.allow("cl")

        # Force stale
        with limiter._lock:
            limiter._states["cl"].last_refill = time.monotonic() - 400

        removed = limiter.cleanup(max_idle=300.0)
        assert removed == 1

    def test_thread_safety(self, limiter):
        limiter.set_limit("ts", RateLimit(requests=100, window=10.0))
        results = {"allowed": 0, "denied": 0}
        lock = threading.Lock()

        def worker():
            for _ in range(20):
                if limiter.allow("ts"):
                    with lock:
                        results["allowed"] += 1
                else:
                    with lock:
                        results["denied"] += 1

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["allowed"] + results["denied"] == 200
        assert results["allowed"] == 100
        assert results["denied"] == 100


class TestSingleton:
    def test_get_rate_limiter(self):
        import spiderfoot.rate_limiter as mod
        mod._limiter_instance = None
        rl1 = get_rate_limiter()
        rl2 = get_rate_limiter()
        assert rl1 is rl2
        mod._limiter_instance = None
