"""Comprehensive tests for the Stealth & Evasion Engine (SOTA Phase I, Cycles 1–20).

Tests cover:
- UserAgentRotator: weighted rotation, filtering, session pinning
- HeaderRandomizer: header generation, referrer strategies, ordering
- TLSFingerprintDiversifier: profile creation, SSL context, pinning
- ProxyRotator: rotation strategies, health tracking, failover
- TorCircuitManager: proxy URL, circuit renewal, timing
- RequestJitter: distributions, clamping, delay statistics
- StealthProfileConfig: level presets, from_level factory
- StealthEngine: unified façade integration
"""

from __future__ import annotations

import ssl
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.recon.stealth_engine import (
    HeaderRandomizer,
    JitterConfig,
    JitterDistribution,
    ProxyEntry,
    ProxyProtocol,
    ProxyRotator,
    ProxySelectionStrategy,
    RequestJitter,
    StealthEngine,
    StealthLevel,
    StealthProfileConfig,
    TLSCipherProfile,
    TLSFingerprintDiversifier,
    TorCircuitManager,
    UserAgentEntry,
    UserAgentRotator,
    _DEFAULT_USER_AGENTS,
)


# ============================================================================
# UserAgentRotator Tests
# ============================================================================


class TestUserAgentRotator:
    """Tests for UserAgentRotator."""

    def test_default_ua_count(self):
        """Default UA list has 15+ entries covering major browsers."""
        rotator = UserAgentRotator()
        assert rotator.count >= 15

    def test_get_returns_string(self):
        """get() returns a non-empty string."""
        rotator = UserAgentRotator()
        ua = rotator.get()
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_get_variety(self):
        """Multiple calls should produce variety (weighted random)."""
        rotator = UserAgentRotator()
        uas = {rotator.get() for _ in range(100)}
        # With 15+ entries and 100 draws, should see at least 3 distinct UAs
        assert len(uas) >= 3

    def test_filter_by_browser(self):
        """Filtering by browser returns only matching UAs."""
        rotator = UserAgentRotator()
        for _ in range(50):
            ua = rotator.get(browser="firefox")
            assert "Firefox" in ua

    def test_filter_by_os(self):
        """Filtering by OS returns matching platform UAs."""
        rotator = UserAgentRotator()
        for _ in range(50):
            ua = rotator.get(os_family="macos")
            assert "Macintosh" in ua or "Mac OS X" in ua

    def test_filter_fallback(self):
        """Invalid filter falls back to full list."""
        rotator = UserAgentRotator()
        ua = rotator.get(browser="netscape_navigator")
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_session_pinning(self):
        """With pin_per_session, same key returns same UA."""
        rotator = UserAgentRotator(pin_per_session=True)
        ua1 = rotator.get(session_key="scan_001")
        for _ in range(20):
            assert rotator.get(session_key="scan_001") == ua1

    def test_different_sessions_different_uas(self):
        """Different session keys may get different UAs."""
        rotator = UserAgentRotator(pin_per_session=True)
        uas = {rotator.get(session_key=f"scan_{i}") for i in range(50)}
        # At least 2 different UAs across 50 sessions
        assert len(uas) >= 2

    def test_clear_sessions(self):
        """clear_sessions resets pinned UAs."""
        rotator = UserAgentRotator(pin_per_session=True)
        ua1 = rotator.get(session_key="test")
        rotator.clear_sessions()
        # After clearing, the next call may return a different UA
        # (probabilistic, but the pin is definitely gone)
        assert isinstance(rotator.get(session_key="test"), str)

    def test_consistent_headers_chrome(self):
        """get_consistent_headers returns Chrome-specific headers."""
        rotator = UserAgentRotator()
        ua = rotator.get(browser="chrome")
        headers = rotator.get_consistent_headers(ua)
        assert "Sec-Ch-Ua" in headers
        assert "Accept" in headers

    def test_consistent_headers_firefox(self):
        """get_consistent_headers returns Firefox-specific headers."""
        rotator = UserAgentRotator()
        ua = rotator.get(browser="firefox")
        headers = rotator.get_consistent_headers(ua)
        assert "Accept" in headers
        # Firefox doesn't send Sec-Ch-Ua
        assert "Sec-Ch-Ua" not in headers

    def test_consistent_headers_safari(self):
        """get_consistent_headers returns Safari-specific headers."""
        rotator = UserAgentRotator()
        ua = rotator.get(browser="safari")
        headers = rotator.get_consistent_headers(ua)
        assert "Accept" in headers

    def test_empty_ua_list_raises(self):
        """Empty UA list raises ValueError."""
        with pytest.raises(ValueError, match="At least one"):
            UserAgentRotator(user_agents=[])

    def test_custom_ua_list(self):
        """Custom UA list is used."""
        custom = [UserAgentEntry("CustomBot/1.0", "custom", "linux", "1.0", weight=1.0)]
        rotator = UserAgentRotator(user_agents=custom)
        assert rotator.count == 1
        assert rotator.get() == "CustomBot/1.0"

    def test_weight_bias(self):
        """Higher-weight UAs are selected more frequently."""
        entries = [
            UserAgentEntry("Heavy/1.0", "chrome", "windows", "1.0", weight=100.0),
            UserAgentEntry("Light/1.0", "firefox", "linux", "1.0", weight=0.01),
        ]
        rotator = UserAgentRotator(user_agents=entries)
        counts = {"Heavy/1.0": 0, "Light/1.0": 0}
        for _ in range(1000):
            ua = rotator.get()
            counts[ua] += 1
        # Heavy should dominate
        assert counts["Heavy/1.0"] > 900


