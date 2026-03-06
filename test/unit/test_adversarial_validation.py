# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_adversarial_validation
# Purpose:      Unit tests for S-010 — Adversarial validation & stealth benchmarks
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------

import threading

import pytest

from spiderfoot.recon.adversarial_validation import (
    AdversarialProbe,
    AdversarialValidator,
    BenchmarkCategory,
    BenchmarkScore,
    DetectionSignature,
    DetectionVector,
    ProbeResult,
    StealthBenchmarkRunner,
    TestResult,
    TestStatus,
    ValidationSuite,
    get_benchmark_categories,
    get_default_signatures,
    get_detection_vectors,
    get_test_statuses,
)


# ============================================================================
# Enums
# ============================================================================


class TestDetectionVector:
    def test_count(self):
        assert len(DetectionVector) == 18

    def test_values(self):
        assert DetectionVector.JA3_HASH.value == "ja3_hash"
        assert DetectionVector.DNS_LEAK.value == "dns_leak"


class TestBenchmarkCategory:
    def test_count(self):
        assert len(BenchmarkCategory) == 8

    def test_overall(self):
        assert BenchmarkCategory.OVERALL.value == "overall"


class TestTestStatus:
    def test_count(self):
        assert len(TestStatus) == 5

    def test_values(self):
        expected = {"passed", "failed", "skipped", "error", "warning"}
        assert {s.value for s in TestStatus} == expected


# ============================================================================
# Data classes
# ============================================================================


class TestTestResult:
    def test_creation(self):
        r = TestResult(test_name="test1", status=TestStatus.PASSED, score=0.95)
        assert r.test_name == "test1"
        assert r.score == 0.95

    def test_to_dict(self):
        r = TestResult(test_name="abc", status=TestStatus.FAILED, score=0.0,
                       detection_vector=DetectionVector.DNS_LEAK)
        d = r.to_dict()
        assert d["status"] == "failed"
        assert d["detection_vector"] == "dns_leak"

    def test_default_values(self):
        r = TestResult()
        assert r.status == TestStatus.PASSED
        assert r.score == 1.0


class TestBenchmarkScore:
    def test_pass_rate_zero(self):
        s = BenchmarkScore()
        assert s.pass_rate == 0.0

    def test_pass_rate(self):
        s = BenchmarkScore(tests_run=10, tests_passed=8)
        assert abs(s.pass_rate - 0.8) < 0.01

    def test_to_dict(self):
        s = BenchmarkScore(category=BenchmarkCategory.TLS, score=85.0,
                           tests_run=5, tests_passed=4, grade="A-")
        d = s.to_dict()
        assert d["category"] == "tls"
        assert d["grade"] == "A-"
        assert d["pass_rate"] == 0.8


class TestAdversarialProbe:
    def test_to_dict(self):
        p = AdversarialProbe(
            name="test_probe", description="desc",
            detection_vector=DetectionVector.JA3_HASH,
            category=BenchmarkCategory.TLS, severity="high")
        d = p.to_dict()
        assert d["name"] == "test_probe"
        assert d["detection_vector"] == "ja3_hash"
        assert d["category"] == "tls"


class TestProbeResult:
    def test_to_dict(self):
        pr = ProbeResult(evaded=True, confidence=0.9)
        d = pr.to_dict()
        assert d["evaded"] is True
        assert d["confidence"] == 0.9


class TestDetectionSignature:
    def test_to_dict(self):
        s = DetectionSignature(
            name="JA3 Test", vendor="test",
            detection_vectors=[DetectionVector.JA3_HASH],
            evasion_techniques=["tls_randomization"])
        d = s.to_dict()
        assert d["name"] == "JA3 Test"
        assert "ja3_hash" in d["detection_vectors"]

    def test_defaults(self):
        s = get_default_signatures()
        assert len(s) == 10
        assert all(isinstance(sig, DetectionSignature) for sig in s)


# ============================================================================
# ValidationSuite
# ============================================================================


