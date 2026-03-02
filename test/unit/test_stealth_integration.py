# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_stealth_integration
# Purpose:      Tests for SOTA S-002 Stealth Integration Layer
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-27
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Unit tests for :mod:`spiderfoot.recon.stealth_integration`.

Covers proxy chains, domain throttling, stealth metrics, scan-level
configuration, stealth scan context, and the fetch middleware.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.recon.stealth_integration import (
    DomainBucket,
    DomainThrottler,
    ProxyChain,
    ProxyChainManager,
    ProxyChainStrategy,
    ProxyHop,
    ScanStealthConfig,
    StealthEventRecord,
    StealthFetchMiddleware,
    StealthMetricsCollector,
    StealthScanContext,
    ThrottleAction,
    create_stealth_context,
    get_all_scan_stats,
    get_scan_context,
    register_scan_context,
    stealthy_fetch,
    unregister_scan_context,
    _extract_domain,
)
from spiderfoot.recon.stealth_engine import (
    ProxyProtocol,
    StealthLevel,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_hop(url: str = "proxy1.example.com:1080", **kwargs) -> ProxyHop:
    return ProxyHop(url=url, **kwargs)


def _make_chain(
    hop_urls: list[str] | None = None, label: str = ""
) -> ProxyChain:
    urls = hop_urls or ["proxy1.test:1080", "proxy2.test:1080"]
    hops = [ProxyHop(url=u) for u in urls]
    return ProxyChain(hops=hops, label=label)


def _make_config(**overrides) -> ScanStealthConfig:
    defaults = {"stealth_level": "medium", "collect_metrics": True}
    defaults.update(overrides)
    return ScanStealthConfig(**defaults)


def _make_context(**overrides) -> StealthScanContext:
    return StealthScanContext(_make_config(**overrides))


def _mock_fetch_ok(url: str, **kwargs) -> dict:
    """Mock fetchUrl that always returns 200."""
    return {
        "code": "200",
        "status": "OK",
        "content": "<html>ok</html>",
        "headers": {"Content-Type": "text/html"},
        "realurl": url,
    }


def _mock_fetch_blocked(url: str, **kwargs) -> dict:
    """Mock fetchUrl that returns 429."""
    return {
        "code": "429",
        "status": "Too Many Requests",
        "content": "rate limit exceeded",
        "headers": {"Retry-After": "60"},
        "realurl": url,
    }


def _mock_fetch_captcha(url: str, **kwargs) -> dict:
    """Mock fetchUrl that returns a captcha challenge."""
    return {
        "code": "403",
        "status": "Forbidden",
        "content": "<html>Please complete the captcha to continue</html>",
        "headers": {"Server": "cloudflare"},
        "realurl": url,
    }


def _mock_fetch_waf(url: str, **kwargs) -> dict:
    """Mock fetchUrl that returns cloudflare challenge."""
    return {
        "code": "503",
        "status": "Service Unavailable",
        "content": "Checking your browser. Cloudflare Ray ID: abc123",
        "headers": {"Server": "cloudflare"},
        "realurl": url,
    }


# ============================================================================
# TestProxyHop
# ============================================================================

class TestProxyHop:
    """Tests for ProxyHop data class."""

    def test_create_default(self):
        hop = ProxyHop(url="proxy.test:1080")
        assert hop.url == "proxy.test:1080"
        assert hop.protocol == ProxyProtocol.SOCKS5
        assert hop.is_healthy is True
        assert hop.failure_rate == 0.0

    def test_record_success(self):
        hop = _make_hop()
        hop.record_success(latency_ms=50.0)
        assert hop.total_requests == 1
        assert hop.consecutive_failures == 0
        assert hop.avg_latency_ms > 0

    def test_record_failure(self):
        hop = _make_hop()
        hop.record_failure()
        assert hop.consecutive_failures == 1
        assert hop.total_failures == 1
        assert hop.failure_rate == 1.0

    def test_unhealthy_after_3_failures(self):
        hop = _make_hop()
        for _ in range(3):
            hop.record_failure()
        assert hop.is_healthy is False

    def test_success_resets_failures(self):
        hop = _make_hop()
        hop.record_failure()
        hop.record_failure()
        hop.record_success()
        assert hop.consecutive_failures == 0
        assert hop.is_healthy is True

    def test_to_proxy_url_no_auth(self):
        hop = ProxyHop(url="proxy.test:1080", protocol=ProxyProtocol.SOCKS5)
        assert hop.to_proxy_url() == "socks5://proxy.test:1080"

    def test_to_proxy_url_with_auth(self):
        hop = ProxyHop(
            url="proxy.test:1080",
            protocol=ProxyProtocol.HTTP,
            username="user",
            password="pass",
        )
        assert hop.to_proxy_url() == "http://user:pass@proxy.test:1080"

    def test_latency_ema(self):
        """Exponential moving average should weight recent samples."""
        hop = _make_hop()
        hop.record_success(100.0)
        first = hop.avg_latency_ms
        hop.record_success(200.0)
        second = hop.avg_latency_ms
        assert second > first  # Should increase toward 200
        assert second < 200  # But not jump to 200


# ============================================================================
# TestProxyChain
# ============================================================================

class TestProxyChain:
    """Tests for ProxyChain."""

    def test_create_chain(self):
        chain = _make_chain()
        assert chain.hop_count == 2
        assert chain.is_healthy is True
        assert chain.chain_id  # Should auto-generate

    def test_chain_id_deterministic(self):
        """Same hops should produce the same chain_id."""
        c1 = _make_chain(["a:1", "b:2"])
        c2 = _make_chain(["a:1", "b:2"])
        assert c1.chain_id == c2.chain_id

    def test_chain_id_different(self):
        c1 = _make_chain(["a:1", "b:2"])
        c2 = _make_chain(["c:3", "d:4"])
        assert c1.chain_id != c2.chain_id

    def test_entry_exit_proxy(self):
        chain = _make_chain(["entry:1080", "mid:1080", "exit:1080"])
        assert chain.entry_proxy.url == "entry:1080"
        assert chain.exit_proxy.url == "exit:1080"

    def test_empty_chain(self):
        chain = ProxyChain()
        assert chain.hop_count == 0
        assert chain.entry_proxy is None
        assert chain.exit_proxy is None
        assert chain.to_requests_proxies() is None

    def test_to_requests_proxies(self):
        chain = _make_chain(["proxy1:1080"])
        proxies = chain.to_requests_proxies()
        assert proxies is not None
        assert "http" in proxies
        assert "https" in proxies
        assert "socks5://" in proxies["http"]

    def test_record_success(self):
        chain = _make_chain(["a:1", "b:2"])
        chain.record_success(latency_ms=100.0)
        assert chain._total_requests == 1

    def test_record_failure(self):
        chain = _make_chain(["a:1", "b:2"])
        chain.record_failure(failed_hop_index=1)
        assert chain._total_failures == 1
        assert chain.hops[1].consecutive_failures == 1

    def test_record_failure_default_exit(self):
        chain = _make_chain(["a:1", "b:2"])
        chain.record_failure()
        assert chain.hops[-1].consecutive_failures == 1

    def test_unhealthy_chain(self):
        chain = _make_chain(["a:1", "b:2"])
        for _ in range(3):
            chain.hops[0].record_failure()
        assert chain.is_healthy is False

    def test_to_dict(self):
        chain = _make_chain(["a:1"], label="test-chain")
        d = chain.to_dict()
        assert d["label"] == "test-chain"
        assert d["hop_count"] == 1
        assert d["healthy"] is True
        assert len(d["hops"]) == 1

    def test_total_latency(self):
        chain = _make_chain(["a:1", "b:2"])
        chain.hops[0].avg_latency_ms = 50.0
        chain.hops[1].avg_latency_ms = 30.0
        assert chain.total_latency_ms == 80.0


# ============================================================================
# TestProxyChainManager
# ============================================================================

class TestProxyChainManager:
    """Tests for ProxyChainManager."""

    def test_create_empty(self):
        mgr = ProxyChainManager()
        assert mgr.chain_count == 0
        assert mgr.healthy_count == 0

    def test_add_chain(self):
        mgr = ProxyChainManager()
        mgr.add_chain(_make_chain())
        assert mgr.chain_count == 1

    def test_remove_chain(self):
        chain = _make_chain()
        mgr = ProxyChainManager(chains=[chain])
        assert mgr.remove_chain(chain.chain_id) is True
        assert mgr.chain_count == 0

    def test_remove_nonexistent(self):
        mgr = ProxyChainManager()
        assert mgr.remove_chain("nonexistent") is False

    def test_get_chain_rotating(self):
        c1 = _make_chain(["a:1"], label="c1")
        c2 = _make_chain(["b:2"], label="c2")
        mgr = ProxyChainManager(
            chains=[c1, c2],
            strategy=ProxyChainStrategy.ROTATING,
        )
        first = mgr.get_chain()
        second = mgr.get_chain()
        # Should rotate between the two chains
        assert first is not None
        assert second is not None

    def test_get_chain_static(self):
        c1 = _make_chain(["a:1"])
        c2 = _make_chain(["b:2"])
        mgr = ProxyChainManager(
            chains=[c1, c2],
            strategy=ProxyChainStrategy.STATIC,
        )
        first = mgr.get_chain()
        second = mgr.get_chain()
        assert first.chain_id == second.chain_id == c1.chain_id

    def test_get_chain_random(self):
        chains = [_make_chain([f"p{i}:1080"]) for i in range(10)]
        mgr = ProxyChainManager(
            chains=chains,
            strategy=ProxyChainStrategy.RANDOM,
        )
        results = [mgr.get_chain() for _ in range(20)]
        assert all(r is not None for r in results)
        # Should have some variety
        ids = set(r.chain_id for r in results)
        assert len(ids) > 1

    def test_get_chain_per_domain(self):
        c1 = _make_chain(["a:1"])
        c2 = _make_chain(["b:2"])
        mgr = ProxyChainManager(
            chains=[c1, c2],
            strategy=ProxyChainStrategy.PER_DOMAIN,
        )
        # Same domain should get same chain
        r1 = mgr.get_chain(domain="example.com")
        r2 = mgr.get_chain(domain="example.com")
        assert r1.chain_id == r2.chain_id

    def test_get_chain_no_healthy(self):
        chain = _make_chain(["a:1"])
        for _ in range(3):
            chain.hops[0].record_failure()
        mgr = ProxyChainManager(chains=[chain], cooldown_seconds=9999)
        assert mgr.get_chain() is None

    def test_record_result(self):
        chain = _make_chain(["a:1"])
        mgr = ProxyChainManager(chains=[chain])
        mgr.record_result(chain.chain_id, success=True, latency_ms=50)
        assert chain._total_requests == 1

    def test_clear_domain_pins(self):
        mgr = ProxyChainManager(
            chains=[_make_chain()],
            strategy=ProxyChainStrategy.PER_DOMAIN,
        )
        mgr.get_chain(domain="example.com")
        mgr.clear_domain_pins()
        # Should work without error
        mgr.get_chain(domain="example.com")

    def test_get_stats(self):
        mgr = ProxyChainManager(chains=[_make_chain()])
        stats = mgr.get_stats()
        assert len(stats) == 1
        assert "chain_id" in stats[0]

    def test_healthy_count(self):
        c1 = _make_chain(["a:1"])
        c2 = _make_chain(["b:2"])
        for _ in range(3):
            c2.hops[0].record_failure()
        mgr = ProxyChainManager(chains=[c1, c2])
        assert mgr.healthy_count == 1


# ============================================================================
# TestDomainBucket
# ============================================================================

class TestDomainBucket:
    """Tests for DomainBucket rate-limiting state."""

    def test_create(self):
        bucket = DomainBucket(domain="example.com")
        assert bucket.domain == "example.com"
        assert bucket.requests_total == 0
        assert bucket.error_rate == 0.0

    def test_record_request(self):
        bucket = DomainBucket(domain="test.com", window_start=time.time())
        bucket.record_request()
        assert bucket.requests_total == 1
        assert bucket.requests_in_window == 1

    def test_record_success_response(self):
        bucket = DomainBucket(domain="test.com", window_start=time.time())
        bucket.record_response(200)
        assert len(bucket.last_status_codes) == 1

    def test_record_block_response(self):
        bucket = DomainBucket(
            domain="test.com",
            window_start=time.time(),
            max_requests_per_window=30,
        )
        bucket.record_request()
        bucket.record_response(429)
        assert bucket.errors_in_window == 1
        assert bucket.backoff_count == 1
        assert bucket.backoff_until > time.time()

    def test_adaptive_throttle_reduction(self):
        bucket = DomainBucket(
            domain="test.com",
            window_start=time.time(),
            max_requests_per_window=30,
        )
        original_max = bucket.max_requests_per_window
        bucket.record_response(429)
        assert bucket.max_requests_per_window < original_max

    def test_recovery_on_success(self):
        bucket = DomainBucket(
            domain="test.com",
            window_start=time.time(),
            max_requests_per_window=20,
            backoff_count=2,
        )
        bucket.record_response(200)
        assert bucket.backoff_count == 1

    def test_error_rate(self):
        bucket = DomainBucket(domain="test.com", window_start=time.time())
        bucket.record_request()
        bucket.record_request()
        bucket.record_response(429)
        assert bucket.error_rate > 0

    def test_recent_block_rate(self):
        bucket = DomainBucket(domain="test.com")
        bucket.record_response(200)
        bucket.record_response(429)
        assert bucket.recent_block_rate == 0.5

    def test_window_reset(self):
        bucket = DomainBucket(
            domain="test.com",
            window_seconds=0.01,
            window_start=time.time() - 1,
        )
        bucket.requests_in_window = 100
        bucket._reset_window_if_needed()
        assert bucket.requests_in_window == 0

    def test_exponential_backoff_cap(self):
        """Backoff should cap at 300 seconds."""
        bucket = DomainBucket(domain="test.com", window_start=time.time())
        for _ in range(20):
            bucket.record_response(429)
        # backoff_count=20, 2^20 > 300, so backoff_until - now should be <= 300
        remaining = bucket.backoff_until - time.time()
        assert remaining <= 301


# ============================================================================
# TestDomainThrottler
# ============================================================================

class TestDomainThrottler:
    """Tests for DomainThrottler."""

    def test_create(self):
        throttler = DomainThrottler()
        assert throttler is not None

    def test_first_request_proceeds(self):
        throttler = DomainThrottler()
        action, delay = throttler.check_throttle("example.com")
        assert action == ThrottleAction.PROCEED
        assert delay == 0.0

    def test_min_interval_delay(self):
        throttler = DomainThrottler(default_min_interval=10.0)
        throttler.record_request("example.com")
        action, delay = throttler.check_throttle("example.com")
        assert action == ThrottleAction.DELAY
        assert delay > 0

    def test_rate_limit_hit(self):
        throttler = DomainThrottler(default_max_rpm=2, default_min_interval=0.0)
        throttler.record_request("test.com")
        throttler.record_request("test.com")
        action, delay = throttler.check_throttle("test.com")
        assert action == ThrottleAction.DELAY

    def test_backoff_on_429(self):
        throttler = DomainThrottler(default_min_interval=0.0)
        throttler.record_response("test.com", 429)
        action, delay = throttler.check_throttle("test.com")
        assert action in (ThrottleAction.BACKOFF, ThrottleAction.BLOCK)

    def test_block_after_many_errors(self):
        throttler = DomainThrottler(default_min_interval=0.0)
        for _ in range(6):
            throttler.record_response("test.com", 429)
        action, delay = throttler.check_throttle("test.com")
        assert action == ThrottleAction.BLOCK

    def test_different_domains_independent(self):
        throttler = DomainThrottler(default_min_interval=0.0, default_max_rpm=1)
        throttler.record_request("a.com")
        action_a, _ = throttler.check_throttle("a.com")
        action_b, _ = throttler.check_throttle("b.com")
        assert action_a == ThrottleAction.DELAY
        assert action_b == ThrottleAction.PROCEED

    def test_get_domain_stats(self):
        throttler = DomainThrottler()
        throttler.record_request("test.com")
        stats = throttler.get_domain_stats("test.com")
        assert stats["domain"] == "test.com"
        assert stats["requests_total"] == 1

    def test_get_all_stats(self):
        throttler = DomainThrottler()
        throttler.record_request("a.com")
        throttler.record_request("b.com")
        stats = throttler.get_all_stats()
        assert "a.com" in stats
        assert "b.com" in stats

    def test_reset_domain(self):
        throttler = DomainThrottler()
        throttler.record_request("test.com")
        throttler.reset_domain("test.com")
        stats = throttler.get_all_stats()
        assert "test.com" not in stats

    def test_reset_all(self):
        throttler = DomainThrottler()
        throttler.record_request("a.com")
        throttler.record_request("b.com")
        throttler.reset_all()
        assert throttler.get_all_stats() == {}


# ============================================================================
# TestStealthMetricsCollector
# ============================================================================

class TestStealthMetricsCollector:
    """Tests for StealthMetricsCollector."""

    def test_create(self):
        mc = StealthMetricsCollector()
        assert mc.detection_rate == 0.0
        assert mc.block_rate == 0.0
        assert mc.success_rate == 0.0

    def test_record_success(self):
        mc = StealthMetricsCollector()
        mc.record_request(domain="test.com", status_code=200)
        assert mc.success_rate == 1.0
        assert mc._total_requests == 1

    def test_record_block(self):
        mc = StealthMetricsCollector()
        mc.record_request(domain="test.com", status_code=429)
        assert mc.block_rate == 1.0

    def test_record_detection(self):
        mc = StealthMetricsCollector()
        mc.record_request(
            domain="test.com",
            status_code=403,
            was_detected=True,
            detection_type="captcha",
        )
        assert mc.detection_rate == 1.0

    def test_fingerprint_diversity(self):
        mc = StealthMetricsCollector()
        for i in range(10):
            mc.record_request(
                domain="test.com",
                status_code=200,
                user_agent=f"UA-{i}",
                tls_profile=f"profile-{i % 4}",
                proxy_chain_id=f"chain-{i % 3}",
            )
        score = mc.fingerprint_diversity_score
        assert score > 0.8  # High diversity

    def test_fingerprint_diversity_low(self):
        mc = StealthMetricsCollector()
        mc.record_request(domain="test.com", status_code=200, user_agent="single")
        score = mc.fingerprint_diversity_score
        assert score < 0.5  # Low diversity

    def test_get_report(self):
        mc = StealthMetricsCollector()
        mc.record_request(domain="test.com", status_code=200)
        report = mc.get_report()
        assert "total_requests" in report
        assert "success_rate" in report
        assert "fingerprint_diversity" in report
        assert "requests_per_minute" in report

    def test_domain_risk_levels(self):
        mc = StealthMetricsCollector()
        assert mc.get_domain_risk("unknown.com") == "low"

        mc.record_request(domain="med.com", status_code=429)
        assert mc.get_domain_risk("med.com") == "medium"

        for _ in range(4):
            mc.record_request(domain="high.com", status_code=429)
        assert mc.get_domain_risk("high.com") == "high"

        for _ in range(6):
            mc.record_request(domain="crit.com", status_code=429)
        assert mc.get_domain_risk("crit.com") == "critical"

    def test_event_cap(self):
        mc = StealthMetricsCollector(max_events=5)
        for i in range(10):
            mc.record_request(domain="test.com", status_code=200)
        assert len(mc._events) == 5

    def test_most_blocked_domains(self):
        mc = StealthMetricsCollector()
        for _ in range(5):
            mc.record_request(domain="bad.com", status_code=429)
        mc.record_request(domain="ok.com", status_code=200)
        report = mc.get_report()
        assert "bad.com" in report["most_blocked_domains"]

    def test_reset(self):
        mc = StealthMetricsCollector()
        mc.record_request(domain="test.com", status_code=200)
        mc.reset()
        assert mc._total_requests == 0
        assert mc.success_rate == 0.0

    def test_record_event_direct(self):
        mc = StealthMetricsCollector()
        event = StealthEventRecord(
            timestamp=time.time(),
            event_type="request",
            domain="direct.com",
            status_code=200,
        )
        mc.record_event(event)
        assert mc._total_requests == 1


# ============================================================================
# TestScanStealthConfig
# ============================================================================

class TestScanStealthConfig:
    """Tests for ScanStealthConfig."""

    def test_create_default(self):
        config = ScanStealthConfig()
        assert config.stealth_level == "medium"
        assert config.tor_enabled is False
        assert config.max_requests_per_minute == 30

    def test_create_with_overrides(self):
        config = ScanStealthConfig(
            stealth_level="high",
            tor_enabled=True,
            max_requests_per_minute=10,
        )
        assert config.stealth_level == "high"
        assert config.tor_enabled is True

    def test_to_stealth_profile(self):
        config = ScanStealthConfig(stealth_level="high")
        profile = config.to_stealth_profile()
        assert profile.level == StealthLevel.HIGH

    def test_to_stealth_profile_with_proxies(self):
        config = ScanStealthConfig(
            proxy_list=["socks5://proxy1:1080", "http://proxy2:8080"],
        )
        profile = config.to_stealth_profile()
        assert len(profile.proxy_entries) == 2

    def test_to_stealth_profile_tor(self):
        config = ScanStealthConfig(
            tor_enabled=True,
            tor_control_password="secret",
            tor_renew_every_n=5,
        )
        profile = config.to_stealth_profile()
        assert profile.use_tor is True
        assert profile.tor_control_password == "secret"

    def test_to_dict_roundtrip(self):
        config = ScanStealthConfig(
            stealth_level="paranoid",
            tor_enabled=True,
            max_requests_per_minute=5,
        )
        d = config.to_dict()
        restored = ScanStealthConfig.from_dict(d)
        assert restored.stealth_level == "paranoid"
        assert restored.tor_enabled is True
        assert restored.max_requests_per_minute == 5

    def test_from_dict_ignores_unknown_keys(self):
        d = {"stealth_level": "low", "unknown_key": "value"}
        config = ScanStealthConfig.from_dict(d)
        assert config.stealth_level == "low"
        assert not hasattr(config, "unknown_key")

    def test_from_sf_options(self):
        opts = {
            "_stealth_level": "high",
            "_stealth_tor_enabled": True,
            "_stealth_max_rpm": 10,
            "_stealth_jitter_min": 0.5,
        }
        config = ScanStealthConfig.from_sf_options(opts)
        assert config.stealth_level == "high"
        assert config.tor_enabled is True
        assert config.max_requests_per_minute == 10
        assert config.jitter_min == 0.5

    def test_from_sf_options_legacy_socks(self):
        opts = {
            "_socks1type": "socks5",
            "_socks2addr": "proxy.test",
            "_socks3port": "1080",
        }
        config = ScanStealthConfig.from_sf_options(opts)
        assert len(config.proxy_list) == 1
        assert "socks5://proxy.test:1080" in config.proxy_list[0]

    def test_jitter_distribution_config(self):
        config = ScanStealthConfig(jitter_distribution="gaussian")
        profile = config.to_stealth_profile()
        from spiderfoot.recon.stealth_engine import JitterDistribution
        assert profile.jitter_distribution == JitterDistribution.GAUSSIAN

    def test_proxy_chain_config(self):
        config = ScanStealthConfig(
            proxy_chains=[
                ["socks5://p1:1080", "socks5://p2:1080"],
                ["http://p3:8080"],
            ],
            chain_strategy="per_domain",
        )
        assert len(config.proxy_chains) == 2
        assert config.chain_strategy == "per_domain"

    def test_stealth_bypass_domains(self):
        config = ScanStealthConfig(
            stealth_bypass_domains=["api.internal.com", "localhost"],
        )
        assert "api.internal.com" in config.stealth_bypass_domains


# ============================================================================
# TestStealthScanContext
# ============================================================================

class TestStealthScanContext:
    """Tests for StealthScanContext."""

    def test_create_default(self):
        ctx = StealthScanContext()
        assert ctx.engine is not None
        assert ctx.throttler is not None
        assert ctx.is_active is True

    def test_create_with_config(self):
        config = ScanStealthConfig(stealth_level="high", collect_metrics=True)
        ctx = StealthScanContext(config)
        assert ctx.config.stealth_level == "high"
        assert ctx.metrics is not None

    def test_create_no_metrics(self):
        config = ScanStealthConfig(collect_metrics=False)
        ctx = StealthScanContext(config)
        assert ctx.metrics is None

    def test_create_with_proxy_chains(self):
        config = ScanStealthConfig(
            proxy_chains=[["socks5://p1:1080", "socks5://p2:1080"]],
        )
        ctx = StealthScanContext(config)
        assert ctx.chain_manager is not None
        assert ctx.chain_manager.chain_count == 1

    def test_bypass_domain(self):
        config = ScanStealthConfig(
            stealth_bypass_domains=["internal.api.com"],
        )
        ctx = StealthScanContext(config)
        assert ctx.is_bypass_domain("internal.api.com") is True
        assert ctx.is_bypass_domain("sub.internal.api.com") is True
        assert ctx.is_bypass_domain("external.com") is False

    def test_add_bypass_domain(self):
        ctx = StealthScanContext()
        ctx.add_bypass_domain("new.domain.com")
        assert ctx.is_bypass_domain("new.domain.com") is True

    def test_deactivate_reactivate(self):
        ctx = StealthScanContext()
        assert ctx.is_active is True
        ctx.deactivate()
        assert ctx.is_active is False
        ctx.reactivate()
        assert ctx.is_active is True

    def test_get_stats(self):
        ctx = _make_context()
        stats = ctx.get_stats()
        assert "active" in stats
        assert "stealth_level" in stats
        assert "engine_stats" in stats
        assert "throttler_stats" in stats

    def test_get_stats_with_metrics(self):
        ctx = _make_context(collect_metrics=True)
        stats = ctx.get_stats()
        assert "metrics" in stats

    def test_get_stats_with_chains(self):
        ctx = _make_context(
            proxy_chains=[["socks5://p1:1080"]],
        )
        stats = ctx.get_stats()
        assert "proxy_chains" in stats

    def test_reset(self):
        ctx = _make_context(collect_metrics=True)
        ctx.throttler.record_request("test.com")
        ctx.reset()
        assert ctx.throttler.get_all_stats() == {}

    def test_engine_stealth_level(self):
        ctx = _make_context(stealth_level="paranoid")
        assert ctx.engine.stealth_level == StealthLevel.PARANOID


# ============================================================================
# TestStealthFetchMiddleware
# ============================================================================

class TestStealthFetchMiddleware:
    """Tests for StealthFetchMiddleware."""

    def test_create(self):
        ctx = _make_context()
        mw = StealthFetchMiddleware(ctx)
        assert mw.fetch_count == 0

    def test_fetch_with_mock(self):
        ctx = _make_context(collect_metrics=True)
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"
        assert mw.fetch_count == 1

    def test_fetch_bypass_domain(self):
        config = ScanStealthConfig(
            stealth_bypass_domains=["bypass.com"],
        )
        ctx = StealthScanContext(config)
        mw = StealthFetchMiddleware(ctx)
        result = mw.fetch(
            "https://bypass.com/page",
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"
        # Bypass should NOT go through stealth middleware
        # so fetch_count stays 0
        assert mw.fetch_count == 0

    def test_fetch_inactive_context(self):
        ctx = _make_context()
        ctx.deactivate()
        mw = StealthFetchMiddleware(ctx)
        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"

    def test_fetch_empty_url(self):
        ctx = _make_context()
        mw = StealthFetchMiddleware(ctx)
        result = mw.fetch("")
        assert result is None

    def test_fetch_blocked_no_retry(self):
        ctx = _make_context(collect_metrics=True)
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_blocked,
        )
        assert result["code"] == "429"

    def test_detection_captcha(self):
        ctx = _make_context(collect_metrics=True)
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_captcha,
        )
        assert result["code"] == "403"
        # Metrics should record the detection
        assert ctx.metrics._total_detections > 0

    def test_detection_waf(self):
        ctx = _make_context(collect_metrics=True)
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_waf,
        )
        assert result["code"] == "503"
        assert ctx.metrics._total_detections > 0

    def test_metrics_collected(self):
        ctx = _make_context(collect_metrics=True)
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        mw.fetch("https://target.com/page", _original_fetch=_mock_fetch_ok)
        report = ctx.metrics.get_report()
        assert report["total_requests"] == 1
        assert report["total_successes"] == 1

    def test_throttle_records(self):
        ctx = _make_context()
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        mw.fetch("https://target.com/page", _original_fetch=_mock_fetch_ok)
        stats = ctx.throttler.get_domain_stats("target.com")
        assert stats["requests_total"] == 1

    def test_fetch_no_original_fetch(self):
        ctx = _make_context()
        mw = StealthFetchMiddleware(ctx, max_retries=0)
        result = mw.fetch("https://target.com/page")
        # Should return default empty result
        assert result["code"] is None

    def test_detection_patterns(self):
        mw = StealthFetchMiddleware(_make_context())
        detected = mw._check_detection({
            "code": "403",
            "content": "Bot detected. Access denied.",
            "headers": {},
        })
        assert detected is True

    def test_classify_rate_limit(self):
        mw = StealthFetchMiddleware(_make_context())
        cls = mw._classify_detection({"code": "429", "content": ""})
        assert cls == "rate_limit"

    def test_classify_captcha(self):
        mw = StealthFetchMiddleware(_make_context())
        cls = mw._classify_detection({
            "code": "403",
            "content": "please complete the captcha",
        })
        assert cls == "captcha"

    def test_classify_cloudflare(self):
        mw = StealthFetchMiddleware(_make_context())
        cls = mw._classify_detection({
            "code": "503",
            "content": "cloudflare protection active",
        })
        assert cls == "waf_cloudflare"

    def test_parse_status_code(self):
        assert StealthFetchMiddleware._parse_status_code({"code": "200"}) == 200
        assert StealthFetchMiddleware._parse_status_code({"code": None}) == 0
        assert StealthFetchMiddleware._parse_status_code(None) == 0
        assert StealthFetchMiddleware._parse_status_code({"code": "abc"}) == 0


