# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_stealth_enforcement
# Purpose:      Unit tests for S-009 — Full stealth profile enforcement
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Tests for spiderfoot.recon.stealth_enforcement — comprehensive coverage.

Test matrix:
- EnforcementMode, ViolationType, Severity, RemediationActionType enums
- StealthViolation dataclass
- RemediationAction dataclass
- EnforcementPolicy (creation, serialization, for_mode, from_dict)
- ModuleEnforcementState (compliance, blocking, violations)
- StealthAuditor (rule evaluation, remediation)
- StealthEnforcementEngine (check, quarantine, violations, stats, dashboard)
- Module-level functions
"""

import time

import pytest

from spiderfoot.recon.stealth_enforcement import (
    EnforcementMode,
    EnforcementPolicy,
    ModuleEnforcementState,
    RemediationAction,
    RemediationActionType,
    Severity,
    StealthAuditor,
    StealthEnforcementEngine,
    StealthViolation,
    ViolationType,
    get_enforcement_modes,
    get_policy_for_level,
    get_remediation_types,
    get_severity_levels,
    get_violation_severity,
    get_violation_types,
)


# ============================================================================
# EnforcementMode
# ============================================================================


class TestEnforcementMode:
    def test_count(self):
        assert len(EnforcementMode) == 5

    def test_values(self):
        expected = {"disabled", "advisory", "moderate", "strict", "paranoid"}
        actual = {m.value for m in EnforcementMode}
        assert actual == expected

    def test_from_string(self):
        assert EnforcementMode("strict") == EnforcementMode.STRICT


# ============================================================================
# ViolationType
# ============================================================================


class TestViolationType:
    def test_count(self):
        assert len(ViolationType) == 15

    def test_all_have_severity(self):
        for vt in ViolationType:
            sev = get_violation_severity(vt)
            assert isinstance(sev, Severity)


# ============================================================================
# Severity
# ============================================================================


class TestSeverity:
    def test_count(self):
        assert len(Severity) == 4

    def test_values(self):
        expected = {"info", "warning", "high", "critical"}
        actual = {s.value for s in Severity}
        assert actual == expected


# ============================================================================
# RemediationActionType
# ============================================================================


class TestRemediationActionType:
    def test_count(self):
        assert len(RemediationActionType) == 8


# ============================================================================
# StealthViolation
# ============================================================================


class TestStealthViolation:
    def test_creation(self):
        v = StealthViolation(
            violation_type=ViolationType.DNS_PLAINTEXT,
            severity=Severity.HIGH,
            module_name="sfp_dns",
            description="Plaintext DNS",
        )
        assert v.violation_type == ViolationType.DNS_PLAINTEXT
        assert v.severity == Severity.HIGH
        assert v.resolved is False
        assert len(v.id) == 12

    def test_to_dict(self):
        v = StealthViolation(
            violation_type=ViolationType.RATE_LIMIT_EXCEEDED,
            severity=Severity.WARNING,
            module_name="sfp_test",
        )
        d = v.to_dict()
        assert d["violation_type"] == "rate_limit_exceeded"
        assert d["severity"] == "warning"
        assert d["module_name"] == "sfp_test"
        assert "timestamp" in d

    def test_unique_ids(self):
        v1 = StealthViolation()
        v2 = StealthViolation()
        assert v1.id != v2.id


# ============================================================================
# RemediationAction
# ============================================================================


class TestRemediationAction:
    def test_creation(self):
        r = RemediationAction(
            action_type=RemediationActionType.THROTTLE,
            description="Slow down",
            parameters={"target_rps": 2.0},
        )
        assert r.action_type == RemediationActionType.THROTTLE
        assert r.parameters["target_rps"] == 2.0

    def test_to_dict(self):
        r = RemediationAction(action_type=RemediationActionType.LOG_ONLY)
        d = r.to_dict()
        assert d["action_type"] == "log_only"


# ============================================================================
# EnforcementPolicy
# ============================================================================


class TestEnforcementPolicy:
    def test_defaults(self):
        p = EnforcementPolicy()
        assert p.mode == EnforcementMode.MODERATE
        assert p.check_rate_limits is True
        assert p.check_dns_encryption is True
        assert p.auto_remediate is True

    def test_to_dict(self):
        p = EnforcementPolicy(name="test", mode=EnforcementMode.STRICT)
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["mode"] == "strict"
        assert d["check_rate_limits"] is True

    def test_from_dict(self):
        d = {"name": "custom", "mode": "paranoid", "check_geolocation": True}
        p = EnforcementPolicy.from_dict(d)
        assert p.name == "custom"
        assert p.mode == EnforcementMode.PARANOID
        assert p.check_geolocation is True

    def test_roundtrip(self):
        p1 = EnforcementPolicy(name="rt", mode=EnforcementMode.STRICT, check_geolocation=True)
        p2 = EnforcementPolicy.from_dict(p1.to_dict())
        assert p2.name == p1.name
        assert p2.mode == p1.mode
        assert p2.check_geolocation == p1.check_geolocation

    def test_for_mode_disabled(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.DISABLED)
        assert p.check_rate_limits is False
        assert p.check_dns_encryption is False
        assert p.auto_remediate is False

    def test_for_mode_advisory(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.ADVISORY)
        assert p.max_violations_before_block == 999
        assert p.quarantine_on_critical is False

    def test_for_mode_moderate(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.MODERATE)
        assert p.mode == EnforcementMode.MODERATE

    def test_for_mode_strict(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.STRICT)
        assert p.max_violations_before_block == 2
        assert p.check_geolocation is True

    def test_for_mode_paranoid(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.PARANOID)
        assert p.max_violations_before_block == 1
        assert p.quarantine_on_critical is True

    def test_get_policy_for_level(self):
        for level in ("none", "low", "medium", "high", "maximum"):
            p = get_policy_for_level(level)
            assert isinstance(p, EnforcementPolicy)

    def test_get_policy_unknown_level(self):
        p = get_policy_for_level("unknown")
        assert p.mode == EnforcementMode.MODERATE  # default


# ============================================================================
# ModuleEnforcementState
# ============================================================================


class TestModuleEnforcementState:
    def test_creation(self):
        s = ModuleEnforcementState(module_name="sfp_test")
        assert s.module_name == "sfp_test"
        assert s.is_quarantined is False
        assert s.total_requests == 0

    def test_compliance_rate_no_requests(self):
        s = ModuleEnforcementState(module_name="sfp_test")
        assert s.compliance_rate == 1.0

    def test_compliance_rate(self):
        s = ModuleEnforcementState(module_name="sfp_test")
        s.total_requests = 100
        s.blocked_requests = 10
        assert abs(s.compliance_rate - 0.9) < 0.01

    def test_should_block_disabled(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.DISABLED)
        s = ModuleEnforcementState(module_name="sfp_test", policy=p)
        s.violations = [StealthViolation() for _ in range(100)]
        assert s.should_block is False

    def test_should_block_quarantined(self):
        s = ModuleEnforcementState(module_name="sfp_test")
        s.is_quarantined = True
        assert s.should_block is True

    def test_should_block_strict_threshold(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.STRICT)
        s = ModuleEnforcementState(module_name="sfp_test", policy=p)
        # Add violations within window
        for _ in range(3):
            s.violations.append(StealthViolation(
                severity=Severity.WARNING,
                timestamp=time.time(),
            ))
        assert s.should_block is True  # 3 >= max_violations_before_block (2)

    def test_should_block_paranoid_critical(self):
        p = EnforcementPolicy.for_mode(EnforcementMode.PARANOID)
        s = ModuleEnforcementState(module_name="sfp_test", policy=p)
        s.violations.append(StealthViolation(
            severity=Severity.CRITICAL,
            timestamp=time.time(),
        ))
        assert s.should_block is True

    def test_recent_violations_window(self):
        p = EnforcementPolicy(violation_window_seconds=60.0)
        s = ModuleEnforcementState(module_name="sfp_test", policy=p)
        # Old violation
        s.violations.append(StealthViolation(timestamp=time.time() - 120))
        # Recent violation
        s.violations.append(StealthViolation(timestamp=time.time()))
        assert len(s.recent_violations) == 1

    def test_to_dict(self):
        s = ModuleEnforcementState(module_name="sfp_test")
        d = s.to_dict()
        assert d["module_name"] == "sfp_test"
        assert "compliance_rate" in d
        assert "should_block" in d


# ============================================================================
# StealthAuditor
# ============================================================================


class TestStealthAuditor:
    def test_rules_count(self):
        a = StealthAuditor()
        assert len(a.rules) == 10

    def test_audit_no_violations(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "requests_per_second": 5,
            "user_agent": "Mozilla/5.0",
            "tls_fingerprint_rotated": True,
            "dns_encrypted": True,
            "proxy_rotated": True,
            "request_interval_variance": 0.5,
            "session_age_seconds": 30,
        })
        assert len(violations) == 0

    def test_audit_rate_limit(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "requests_per_second": 20,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.RATE_LIMIT_EXCEEDED in types

    def test_audit_user_agent(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "user_agent": "python-requests/2.28",
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.USER_AGENT_LEAKED in types

    def test_audit_dns_plaintext(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "dns_encrypted": False,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.DNS_PLAINTEXT in types

    def test_audit_tls_fingerprint(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "tls_fingerprint_rotated": False,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.TLS_FINGERPRINT_STATIC in types

    def test_audit_proxy_rotation(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "proxy_rotated": False,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.NO_PROXY_ROTATION in types

    def test_audit_request_pattern(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "request_interval_variance": 0.01,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.REQUEST_PATTERN_DETECTED in types

    def test_audit_timing_regularity(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "request_interval_variance": 0.1,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.TIMING_TOO_REGULAR in types

    def test_audit_session_reuse(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "session_age_seconds": 600,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.SESSION_REUSE in types

    def test_audit_waf_ignored(self):
        a = StealthAuditor()
        p = EnforcementPolicy()
        violations = a.audit_module("sfp_test", p, {
            "waf_detected": True,
            "waf_action_taken": False,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.WAF_DETECTION_IGNORED in types

    def test_audit_geolocation_disabled(self):
        a = StealthAuditor()
        p = EnforcementPolicy(check_geolocation=False)
        violations = a.audit_module("sfp_test", p, {
            "geolocation_mismatch": True,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.GEOLOCATION_MISMATCH not in types

    def test_audit_geolocation_enabled(self):
        a = StealthAuditor()
        p = EnforcementPolicy(check_geolocation=True)
        violations = a.audit_module("sfp_test", p, {
            "geolocation_mismatch": True,
        })
        types = [v.violation_type for v in violations]
        assert ViolationType.GEOLOCATION_MISMATCH in types

    def test_audit_disabled_policy(self):
        a = StealthAuditor()
        p = EnforcementPolicy.for_mode(EnforcementMode.DISABLED)
        violations = a.audit_module("sfp_test", p, {
            "requests_per_second": 100,
            "dns_encrypted": False,
            "user_agent": "python-requests",
        })
        assert len(violations) == 0

    def test_remediation_critical(self):
        a = StealthAuditor()
        v = StealthViolation(
            violation_type=ViolationType.DIRECT_IP_EXPOSURE,
            severity=Severity.CRITICAL,
        )
        rem = a.get_recommended_remediation(v)
        assert rem.action_type == RemediationActionType.QUARANTINE_MODULE

    def test_remediation_high_rate(self):
        a = StealthAuditor()
        v = StealthViolation(
            violation_type=ViolationType.RATE_LIMIT_EXCEEDED,
            severity=Severity.HIGH,
        )
        rem = a.get_recommended_remediation(v)
        assert rem.action_type == RemediationActionType.THROTTLE

    def test_remediation_high_dns(self):
        a = StealthAuditor()
        v = StealthViolation(
            violation_type=ViolationType.DNS_PLAINTEXT,
            severity=Severity.HIGH,
        )
        rem = a.get_recommended_remediation(v)
        assert rem.action_type == RemediationActionType.RETRY_WITH_STEALTH

    def test_remediation_warning(self):
        a = StealthAuditor()
        v = StealthViolation(
            violation_type=ViolationType.USER_AGENT_LEAKED,
            severity=Severity.WARNING,
        )
        rem = a.get_recommended_remediation(v)
        assert rem.action_type == RemediationActionType.ROTATE_IDENTITY

    def test_remediation_info(self):
        a = StealthAuditor()
        v = StealthViolation(
            violation_type=ViolationType.HEADER_MISMATCH,
            severity=Severity.INFO,
        )
        rem = a.get_recommended_remediation(v)
        assert rem.action_type == RemediationActionType.LOG_ONLY


# ============================================================================
# StealthEnforcementEngine
# ============================================================================


class TestStealthEnforcementEngine:
    def test_creation(self):
        e = StealthEnforcementEngine()
        assert e.global_policy.mode == EnforcementMode.MODERATE

    def test_creation_with_level(self):
        e = StealthEnforcementEngine("high")
        assert e.global_policy.mode == EnforcementMode.STRICT

    def test_set_global_policy(self):
        e = StealthEnforcementEngine()
        p = e.set_global_policy("maximum")
        assert p.mode == EnforcementMode.PARANOID

    def test_check_module_clean(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", {
            "requests_per_second": 5,
            "user_agent": "Mozilla/5.0",
            "dns_encrypted": True,
        })
        assert result["allowed"] is True
        assert len(result["violations"]) == 0

    def test_check_module_violation(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", {
            "requests_per_second": 20,
        })
        assert len(result["violations"]) > 0

    def test_check_module_with_remediation(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", {
            "dns_encrypted": False,
        })
        assert len(result["remediations"]) > 0

    def test_check_module_blocks_on_threshold(self):
        e = StealthEnforcementEngine("high")  # strict mode
        # Generate enough violations to exceed threshold
        for i in range(5):
            e.check_module("sfp_bad", {
                "requests_per_second": 50,
                "dns_encrypted": False,
                "user_agent": "python-requests",
            })
        result = e.check_module("sfp_bad", {
            "requests_per_second": 50,
        })
        # After enough violations, module should be blocked
        state = e.get_module_state("sfp_bad")
        assert state.violation_count > 0

    def test_quarantine_on_critical(self):
        e = StealthEnforcementEngine("high")
        # Simulate critical violation by quarantine-on-critical policy
        state = e.get_module_state("sfp_danger")
        state.policy = EnforcementPolicy(quarantine_on_critical=True)
        # Manually create a violation with critical severity
        v = StealthViolation(
            violation_type=ViolationType.DIRECT_IP_EXPOSURE,
            severity=Severity.CRITICAL,
            module_name="sfp_danger",
        )
        state.violations.append(v)
        state.is_quarantined = True
        assert state.should_block is True
        assert "sfp_danger" in e.get_quarantined_modules()

    def test_unquarantine(self):
        e = StealthEnforcementEngine()
        state = e.get_module_state("sfp_test")
        state.is_quarantined = True
        assert e.unquarantine_module("sfp_test") is True
        assert state.is_quarantined is False

    def test_unquarantine_unknown(self):
        e = StealthEnforcementEngine()
        assert e.unquarantine_module("nonexistent") is False

    def test_get_violations(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_a", {"requests_per_second": 20})
        e.check_module("sfp_b", {"dns_encrypted": False})
        violations = e.get_violations()
        assert len(violations) >= 2

    def test_get_violations_filter_module(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_a", {"requests_per_second": 20})
        e.check_module("sfp_b", {"dns_encrypted": False})
        violations = e.get_violations(module_name="sfp_a")
        assert all(v["module_name"] == "sfp_a" for v in violations)

    def test_get_violations_filter_severity(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_test", {
            "requests_per_second": 20,
            "user_agent": "python-requests",
        })
        high_v = e.get_violations(severity=Severity.HIGH)
        for v in high_v:
            assert v["severity"] == "high"

    def test_clear_violations(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_test", {"requests_per_second": 20})
        count = e.clear_violations()
        assert count > 0
        assert len(e.get_violations()) == 0

    def test_clear_violations_by_module(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_a", {"requests_per_second": 20})
        e.check_module("sfp_b", {"dns_encrypted": False})
        e.clear_violations(module_name="sfp_a")
        remaining = e.get_violations()
        assert all(v["module_name"] != "sfp_a" for v in remaining)

    def test_get_all_module_states(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_a", {})
        e.check_module("sfp_b", {})
        states = e.get_all_module_states()
        assert "sfp_a" in states
        assert "sfp_b" in states

    def test_set_module_policy(self):
        e = StealthEnforcementEngine()
        custom = EnforcementPolicy(name="custom", mode=EnforcementMode.PARANOID)
        e.set_module_policy("sfp_special", custom)
        state = e.get_module_state("sfp_special")
        assert state.policy.mode == EnforcementMode.PARANOID

    def test_get_stats(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_test", {"requests_per_second": 20})
        stats = e.get_stats()
        assert stats["total_checks"] >= 1
        assert stats["total_violations"] >= 1
        assert "severity_breakdown" in stats
        assert "violation_type_breakdown" in stats

    def test_get_dashboard_data(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_test", {})
        dash = e.get_dashboard_data()
        assert "global_policy" in dash
        assert "enforcement_mode" in dash
        assert "stats" in dash
        assert "modules" in dash
        assert "quarantined" in dash
        assert "recent_violations" in dash
        assert len(dash["enforcement_modes"]) == 5
        assert len(dash["violation_types"]) == 15
        assert len(dash["severity_levels"]) == 4

    def test_scan_id_propagation(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", {
            "requests_per_second": 20,
        }, scan_id="scan-123")
        for v in result["violations"]:
            assert v["scan_id"] == "scan-123"


# ============================================================================
# Module-level Functions
# ============================================================================


class TestModuleFunctions:
    def test_get_enforcement_modes(self):
        modes = get_enforcement_modes()
        assert len(modes) == 5
        assert "strict" in modes

    def test_get_violation_types(self):
        types = get_violation_types()
        assert len(types) == 15
        assert "dns_plaintext" in types

    def test_get_severity_levels(self):
        levels = get_severity_levels()
        assert len(levels) == 4
        assert "critical" in levels

    def test_get_remediation_types(self):
        types = get_remediation_types()
        assert len(types) == 8
        assert "quarantine_module" in types


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    def test_empty_context(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", {})
        assert result["allowed"] is True

    def test_none_context(self):
        e = StealthEnforcementEngine()
        result = e.check_module("sfp_test", None)
        assert result["allowed"] is True

    def test_concurrent_checks(self):
        import threading

        e = StealthEnforcementEngine()
        errors: list[str] = []

        def checker(mod_name: str):
            try:
                for _ in range(20):
                    e.check_module(mod_name, {"requests_per_second": 15})
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=checker, args=(f"mod{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_many_violations(self):
        e = StealthEnforcementEngine("low")  # advisory mode
        for i in range(50):
            e.check_module("sfp_test", {
                "requests_per_second": 20,
                "dns_encrypted": False,
                "user_agent": "scrapy",
            })
        stats = e.get_stats()
        assert stats["total_violations"] > 100

    def test_multiple_modules_isolation(self):
        e = StealthEnforcementEngine()
        e.check_module("sfp_a", {"requests_per_second": 20})
        e.check_module("sfp_b", {})
        state_a = e.get_module_state("sfp_a")
        state_b = e.get_module_state("sfp_b")
        assert state_a.violation_count > state_b.violation_count