class TestValidationSuite:
    def test_default_probes(self):
        s = ValidationSuite()
        assert len(s.probes) == 16

    def test_get_by_category(self):
        s = ValidationSuite()
        tls = s.get_probes_by_category(BenchmarkCategory.TLS)
        assert len(tls) == 3
        assert all(p.category == BenchmarkCategory.TLS for p in tls)

    def test_get_by_vector(self):
        s = ValidationSuite()
        ja3 = s.get_probes_by_vector(DetectionVector.JA3_HASH)
        assert len(ja3) >= 1

    def test_add_probe(self):
        s = ValidationSuite()
        initial = len(s.probes)
        s.add_probe(AdversarialProbe(name="custom"))
        assert len(s.probes) == initial + 1

    def test_to_dict(self):
        s = ValidationSuite()
        d = s.to_dict()
        assert d["probe_count"] == 16
        assert "categories" in d

    # ── individual probe checks ───────────────────────────────────

    def test_check_tls_rotation_pass(self):
        r = ValidationSuite._check_tls_rotation({
            "tls_fingerprint_rotated": True, "tls_fingerprint_diversity": 0.8})
        assert r.status == TestStatus.PASSED

    def test_check_tls_rotation_warning(self):
        r = ValidationSuite._check_tls_rotation({
            "tls_fingerprint_rotated": True, "tls_fingerprint_diversity": 0.3})
        assert r.status == TestStatus.WARNING

    def test_check_tls_rotation_fail(self):
        r = ValidationSuite._check_tls_rotation({
            "tls_fingerprint_rotated": False})
        assert r.status == TestStatus.FAILED

    def test_check_ja3_pass(self):
        r = ValidationSuite._check_ja3_uniqueness({
            "ja3_unique_count": 9, "ja3_total_connections": 10})
        assert r.status == TestStatus.PASSED

    def test_check_ja3_fail(self):
        r = ValidationSuite._check_ja3_uniqueness({
            "ja3_unique_count": 1, "ja3_total_connections": 10})
        assert r.status == TestStatus.FAILED

    def test_check_ja4_pass(self):
        r = ValidationSuite._check_ja4_variance({"ja4_variance": 0.9})
        assert r.status == TestStatus.PASSED

    def test_check_ja4_fail(self):
        r = ValidationSuite._check_ja4_variance({"ja4_variance": 0.1})
        assert r.status == TestStatus.FAILED

    def test_check_timing_pass(self):
        r = ValidationSuite._check_timing_jitter({"request_interval_variance": 0.5})
        assert r.status == TestStatus.PASSED

    def test_check_timing_warning(self):
        r = ValidationSuite._check_timing_jitter({"request_interval_variance": 0.15})
        assert r.status == TestStatus.WARNING

    def test_check_timing_fail(self):
        r = ValidationSuite._check_timing_jitter({"request_interval_variance": 0.01})
        assert r.status == TestStatus.FAILED

    def test_check_rate_pass(self):
        r = ValidationSuite._check_rate_pattern({"requests_per_second": 3})
        assert r.status == TestStatus.PASSED

    def test_check_rate_warning(self):
        r = ValidationSuite._check_rate_pattern({"requests_per_second": 7})
        assert r.status == TestStatus.WARNING

    def test_check_rate_fail(self):
        r = ValidationSuite._check_rate_pattern({"requests_per_second": 50})
        assert r.status == TestStatus.FAILED

    def test_check_tcp_pass(self):
        r = ValidationSuite._check_tcp_fingerprint({"tcp_fingerprint_masked": True})
        assert r.status == TestStatus.PASSED

    def test_check_tcp_warn(self):
        r = ValidationSuite._check_tcp_fingerprint({"tcp_fingerprint_masked": False})
        assert r.status == TestStatus.WARNING

    def test_check_header_order_pass(self):
        r = ValidationSuite._check_header_order({"header_order_consistent": True})
        assert r.status == TestStatus.PASSED

    def test_check_header_order_fail(self):
        r = ValidationSuite._check_header_order({"header_order_consistent": False})
        assert r.status == TestStatus.FAILED

    def test_check_http2_pass(self):
        r = ValidationSuite._check_http2_settings({"http2_settings_mimicked": True})
        assert r.status == TestStatus.PASSED

    def test_check_http2_warn(self):
        r = ValidationSuite._check_http2_settings({"http2_settings_mimicked": False})
        assert r.status == TestStatus.WARNING

    def test_check_ua_pass(self):
        r = ValidationSuite._check_user_agent_consistency({"user_agent": "Mozilla/5.0 Chrome/120"})
        assert r.status == TestStatus.PASSED

    def test_check_ua_fail(self):
        r = ValidationSuite._check_user_agent_consistency({"user_agent": "python-requests/2.28"})
        assert r.status == TestStatus.FAILED

    def test_check_ua_warn(self):
        r = ValidationSuite._check_user_agent_consistency({"user_agent": "custom-agent/1.0"})
        assert r.status == TestStatus.WARNING

    def test_check_dns_pass(self):
        r = ValidationSuite._check_dns_encryption({"dns_encrypted": True, "dns_protocol": "doh"})
        assert r.status == TestStatus.PASSED

    def test_check_dns_fail(self):
        r = ValidationSuite._check_dns_encryption({"dns_encrypted": False})
        assert r.status == TestStatus.FAILED

    def test_check_cookie_pass(self):
        r = ValidationSuite._check_cookie_handling({"cookie_jar_managed": True})
        assert r.status == TestStatus.PASSED

    def test_check_cookie_warn(self):
        r = ValidationSuite._check_cookie_handling({"cookie_jar_managed": False})
        assert r.status == TestStatus.WARNING

    def test_check_behavioral_pass(self):
        r = ValidationSuite._check_behavioral_pattern({"navigation_randomized": True, "behavioral_variance": 0.7})
        assert r.status == TestStatus.PASSED

    def test_check_behavioral_fail(self):
        r = ValidationSuite._check_behavioral_pattern({"navigation_randomized": False, "behavioral_variance": 0.1})
        assert r.status == TestStatus.FAILED

    def test_check_ip_pass(self):
        r = ValidationSuite._check_ip_reputation({"ip_reputation_score": 0.9})
        assert r.status == TestStatus.PASSED

    def test_check_ip_warn(self):
        r = ValidationSuite._check_ip_reputation({"ip_reputation_score": 0.3})
        assert r.status == TestStatus.WARNING

    def test_check_geo_pass(self):
        r = ValidationSuite._check_geolocation({"geolocation_consistent": True})
        assert r.status == TestStatus.PASSED

    def test_check_geo_fail(self):
        r = ValidationSuite._check_geolocation({"geolocation_consistent": False})
        assert r.status == TestStatus.FAILED

    def test_check_captcha_pass(self):
        r = ValidationSuite._check_captcha_handling({"captcha_encountered": False})
        assert r.status == TestStatus.PASSED

    def test_check_captcha_warn(self):
        r = ValidationSuite._check_captcha_handling({"captcha_encountered": True, "captcha_solved": True})
        assert r.status == TestStatus.WARNING

    def test_check_captcha_fail(self):
        r = ValidationSuite._check_captcha_handling({"captcha_encountered": True, "captcha_solved": False})
        assert r.status == TestStatus.FAILED

    def test_check_session_pass(self):
        r = ValidationSuite._check_session_anomaly({"session_appears_natural": True})
        assert r.status == TestStatus.PASSED

    def test_check_session_warn(self):
        r = ValidationSuite._check_session_anomaly({"session_appears_natural": False})
        assert r.status == TestStatus.WARNING