# ============================================================================
# TestCreateStealthContext
# ============================================================================

class TestCreateStealthContext:
    """Tests for create_stealth_context factory."""

    def test_with_config(self):
        config = ScanStealthConfig(stealth_level="high")
        ctx = create_stealth_context(config)
        assert ctx.config.stealth_level == "high"

    def test_with_level(self):
        ctx = create_stealth_context(stealth_level="low")
        assert ctx.config.stealth_level == "low"

    def test_with_sf_options(self):
        opts = {"_stealth_level": "paranoid"}
        ctx = create_stealth_context(sf_options=opts)
        assert ctx.config.stealth_level == "paranoid"

    def test_default(self):
        ctx = create_stealth_context()
        assert ctx.config.stealth_level == "medium"

    def test_config_priority(self):
        """Config should take priority over sf_options and stealth_level."""
        config = ScanStealthConfig(stealth_level="high")
        ctx = create_stealth_context(
            config, stealth_level="low", sf_options={"_stealth_level": "paranoid"},
        )
        assert ctx.config.stealth_level == "high"


# ============================================================================
# TestScanContextRegistry
# ============================================================================

class TestScanContextRegistry:
    """Tests for scan context registration/retrieval."""

    def test_register_and_get(self):
        ctx = _make_context()
        register_scan_context("scan-001", ctx)
        try:
            retrieved = get_scan_context("scan-001")
            assert retrieved is ctx
        finally:
            unregister_scan_context("scan-001")

    def test_get_nonexistent(self):
        assert get_scan_context("nonexistent") is None

    def test_unregister(self):
        ctx = _make_context()
        register_scan_context("scan-002", ctx)
        unregister_scan_context("scan-002")
        assert get_scan_context("scan-002") is None
        assert ctx.is_active is False

    def test_unregister_nonexistent(self):
        # Should not raise
        unregister_scan_context("nonexistent")

    def test_get_all_scan_stats(self):
        ctx1 = _make_context()
        ctx2 = _make_context(stealth_level="high")
        register_scan_context("stats-1", ctx1)
        register_scan_context("stats-2", ctx2)
        try:
            stats = get_all_scan_stats()
            assert "stats-1" in stats
            assert "stats-2" in stats
        finally:
            unregister_scan_context("stats-1")
            unregister_scan_context("stats-2")


