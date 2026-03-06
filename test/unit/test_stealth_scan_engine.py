# -------------------------------------------------------------------------------
# Name:         test_stealth_scan_engine
# Purpose:      Tests for S-006 stealth scan engine integration
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Unit tests for spiderfoot.recon.stealth_scan_engine (S-006)."""

from __future__ import annotations

import threading

import pytest

from spiderfoot.recon.stealth_scan_engine import (
    ModuleRiskLevel,
    ModuleStealthProfile,
    ModuleStealthRegistry,
    StealthConfig,
    StealthDashboardCollector,
    StealthDashboardData,
    StealthLevel,
    StealthScanBridge,
    _STEALTH_LEVEL_DEFAULTS,
    get_stealth_defaults,
)


# ============================================================================
# StealthLevel Tests
# ============================================================================


class TestStealthLevel:
    def test_all_levels_present(self):
        assert len(StealthLevel) == 5

    def test_none_value(self):
        assert StealthLevel.NONE.value == "none"

    def test_maximum_value(self):
        assert StealthLevel.MAXIMUM.value == "maximum"

    def test_from_string(self):
        assert StealthLevel("low") == StealthLevel.LOW
        assert StealthLevel("high") == StealthLevel.HIGH

    def test_all_string_values(self):
        expected = {"none", "low", "medium", "high", "maximum"}
        assert {l.value for l in StealthLevel} == expected


class TestStealthDefaults:
    def test_all_levels_have_defaults(self):
        for level in StealthLevel:
            defaults = get_stealth_defaults(level)
            assert isinstance(defaults, dict)
            assert len(defaults) > 0

    def test_none_disables_everything(self):
        defaults = get_stealth_defaults(StealthLevel.NONE)
        assert defaults["ua_rotation"] is False
        assert defaults["proxy_rotation"] is False
        assert defaults["adaptive_feedback"] is False

    def test_maximum_enables_everything(self):
        defaults = get_stealth_defaults(StealthLevel.MAXIMUM)
        assert defaults["ua_rotation"] is True
        assert defaults["proxy_rotation"] is True
        assert defaults["adaptive_feedback"] is True
        assert defaults["waf_detection"] is True

    def test_delay_increases_with_level(self):
        lvls = ["none", "low", "medium", "high", "maximum"]
        delays = [get_stealth_defaults(l)["request_delay_ms"] for l in lvls]
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]

    def test_accepts_string(self):
        defaults = get_stealth_defaults("medium")
        assert defaults["tls_fingerprint_rotation"] is True

    def test_returns_copy(self):
        d1 = get_stealth_defaults(StealthLevel.HIGH)
        d2 = get_stealth_defaults(StealthLevel.HIGH)
        d1["ua_rotation"] = "modified"
        assert d2["ua_rotation"] is True

    def test_unknown_level_returns_none_defaults(self):
        defaults = get_stealth_defaults("nonexistent")
        assert defaults["ua_rotation"] is False


# ============================================================================
# StealthConfig Tests
# ============================================================================


class TestStealthConfig:
    def test_default_config(self):
        c = StealthConfig()
        assert c.level == StealthLevel.NONE
        assert c.ua_rotation is False
        assert c.is_active() is False

    def test_from_level(self):
        c = StealthConfig.from_level(StealthLevel.HIGH)
        assert c.level == StealthLevel.HIGH
        assert c.ua_rotation is True
        assert c.proxy_rotation is True
        assert c.is_active() is True

    def test_from_level_string(self):
        c = StealthConfig.from_level("medium")
        assert c.level == StealthLevel.MEDIUM
        assert c.tls_fingerprint_rotation is True

    def test_from_dict(self):
        data = {
            "level": "low",
            "ua_rotation": True,
            "request_delay_ms": 500,
        }
        c = StealthConfig.from_dict(data)
        assert c.level == StealthLevel.LOW
        assert c.ua_rotation is True
        assert c.request_delay_ms == 500

    def test_from_dict_invalid_level(self):
        data = {"level": "unknown_level"}
        c = StealthConfig.from_dict(data)
        assert c.level == StealthLevel.NONE

    def test_to_dict(self):
        c = StealthConfig.from_level(StealthLevel.MEDIUM)
        d = c.to_dict()
        assert d["level"] == "medium"
        assert d["ua_rotation"] is True
        assert "tls_fingerprint_rotation" in d

    def test_to_dict_roundtrip(self):
        c1 = StealthConfig.from_level(StealthLevel.HIGH)
        d = c1.to_dict()
        c2 = StealthConfig.from_dict(d)
        assert c1.level == c2.level
        assert c1.ua_rotation == c2.ua_rotation
        assert c1.proxy_rotation == c2.proxy_rotation

    def test_is_active(self):
        assert StealthConfig(level=StealthLevel.NONE).is_active() is False
        assert StealthConfig(level=StealthLevel.LOW).is_active() is True
        assert StealthConfig(level=StealthLevel.MAXIMUM).is_active() is True

    def test_all_fields_in_to_dict(self):
        c = StealthConfig()
        d = c.to_dict()
        expected_keys = {
            "level", "ua_rotation", "header_randomization", "request_jitter",
            "tls_fingerprint_rotation", "fingerprint_grease",
            "profile_rotation_interval", "timing_profile",
            "session_simulation", "max_requests_per_second",
            "request_delay_ms", "adaptive_feedback", "waf_detection",
            "proxy_rotation", "domain_throttle",
        }
        assert set(d.keys()) == expected_keys


# ============================================================================
# ModuleRiskLevel Tests
# ============================================================================


class TestModuleRiskLevel:
    def test_all_levels(self):
        assert len(ModuleRiskLevel) == 5

    def test_values(self):
        expected = {"passive", "low", "medium", "high", "aggressive"}
        assert {r.value for r in ModuleRiskLevel} == expected


# ============================================================================
# ModuleStealthProfile Tests
# ============================================================================


class TestModuleStealthProfile:
    def test_create_default(self):
        p = ModuleStealthProfile(module_name="test_mod")
        assert p.module_name == "test_mod"
        assert p.risk_level == ModuleRiskLevel.MEDIUM
        assert p.makes_http_requests is True

    def test_create_custom(self):
        p = ModuleStealthProfile(
            module_name="sfp_spider",
            risk_level=ModuleRiskLevel.HIGH,
            typical_requests_per_target=100,
            min_stealth_level=StealthLevel.MEDIUM,
        )
        assert p.risk_level == ModuleRiskLevel.HIGH
        assert p.typical_requests_per_target == 100

    def test_to_dict(self):
        p = ModuleStealthProfile(module_name="test_mod")
        d = p.to_dict()
        assert d["module_name"] == "test_mod"
        assert d["risk_level"] == "medium"
        assert "max_concurrent_requests" in d

    def test_to_dict_keys(self):
        p = ModuleStealthProfile(module_name="x")
        d = p.to_dict()
        expected = {
            "module_name", "risk_level", "typical_requests_per_target",
            "makes_http_requests", "makes_dns_requests",
            "uses_third_party_apis", "min_stealth_level",
            "recommended_delay_ms", "max_concurrent_requests",
            "supports_proxy", "category", "tags",
        }
        assert set(d.keys()) == expected


# ============================================================================
# ModuleStealthRegistry Tests
# ============================================================================


class TestModuleStealthRegistry:
    def test_create_with_defaults(self):
        r = ModuleStealthRegistry()
        assert r.module_count >= 10

    def test_register_custom(self):
        r = ModuleStealthRegistry()
        p = ModuleStealthProfile("custom_mod", ModuleRiskLevel.HIGH)
        r.register(p)
        assert r.get("custom_mod") is not None

    def test_get_existing(self):
        r = ModuleStealthRegistry()
        p = r.get("sfp_spider")
        assert p is not None
        assert p.risk_level == ModuleRiskLevel.MEDIUM

    def test_get_missing(self):
        r = ModuleStealthRegistry()
        assert r.get("nonexistent") is None

    def test_get_or_default(self):
        r = ModuleStealthRegistry()
        p = r.get_or_default("unknown_module")
        assert p.module_name == "unknown_module"
        assert p.risk_level == ModuleRiskLevel.MEDIUM

    def test_get_by_risk_level(self):
        r = ModuleStealthRegistry()
        high_risk = r.get_by_risk_level(ModuleRiskLevel.HIGH)
        assert len(high_risk) >= 1
        for p in high_risk:
            assert p.risk_level == ModuleRiskLevel.HIGH

    def test_get_by_category(self):
        r = ModuleStealthRegistry()
        web = r.get_by_category("web")
        assert len(web) >= 1
        for p in web:
            assert p.category == "web"

    def test_get_high_risk_modules(self):
        r = ModuleStealthRegistry()
        high_risk = r.get_high_risk_modules()
        assert isinstance(high_risk, list)
        assert "sfp_portscan_tcp" in high_risk

    def test_get_stealth_compatible(self):
        r = ModuleStealthRegistry()
        # LOW level should include PASSIVE and LOW-min modules
        compatible = r.get_stealth_compatible(StealthLevel.LOW)
        assert len(compatible) >= 5

    def test_stealth_compatible_maximum_includes_all(self):
        r = ModuleStealthRegistry()
        all_compat = r.get_stealth_compatible(StealthLevel.MAXIMUM)
        assert len(all_compat) == r.module_count

    def test_all_profiles(self):
        r = ModuleStealthRegistry()
        profiles = r.all_profiles()
        assert len(profiles) == r.module_count

    def test_to_dict(self):
        r = ModuleStealthRegistry()
        d = r.to_dict()
        assert isinstance(d, dict)
        assert "sfp_spider" in d


# ============================================================================
# StealthScanBridge Tests
# ============================================================================


class TestStealthScanBridge:
    def test_create_default(self):
        b = StealthScanBridge()
        assert b.registry.module_count >= 10

    def test_apply_stealth_none(self):
        b = StealthScanBridge()
        config = {"_maxthreads": 10}
        stealth = StealthConfig(level=StealthLevel.NONE)
        result = b.apply_stealth(config, stealth)
        assert result["_maxthreads"] == 10
        assert result["_stealth"]["level"] == "none"

    def test_apply_stealth_high(self):
        b = StealthScanBridge()
        config = {"_maxthreads": 10, "_delay": 0}
        stealth = StealthConfig.from_level(StealthLevel.HIGH)
        result = b.apply_stealth(config, stealth)
        # Threads should be halved for HIGH
        assert result["_maxthreads"] == 5
        assert result["_stealth_ua_rotation"] is True
        assert result["_stealth_proxy_rotation"] is True

    def test_apply_stealth_maximum(self):
        b = StealthScanBridge()
        config = {"_maxthreads": 8}
        stealth = StealthConfig.from_level(StealthLevel.MAXIMUM)
        result = b.apply_stealth(config, stealth)
        assert result["_maxthreads"] == 4
        assert result["_stealth_adaptive"] is True
        assert result["_stealth_waf_detect"] is True

    def test_apply_stealth_preserves_original(self):
        b = StealthScanBridge()
        config = {"_maxthreads": 10, "custom_key": "value"}
        stealth = StealthConfig.from_level(StealthLevel.LOW)
        result = b.apply_stealth(config, stealth)
        assert result["custom_key"] == "value"
        # Original not modified
        assert config.get("_stealth_ua_rotation") is None

    def test_apply_stealth_delay_respects_max(self):
        b = StealthScanBridge()
        config = {"_delay": 5000}  # Already high delay
        stealth = StealthConfig.from_level(StealthLevel.LOW)
        result = b.apply_stealth(config, stealth)
        assert result["_delay"] >= 5000  # Should not lower existing delay

    def test_apply_module_stealth(self):
        b = StealthScanBridge()
        config = {}
        modules = ["sfp_spider", "sfp_portscan_tcp", "sfp_whois"]
        stealth = StealthConfig.from_level(StealthLevel.MEDIUM)
        result = b.apply_module_stealth(config, modules, stealth)
        assert "_module_stealth" in result
        assert "sfp_spider" in result["_module_stealth"]
        assert "sfp_portscan_tcp" in result["_module_stealth"]

    def test_module_stealth_risk_multiplier(self):
        b = StealthScanBridge()
        config = {}
        # Use two modules with the SAME recommended_delay_ms to isolate risk multiplier
        r = b.registry
        r.register(ModuleStealthProfile("test_low", ModuleRiskLevel.LOW, recommended_delay_ms=100))
        r.register(ModuleStealthProfile("test_high", ModuleRiskLevel.HIGH, recommended_delay_ms=100))
        modules = ["test_low", "test_high"]
        stealth = StealthConfig.from_level(StealthLevel.MEDIUM)
        result = b.apply_module_stealth(config, modules, stealth)
        ms = result["_module_stealth"]
        # HIGH risk multiplier (2.0) > LOW risk multiplier (0.8)
        assert ms["test_high"]["delay_ms"] > ms["test_low"]["delay_ms"]

    def test_module_stealth_inactive_config(self):
        b = StealthScanBridge()
        config = {}
        modules = ["sfp_spider"]
        stealth = StealthConfig(level=StealthLevel.NONE)
        result = b.apply_module_stealth(config, modules, stealth)
        # No delay when stealth inactive
        assert "delay_ms" not in result["_module_stealth"]["sfp_spider"]

    def test_module_stealth_high_risk_concurrency(self):
        b = StealthScanBridge()
        config = {}
        modules = ["sfp_portscan_tcp"]
        stealth = StealthConfig.from_level(StealthLevel.HIGH)
        result = b.apply_module_stealth(config, modules, stealth)
        assert result["_module_stealth"]["sfp_portscan_tcp"]["max_concurrent"] <= 2

    def test_get_module_warnings_clean(self):
        b = StealthScanBridge()
        stealth = StealthConfig.from_level(StealthLevel.MAXIMUM)
        warnings = b.get_module_warnings(["sfp_spider"], stealth)
        # MAXIMUM includes everything, no warnings about level
        level_warnings = [w for w in warnings if w["level"] == "warning"]
        assert len(level_warnings) == 0

    def test_get_module_warnings_high_risk_max_stealth(self):
        b = StealthScanBridge()
        stealth = StealthConfig.from_level(StealthLevel.MAXIMUM)
        warnings = b.get_module_warnings(["sfp_portscan_tcp"], stealth)
        info_warnings = [w for w in warnings if w["level"] == "info"]
        assert len(info_warnings) >= 1

    def test_get_module_warnings_low_stealth_high_module(self):
        b = StealthScanBridge()
        stealth = StealthConfig.from_level(StealthLevel.NONE)
        warnings = b.get_module_warnings(["sfp_spider"], stealth)
        # sfp_spider recommends MEDIUM+ stealth
        warn = [w for w in warnings if w["level"] == "warning"]
        assert len(warn) >= 1

    def test_get_module_warnings_unknown_module(self):
        b = StealthScanBridge()
        stealth = StealthConfig.from_level(StealthLevel.HIGH)
        warnings = b.get_module_warnings(["nonexistent_module"], stealth)
        # Unknown modules have no profile, no warnings
        assert len(warnings) == 0

    def test_registry_access(self):
        r = ModuleStealthRegistry()
        b = StealthScanBridge(registry=r)
        assert b.registry is r


# ============================================================================
# StealthDashboardData Tests
# ============================================================================


class TestStealthDashboardData:
    def test_create_default(self):
        d = StealthDashboardData()
        assert d.total_requests == 0
        assert d.active_stealth_level == "none"

    def test_to_dict(self):
        d = StealthDashboardData(
            active_stealth_level="high",
            total_requests=100,
            total_detections=5,
            detection_rate=5 / 100,
        )
        out = d.to_dict()
        assert out["active_stealth_level"] == "high"
        assert out["total_requests"] == 100
        assert out["detection_rate"] == 0.05

    def test_to_dict_keys(self):
        d = StealthDashboardData()
        out = d.to_dict()
        expected = {
            "active_stealth_level", "total_requests", "total_detections",
            "detection_rate", "target_count", "targets", "waf_distribution",
            "avg_delay_ms", "avg_response_time_ms", "module_risk_distribution",
            "active_features", "collected_at",
        }
        assert set(out.keys()) == expected


# ============================================================================
# StealthDashboardCollector Tests
# ============================================================================


class TestStealthDashboardCollector:
    def test_create_default(self):
        c = StealthDashboardCollector()
        data = c.collect()
        assert data.total_requests == 0

    def test_record_request(self):
        c = StealthDashboardCollector()
        c.record_request("test.com", response_time_ms=100.0)
        data = c.collect()
        assert data.total_requests == 1
        assert data.total_detections == 0

    def test_record_detection(self):
        c = StealthDashboardCollector()
        c.record_request("test.com", detected=True, waf_vendor="cloudflare")
        data = c.collect()
        assert data.total_detections == 1
        assert data.waf_distribution.get("cloudflare") == 1

    def test_detection_rate(self):
        c = StealthDashboardCollector()
        for _ in range(8):
            c.record_request("t.com")
        for _ in range(2):
            c.record_request("t.com", detected=True)
        data = c.collect()
        assert data.detection_rate == pytest.approx(0.2)

    def test_avg_response_time(self):
        c = StealthDashboardCollector()
        c.record_request("t.com", response_time_ms=100.0)
        c.record_request("t.com", response_time_ms=200.0)
        data = c.collect()
        assert data.avg_response_time_ms == pytest.approx(150.0)

    def test_active_features_none(self):
        c = StealthDashboardCollector(StealthConfig(level=StealthLevel.NONE))
        data = c.collect()
        assert data.active_features == []

    def test_active_features_high(self):
        c = StealthDashboardCollector(StealthConfig.from_level(StealthLevel.HIGH))
        data = c.collect()
        assert "UA Rotation" in data.active_features
        assert "Proxy Rotation" in data.active_features
        assert "WAF Detection" in data.active_features

    def test_target_tracking(self):
        c = StealthDashboardCollector()
        c.record_request("a.com")
        c.record_request("b.com")
        c.record_request("a.com")
        data = c.collect()
        assert len(data.targets) == 2
        assert data.targets["a.com"]["requests"] == 2

    def test_module_risk_distribution(self):
        c = StealthDashboardCollector()
        data = c.collect()
        assert "medium" in data.module_risk_distribution

    def test_update_config(self):
        c = StealthDashboardCollector()
        data1 = c.collect()
        assert data1.active_stealth_level == "none"

        c.update_config(StealthConfig.from_level(StealthLevel.HIGH))
        data2 = c.collect()
        assert data2.active_stealth_level == "high"

    def test_reset(self):
        c = StealthDashboardCollector()
        c.record_request("t.com", detected=True)
        c.reset()
        data = c.collect()
        assert data.total_requests == 0
        assert data.total_detections == 0

    def test_response_time_window(self):
        c = StealthDashboardCollector()
        for i in range(1100):
            c.record_request("t.com", response_time_ms=float(i))
        data = c.collect()
        # Should be capped at 1000 entries
        assert data.avg_response_time_ms > 0


# ============================================================================
# Thread Safety Tests
# ============================================================================


class TestThreadSafety:
    def test_concurrent_recording(self):
        c = StealthDashboardCollector()
        errors: list[str] = []

        def worker(tid: int) -> None:
            try:
                for _ in range(100):
                    c.record_request(
                        f"t{tid}.com",
                        response_time_ms=50.0,
                        detected=tid % 3 == 0,
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        data = c.collect()
        assert data.total_requests == 1000

    def test_concurrent_registry(self):
        r = ModuleStealthRegistry()
        errors: list[str] = []

        def worker(tid: int) -> None:
            try:
                r.register(ModuleStealthProfile(
                    module_name=f"mod_{tid}",
                    risk_level=ModuleRiskLevel.MEDIUM,
                ))
                r.get(f"mod_{tid}")
                r.all_profiles()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_collect(self):
        c = StealthDashboardCollector(StealthConfig.from_level(StealthLevel.MEDIUM))
        errors: list[str] = []

        def record_worker() -> None:
            try:
                for _ in range(50):
                    c.record_request("t.com", response_time_ms=10.0)
            except Exception as e:
                errors.append(str(e))

        def collect_worker() -> None:
            try:
                for _ in range(50):
                    c.collect()
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=record_worker)
        t2 = threading.Thread(target=collect_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    def test_full_pipeline(self):
        """Test complete pipeline: config → bridge → module stealth → dashboard."""
        # 1. Create stealth config
        config = StealthConfig.from_level(StealthLevel.MEDIUM)
        assert config.is_active()

        # 2. Create bridge and apply to scan config
        bridge = StealthScanBridge()
        scan_config = {"_maxthreads": 10, "_delay": 0}
        result = bridge.apply_stealth(scan_config, config)
        assert result["_stealth"]["level"] == "medium"

        # 3. Apply module stealth
        modules = ["sfp_spider", "sfp_whois", "sfp_portscan_tcp"]
        result = bridge.apply_module_stealth(result, modules, config)
        assert "_module_stealth" in result

        # 4. Get warnings
        warnings = bridge.get_module_warnings(modules, config)
        # portscan should warn about medium stealth being low
        assert isinstance(warnings, list)

        # 5. Dashboard
        collector = StealthDashboardCollector(config, bridge.registry)
        collector.record_request("example.com", response_time_ms=120.0)
        data = collector.collect()
        assert data.active_stealth_level == "medium"
        assert data.total_requests == 1

    def test_level_upgrade_flow(self):
        """Simulate upgrading stealth level mid-scan."""
        collector = StealthDashboardCollector(
            StealthConfig.from_level(StealthLevel.LOW)
        )
        collector.record_request("t.com")
        data = collector.collect()
        assert data.active_stealth_level == "low"

        # Upgrade to HIGH
        collector.update_config(StealthConfig.from_level(StealthLevel.HIGH))
        data = collector.collect()
        assert data.active_stealth_level == "high"
        assert "Session Simulation" in data.active_features

    def test_multi_target_dashboard(self):
        """Multiple targets with different WAFs."""
        collector = StealthDashboardCollector(
            StealthConfig.from_level(StealthLevel.MEDIUM)
        )
        collector.record_request("a.com", detected=True, waf_vendor="cloudflare")
        collector.record_request("b.com", detected=True, waf_vendor="akamai")
        collector.record_request("c.com")

        data = collector.collect()
        assert data.total_requests == 3
        assert data.total_detections == 2
        assert data.waf_distribution["cloudflare"] == 1
        assert data.waf_distribution["akamai"] == 1

    def test_registry_to_dashboard(self):
        """Registry modules appear in dashboard risk distribution."""
        registry = ModuleStealthRegistry()
        collector = StealthDashboardCollector(
            StealthConfig.from_level(StealthLevel.NONE),
            registry,
        )
        data = collector.collect()
        assert sum(data.module_risk_distribution.values()) == registry.module_count

    def test_bridge_with_custom_registry(self):
        """Custom registry with bridge."""
        registry = ModuleStealthRegistry()
        registry.register(ModuleStealthProfile(
            "custom_mod",
            ModuleRiskLevel.AGGRESSIVE,
            typical_requests_per_target=500,
            min_stealth_level=StealthLevel.HIGH,
        ))
        bridge = StealthScanBridge(registry)
        warnings = bridge.get_module_warnings(
            ["custom_mod"],
            StealthConfig.from_level(StealthLevel.LOW),
        )
        assert any(w["level"] == "warning" for w in warnings)