# ============================================================================
# HeaderRandomizer Tests
# ============================================================================


class TestHeaderRandomizer:
    """Tests for HeaderRandomizer."""

    def test_generate_returns_dict(self):
        """generate() returns a dict with User-Agent."""
        rand = HeaderRandomizer()
        headers = rand.generate()
        assert isinstance(headers, dict)
        assert "User-Agent" in headers

    def test_generate_has_accept(self):
        """Generated headers include Accept header."""
        rand = HeaderRandomizer()
        headers = rand.generate()
        assert "Accept" in headers

    def test_generate_has_accept_encoding(self):
        """Generated headers include Accept-Encoding."""
        rand = HeaderRandomizer()
        headers = rand.generate()
        assert "Accept-Encoding" in headers

    def test_extra_headers_override(self):
        """Extra headers override generated ones."""
        rand = HeaderRandomizer()
        headers = rand.generate(extra_headers={"User-Agent": "MyBot/1.0"})
        assert headers["User-Agent"] == "MyBot/1.0"

    def test_referer_google(self):
        """Google referrer strategy produces Google URL."""
        rand = HeaderRandomizer()
        headers = rand.generate(referrer_strategy="google")
        assert "Referer" in headers
        assert "google" in headers["Referer"]

    def test_referer_self(self):
        """Self referrer strategy uses target origin."""
        rand = HeaderRandomizer()
        headers = rand.generate(
            target_url="https://example.com/page",
            referrer_strategy="self",
        )
        assert headers.get("Referer") == "https://example.com/"

    def test_referer_none(self):
        """None referrer strategy omits Referer."""
        rand = HeaderRandomizer()
        headers = rand.generate(referrer_strategy="none")
        assert "Referer" not in headers

    def test_header_ordering_varies(self):
        """Header key ordering should vary across calls."""
        rand = HeaderRandomizer()
        orderings = []
        for _ in range(30):
            h = rand.generate()
            orderings.append(tuple(h.keys()))
        unique = set(orderings)
        # Should see multiple orderings
        assert len(unique) >= 2

    def test_optional_headers_with_rate_zero(self):
        """include_rate=0 should not include optional headers."""
        rand = HeaderRandomizer(include_rate=0.0)
        headers = rand.generate(referrer_strategy="none")
        # DNT, Cache-Control, Pragma should not appear
        assert "DNT" not in headers
        assert "Pragma" not in headers

    def test_optional_headers_with_rate_one(self):
        """include_rate=1.0 should always include optional headers."""
        rand = HeaderRandomizer(include_rate=1.0)
        headers = rand.generate(referrer_strategy="none")
        assert "DNT" in headers
        assert "Cache-Control" in headers


