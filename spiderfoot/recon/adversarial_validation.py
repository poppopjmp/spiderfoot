# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         adversarial_validation
# Purpose:      S-010 — Adversarial validation & stealth benchmarks
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Adversarial validation and stealth benchmarks.

This module provides automated adversarial testing of stealth configurations,
running targeted probes against stealth profiles to ensure they hold up
under realistic detection scenarios, and producing benchmark scores for
stealth readiness.

Components
----------
- DetectionVector        – enum of adversarial detection techniques
- BenchmarkCategory      – enum of benchmark groupings
- TestResult             – individual test outcome
- BenchmarkScore         – scored aggregate for a category
- AdversarialProbe       – single detection-avoidance probe
- ProbeResult            – outcome of a probe execution
- DetectionSignature     – known detection signature to test against
- ValidationSuite        – curated set of probes
- StealthBenchmarkRunner – runs benchmarks across categories
- AdversarialValidator   – end-to-end validation engine (façade)
"""

from __future__ import annotations

import hashlib
import statistics
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable


# ============================================================================
# Enums
# ============================================================================


class DetectionVector(Enum):
    """Adversarial detection techniques to test against."""
    TLS_FINGERPRINT = "tls_fingerprint"
    JA3_HASH = "ja3_hash"
    JA4_HASH = "ja4_hash"
    HTTP2_FINGERPRINT = "http2_fingerprint"
    HEADER_ORDER = "header_order"
    TIMING_ANALYSIS = "timing_analysis"
    RATE_PATTERN = "rate_pattern"
    DNS_LEAK = "dns_leak"
    IP_REPUTATION = "ip_reputation"
    BROWSER_FINGERPRINT = "browser_fingerprint"
    COOKIE_BEHAVIOR = "cookie_behavior"
    JAVASCRIPT_EXECUTION = "javascript_execution"
    CAPTCHA_DETECTION = "captcha_detection"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    GEOLOCATION_MISMATCH = "geolocation_mismatch"
    SESSION_ANOMALY = "session_anomaly"
    USER_AGENT_INCONSISTENCY = "user_agent_inconsistency"
    TCP_FINGERPRINT = "tcp_fingerprint"


class BenchmarkCategory(Enum):
    """Stealth benchmark categories."""
    NETWORK = "network"
    TLS = "tls"
    HTTP = "http"
    DNS = "dns"
    BEHAVIORAL = "behavioral"
    IDENTITY = "identity"
    EVASION = "evasion"
    OVERALL = "overall"


class TestStatus(Enum):
    """Status of a test/probe execution."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    WARNING = "warning"


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class TestResult:
    """Outcome of a single validation test."""
    test_name: str = ""
    status: TestStatus = TestStatus.PASSED
    score: float = 1.0  # 0.0 = fail, 1.0 = pass
    details: str = ""
    detection_vector: DetectionVector | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "status": self.status.value,
            "score": round(self.score, 4),
            "details": self.details,
            "detection_vector": self.detection_vector.value if self.detection_vector else None,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class BenchmarkScore:
    """Scored aggregate for a benchmark category."""
    category: BenchmarkCategory = BenchmarkCategory.OVERALL
    score: float = 0.0
    max_score: float = 100.0
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    grade: str = "F"
    details: list[TestResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.tests_run == 0:
            return 0.0
        return self.tests_passed / self.tests_run

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "score": round(self.score, 2),
            "max_score": self.max_score,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "grade": self.grade,
            "pass_rate": round(self.pass_rate, 4),
            "details": [d.to_dict() for d in self.details],
        }


@dataclass
class AdversarialProbe:
    """A single adversarial detection-avoidance probe."""
    name: str = ""
    description: str = ""
    detection_vector: DetectionVector = DetectionVector.TLS_FINGERPRINT
    category: BenchmarkCategory = BenchmarkCategory.TLS
    severity: str = "medium"  # low, medium, high, critical
    check_fn: Callable[..., TestResult] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "detection_vector": self.detection_vector.value,
            "category": self.category.value,
            "severity": self.severity,
        }