# ============================================================================
# StealthBenchmarkRunner
# ============================================================================


class TestStealthBenchmarkRunner:
    def _good_context(self) -> dict:
        return {
            "tls_fingerprint_rotated": True, "tls_fingerprint_diversity": 0.9,
            "ja3_unique_count": 9, "ja3_total_connections": 10,
            "ja4_variance": 0.85,
            "request_interval_variance": 0.5, "requests_per_second": 3,
            "tcp_fingerprint_masked": True,
            "header_order_consistent": True, "http2_settings_mimicked": True,
            "user_agent": "Mozilla/5.0 Chrome/120",
            "dns_encrypted": True, "dns_protocol": "doh",
            "cookie_jar_managed": True,
            "navigation_randomized": True, "behavioral_variance": 0.7,
            "ip_reputation_score": 0.9, "geolocation_consistent": True,
            "captcha_encountered": False, "session_appears_natural": True,
        }

    def test_run_category_tls(self):
        runner = StealthBenchmarkRunner()
        score = runner.run_category(BenchmarkCategory.TLS, self._good_context())
        assert score.tests_run == 3
        assert score.tests_passed == 3
        assert score.score == 100.0

    def test_run_category_empty(self):
        runner = StealthBenchmarkRunner()
        score = runner.run_category(BenchmarkCategory.OVERALL, {})
        assert score.tests_run == 0

    def test_run_all_good(self):
        runner = StealthBenchmarkRunner()
        results = runner.run_all(self._good_context())
        assert "overall" in results
        assert results["overall"].score > 80.0
        assert results["overall"].grade in ("A+", "A", "A-", "B+")

    def test_run_all_bad(self):
        runner = StealthBenchmarkRunner()
        results = runner.run_all({})
        assert results["overall"].score < 50.0

    def test_grade_computation(self):
        from spiderfoot.recon.adversarial_validation import _compute_grade
        assert _compute_grade(97) == "A+"
        assert _compute_grade(92) == "A"
        assert _compute_grade(87) == "A-"
        assert _compute_grade(82) == "B+"
        assert _compute_grade(77) == "B"
        assert _compute_grade(72) == "B-"
        assert _compute_grade(67) == "C+"
        assert _compute_grade(62) == "C"
        assert _compute_grade(57) == "C-"
        assert _compute_grade(52) == "D"
        assert _compute_grade(30) == "F"