# ============================================================================
# TLS Fingerprint Diversifier Tests
# ============================================================================


class TestTLSFingerprintDiversifier:
    """Tests for TLSFingerprintDiversifier."""

    def test_default_profiles(self):
        """Default initialization uses all available profiles."""
        div = TLSFingerprintDiversifier()
        assert len(TLSCipherProfile.profile_names()) >= 4

    def test_create_ssl_context(self):
        """create_ssl_context returns a valid SSLContext."""
        div = TLSFingerprintDiversifier()
        ctx = div.create_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)

    def test_ssl_context_no_verify(self):
        """With verify=False, cert verification is disabled."""
        div = TLSFingerprintDiversifier()
        ctx = div.create_ssl_context(verify=False)
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_ssl_context_verify(self):
        """With verify=True, cert verification is enabled."""
        div = TLSFingerprintDiversifier()
        ctx = div.create_ssl_context(verify=True)
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_pin_per_target(self):
        """Same target host gets same TLS profile."""
        div = TLSFingerprintDiversifier(pin_per_target=True)
        profile1 = div.get_current_profile("example.com")
        for _ in range(20):
            assert div.get_current_profile("example.com") == profile1

    def test_different_targets_may_differ(self):
        """Different targets may get different profiles."""
        div = TLSFingerprintDiversifier(pin_per_target=True)
        profiles = {div.get_current_profile(f"host{i}.com") for i in range(50)}
        # Should see at least 2 different profiles
        assert len(profiles) >= 2

    def test_clear_pins(self):
        """clear_pins resets target-pinned profiles."""
        div = TLSFingerprintDiversifier(pin_per_target=True)
        p1 = div.get_current_profile("test.com")
        div.clear_pins()
        # After clear, might get a different profile
        assert isinstance(div.get_current_profile("test.com"), str)

    def test_invalid_profile_raises(self):
        """Invalid profile names are silently filtered, empty raises."""
        with pytest.raises(ValueError, match="No valid"):
            TLSFingerprintDiversifier(profiles=["nonexistent_browser_999"])

    def test_specific_profile(self):
        """Specifying a single profile always returns that profile."""
        div = TLSFingerprintDiversifier(profiles=["firefox_133"])
        assert div.get_current_profile("any.com") == "firefox_133"

    def test_tls_min_version(self):
        """SSL context has TLS 1.2 minimum."""
        div = TLSFingerprintDiversifier()
        ctx = div.create_ssl_context()
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


# ============================================================================
# Proxy Rotator Tests
# ============================================================================