@dataclass
class ProbeResult:
    """Outcome of running an adversarial probe."""
    probe: AdversarialProbe = field(default_factory=AdversarialProbe)
    test_result: TestResult = field(default_factory=TestResult)
    evaded: bool = False  # whether the detection was successfully evaded
    confidence: float = 0.0  # 0-1 confidence of evasion

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe": self.probe.to_dict(),
            "test_result": self.test_result.to_dict(),
            "evaded": self.evaded,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class DetectionSignature:
    """Known detection signature to test against."""
    name: str = ""
    vendor: str = ""
    signature_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    detection_vectors: list[DetectionVector] = field(default_factory=list)
    description: str = ""
    severity: str = "medium"
    evasion_techniques: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "signature_id": self.signature_id,
            "detection_vectors": [v.value for v in self.detection_vectors],
            "description": self.description,
            "severity": self.severity,
            "evasion_techniques": self.evasion_techniques,
        }


# ============================================================================
# Default detection signatures
# ============================================================================


_DEFAULT_SIGNATURES: list[DetectionSignature] = [
    DetectionSignature(
        name="JA3 Fingerprint Match",
        vendor="salesforce",
        description="Detects automated tools via TLS client hello fingerprinting",
        detection_vectors=[DetectionVector.JA3_HASH, DetectionVector.TLS_FINGERPRINT],
        severity="high",
        evasion_techniques=["tls_randomization", "cipher_rotation", "extension_shuffling"],
    ),
    DetectionSignature(
        name="JA4 Fingerprint Match",
        vendor="foxio",
        description="Next-gen TLS fingerprinting (JA4+)",
        detection_vectors=[DetectionVector.JA4_HASH, DetectionVector.TLS_FINGERPRINT],
        severity="high",
        evasion_techniques=["tls_randomization", "alpn_variation"],
    ),
    DetectionSignature(
        name="HTTP/2 Settings Fingerprint",
        vendor="akamai",
        description="Detects non-browser HTTP/2 settings frames",
        detection_vectors=[DetectionVector.HTTP2_FINGERPRINT],
        severity="medium",
        evasion_techniques=["h2_settings_mimicry", "browser_profile_matching"],
    ),
    DetectionSignature(
        name="Header Order Analysis",
        vendor="cloudflare",
        description="Compares HTTP header order against known browser profiles",
        detection_vectors=[DetectionVector.HEADER_ORDER],
        severity="medium",
        evasion_techniques=["header_ordering", "browser_profile_matching"],
    ),
    DetectionSignature(
        name="Request Timing Analysis",
        vendor="imperva",
        description="Detects regular request timing patterns of bots",
        detection_vectors=[DetectionVector.TIMING_ANALYSIS, DetectionVector.RATE_PATTERN],
        severity="high",
        evasion_techniques=["jitter_injection", "human_timing_simulation"],
    ),
    DetectionSignature(
        name="DNS Leak Detection",
        vendor="generic",
        description="Detects plaintext DNS queries revealing target enumeration",
        detection_vectors=[DetectionVector.DNS_LEAK],
        severity="critical",
        evasion_techniques=["doh", "dot", "dns_caching"],
    ),
    DetectionSignature(
        name="IP Reputation Check",
        vendor="maxmind",
        description="Flags traffic from known proxy/VPN/datacenter IPs",
        detection_vectors=[DetectionVector.IP_REPUTATION],
        severity="medium",
        evasion_techniques=["residential_proxy", "ip_rotation"],
    ),
    DetectionSignature(
        name="Browser Behavior Validation",
        vendor="perimeterx",
        description="Validates browser-like behavior (JS execution, mouse events)",
        detection_vectors=[DetectionVector.BROWSER_FINGERPRINT, DetectionVector.JAVASCRIPT_EXECUTION],
        severity="high",
        evasion_techniques=["headless_browser", "js_engine_integration"],
    ),
    DetectionSignature(
        name="Session Anomaly Detection",
        vendor="datadome",
        description="Detects anomalous session patterns (no cookies, rapid navigation)",
        detection_vectors=[DetectionVector.SESSION_ANOMALY, DetectionVector.COOKIE_BEHAVIOR],
        severity="medium",
        evasion_techniques=["cookie_management", "session_simulation"],
    ),
    DetectionSignature(
        name="Geolocation Consistency",
        vendor="generic",
        description="Cross-references IP geolocation with timezone/language headers",
        detection_vectors=[DetectionVector.GEOLOCATION_MISMATCH],
        severity="medium",
        evasion_techniques=["geo_consistent_proxy", "locale_matching"],
    ),
]


def get_default_signatures() -> list[DetectionSignature]:
    """Return copy of default detection signatures."""
    return list(_DEFAULT_SIGNATURES)


# ============================================================================
# ValidationSuite — curated set of probes
# ============================================================================