# ============================================================================
# AdversarialValidator (façade)
# ============================================================================


class TestAdversarialValidator:
    def _good_context(self) -> dict:
        return {
            "tls_fingerprint_rotated": True, "tls_fingerprint_diversity": 0.9,
            "ja3_unique_count": 9, "ja3_total_connections": 10,
            "ja4_variance": 0.85,
            "request_interval_variance": 0.5, "requests_per_second": 3,
            "tcp_fingerprint_masked": True,
            "header_order_consistent": True, "http2_settings_mimicked": True,
            "user_agent": "Mozilla/5.0 Chrome/120",
            "dns_encrypted": True, "dns_protocol": "doh",
            "cookie_jar_managed": True,
            "navigation_randomized": True, "behavioral_variance": 0.7,
            "ip_reputation_score": 0.9, "geolocation_consistent": True,
            "captcha_encountered": False, "session_appears_natural": True,
        }

    def test_creation(self):
        v = AdversarialValidator()
        assert len(v.get_probes()) == 16

    def test_run_probes(self):
        v = AdversarialValidator()
        results = v.run_probes(self._good_context())
        assert len(results) == 16
        assert all(isinstance(r, ProbeResult) for r in results)

    def test_run_probes_category(self):
        v = AdversarialValidator()
        results = v.run_probes(self._good_context(), BenchmarkCategory.TLS)
        assert len(results) == 3

    def test_run_probes_bad_context(self):
        v = AdversarialValidator()
        results = v.run_probes({})
        failed = [r for r in results if not r.evaded]
        assert len(failed) > 0

    def test_run_benchmark(self):
        v = AdversarialValidator()
        scores = v.run_benchmark(self._good_context())
        assert "overall" in scores
        assert scores["overall"].score > 80.0

    def test_benchmark_history(self):
        v = AdversarialValidator()
        v.run_benchmark(self._good_context())
        v.run_benchmark({})
        history = v.get_benchmark_history()
        assert len(history) == 2
        assert history[0]["overall_score"] > history[1]["overall_score"]

    def test_clear_history(self):
        v = AdversarialValidator()
        v.run_benchmark({})
        count = v.clear_history()
        assert count == 1
        assert len(v.get_benchmark_history()) == 0

    def test_get_signatures(self):
        v = AdversarialValidator()
        sigs = v.get_signatures()
        assert len(sigs) == 10

    def test_test_against_signatures(self):
        v = AdversarialValidator()
        results = v.test_against_signatures(self._good_context())
        assert len(results) == 10
        evaded_count = sum(1 for r in results if r["evaded"])
        assert evaded_count > 5

    def test_get_suite(self):
        v = AdversarialValidator()
        s = v.get_suite()
        assert s["name"] == "default"
        assert s["probe_count"] == 16

    def test_get_stats(self):
        v = AdversarialValidator()
        stats = v.get_stats()
        assert stats["total_runs"] == 0
        assert stats["probes_available"] == 16
        assert stats["signatures_available"] == 10
        assert stats["detection_vectors"] == 18

    def test_get_stats_after_run(self):
        v = AdversarialValidator()
        v.run_benchmark(self._good_context())
        stats = v.get_stats()
        assert stats["total_runs"] == 1
        assert stats["latest_score"] is not None
        assert stats["latest_grade"] is not None

    def test_get_dashboard_data(self):
        v = AdversarialValidator()
        v.run_benchmark(self._good_context())
        dash = v.get_dashboard_data()
        assert "suite" in dash
        assert "stats" in dash
        assert "signatures" in dash
        assert "history" in dash
        assert len(dash["detection_vectors"]) == 18
        assert len(dash["benchmark_categories"]) == 8

    def test_concurrent(self):
        v = AdversarialValidator()
        errors: list[str] = []

        def runner():
            try:
                for _ in range(5):
                    v.run_benchmark(self._good_context())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=runner) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(v.get_benchmark_history()) == 20


# ============================================================================
# Module-level functions
# ============================================================================


class TestModuleFunctions:
    def test_get_detection_vectors(self):
        vecs = get_detection_vectors()
        assert len(vecs) == 18
        assert "ja3_hash" in vecs

    def test_get_benchmark_categories(self):
        cats = get_benchmark_categories()
        assert len(cats) == 8
        assert "overall" in cats

    def test_get_test_statuses(self):
        statuses = get_test_statuses()
        assert len(statuses) == 5
        assert "passed" in statuses