# ============================================================================
# TestStealthyFetch
# ============================================================================

class TestStealthyFetch:
    """Tests for the stealthy_fetch convenience function."""

    def test_with_context(self):
        ctx = _make_context()
        result = stealthy_fetch(
            "https://target.com/page",
            context=ctx,
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"

    def test_with_scan_id(self):
        ctx = _make_context()
        register_scan_context("fetch-test", ctx)
        try:
            result = stealthy_fetch(
                "https://target.com/page",
                scan_id="fetch-test",
                _original_fetch=_mock_fetch_ok,
            )
            assert result["code"] == "200"
        finally:
            unregister_scan_context("fetch-test")

    def test_no_context_with_original_fetch(self):
        result = stealthy_fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"

    def test_empty_url(self):
        ctx = _make_context()
        result = stealthy_fetch("", context=ctx)
        assert result is None


# ============================================================================
# TestExtractDomain
# ============================================================================

class TestExtractDomain:
    """Tests for _extract_domain helper."""

    def test_http(self):
        assert _extract_domain("http://example.com/page") == "example.com"

    def test_https_with_port(self):
        assert _extract_domain("https://example.com:8443/api") == "example.com"

    def test_subdomain(self):
        assert _extract_domain("https://sub.example.com/") == "sub.example.com"

    def test_empty(self):
        assert _extract_domain("") == ""

    def test_invalid(self):
        result = _extract_domain("not a url")
        # Should not crash, returns something
        assert isinstance(result, str)


# ============================================================================
# TestThreadSafety
# ============================================================================

class TestThreadSafety:
    """Verify thread safety of key components."""

    def test_throttler_concurrent(self):
        throttler = DomainThrottler(default_min_interval=0.0, default_max_rpm=1000)
        errors = []

        def worker(domain: str):
            try:
                for _ in range(50):
                    throttler.check_throttle(domain)
                    throttler.record_request(domain)
                    throttler.record_response(domain, 200)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"domain-{i}.com",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors

    def test_metrics_concurrent(self):
        mc = StealthMetricsCollector()
        errors = []

        def worker(worker_id: int):
            try:
                for i in range(50):
                    mc.record_request(
                        domain=f"domain-{worker_id}.com",
                        status_code=200,
                        user_agent=f"UA-{worker_id}-{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert mc._total_requests == 250

    def test_chain_manager_concurrent(self):
        chains = [_make_chain([f"proxy-{i}:1080"]) for i in range(5)]
        mgr = ProxyChainManager(chains=chains, strategy=ProxyChainStrategy.RANDOM)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    chain = mgr.get_chain()
                    if chain:
                        mgr.record_result(chain.chain_id, success=True, latency_ms=10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors


# ============================================================================
# TestIntegrationScenarios
# ============================================================================

class TestIntegrationScenarios:
    """End-to-end integration tests combining multiple components."""

    def test_full_scan_lifecycle(self):
        """Simulate a complete scan lifecycle with stealth."""
        # 1. Create config
        config = ScanStealthConfig(
            stealth_level="high",
            max_requests_per_minute=100,
            min_request_interval=0.0,
            collect_metrics=True,
        )

        # 2. Create context
        ctx = create_stealth_context(config)

        # 3. Register for scan
        register_scan_context("lifecycle-test", ctx)

        try:
            # 4. Simulate requests
            for i in range(5):
                result = stealthy_fetch(
                    f"https://target.com/page-{i}",
                    scan_id="lifecycle-test",
                    _original_fetch=_mock_fetch_ok,
                )
                assert result["code"] == "200"

            # 5. Check stats
            stats = ctx.get_stats()
            assert stats["active"] is True
            assert ctx.metrics._total_requests == 5

        finally:
            # 6. Cleanup
            unregister_scan_context("lifecycle-test")
            assert ctx.is_active is False

    def test_proxy_chain_with_middleware(self):
        """Test middleware using proxy chains."""
        config = ScanStealthConfig(
            stealth_level="medium",
            proxy_chains=[
                ["socks5://chain1-hop1:1080", "socks5://chain1-hop2:1080"],
                ["socks5://chain2-hop1:1080"],
            ],
            chain_strategy="rotating",
            collect_metrics=True,
            min_request_interval=0.0,
        )
        ctx = create_stealth_context(config)
        mw = StealthFetchMiddleware(ctx, max_retries=0)

        for i in range(4):
            result = mw.fetch(
                f"https://target.com/page-{i}",
                _original_fetch=_mock_fetch_ok,
            )
            assert result["code"] == "200"

        # Proxy chains should have recorded requests
        chain_stats = ctx.chain_manager.get_stats()
        total_chain_requests = sum(s["total_requests"] for s in chain_stats)
        assert total_chain_requests == 4

    def test_adaptive_throttle_scenario(self):
        """Simulate progressive blocking and adaptive throttle."""
        config = ScanStealthConfig(
            stealth_level="medium",
            max_requests_per_minute=30,
            min_request_interval=0.0,
            collect_metrics=True,
        )
        ctx = create_stealth_context(config)

        # Record several blocks
        for _ in range(3):
            ctx.throttler.record_response("defended.com", 429)

        # Check that throttle adapted
        stats = ctx.throttler.get_domain_stats("defended.com")
        assert stats["backoff_count"] == 3
        assert stats["max_rpm"] < 30  # Should have reduced

    def test_metrics_report_completeness(self):
        """Verify metrics report contains all expected fields."""
        ctx = _make_context(collect_metrics=True, min_request_interval=0.0)
        mw = StealthFetchMiddleware(ctx, max_retries=0)

        # Mix of successful and blocked requests
        mw.fetch("https://ok.com/page", _original_fetch=_mock_fetch_ok)
        mw.fetch("https://blocked.com/page", _original_fetch=_mock_fetch_blocked)
        mw.fetch("https://captcha.com/page", _original_fetch=_mock_fetch_captcha)

        report = ctx.metrics.get_report()
        assert report["total_requests"] == 3
        assert report["total_successes"] >= 1
        assert report["total_blocks"] >= 1
        assert "elapsed_seconds" in report
        assert "requests_per_minute" in report

    def test_stealth_none_level(self):
        """Stealth level NONE should still work but with minimal overhead."""
        config = ScanStealthConfig(stealth_level="none", collect_metrics=True)
        ctx = create_stealth_context(config)
        mw = StealthFetchMiddleware(ctx, max_retries=0)

        result = mw.fetch(
            "https://target.com/page",
            _original_fetch=_mock_fetch_ok,
        )
        assert result["code"] == "200"