class ValidationSuite:
    """A curated set of adversarial probes for a specific scenario."""

    def __init__(self, name: str = "default", description: str = ""):
        self.name = name
        self.description = description or f"Validation suite: {name}"
        self._probes: list[AdversarialProbe] = []
        if name == "default":
            self._build_default_probes()

    def _build_default_probes(self) -> None:
        """Build the default adversarial probe set."""
        self._probes = [
            # TLS probes
            AdversarialProbe(
                name="tls_fingerprint_rotation",
                description="Verify TLS fingerprint changes between sessions",
                detection_vector=DetectionVector.TLS_FINGERPRINT,
                category=BenchmarkCategory.TLS,
                severity="high",
                check_fn=self._check_tls_rotation,
            ),
            AdversarialProbe(
                name="ja3_hash_uniqueness",
                description="Verify JA3 hash varies across connections",
                detection_vector=DetectionVector.JA3_HASH,
                category=BenchmarkCategory.TLS,
                severity="high",
                check_fn=self._check_ja3_uniqueness,
            ),
            AdversarialProbe(
                name="ja4_hash_variance",
                description="Verify JA4+ fingerprint diversity",
                detection_vector=DetectionVector.JA4_HASH,
                category=BenchmarkCategory.TLS,
                severity="high",
                check_fn=self._check_ja4_variance,
            ),
            # Network probes
            AdversarialProbe(
                name="request_timing_jitter",
                description="Ensure request intervals have sufficient randomness",
                detection_vector=DetectionVector.TIMING_ANALYSIS,
                category=BenchmarkCategory.NETWORK,
                severity="high",
                check_fn=self._check_timing_jitter,
            ),
            AdversarialProbe(
                name="rate_pattern_detection",
                description="Verify no detectable rate patterns",
                detection_vector=DetectionVector.RATE_PATTERN,
                category=BenchmarkCategory.NETWORK,
                severity="medium",
                check_fn=self._check_rate_pattern,
            ),
            AdversarialProbe(
                name="tcp_fingerprint_masking",
                description="TCP/IP stack fingerprint does not reveal OS/tool",
                detection_vector=DetectionVector.TCP_FINGERPRINT,
                category=BenchmarkCategory.NETWORK,
                severity="medium",
                check_fn=self._check_tcp_fingerprint,
            ),
            # HTTP probes
            AdversarialProbe(
                name="header_order_consistency",
                description="HTTP headers match expected browser ordering",
                detection_vector=DetectionVector.HEADER_ORDER,
                category=BenchmarkCategory.HTTP,
                severity="medium",
                check_fn=self._check_header_order,
            ),
            AdversarialProbe(
                name="http2_settings_mimicry",
                description="HTTP/2 settings match browser profile",
                detection_vector=DetectionVector.HTTP2_FINGERPRINT,
                category=BenchmarkCategory.HTTP,
                severity="medium",
                check_fn=self._check_http2_settings,
            ),
            AdversarialProbe(
                name="user_agent_consistency",
                description="User-Agent consistent across request properties",
                detection_vector=DetectionVector.USER_AGENT_INCONSISTENCY,
                category=BenchmarkCategory.HTTP,
                severity="high",
                check_fn=self._check_user_agent_consistency,
            ),
            # DNS probes
            AdversarialProbe(
                name="dns_encryption_status",
                description="DNS queries are encrypted (DoH/DoT)",
                detection_vector=DetectionVector.DNS_LEAK,
                category=BenchmarkCategory.DNS,
                severity="critical",
                check_fn=self._check_dns_encryption,
            ),
            # Behavioral probes
            AdversarialProbe(
                name="session_cookie_handling",
                description="Proper cookie jar management across requests",
                detection_vector=DetectionVector.COOKIE_BEHAVIOR,
                category=BenchmarkCategory.BEHAVIORAL,
                severity="medium",
                check_fn=self._check_cookie_handling,
            ),
            AdversarialProbe(
                name="behavioral_pattern_variance",
                description="Navigation pattern does not follow deterministic path",
                detection_vector=DetectionVector.BEHAVIORAL_ANALYSIS,
                category=BenchmarkCategory.BEHAVIORAL,
                severity="high",
                check_fn=self._check_behavioral_pattern,
            ),
            # Identity probes
            AdversarialProbe(
                name="ip_reputation_check",
                description="Source IP has acceptable reputation score",
                detection_vector=DetectionVector.IP_REPUTATION,
                category=BenchmarkCategory.IDENTITY,
                severity="medium",
                check_fn=self._check_ip_reputation,
            ),
            AdversarialProbe(
                name="geolocation_consistency",
                description="IP geolocation matches timezone/language headers",
                detection_vector=DetectionVector.GEOLOCATION_MISMATCH,
                category=BenchmarkCategory.IDENTITY,
                severity="medium",
                check_fn=self._check_geolocation,
            ),
            # Evasion probes
            AdversarialProbe(
                name="captcha_handling",
                description="Captcha challenges handled or avoided",
                detection_vector=DetectionVector.CAPTCHA_DETECTION,
                category=BenchmarkCategory.EVASION,
                severity="high",
                check_fn=self._check_captcha_handling,
            ),
            AdversarialProbe(
                name="session_anomaly_avoidance",
                description="Session patterns appear natural",
                detection_vector=DetectionVector.SESSION_ANOMALY,
                category=BenchmarkCategory.EVASION,
                severity="medium",
                check_fn=self._check_session_anomaly,
            ),
        ]

    @property
    def probes(self) -> list[AdversarialProbe]:
        return list(self._probes)

    def add_probe(self, probe: AdversarialProbe) -> None:
        self._probes.append(probe)

    def get_probes_by_category(self, category: BenchmarkCategory) -> list[AdversarialProbe]:
        return [p for p in self._probes if p.category == category]

    def get_probes_by_vector(self, vector: DetectionVector) -> list[AdversarialProbe]:
        return [p for p in self._probes if p.detection_vector == vector]

    # ── Probe check functions ─────────────────────────────────────────────

    @staticmethod
    def _check_tls_rotation(context: dict[str, Any]) -> TestResult:
        rotated = context.get("tls_fingerprint_rotated", False)
        diversity = context.get("tls_fingerprint_diversity", 0.0)
        if rotated and diversity >= 0.5:
            return TestResult(test_name="tls_fingerprint_rotation", status=TestStatus.PASSED,
                              score=1.0, details=f"TLS fingerprint diversity: {diversity:.2f}",
                              detection_vector=DetectionVector.TLS_FINGERPRINT)
        elif rotated:
            return TestResult(test_name="tls_fingerprint_rotation", status=TestStatus.WARNING,
                              score=0.6, details=f"Low diversity: {diversity:.2f}",
                              detection_vector=DetectionVector.TLS_FINGERPRINT)
        return TestResult(test_name="tls_fingerprint_rotation", status=TestStatus.FAILED,
                          score=0.0, details="TLS fingerprint not rotated",
                          detection_vector=DetectionVector.TLS_FINGERPRINT)

    @staticmethod
    def _check_ja3_uniqueness(context: dict[str, Any]) -> TestResult:
        unique = context.get("ja3_unique_count", 0)
        total = context.get("ja3_total_connections", 1)
        ratio = unique / max(total, 1)
        if ratio >= 0.8:
            return TestResult(test_name="ja3_hash_uniqueness", status=TestStatus.PASSED,
                              score=1.0, details=f"JA3 uniqueness: {ratio:.0%}",
                              detection_vector=DetectionVector.JA3_HASH)
        elif ratio >= 0.4:
            return TestResult(test_name="ja3_hash_uniqueness", status=TestStatus.WARNING,
                              score=0.5, details=f"JA3 uniqueness: {ratio:.0%}",
                              detection_vector=DetectionVector.JA3_HASH)
        return TestResult(test_name="ja3_hash_uniqueness", status=TestStatus.FAILED,
                          score=0.0, details=f"JA3 uniqueness too low: {ratio:.0%}",
                          detection_vector=DetectionVector.JA3_HASH)

    @staticmethod
    def _check_ja4_variance(context: dict[str, Any]) -> TestResult:
        variance = context.get("ja4_variance", 0.0)
        if variance >= 0.7:
            return TestResult(test_name="ja4_hash_variance", status=TestStatus.PASSED,
                              score=1.0, details=f"JA4+ variance: {variance:.2f}",
                              detection_vector=DetectionVector.JA4_HASH)
        return TestResult(test_name="ja4_hash_variance", status=TestStatus.FAILED,
                          score=variance, details=f"JA4+ variance low: {variance:.2f}",
                          detection_vector=DetectionVector.JA4_HASH)

    @staticmethod
    def _check_timing_jitter(context: dict[str, Any]) -> TestResult:
        variance = context.get("request_interval_variance", 0.0)
        if variance >= 0.3:
            return TestResult(test_name="request_timing_jitter", status=TestStatus.PASSED,
                              score=1.0, details=f"Timing variance: {variance:.2f}",
                              detection_vector=DetectionVector.TIMING_ANALYSIS)
        elif variance >= 0.1:
            return TestResult(test_name="request_timing_jitter", status=TestStatus.WARNING,
                              score=0.5, details=f"Marginal timing variance: {variance:.2f}",
                              detection_vector=DetectionVector.TIMING_ANALYSIS)
        return TestResult(test_name="request_timing_jitter", status=TestStatus.FAILED,
                          score=0.0, details=f"Timing too regular: {variance:.2f}",
                          detection_vector=DetectionVector.TIMING_ANALYSIS)

    @staticmethod
    def _check_rate_pattern(context: dict[str, Any]) -> TestResult:
        rps = context.get("requests_per_second", 0.0)
        if rps <= 5.0:
            return TestResult(test_name="rate_pattern_detection", status=TestStatus.PASSED,
                              score=1.0, details=f"Rate: {rps:.1f} rps (safe)",
                              detection_vector=DetectionVector.RATE_PATTERN)
        elif rps <= 10.0:
            return TestResult(test_name="rate_pattern_detection", status=TestStatus.WARNING,
                              score=0.5, details=f"Rate: {rps:.1f} rps (borderline)",
                              detection_vector=DetectionVector.RATE_PATTERN)
        return TestResult(test_name="rate_pattern_detection", status=TestStatus.FAILED,
                          score=0.0, details=f"Rate: {rps:.1f} rps (too high)",
                          detection_vector=DetectionVector.RATE_PATTERN)

    @staticmethod
    def _check_tcp_fingerprint(context: dict[str, Any]) -> TestResult:
        masked = context.get("tcp_fingerprint_masked", False)
        if masked:
            return TestResult(test_name="tcp_fingerprint_masking", status=TestStatus.PASSED,
                              score=1.0, details="TCP fingerprint masked",
                              detection_vector=DetectionVector.TCP_FINGERPRINT)
        return TestResult(test_name="tcp_fingerprint_masking", status=TestStatus.WARNING,
                          score=0.3, details="TCP fingerprint not masked (OS may leak)",
                          detection_vector=DetectionVector.TCP_FINGERPRINT)

    @staticmethod
    def _check_header_order(context: dict[str, Any]) -> TestResult:
        consistent = context.get("header_order_consistent", False)
        if consistent:
            return TestResult(test_name="header_order_consistency", status=TestStatus.PASSED,
                              score=1.0, details="Header order matches browser profile",
                              detection_vector=DetectionVector.HEADER_ORDER)
        return TestResult(test_name="header_order_consistency", status=TestStatus.FAILED,
                          score=0.0, details="Header order does not match expected browser",
                          detection_vector=DetectionVector.HEADER_ORDER)

    @staticmethod
    def _check_http2_settings(context: dict[str, Any]) -> TestResult:
        mimicked = context.get("http2_settings_mimicked", False)
        if mimicked:
            return TestResult(test_name="http2_settings_mimicry", status=TestStatus.PASSED,
                              score=1.0, details="HTTP/2 settings match browser",
                              detection_vector=DetectionVector.HTTP2_FINGERPRINT)
        return TestResult(test_name="http2_settings_mimicry", status=TestStatus.WARNING,
                          score=0.4, details="HTTP/2 settings may reveal automation",
                          detection_vector=DetectionVector.HTTP2_FINGERPRINT)

    @staticmethod
    def _check_user_agent_consistency(context: dict[str, Any]) -> TestResult:
        user_agent = context.get("user_agent", "")
        ua_lower = user_agent.lower()
        bad_markers = ["python", "scrapy", "curl", "wget", "httpie", "go-http-client"]
        for marker in bad_markers:
            if marker in ua_lower:
                return TestResult(test_name="user_agent_consistency", status=TestStatus.FAILED,
                                  score=0.0, details=f"Automation marker in UA: {marker}",
                                  detection_vector=DetectionVector.USER_AGENT_INCONSISTENCY)
        if "mozilla" in ua_lower or "chrome" in ua_lower or "firefox" in ua_lower:
            return TestResult(test_name="user_agent_consistency", status=TestStatus.PASSED,
                              score=1.0, details="UA appears browser-like",
                              detection_vector=DetectionVector.USER_AGENT_INCONSISTENCY)
        return TestResult(test_name="user_agent_consistency", status=TestStatus.WARNING,
                          score=0.5, details="UA not clearly browser-like",
                          detection_vector=DetectionVector.USER_AGENT_INCONSISTENCY)

    @staticmethod
    def _check_dns_encryption(context: dict[str, Any]) -> TestResult:
        encrypted = context.get("dns_encrypted", False)
        protocol = context.get("dns_protocol", "plain")
        if encrypted and protocol in ("doh", "dot"):
            return TestResult(test_name="dns_encryption_status", status=TestStatus.PASSED,
                              score=1.0, details=f"DNS encrypted via {protocol.upper()}",
                              detection_vector=DetectionVector.DNS_LEAK)
        return TestResult(test_name="dns_encryption_status", status=TestStatus.FAILED,
                          score=0.0, details="DNS queries are plaintext — leak risk",
                          detection_vector=DetectionVector.DNS_LEAK)

    @staticmethod
    def _check_cookie_handling(context: dict[str, Any]) -> TestResult:
        managed = context.get("cookie_jar_managed", False)
        if managed:
            return TestResult(test_name="session_cookie_handling", status=TestStatus.PASSED,
                              score=1.0, details="Cookies managed properly",
                              detection_vector=DetectionVector.COOKIE_BEHAVIOR)
        return TestResult(test_name="session_cookie_handling", status=TestStatus.WARNING,
                          score=0.3, details="Cookie management not verified",
                          detection_vector=DetectionVector.COOKIE_BEHAVIOR)

    @staticmethod
    def _check_behavioral_pattern(context: dict[str, Any]) -> TestResult:
        randomized = context.get("navigation_randomized", False)
        variance = context.get("behavioral_variance", 0.0)
        if randomized and variance >= 0.5:
            return TestResult(test_name="behavioral_pattern_variance", status=TestStatus.PASSED,
                              score=1.0, details=f"Behavioral variance: {variance:.2f}",
                              detection_vector=DetectionVector.BEHAVIORAL_ANALYSIS)
        return TestResult(test_name="behavioral_pattern_variance", status=TestStatus.FAILED,
                          score=variance * 0.8, details=f"Behavioral variance low: {variance:.2f}",
                          detection_vector=DetectionVector.BEHAVIORAL_ANALYSIS)

    @staticmethod
    def _check_ip_reputation(context: dict[str, Any]) -> TestResult:
        score = context.get("ip_reputation_score", 0.5)
        if score >= 0.7:
            return TestResult(test_name="ip_reputation_check", status=TestStatus.PASSED,
                              score=1.0, details=f"IP reputation: {score:.2f}",
                              detection_vector=DetectionVector.IP_REPUTATION)
        return TestResult(test_name="ip_reputation_check", status=TestStatus.WARNING,
                          score=score, details=f"IP reputation low: {score:.2f}",
                          detection_vector=DetectionVector.IP_REPUTATION)

    @staticmethod
    def _check_geolocation(context: dict[str, Any]) -> TestResult:
        consistent = context.get("geolocation_consistent", True)
        if consistent:
            return TestResult(test_name="geolocation_consistency", status=TestStatus.PASSED,
                              score=1.0, details="Geolocation consistent",
                              detection_vector=DetectionVector.GEOLOCATION_MISMATCH)
        return TestResult(test_name="geolocation_consistency", status=TestStatus.FAILED,
                          score=0.0, details="IP geo does not match request headers",
                          detection_vector=DetectionVector.GEOLOCATION_MISMATCH)

    @staticmethod
    def _check_captcha_handling(context: dict[str, Any]) -> TestResult:
        encountered = context.get("captcha_encountered", False)
        solved = context.get("captcha_solved", False)
        if not encountered:
            return TestResult(test_name="captcha_handling", status=TestStatus.PASSED,
                              score=1.0, details="No captcha encountered (stealth effective)",
                              detection_vector=DetectionVector.CAPTCHA_DETECTION)
        if solved:
            return TestResult(test_name="captcha_handling", status=TestStatus.WARNING,
                              score=0.5, details="Captcha encountered but solved",
                              detection_vector=DetectionVector.CAPTCHA_DETECTION)
        return TestResult(test_name="captcha_handling", status=TestStatus.FAILED,
                          score=0.0, details="Captcha encountered and blocked",
                          detection_vector=DetectionVector.CAPTCHA_DETECTION)

    @staticmethod
    def _check_session_anomaly(context: dict[str, Any]) -> TestResult:
        natural = context.get("session_appears_natural", False)
        if natural:
            return TestResult(test_name="session_anomaly_avoidance", status=TestStatus.PASSED,
                              score=1.0, details="Session patterns appear natural",
                              detection_vector=DetectionVector.SESSION_ANOMALY)
        return TestResult(test_name="session_anomaly_avoidance", status=TestStatus.WARNING,
                          score=0.4, details="Session may exhibit anomalous patterns",
                          detection_vector=DetectionVector.SESSION_ANOMALY)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "probe_count": len(self._probes),
            "categories": list({p.category.value for p in self._probes}),
            "probes": [p.to_dict() for p in self._probes],
        }