class TestProxyRotator:
    """Tests for ProxyRotator."""

    def _make_proxies(self, n: int = 3) -> list[ProxyEntry]:
        return [
            ProxyEntry(
                url=f"proxy{i}.example.com:8080",
                protocol=ProxyProtocol.HTTP,
                region=f"region{i % 2}",
            )
            for i in range(n)
        ]

    def test_empty_rotator(self):
        """Empty rotator returns None."""
        rotator = ProxyRotator()
        assert rotator.get_next() is None
        assert rotator.count == 0

    def test_round_robin(self):
        """Round-robin cycles through proxies."""
        proxies = self._make_proxies(3)
        rotator = ProxyRotator(proxies, ProxySelectionStrategy.ROUND_ROBIN)
        urls = [rotator.get_next().url for _ in range(6)]
        assert urls == [
            "proxy0.example.com:8080",
            "proxy1.example.com:8080",
            "proxy2.example.com:8080",
            "proxy0.example.com:8080",
            "proxy1.example.com:8080",
            "proxy2.example.com:8080",
        ]

    def test_random_strategy(self):
        """Random strategy returns various proxies."""
        proxies = self._make_proxies(5)
        rotator = ProxyRotator(proxies, ProxySelectionStrategy.RANDOM)
        urls = {rotator.get_next().url for _ in range(100)}
        assert len(urls) >= 2

    def test_least_used(self):
        """Least-used strategy prefers proxies with fewer requests."""
        proxies = self._make_proxies(3)
        proxies[0].total_requests = 100
        proxies[1].total_requests = 5
        proxies[2].total_requests = 50
        rotator = ProxyRotator(proxies, ProxySelectionStrategy.LEAST_USED)
        chosen = rotator.get_next()
        assert chosen.url == "proxy1.example.com:8080"

    def test_lowest_latency(self):
        """Lowest-latency strategy prefers fastest proxy."""
        proxies = self._make_proxies(3)
        proxies[0].record_success(latency_ms=200)
        proxies[1].record_success(latency_ms=30)
        proxies[2].record_success(latency_ms=150)
        rotator = ProxyRotator(proxies, ProxySelectionStrategy.LOWEST_LATENCY)
        chosen = rotator.get_next()
        assert chosen.url == "proxy1.example.com:8080"

    def test_region_affinity(self):
        """Region affinity prefers proxies in the requested region."""
        proxies = self._make_proxies(4)
        rotator = ProxyRotator(proxies, ProxySelectionStrategy.REGION_AFFINITY)
        for _ in range(20):
            chosen = rotator.get_next(region="region1")
            assert chosen.region == "region1"

    def test_health_tracking(self):
        """Proxies become unhealthy after consecutive failures."""
        proxies = self._make_proxies(2)
        rotator = ProxyRotator(proxies, max_consecutive_failures=3)
        # Fail proxy0 three times
        for _ in range(3):
            rotator.record_result("proxy0.example.com:8080", success=False)
        # Now it should be skipped
        for _ in range(5):
            chosen = rotator.get_next()
            assert chosen.url == "proxy1.example.com:8080"

    def test_cooldown_recovery(self):
        """Unhealthy proxies recover after cooldown period."""
        proxies = self._make_proxies(1)
        rotator = ProxyRotator(proxies, max_consecutive_failures=2, cooldown_seconds=0.01)
        rotator.record_result("proxy0.example.com:8080", success=False)
        rotator.record_result("proxy0.example.com:8080", success=False)
        # Proxy is unhealthy
        assert rotator.get_next() is None
        # Wait for cooldown
        time.sleep(0.02)
        # Now it should be available again
        assert rotator.get_next() is not None

    def test_add_remove_proxy(self):
        """Can add and remove proxies dynamically."""
        rotator = ProxyRotator()
        p = ProxyEntry(url="new.proxy.com:8080")
        rotator.add_proxy(p)
        assert rotator.count == 1
        assert rotator.remove_proxy("new.proxy.com:8080")
        assert rotator.count == 0

    def test_get_stats(self):
        """get_stats returns per-proxy statistics."""
        proxies = self._make_proxies(2)
        rotator = ProxyRotator(proxies)
        rotator.record_result("proxy0.example.com:8080", success=True, latency_ms=50)
        stats = rotator.get_stats()
        assert len(stats) == 2
        assert stats[0]["total_requests"] == 1
        assert stats[0]["avg_latency_ms"] == 50.0

    def test_to_requests_dict(self):
        """ProxyEntry.to_requests_dict produces valid proxy dict."""
        p = ProxyEntry(url="1.2.3.4:8080", protocol=ProxyProtocol.SOCKS5)
        d = p.to_requests_dict()
        assert d["http"] == "socks5://1.2.3.4:8080"
        assert d["https"] == "socks5://1.2.3.4:8080"

    def test_to_requests_dict_with_auth(self):
        """ProxyEntry with auth includes credentials."""
        p = ProxyEntry(url="proxy.com:443", protocol=ProxyProtocol.HTTPS,
                       username="user", password="pass")
        d = p.to_requests_dict()
        assert d["http"] == "https://user:pass@proxy.com:443"

    def test_failure_rate(self):
        """failure_rate computes correctly."""
        p = ProxyEntry(url="test:8080")
        p.total_requests = 10
        p.total_failures = 3
        assert abs(p.failure_rate - 0.3) < 0.001


