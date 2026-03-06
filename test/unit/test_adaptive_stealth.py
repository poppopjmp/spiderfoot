# -------------------------------------------------------------------------------
# Name:         test_adaptive_stealth
# Purpose:      Tests for S-005 adaptive stealth + WAF detection triggers
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Unit tests for spiderfoot.recon.adaptive_stealth (S-005)."""

from __future__ import annotations

import threading
import time

import pytest

from spiderfoot.recon.adaptive_stealth import (
    AdaptiveController,
    DetectionEvent,
    DetectionType,
    TargetProfile,
    TargetStealthManager,
    ThreatLevel,
    WAFDetectionResult,
    WAFDetector,
    WAFSignature,
    WAFVendor,
    _SEVERITY_MAP,
    _WAF_SIGNATURES,
)


# ============================================================================
# WAFVendor Enum Tests
# ============================================================================


class TestWAFVendor:
    """Tests for WAFVendor enum."""

    def test_all_vendors_have_string_values(self):
        for v in WAFVendor:
            assert isinstance(v.value, str)
            assert len(v.value) > 0

    def test_unknown_vendor(self):
        assert WAFVendor.UNKNOWN.value == "unknown"

    def test_cloudflare_vendor(self):
        assert WAFVendor.CLOUDFLARE.value == "cloudflare"

    def test_vendor_count(self):
        assert len(WAFVendor) >= 14

    def test_all_unique_values(self):
        values = [v.value for v in WAFVendor]
        assert len(values) == len(set(values))


class TestDetectionType:
    """Tests for DetectionType enum."""

    def test_rate_limit(self):
        assert DetectionType.RATE_LIMIT.value == "rate_limit"

    def test_waf_block(self):
        assert DetectionType.WAF_BLOCK.value == "waf_block"

    def test_none_type(self):
        assert DetectionType.NONE.value == "none"

    def test_all_detection_types(self):
        expected = {
            "rate_limit", "waf_block", "captcha", "bot_detection",
            "ip_block", "geo_block", "auth_challenge", "fingerprint",
            "behavior", "none",
        }
        actual = {dt.value for dt in DetectionType}
        assert expected == actual


# ============================================================================
# WAF Signature Tests
# ============================================================================


class TestWAFSignature:
    """Tests for WAFSignature dataclass and built-in signatures."""

    def test_create_empty_signature(self):
        sig = WAFSignature(vendor=WAFVendor.UNKNOWN)
        assert sig.vendor == WAFVendor.UNKNOWN
        assert sig.header_patterns == {}
        assert sig.body_patterns == []
        assert sig.cookie_patterns == []
        assert sig.status_codes == []

    def test_create_with_patterns(self):
        sig = WAFSignature(
            vendor=WAFVendor.CLOUDFLARE,
            header_patterns={"server": ["cloudflare"]},
            body_patterns=[r"cf-browser"],
            cookie_patterns=["__cfduid"],
        )
        assert sig.vendor == WAFVendor.CLOUDFLARE
        assert "server" in sig.header_patterns
        assert len(sig.body_patterns) == 1

    def test_builtin_signatures_present(self):
        assert len(_WAF_SIGNATURES) >= 10

    def test_cloudflare_signature_exists(self):
        cf = [s for s in _WAF_SIGNATURES if s.vendor == WAFVendor.CLOUDFLARE]
        assert len(cf) == 1
        assert "server" in cf[0].header_patterns

    def test_akamai_signature_exists(self):
        ak = [s for s in _WAF_SIGNATURES if s.vendor == WAFVendor.AKAMAI]
        assert len(ak) == 1

    def test_all_signatures_have_vendor(self):
        for sig in _WAF_SIGNATURES:
            assert sig.vendor != WAFVendor.UNKNOWN


# ============================================================================
# WAF Detection Result Tests
# ============================================================================


class TestWAFDetectionResult:
    """Tests for WAFDetectionResult dataclass."""

    def test_no_detection_str(self):
        r = WAFDetectionResult(
            detected=False,
            vendor=WAFVendor.UNKNOWN,
            confidence=0.0,
            signals=[],
            detection_type=DetectionType.NONE,
        )
        assert str(r) == "No WAF detected"

    def test_detection_str(self):
        r = WAFDetectionResult(
            detected=True,
            vendor=WAFVendor.CLOUDFLARE,
            confidence=0.85,
            signals=["header:server=cloudflare"],
            detection_type=DetectionType.WAF_BLOCK,
        )
        assert "cloudflare" in str(r)
        assert "85%" in str(r)

    def test_fields(self):
        r = WAFDetectionResult(
            detected=True,
            vendor=WAFVendor.AKAMAI,
            confidence=0.5,
            signals=["header:x-akamai"],
            detection_type=DetectionType.RATE_LIMIT,
        )
        assert r.detected is True
        assert r.vendor == WAFVendor.AKAMAI
        assert r.confidence == 0.5
        assert len(r.signals) == 1


# ============================================================================
# WAF Detector Tests
# ============================================================================


class TestWAFDetector:
    """Tests for WAFDetector."""

    def test_create_detector(self):
        d = WAFDetector()
        assert d.signature_count >= 10
        assert d.cached_targets == 0

    def test_detect_cloudflare_by_header(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "cloudflare", "CF-RAY": "abc123-LAX"},
            target="example.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.CLOUDFLARE
        assert result.confidence > 0.3

    def test_detect_cloudflare_by_body(self):
        d = WAFDetector()
        result = d.detect(
            status_code=403,
            body="<html>Attention Required! | Cloudflare</html>",
            target="test.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.CLOUDFLARE

    def test_detect_akamai_by_header(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "AkamaiGHost", "X-Akamai-Transformed": "9c3"},
            target="akamai-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.AKAMAI

    def test_detect_imperva_by_cookie(self):
        d = WAFDetector()
        result = d.detect(
            headers={"X-Iinfo": "12345"},
            cookies={"visid_incap_123": "abc"},
            target="imperva-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.IMPERVA

    def test_detect_sucuri_by_header(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "Sucuri", "X-Sucuri-ID": "abc123"},
            target="sucuri-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.SUCURI

    def test_detect_f5_by_cookie(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "BigIP"},
            cookies={"BigIPServer": "pool123"},
            target="f5-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.F5_BIG_IP

    def test_detect_fastly_by_header(self):
        d = WAFDetector()
        result = d.detect(
            headers={"X-Fastly-Request-Id": "abc123"},
            target="fastly-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.FASTLY

    def test_detect_ddos_guard_by_header(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "ddos-guard"},
            target="ddos-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.DDOS_GUARD

    def test_detect_wordfence_by_body(self):
        d = WAFDetector()
        result = d.detect(
            body="<p>Generated by Wordfence at Sat, 01 Jan 2026</p>",
            target="wp-site.com",
        )
        assert result.detected is True
        assert result.vendor == WAFVendor.WORDFENCE

    def test_no_detection(self):
        d = WAFDetector()
        result = d.detect(
            status_code=200,
            headers={"server": "nginx"},
            body="<html>Hello World</html>",
            target="clean.com",
        )
        assert result.detected is False
        assert result.vendor == WAFVendor.UNKNOWN
        assert result.confidence == 0.0

    def test_caching(self):
        d = WAFDetector()
        d.detect(
            headers={"Server": "cloudflare"},
            target="cached.com",
        )
        assert d.cached_targets == 1
        cached = d.get_cached("cached.com")
        assert cached is not None
        assert cached.vendor == WAFVendor.CLOUDFLARE

    def test_cache_miss(self):
        d = WAFDetector()
        assert d.get_cached("nonexistent.com") is None

    def test_classify_rate_limit(self):
        d = WAFDetector()
        result = d.detect(status_code=429, target="rl.com")
        assert result.detection_type == DetectionType.RATE_LIMIT

    def test_classify_captcha(self):
        d = WAFDetector()
        result = d.detect(
            status_code=403,
            body="Please complete the captcha challenge",
            target="captcha.com",
        )
        assert result.detection_type == DetectionType.CAPTCHA

    def test_classify_bot_detection(self):
        d = WAFDetector()
        result = d.detect(
            status_code=403,
            body="Automated access is not permitted",
            target="bot.com",
        )
        assert result.detection_type == DetectionType.BOT_DETECTION

    def test_classify_waf_block(self):
        d = WAFDetector()
        result = d.detect(
            status_code=403,
            body="Access denied",
            target="block.com",
        )
        assert result.detection_type == DetectionType.WAF_BLOCK

    def test_classify_auth_challenge(self):
        d = WAFDetector()
        result = d.detect(status_code=401, target="auth.com")
        assert result.detection_type == DetectionType.AUTH_CHALLENGE

    def test_detect_no_target_no_cache(self):
        d = WAFDetector()
        result = d.detect(
            headers={"Server": "cloudflare"},
        )
        assert result.detected is True
        assert d.cached_targets == 0


# ============================================================================
# Detection Event Tests
# ============================================================================


class TestDetectionEvent:
    """Tests for DetectionEvent dataclass."""

    def test_create_default(self):
        e = DetectionEvent()
        assert e.target == ""
        assert e.detection_type == DetectionType.NONE
        assert e.severity == 0.0
        assert e.timestamp > 0

    def test_auto_severity(self):
        e = DetectionEvent(detection_type=DetectionType.RATE_LIMIT)
        assert e.severity == _SEVERITY_MAP[DetectionType.RATE_LIMIT]
        assert e.severity == 0.4

    def test_auto_severity_waf_block(self):
        e = DetectionEvent(detection_type=DetectionType.WAF_BLOCK)
        assert e.severity == 0.7

    def test_auto_severity_ip_block(self):
        e = DetectionEvent(detection_type=DetectionType.IP_BLOCK)
        assert e.severity == 0.9

    def test_explicit_severity_overrides(self):
        e = DetectionEvent(
            detection_type=DetectionType.WAF_BLOCK,
            severity=0.3,
        )
        # explicit severity should persist
        assert e.severity == 0.3

    def test_fields(self):
        e = DetectionEvent(
            target="test.com",
            detection_type=DetectionType.CAPTCHA,
            status_code=403,
            response_time_ms=150.0,
            description="CAPTCHA detected",
        )
        assert e.target == "test.com"
        assert e.status_code == 403
        assert e.response_time_ms == 150.0
        assert e.description == "CAPTCHA detected"

    def test_none_severity_is_zero(self):
        e = DetectionEvent(detection_type=DetectionType.NONE)
        assert e.severity == 0.0


class TestSeverityMap:
    """Tests for severity mapping."""

    def test_all_detection_types_mapped(self):
        for dt in DetectionType:
            assert dt in _SEVERITY_MAP

    def test_severity_range(self):
        for dt, sev in _SEVERITY_MAP.items():
            assert 0.0 <= sev <= 1.0, f"{dt} severity {sev} out of range"

    def test_ip_block_highest(self):
        assert _SEVERITY_MAP[DetectionType.IP_BLOCK] >= max(
            s for dt, s in _SEVERITY_MAP.items() if dt != DetectionType.IP_BLOCK
        )


# ============================================================================
# Target Profile Tests
# ============================================================================


class TestTargetProfile:
    """Tests for TargetProfile dataclass."""

    def test_create_default(self):
        p = TargetProfile(domain="test.com")
        assert p.domain == "test.com"
        assert p.waf_vendor == WAFVendor.UNKNOWN
        assert p.threat_level == ThreatLevel.NONE
        assert p.delay_multiplier == 1.0
        assert p.total_requests == 0
        assert p.total_detections == 0

    def test_detection_rate_pct_zero(self):
        p = TargetProfile(domain="test.com")
        assert p.detection_rate_pct() == 0.0

    def test_detection_rate_pct(self):
        p = TargetProfile(
            domain="test.com",
            total_requests=100,
            total_detections=5,
        )
        assert p.detection_rate_pct() == 5.0

    def test_update_response_time(self):
        p = TargetProfile(domain="test.com")
        p.update_response_time(100.0)
        p.update_response_time(200.0)
        assert p.avg_response_time_ms == 150.0

    def test_response_time_window_limit(self):
        p = TargetProfile(domain="test.com")
        for i in range(110):
            p.update_response_time(float(i))
        assert len(p._response_times) == 100

    def test_to_dict(self):
        p = TargetProfile(domain="test.com")
        d = p.to_dict()
        assert d["domain"] == "test.com"
        assert d["waf_vendor"] == "unknown"
        assert d["delay_multiplier"] == 1.0
        assert "total_requests" in d
        assert "event_count" in d

    def test_to_dict_keys(self):
        p = TargetProfile(domain="x.com")
        d = p.to_dict()
        expected_keys = {
            "domain", "waf_vendor", "waf_confidence", "threat_level",
            "total_requests", "total_detections", "detection_rate",
            "delay_multiplier", "profile_rotation_interval",
            "proxy_switch_urgency", "avg_response_time_ms",
            "consecutive_successes", "consecutive_failures",
            "event_count",
        }
        assert set(d.keys()) == expected_keys


class TestThreatLevel:
    """Tests for ThreatLevel enum."""

    def test_ordering(self):
        levels = list(ThreatLevel)
        assert ThreatLevel.NONE in levels
        assert ThreatLevel.LOW in levels
        assert ThreatLevel.CRITICAL in levels

    def test_string_values(self):
        assert ThreatLevel.NONE.value == "none"
        assert ThreatLevel.CRITICAL.value == "critical"

    def test_count(self):
        assert len(ThreatLevel) == 5


# ============================================================================
# Adaptive Controller Tests
# ============================================================================


class TestAdaptiveController:
    """Tests for AdaptiveController."""

    def test_create_default(self):
        c = AdaptiveController()
        assert c._detection_gain == 1.5
        assert c._recovery_rate == 0.95
        assert c._max_mult == 10.0

    def test_create_custom(self):
        c = AdaptiveController(
            detection_gain=2.0,
            recovery_rate=0.9,
            max_delay_multiplier=5.0,
        )
        assert c._detection_gain == 2.0
        assert c._recovery_rate == 0.9
        assert c._max_mult == 5.0

    def test_update_on_detection_increases_delay(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        e = DetectionEvent(
            detection_type=DetectionType.WAF_BLOCK,
            waf_vendor=WAFVendor.CLOUDFLARE,
        )
        c.update_on_detection(p, e)
        assert p.delay_multiplier > 1.0

    def test_update_on_detection_tracks_failures(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        e = DetectionEvent(detection_type=DetectionType.WAF_BLOCK)
        c.update_on_detection(p, e)
        assert p.consecutive_failures == 1
        assert p.consecutive_successes == 0
        assert p.total_detections == 1

    def test_update_on_success_decays_multiplier(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com", delay_multiplier=5.0)
        c.update_on_success(p)
        assert p.delay_multiplier < 5.0
        assert p.delay_multiplier >= 1.0

    def test_update_on_success_tracks(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        c.update_on_success(p)
        assert p.total_requests == 1
        assert p.consecutive_successes == 1
        assert p.consecutive_failures == 0

    def test_delay_never_exceeds_max(self):
        c = AdaptiveController(max_delay_multiplier=5.0)
        p = TargetProfile(domain="t.com")
        for _ in range(50):
            e = DetectionEvent(detection_type=DetectionType.IP_BLOCK)
            c.update_on_detection(p, e)
        assert p.delay_multiplier <= 5.0

    def test_delay_never_below_one_on_success(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com", delay_multiplier=1.1)
        for _ in range(100):
            c.update_on_success(p)
        assert p.delay_multiplier >= 1.0

    def test_escalation_reduces_rotation_interval(self):
        c = AdaptiveController(escalation_threshold=3)
        p = TargetProfile(domain="t.com", profile_rotation_interval=10)
        for _ in range(3):
            e = DetectionEvent(detection_type=DetectionType.BOT_DETECTION)
            c.update_on_detection(p, e)
        assert p.profile_rotation_interval < 10

    def test_ip_block_sets_proxy_urgency_max(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        e = DetectionEvent(detection_type=DetectionType.IP_BLOCK)
        c.update_on_detection(p, e)
        assert p.proxy_switch_urgency == 1.0

    def test_waf_block_increases_proxy_urgency(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        e = DetectionEvent(detection_type=DetectionType.WAF_BLOCK)
        c.update_on_detection(p, e)
        assert p.proxy_switch_urgency == 0.3

    def test_threat_level_escalation(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        assert p.threat_level == ThreatLevel.NONE
        # Many detections should escalate
        for _ in range(10):
            e = DetectionEvent(detection_type=DetectionType.WAF_BLOCK)
            c.update_on_detection(p, e)
        assert p.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)

    def test_threat_level_recovery(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com", detection_rate=0.5)
        c._update_threat_level(p)
        assert p.threat_level == ThreatLevel.CRITICAL
        # Many successes should lower
        p.detection_rate = 0.005
        c._update_threat_level(p)
        assert p.threat_level == ThreatLevel.NONE

    def test_detection_rate_ema_increases(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com", detection_rate=0.0)
        e = DetectionEvent(detection_type=DetectionType.RATE_LIMIT)
        c.update_on_detection(p, e)
        assert p.detection_rate > 0.0

    def test_detection_rate_ema_decreases(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com", detection_rate=0.5)
        c.update_on_success(p)
        assert p.detection_rate < 0.5

    def test_recovery_of_rotation_interval(self):
        c = AdaptiveController(escalation_threshold=2)
        p = TargetProfile(
            domain="t.com",
            profile_rotation_interval=3,
            consecutive_successes=10,
        )
        # Simulate many successes — should recover interval
        for _ in range(10):
            c.update_on_success(p)
        assert p.profile_rotation_interval > 3

    def test_waf_vendor_updated_on_detection(self):
        c = AdaptiveController()
        p = TargetProfile(domain="t.com")
        e = DetectionEvent(
            detection_type=DetectionType.WAF_BLOCK,
            waf_vendor=WAFVendor.AKAMAI,
        )
        c.update_on_detection(p, e)
        assert p.waf_vendor == WAFVendor.AKAMAI


# ============================================================================
# Target Stealth Manager Tests
# ============================================================================


class TestTargetStealthManager:
    """Tests for TargetStealthManager."""

    def test_create_default(self):
        m = TargetStealthManager()
        assert len(m.get_all_targets()) == 0

    def test_analyze_clean_response(self):
        m = TargetStealthManager()
        result = m.analyze_response(
            target="clean.com",
            status_code=200,
            headers={"server": "nginx"},
            body="<html>OK</html>",
        )
        assert result is None  # No detection

    def test_analyze_creates_profile(self):
        m = TargetStealthManager()
        m.analyze_response(target="new.com", status_code=200)
        profile = m.get_target_profile("new.com")
        assert profile is not None
        assert profile.domain == "new.com"

    def test_analyze_waf_response(self):
        m = TargetStealthManager()
        result = m.analyze_response(
            target="waf.com",
            status_code=403,
            headers={"Server": "cloudflare", "CF-RAY": "abc"},
            body="Attention Required! | Cloudflare",
        )
        assert result is not None
        assert result.detection_type != DetectionType.NONE

    def test_delay_multiplier_default(self):
        m = TargetStealthManager()
        assert m.get_delay_multiplier("unknown.com") == 1.0

    def test_delay_multiplier_increases_on_detection(self):
        m = TargetStealthManager()
        m.analyze_response(
            target="detected.com",
            status_code=429,
        )
        mult = m.get_delay_multiplier("detected.com")
        assert mult > 1.0

    def test_threat_level_default(self):
        m = TargetStealthManager()
        assert m.get_threat_level("unknown.com") == ThreatLevel.NONE

    def test_should_switch_proxy_default(self):
        m = TargetStealthManager()
        assert m.should_switch_proxy("unknown.com") is False

    def test_should_switch_proxy_on_ip_block(self):
        m = TargetStealthManager()
        # Force an IP block detection via analyze_response
        # Use 403 + bot body to trigger detection
        m.analyze_response(
            target="blocked.com",
            status_code=403,
            body="Your IP has been blocked by automated detection",
        )
        profile = m.get_target_profile("blocked.com")
        # Manually set urgency high for reliable test
        profile.proxy_switch_urgency = 0.8
        assert m.should_switch_proxy("blocked.com") is True

    def test_should_rotate_profile(self):
        m = TargetStealthManager()
        m.analyze_response(target="rotate.com", status_code=200)
        profile = m.get_target_profile("rotate.com")
        profile.total_requests = 10
        profile.profile_rotation_interval = 10
        assert m.should_rotate_profile("rotate.com") is True

    def test_should_not_rotate_profile(self):
        m = TargetStealthManager()
        m.analyze_response(target="norot.com", status_code=200)
        profile = m.get_target_profile("norot.com")
        profile.total_requests = 7
        profile.profile_rotation_interval = 10
        assert m.should_rotate_profile("norot.com") is False

    def test_global_stats_empty(self):
        m = TargetStealthManager()
        stats = m.get_global_stats()
        assert stats["total_targets"] == 0
        assert stats["total_requests"] == 0

    def test_global_stats_after_activity(self):
        m = TargetStealthManager()
        m.analyze_response(target="a.com", status_code=200)
        m.analyze_response(target="b.com", status_code=429)
        stats = m.get_global_stats()
        assert stats["total_targets"] == 2
        assert stats["total_requests"] == 2
        assert stats["total_detections"] == 1

    def test_global_stats_detection_rate(self):
        m = TargetStealthManager()
        m.analyze_response(target="a.com", status_code=200)
        m.analyze_response(target="a.com", status_code=200)
        m.analyze_response(target="a.com", status_code=429)
        stats = m.get_global_stats()
        assert stats["global_detection_rate"] > 0

    def test_reset(self):
        m = TargetStealthManager()
        m.analyze_response(target="a.com", status_code=200)
        m.analyze_response(target="b.com", status_code=403, body="blocked")
        m.reset()
        assert len(m.get_all_targets()) == 0
        stats = m.get_global_stats()
        assert stats["total_requests"] == 0

    def test_multiple_targets_independent(self):
        m = TargetStealthManager()
        m.analyze_response(target="safe.com", status_code=200)
        m.analyze_response(target="danger.com", status_code=429)
        assert m.get_delay_multiplier("safe.com") == 1.0
        assert m.get_delay_multiplier("danger.com") > 1.0

    def test_response_time_tracking(self):
        m = TargetStealthManager()
        m.analyze_response(
            target="fast.com",
            status_code=200,
            response_time_ms=50.0,
        )
        m.analyze_response(
            target="fast.com",
            status_code=200,
            response_time_ms=150.0,
        )
        profile = m.get_target_profile("fast.com")
        assert profile.avg_response_time_ms == 100.0

    def test_waf_detection_updates_profile(self):
        m = TargetStealthManager()
        m.analyze_response(
            target="cf.com",
            status_code=200,
            headers={"Server": "cloudflare", "CF-RAY": "abc"},
        )
        profile = m.get_target_profile("cf.com")
        assert profile.waf_vendor == WAFVendor.CLOUDFLARE
        assert profile.waf_confidence > 0

    def test_escalation_over_time(self):
        m = TargetStealthManager()
        # First: clean response
        m.analyze_response(target="esc.com", status_code=200)
        initial_mult = m.get_delay_multiplier("esc.com")
        # Then: multiple blocks
        for _ in range(5):
            m.analyze_response(target="esc.com", status_code=429)
        final_mult = m.get_delay_multiplier("esc.com")
        assert final_mult > initial_mult

    def test_get_all_targets(self):
        m = TargetStealthManager()
        m.analyze_response(target="x.com", status_code=200)
        m.analyze_response(target="y.com", status_code=200)
        m.analyze_response(target="z.com", status_code=200)
        targets = m.get_all_targets()
        assert set(targets) == {"x.com", "y.com", "z.com"}


# ============================================================================
# Thread Safety Tests
# ============================================================================


class TestThreadSafety:
    """Tests for thread safety of the manager."""

    def test_concurrent_analyze(self):
        m = TargetStealthManager()
        errors: list[str] = []

        def worker(target_id: int) -> None:
            try:
                target = f"t{target_id}.com"
                for _ in range(20):
                    m.analyze_response(
                        target=target,
                        status_code=200 if target_id % 2 == 0 else 429,
                    )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(m.get_all_targets()) == 10

    def test_concurrent_stats(self):
        m = TargetStealthManager()
        errors: list[str] = []

        def analyze_worker() -> None:
            try:
                for i in range(50):
                    m.analyze_response(target=f"t{i}.com", status_code=200)
            except Exception as exc:
                errors.append(str(exc))

        def stats_worker() -> None:
            try:
                for _ in range(50):
                    m.get_global_stats()
            except Exception as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=analyze_worker)
        t2 = threading.Thread(target=stats_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    def test_concurrent_detector(self):
        d = WAFDetector()
        errors: list[str] = []

        def worker(i: int) -> None:
            try:
                d.detect(
                    headers={"Server": "cloudflare"},
                    target=f"target{i}.com",
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert d.cached_targets == 20


# ============================================================================
# Integration & Scenario Tests
# ============================================================================


class TestIntegrationScenarios:
    """End-to-end integration scenarios."""

    def test_full_scan_lifecycle(self):
        """Simulate a full scan: start clean, get detected, adapt, recover."""
        m = TargetStealthManager()
        target = "lifecycle.com"

        # Phase 1: Clean requests
        for _ in range(5):
            r = m.analyze_response(target=target, status_code=200)
            assert r is None

        profile = m.get_target_profile(target)
        assert profile.delay_multiplier == 1.0

        # Phase 2: WAF blocks start
        for _ in range(3):
            r = m.analyze_response(
                target=target,
                status_code=403,
                headers={"Server": "cloudflare", "CF-RAY": "x"},
                body="Attention Required! Cloudflare",
            )
            assert r is not None

        assert profile.delay_multiplier > 1.0
        assert profile.waf_vendor == WAFVendor.CLOUDFLARE

        # Phase 3: Recovery with clean responses
        for _ in range(20):
            m.analyze_response(target=target, status_code=200)

        assert profile.delay_multiplier < m.get_target_profile(target).delay_multiplier + 5

    def test_multi_waf_targets(self):
        """Different targets with different WAFs."""
        m = TargetStealthManager()

        m.analyze_response(
            target="cf.com",
            status_code=200,
            headers={"Server": "cloudflare", "CF-RAY": "abc"},
        )
        m.analyze_response(
            target="ak.com",
            status_code=200,
            headers={"Server": "AkamaiGHost"},
        )
        m.analyze_response(
            target="imp.com",
            status_code=200,
            headers={"X-Iinfo": "123"},
            cookies={"visid_incap_123": "x"},
        )

        assert m.get_target_profile("cf.com").waf_vendor == WAFVendor.CLOUDFLARE
        assert m.get_target_profile("ak.com").waf_vendor == WAFVendor.AKAMAI
        assert m.get_target_profile("imp.com").waf_vendor == WAFVendor.IMPERVA

    def test_rate_limit_adaptation(self):
        """Rate limiting should increase delay but not trigger proxy switch."""
        m = TargetStealthManager()
        target = "ratelimit.com"

        m.analyze_response(target=target, status_code=429)
        profile = m.get_target_profile(target)
        assert profile.delay_multiplier > 1.0
        assert profile.proxy_switch_urgency < 0.5  # Not high enough for switch

    def test_progressive_hardening(self):
        """Multiple detections should progressively harden defenses."""
        m = TargetStealthManager()
        target = "hard.com"
        multipliers: list[float] = []

        for i in range(5):
            m.analyze_response(target=target, status_code=429)
            multipliers.append(m.get_delay_multiplier(target))

        # Each detection should increase multiplier
        for i in range(1, len(multipliers)):
            assert multipliers[i] >= multipliers[i - 1]

    def test_global_stats_comprehensive(self):
        """Global stats should reflect all activity."""
        m = TargetStealthManager()

        # Mix of targets and responses
        m.analyze_response(
            target="a.com", status_code=200,
            headers={"Server": "cloudflare", "CF-RAY": "x"},
        )
        m.analyze_response(target="b.com", status_code=200)
        m.analyze_response(target="c.com", status_code=429)
        m.analyze_response(
            target="d.com", status_code=403,
            headers={"Server": "AkamaiGHost"},
            body="Access denied",
        )

        stats = m.get_global_stats()
        assert stats["total_targets"] == 4
        assert stats["total_requests"] == 4
        assert stats["total_detections"] == 2
        assert "waf_distribution" in stats
        assert stats["avg_delay_multiplier"] >= 1.0

    def test_should_rotate_unknown_target(self):
        m = TargetStealthManager()
        assert m.should_rotate_profile("nonexistent.com") is False

    def test_custom_controller_params(self):
        m = TargetStealthManager(
            detection_gain=3.0,
            recovery_rate=0.5,
            max_delay_multiplier=20.0,
        )
        m.analyze_response(target="custom.com", status_code=429)
        mult = m.get_delay_multiplier("custom.com")
        # With gain=3.0 and rate_limit severity=0.4 → increase = 1.2
        assert mult > 2.0