# ============================================================================
# StealthBenchmarkRunner
# ============================================================================


def _compute_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "A-"
    elif score >= 80:
        return "B+"
    elif score >= 75:
        return "B"
    elif score >= 70:
        return "B-"
    elif score >= 65:
        return "C+"
    elif score >= 60:
        return "C"
    elif score >= 55:
        return "C-"
    elif score >= 50:
        return "D"
    else:
        return "F"


class StealthBenchmarkRunner:
    """Runs stealth benchmarks across categories and produces scores."""

    def __init__(self, suite: ValidationSuite | None = None):
        self._suite = suite or ValidationSuite()

    def run_category(
        self,
        category: BenchmarkCategory,
        context: dict[str, Any],
    ) -> BenchmarkScore:
        """Run all probes in a category and return a scored result."""
        probes = self._suite.get_probes_by_category(category)
        if not probes:
            return BenchmarkScore(category=category)

        results: list[TestResult] = []
        for probe in probes:
            start = time.time()
            if probe.check_fn:
                try:
                    result = probe.check_fn(context)
                    result.duration_ms = (time.time() - start) * 1000
                    results.append(result)
                except Exception as e:
                    results.append(TestResult(
                        test_name=probe.name,
                        status=TestStatus.ERROR,
                        score=0.0,
                        details=str(e),
                        detection_vector=probe.detection_vector,
                        duration_ms=(time.time() - start) * 1000,
                    ))
            else:
                results.append(TestResult(
                    test_name=probe.name,
                    status=TestStatus.SKIPPED,
                    score=0.0,
                    details="No check function",
                    detection_vector=probe.detection_vector,
                ))

        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
        scores = [r.score for r in results if r.status != TestStatus.SKIPPED]
        avg_score = statistics.mean(scores) * 100 if scores else 0.0

        return BenchmarkScore(
            category=category,
            score=avg_score,
            tests_run=len(results) - skipped,
            tests_passed=passed,
            tests_failed=failed,
            tests_skipped=skipped,
            grade=_compute_grade(avg_score),
            details=results,
        )

    def run_all(self, context: dict[str, Any]) -> dict[str, BenchmarkScore]:
        """Run benchmarks across all categories."""
        categories = list(BenchmarkCategory)
        results: dict[str, BenchmarkScore] = {}

        for cat in categories:
            if cat == BenchmarkCategory.OVERALL:
                continue
            results[cat.value] = self.run_category(cat, context)

        # Compute overall
        all_scores = [s.score for s in results.values() if s.tests_run > 0]
        overall_score = statistics.mean(all_scores) if all_scores else 0.0
        total_run = sum(s.tests_run for s in results.values())
        total_passed = sum(s.tests_passed for s in results.values())
        total_failed = sum(s.tests_failed for s in results.values())
        total_skipped = sum(s.tests_skipped for s in results.values())

        results["overall"] = BenchmarkScore(
            category=BenchmarkCategory.OVERALL,
            score=overall_score,
            tests_run=total_run,
            tests_passed=total_passed,
            tests_failed=total_failed,
            tests_skipped=total_skipped,
            grade=_compute_grade(overall_score),
        )

        return results