# ============================================================================
# TorCircuitManager Tests
# ============================================================================


class TestTorCircuitManager:
    """Tests for TorCircuitManager."""

    def test_proxy_url(self):
        """proxy_url returns correct SOCKS5H URL."""
        mgr = TorCircuitManager()
        assert mgr.proxy_url == "socks5h://127.0.0.1:9050"

    def test_proxy_dict(self):
        """proxy_dict returns requests-compatible dict."""
        mgr = TorCircuitManager()
        d = mgr.proxy_dict
        assert "http" in d
        assert "https" in d
        assert "socks5h" in d["http"]

    def test_custom_ports(self):
        """Custom host/port configuration."""
        mgr = TorCircuitManager(socks_host="10.0.0.1", socks_port=9150)
        assert mgr.proxy_url == "socks5h://10.0.0.1:9150"

    def test_circuit_count_starts_zero(self):
        """Circuit count starts at 0."""
        mgr = TorCircuitManager()
        assert mgr.circuit_count == 0

    def test_should_renew_by_count(self):
        """should_renew triggers on request count threshold."""
        mgr = TorCircuitManager()
        assert mgr.should_renew(requests_since_last=10, threshold=10)
        assert not mgr.should_renew(requests_since_last=5, threshold=10)

    def test_should_renew_by_time(self):
        """should_renew triggers after 10 minutes."""
        mgr = TorCircuitManager()
        mgr._last_renewal = time.time() - 700  # Over 10 minutes ago
        assert mgr.should_renew(requests_since_last=0, threshold=100)

    def test_renew_respects_min_age(self):
        """renew_circuit returns False if called too quickly."""
        mgr = TorCircuitManager(min_circuit_age=999)
        mgr._last_renewal = time.time()  # Just renewed
        # Should return False due to min_circuit_age
        result = mgr.renew_circuit()
        assert result is False


# ============================================================================
# RequestJitter Tests
# ============================================================================


class TestRequestJitter:
    """Tests for RequestJitter."""

    def test_uniform_distribution(self):
        """Uniform distribution stays within bounds."""
        config = JitterConfig(
            distribution=JitterDistribution.UNIFORM,
            min_delay=0.5,
            max_delay=2.0,
        )
        jitter = RequestJitter(config)
        for _ in range(200):
            delay = jitter.get_delay()
            assert 0.5 <= delay <= 2.0

    def test_gaussian_distribution(self):
        """Gaussian distribution is clamped to bounds."""
        config = JitterConfig(
            distribution=JitterDistribution.GAUSSIAN,
            min_delay=0.1,
            max_delay=5.0,
            mean_delay=1.5,
            stddev=0.8,
        )
        jitter = RequestJitter(config)
        for _ in range(200):
            delay = jitter.get_delay()
            assert 0.1 <= delay <= 5.0

    def test_exponential_distribution(self):
        """Exponential distribution is clamped."""
        config = JitterConfig(
            distribution=JitterDistribution.EXPONENTIAL,
            min_delay=0.05,
            max_delay=10.0,
            mean_delay=1.0,
        )
        jitter = RequestJitter(config)
        for _ in range(200):
            assert 0.05 <= jitter.get_delay() <= 10.0

    def test_human_distribution(self):
        """Human distribution produces varied delays within bounds."""
        config = JitterConfig(
            distribution=JitterDistribution.HUMAN,
            min_delay=0.05,
            max_delay=10.0,
        )
        jitter = RequestJitter(config)
        delays = [jitter.get_delay() for _ in range(200)]
        assert all(0.05 <= d <= 10.0 for d in delays)
        # Should have some variety
        assert max(delays) > 2 * min(delays)

    def test_poisson_distribution(self):
        """Poisson distribution is clamped."""
        config = JitterConfig(
            distribution=JitterDistribution.POISSON,
            min_delay=0.1,
            max_delay=5.0,
            mean_delay=1.0,
        )
        jitter = RequestJitter(config)
        for _ in range(200):
            assert 0.1 <= jitter.get_delay() <= 5.0

    def test_avg_jitter_tracking(self):
        """avg_jitter tracks the running average."""
        config = JitterConfig(
            distribution=JitterDistribution.UNIFORM,
            min_delay=1.0,
            max_delay=1.0,
        )
        jitter = RequestJitter(config)
        for _ in range(10):
            jitter.get_delay()
        assert jitter.avg_jitter == pytest.approx(1.0, abs=0.01)

    def test_request_count(self):
        """request_count increments with each get_delay call."""
        jitter = RequestJitter()
        assert jitter.request_count == 0
        for i in range(5):
            jitter.get_delay()
            assert jitter.request_count == i + 1

    def test_apply_delay_calls_sleep(self):
        """apply_delay calls time.sleep with the delay value."""
        config = JitterConfig(
            distribution=JitterDistribution.UNIFORM,
            min_delay=0.001,
            max_delay=0.002,
        )
        jitter = RequestJitter(config)
        with patch("spiderfoot.recon.stealth_engine.time.sleep") as mock_sleep:
            delay = jitter.apply_delay()
            mock_sleep.assert_called_once()
            actual_arg = mock_sleep.call_args[0][0]
            assert 0.001 <= actual_arg <= 0.002


# ============================================================================
# StealthProfileConfig Tests
# ============================================================================


class TestStealthProfileConfig:
    """Tests for StealthProfileConfig presets."""

    @pytest.mark.parametrize("level", ["none", "low", "medium", "high", "paranoid"])
    def test_from_level_string(self, level):
        """from_level accepts string level names."""
        config = StealthProfileConfig.from_level(level)
        assert config.level == StealthLevel(level)

    @pytest.mark.parametrize("level", list(StealthLevel))
    def test_from_level_enum(self, level):
        """from_level accepts StealthLevel enums."""
        config = StealthProfileConfig.from_level(level)
        assert config.level == level

    def test_paranoid_uses_tor(self):
        """PARANOID level enables Tor."""
        config = StealthProfileConfig.from_level(StealthLevel.PARANOID)
        assert config.use_tor is True

    def test_none_minimal_jitter(self):
        """NONE level has minimal jitter."""
        config = StealthProfileConfig.from_level(StealthLevel.NONE)
        assert config.jitter_max_delay <= 0.1

    def test_high_has_high_jitter(self):
        """HIGH level has significant jitter."""
        config = StealthProfileConfig.from_level(StealthLevel.HIGH)
        assert config.jitter_min_delay >= 1.0
        assert config.jitter_max_delay >= 5.0

    def test_jitter_increases_with_level(self):
        """Jitter delay increases with stealth level."""
        levels = [StealthLevel.NONE, StealthLevel.LOW, StealthLevel.MEDIUM,
                  StealthLevel.HIGH, StealthLevel.PARANOID]
        delays = [StealthProfileConfig.from_level(l).jitter_mean_delay for l in levels]
        # Each level should have equal or higher mean delay
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]


# ============================================================================
# StealthEngine Integration Tests
# ============================================================================