# ============================================================================
# AdversarialValidator — façade
# ============================================================================


class AdversarialValidator:
    """End-to-end adversarial validation engine.

    Provides:
    - Run adversarial probes against a stealth context
    - Benchmark stealth readiness across categories
    - Track validation history
    - Dashboard-ready data
    """

    def __init__(self, suite_name: str = "default"):
        self._suite = ValidationSuite(suite_name)
        self._runner = StealthBenchmarkRunner(self._suite)
        self._history: list[dict[str, Any]] = []
        self._lock = Lock()

    # ── Probing ───────────────────────────────────────────────

    def run_probes(
        self,
        context: dict[str, Any],
        category: BenchmarkCategory | None = None,
    ) -> list[ProbeResult]:
        """Run adversarial probes against a stealth context."""
        probes = (
            self._suite.get_probes_by_category(category)
            if category
            else self._suite.probes
        )

        results: list[ProbeResult] = []
        for probe in probes:
            if probe.check_fn:
                try:
                    tr = probe.check_fn(context)
                    evaded = tr.status in (TestStatus.PASSED, TestStatus.WARNING)
                    confidence = tr.score
                except Exception as e:
                    tr = TestResult(
                        test_name=probe.name,
                        status=TestStatus.ERROR,
                        score=0.0,
                        details=str(e),
                        detection_vector=probe.detection_vector,
                    )
                    evaded = False
                    confidence = 0.0
            else:
                tr = TestResult(
                    test_name=probe.name,
                    status=TestStatus.SKIPPED,
                    score=0.0,
                    detection_vector=probe.detection_vector,
                )
                evaded = False
                confidence = 0.0

            results.append(ProbeResult(
                probe=probe,
                test_result=tr,
                evaded=evaded,
                confidence=confidence,
            ))

        return results

    # ── Benchmarking ──────────────────────────────────────────

    def run_benchmark(
        self,
        context: dict[str, Any],
    ) -> dict[str, BenchmarkScore]:
        """Run full stealth benchmark and track result."""
        scores = self._runner.run_all(context)

        entry = {
            "timestamp": time.time(),
            "overall_score": scores["overall"].score,
            "overall_grade": scores["overall"].grade,
            "categories": {k: v.to_dict() for k, v in scores.items()},
        }
        with self._lock:
            self._history.append(entry)

        return scores

    def get_benchmark_history(self) -> list[dict[str, Any]]:
        """Get history of benchmark runs."""
        with self._lock:
            return list(self._history)

    def clear_history(self) -> int:
        """Clear benchmark history. Returns count cleared."""
        with self._lock:
            count = len(self._history)
            self._history.clear()
            return count

    # ── Signatures ────────────────────────────────────────────

    def get_signatures(self) -> list[dict[str, Any]]:
        """Get known detection signatures."""
        return [s.to_dict() for s in get_default_signatures()]

    def test_against_signatures(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Test stealth context against all known detection signatures."""
        results: list[dict[str, Any]] = []
        probe_results = self.run_probes(context)
        vector_map: dict[str, ProbeResult] = {
            pr.probe.detection_vector.value: pr for pr in probe_results
        }

        for sig in get_default_signatures():
            sig_evaded = True
            sig_score = 1.0
            details: list[dict[str, Any]] = []
            for vec in sig.detection_vectors:
                pr = vector_map.get(vec.value)
                if pr:
                    details.append(pr.to_dict())
                    if not pr.evaded:
                        sig_evaded = False
                    sig_score = min(sig_score, pr.confidence)

            results.append({
                "signature": sig.to_dict(),
                "evaded": sig_evaded,
                "confidence": round(sig_score, 4),
                "probe_results": details,
            })

        return results

    # ── Suite info ────────────────────────────────────────────

    def get_suite(self) -> dict[str, Any]:
        """Get validation suite information."""
        return self._suite.to_dict()

    def get_probes(self) -> list[dict[str, Any]]:
        """Get all available probes."""
        return [p.to_dict() for p in self._suite.probes]

    # ── Stats & dashboard ─────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        with self._lock:
            runs = len(self._history)
            if runs > 0:
                latest = self._history[-1]
                avg_score = statistics.mean(h["overall_score"] for h in self._history)
            else:
                latest = None
                avg_score = 0.0

        return {
            "total_runs": runs,
            "probes_available": len(self._suite.probes),
            "signatures_available": len(get_default_signatures()),
            "categories": len(BenchmarkCategory) - 1,  # minus OVERALL
            "detection_vectors": len(DetectionVector),
            "average_score": round(avg_score, 2),
            "latest_score": latest["overall_score"] if latest else None,
            "latest_grade": latest["overall_grade"] if latest else None,
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get dashboard-ready data."""
        stats = self.get_stats()
        return {
            "suite": self.get_suite(),
            "stats": stats,
            "signatures": self.get_signatures(),
            "history": self.get_benchmark_history()[-10:],  # last 10
            "detection_vectors": [v.value for v in DetectionVector],
            "benchmark_categories": [c.value for c in BenchmarkCategory],
            "test_statuses": [s.value for s in TestStatus],
        }


# ============================================================================
# Module-level functions
# ============================================================================


def get_detection_vectors() -> list[str]:
    """Get all detection vector names."""
    return [v.value for v in DetectionVector]


def get_benchmark_categories() -> list[str]:
    """Get all benchmark category names."""
    return [c.value for c in BenchmarkCategory]


def get_test_statuses() -> list[str]:
    """Get all test status values."""
    return [s.value for s in TestStatus]