class TestStealthEngine:
    """Tests for the unified StealthEngine façade."""

    def test_default_initialization(self):
        """Default engine initializes at MEDIUM level."""
        engine = StealthEngine()
        assert engine.stealth_level == StealthLevel.MEDIUM

    def test_none_level_returns_simple_headers(self):
        """NONE level returns minimal headers."""
        config = StealthProfileConfig.from_level(StealthLevel.NONE)
        engine = StealthEngine(config)
        headers = engine.prepare_headers()
        assert headers["User-Agent"] == "SpiderFoot"

    def test_medium_level_returns_diverse_headers(self):
        """MEDIUM level returns full browser headers."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        engine = StealthEngine(config)
        headers = engine.prepare_headers(target_url="https://example.com")
        assert headers["User-Agent"] != "SpiderFoot"
        assert "Accept" in headers

    def test_high_level_has_tls_diversifier(self):
        """HIGH level enables TLS fingerprint diversification."""
        config = StealthProfileConfig.from_level(StealthLevel.HIGH)
        engine = StealthEngine(config)
        ctx = engine.get_ssl_context(target_host="example.com")
        assert isinstance(ctx, ssl.SSLContext)

    def test_ssl_context_without_diversifier(self):
        """LOW level returns basic SSL context."""
        config = StealthProfileConfig.from_level(StealthLevel.LOW)
        engine = StealthEngine(config)
        ctx = engine.get_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_no_proxy_returns_none(self):
        """Without proxies configured, get_proxy returns None."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        engine = StealthEngine(config)
        assert engine.get_proxy() is None

    def test_proxy_rotation(self):
        """Engine rotates through configured proxies."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        config.proxy_entries = [
            ProxyEntry(url="p1:8080"),
            ProxyEntry(url="p2:8080"),
        ]
        engine = StealthEngine(config)
        proxies = {engine.get_proxy()["http"] for _ in range(20)}
        assert len(proxies) >= 2

    def test_jitter_none_level(self):
        """NONE level applies zero jitter."""
        config = StealthProfileConfig.from_level(StealthLevel.NONE)
        engine = StealthEngine(config)
        delay = engine.get_jitter_delay()
        assert delay == 0.0

    def test_jitter_medium_level(self):
        """MEDIUM level applies non-zero jitter."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        engine = StealthEngine(config)
        delay = engine.get_jitter_delay()
        assert delay > 0

    def test_get_stats(self):
        """get_stats returns comprehensive statistics dict."""
        engine = StealthEngine()
        stats = engine.get_stats()
        assert "stealth_level" in stats
        assert stats["stealth_level"] == "medium"
        assert "total_requests" in stats
        assert "avg_jitter_seconds" in stats

    def test_get_stats_with_proxies(self):
        """get_stats includes proxy info when configured."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        config.proxy_entries = [ProxyEntry(url="p1:8080")]
        engine = StealthEngine(config)
        stats = engine.get_stats()
        assert "proxies" in stats
        assert "healthy_proxies" in stats

    def test_request_counter(self):
        """Request counter increments."""
        engine = StealthEngine()
        assert engine.request_count == 0
        engine.increment_request_counter()
        engine.increment_request_counter()
        assert engine.request_count == 2

    def test_reset(self):
        """reset clears all state."""
        engine = StealthEngine()
        engine.increment_request_counter()
        engine.increment_request_counter()
        engine.reset()
        assert engine.request_count == 0

    def test_record_proxy_result(self):
        """record_proxy_result delegates to proxy rotator."""
        config = StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        config.proxy_entries = [ProxyEntry(url="p1:8080")]
        engine = StealthEngine(config)
        # Should not raise
        engine.record_proxy_result("p1:8080", success=True, latency_ms=100)

    def test_thread_safety(self):
        """Engine operations are thread-safe."""
        engine = StealthEngine()
        errors = []

        def worker():
            try:
                for _ in range(100):
                    engine.prepare_headers()
                    engine.get_jitter_delay()
                    engine.increment_request_counter()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert engine.request_count == 1000

    def test_paranoid_tor_proxy(self):
        """PARANOID level returns Tor proxy dict (without live Tor)."""
        config = StealthProfileConfig.from_level(StealthLevel.PARANOID)
        engine = StealthEngine(config)
        proxy = engine.get_proxy()
        assert proxy is not None
        assert "socks5h" in proxy["http"]

    def test_high_level_tls_stats(self):
        """HIGH level includes TLS profile info in stats."""
        config = StealthProfileConfig.from_level(StealthLevel.HIGH)
        engine = StealthEngine(config)
        stats = engine.get_stats()
        assert "tls_profiles" in stats
        assert len(stats["tls_profiles"]) >= 4
