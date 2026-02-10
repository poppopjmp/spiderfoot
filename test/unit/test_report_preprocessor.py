"""Tests for LLM report preprocessor."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from spiderfoot.report_preprocessor import (
    NormalizedEvent,
    PreprocessorConfig,
    ReportContext,
    ReportPreprocessor,
    ReportSection,
    ReportSectionType,
    RiskLevel,
    _categorize_event_type,
    _classify_risk,
    _estimate_tokens,
    _make_dedup_key,
    _normalize_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_event(
    event_type="IP_ADDRESS",
    data="192.168.1.1",
    module="sfp_test",
    confidence=80,
    risk=50,
    **kwargs,
):
    """Factory for raw event dicts."""
    return {
        "event_type": event_type,
        "data": data,
        "module": module,
        "confidence": confidence,
        "risk": risk,
        "timestamp": time.time(),
        "event_id": f"evt-{hash(data) % 10000}",
        "source_event_id": "",
        "tags": [],
        "metadata": {},
        **kwargs,
    }


def _sample_events():
    """A diverse set of sample scan events."""
    return [
        _make_event("IP_ADDRESS", "10.0.0.1", "sfp_dns", confidence=90, risk=30),
        _make_event("IP_ADDRESS", "10.0.0.2", "sfp_dns", confidence=90, risk=20),
        _make_event("DOMAIN_NAME", "example.com", "sfp_dns", confidence=95, risk=10),
        _make_event("DOMAIN_NAME", "Example.COM.", "sfp_cert", confidence=85, risk=10),  # duplicate
        _make_event("MALICIOUS_IPADDR", "203.0.113.5", "sfp_threatfox", confidence=70, risk=80),
        _make_event("VULNERABILITY_CVE_CRITICAL", "CVE-2024-1234", "sfp_vulndb", confidence=95, risk=95),
        _make_event("VULNERABILITY_CVE_HIGH", "CVE-2024-5678", "sfp_vulndb", confidence=85, risk=70),
        _make_event("EMAIL_ADDRESS", "Admin@EXAMPLE.COM", "sfp_email", confidence=80, risk=40),
        _make_event("EMAIL_ADDRESS", "admin@example.com", "sfp_whois", confidence=75, risk=40),  # duplicate
        _make_event("USERNAME", "admin_user", "sfp_social", confidence=60, risk=30),
        _make_event("LEAKED_CREDENTIAL", "admin@example.com:password", "sfp_breach", confidence=90, risk=90),
        _make_event("WEBSERVER_BANNER", "Apache/2.4.51", "sfp_spider", confidence=70, risk=20),
        _make_event("URL_WEB_FRAMEWORK", "https://example.com/#section", "sfp_spider", confidence=60, risk=10),
        _make_event("TCP_PORT_OPEN", "22", "sfp_portscan", confidence=100, risk=30),
        _make_event("TCP_PORT_OPEN", "443", "sfp_portscan", confidence=100, risk=10),
        _make_event("GEOINFO", "San Francisco, US", "sfp_geo", confidence=80, risk=0),
        _make_event("SOCIAL_MEDIA", "@example on Twitter", "sfp_social", confidence=65, risk=10),
        _make_event("SSL_CERTIFICATE_ISSUED", "*.example.com", "sfp_cert", confidence=90, risk=5),
    ]


# ===========================================================================
# Helper functions
# ===========================================================================

class TestEstimateTokens:
    def test_empty_string(self):
        assert _estimate_tokens("") == 1  # min 1

    def test_normal_text(self):
        text = "Hello world this is a test"
        tokens = _estimate_tokens(text)
        assert tokens == len(text) // 4

    def test_custom_chars_per_token(self):
        text = "x" * 100
        assert _estimate_tokens(text, chars_per_token=10) == 10


class TestClassifyRisk:
    def test_critical(self):
        assert _classify_risk(95, {"critical": 80, "high": 60, "medium": 40, "low": 20}) == RiskLevel.CRITICAL

    def test_high(self):
        assert _classify_risk(65, {"critical": 80, "high": 60, "medium": 40, "low": 20}) == RiskLevel.HIGH

    def test_medium(self):
        assert _classify_risk(45, {"critical": 80, "high": 60, "medium": 40, "low": 20}) == RiskLevel.MEDIUM

    def test_low(self):
        assert _classify_risk(25, {"critical": 80, "high": 60, "medium": 40, "low": 20}) == RiskLevel.LOW

    def test_info(self):
        assert _classify_risk(5, {"critical": 80, "high": 60, "medium": 40, "low": 20}) == RiskLevel.INFO


class TestCategorizeEventType:
    def test_malicious(self):
        assert _categorize_event_type("MALICIOUS_IPADDR") == "threat"

    def test_vulnerability(self):
        assert _categorize_event_type("VULNERABILITY_CVE_HIGH") == "vulnerability"

    def test_ip_address(self):
        assert _categorize_event_type("IP_ADDRESS") == "network"

    def test_domain(self):
        assert _categorize_event_type("DOMAIN_NAME") == "infrastructure"

    def test_email(self):
        assert _categorize_event_type("EMAIL_ADDRESS") == "identity"

    def test_leaked(self):
        assert _categorize_event_type("LEAKED_CREDENTIAL") == "data_leak"

    def test_social(self):
        assert _categorize_event_type("SOCIAL_MEDIA") == "social"

    def test_geo(self):
        assert _categorize_event_type("GEOINFO") == "geolocation"

    def test_url(self):
        assert _categorize_event_type("URL_WEB_FRAMEWORK") == "web"

    def test_unknown(self):
        assert _categorize_event_type("SOME_UNKNOWN_TYPE") == "other"


class TestNormalizeData:
    def test_email_lowered(self):
        assert _normalize_data("Admin@EXAMPLE.COM", "EMAIL_ADDRESS") == "admin@example.com"

    def test_domain_lowered_and_stripped(self):
        assert _normalize_data("Example.COM.", "DOMAIN_NAME") == "example.com"

    def test_url_fragment_stripped(self):
        assert _normalize_data("https://example.com/page#section", "URL_WEB") == "https://example.com/page"

    def test_url_trailing_slash(self):
        assert _normalize_data("https://example.com/", "URL_WEB") == "https://example.com"

    def test_ip_leading_zeros(self):
        assert _normalize_data("010.000.001.001", "IP_ADDRESS") == "10.0.1.1"

    def test_ip_normal(self):
        assert _normalize_data("192.168.1.1", "IP_ADDRESS") == "192.168.1.1"

    def test_whitespace_stripped(self):
        assert _normalize_data("  data  ", "OTHER") == "data"


class TestMakeDedupKey:
    def test_deterministic(self):
        k1 = _make_dedup_key("IP", "1.2.3.4")
        k2 = _make_dedup_key("IP", "1.2.3.4")
        assert k1 == k2

    def test_different_types(self):
        k1 = _make_dedup_key("IP", "1.2.3.4")
        k2 = _make_dedup_key("DOMAIN", "1.2.3.4")
        assert k1 != k2


# ===========================================================================
# NormalizedEvent
# ===========================================================================

class TestNormalizedEvent:
    def test_priority_score_basic(self):
        evt = NormalizedEvent(risk=80, confidence=90, category="network")
        score = evt.priority_score
        assert 0 <= score <= 100

    def test_priority_score_threat_boost(self):
        evt_normal = NormalizedEvent(risk=50, confidence=50, category="network")
        evt_threat = NormalizedEvent(risk=50, confidence=50, category="threat")
        assert evt_threat.priority_score > evt_normal.priority_score

    def test_priority_score_capped_at_100(self):
        evt = NormalizedEvent(risk=100, confidence=100, category="threat")
        assert evt.priority_score == 100.0


# ===========================================================================
# ReportSection
# ===========================================================================

class TestReportSection:
    def test_has_content_empty(self):
        s = ReportSection(section_type=ReportSectionType.APPENDIX, title="Test")
        assert s.has_content is False

    def test_has_content_with_events(self):
        s = ReportSection(
            section_type=ReportSectionType.APPENDIX,
            title="Test",
            events=[NormalizedEvent(data="x")],
        )
        assert s.has_content is True

    def test_to_text(self):
        s = ReportSection(
            section_type=ReportSectionType.THREAT_INTELLIGENCE,
            title="Threats",
            events=[
                NormalizedEvent(
                    event_type="MALICIOUS_IP", data="1.2.3.4",
                    risk_level=RiskLevel.CRITICAL, confidence=90, module="sfp_x"
                ),
            ],
        )
        text = s.to_text()
        assert "## Threats" in text
        assert "MALICIOUS_IP" in text
        assert "1.2.3.4" in text
        assert "CRITICAL" in text

    def test_to_text_truncation(self):
        events = [
            NormalizedEvent(event_type="X", data=f"d{i}", risk_level=RiskLevel.INFO,
                            confidence=50, module="m")
            for i in range(10)
        ]
        s = ReportSection(
            section_type=ReportSectionType.APPENDIX,
            title="Many",
            events=events,
            max_events=3,
        )
        text = s.to_text()
        assert "7 more events" in text

    def test_event_count(self):
        s = ReportSection(
            section_type=ReportSectionType.APPENDIX,
            title="T",
            events=[NormalizedEvent(), NormalizedEvent()],
        )
        assert s.event_count == 2


# ===========================================================================
# ReportContext
# ===========================================================================

class TestReportContext:
    def test_total_events(self):
        ctx = ReportContext(sections=[
            ReportSection(section_type=ReportSectionType.APPENDIX, title="A",
                          events=[NormalizedEvent(), NormalizedEvent()]),
            ReportSection(section_type=ReportSectionType.APPENDIX, title="B",
                          events=[NormalizedEvent()]),
        ])
        assert ctx.total_events == 3

    def test_non_empty_sections(self):
        ctx = ReportContext(sections=[
            ReportSection(section_type=ReportSectionType.APPENDIX, title="A",
                          events=[NormalizedEvent()]),
            ReportSection(section_type=ReportSectionType.APPENDIX, title="B",
                          events=[]),
        ])
        assert len(ctx.non_empty_sections) == 1

    def test_to_text(self):
        ctx = ReportContext(
            scan_id="scan-123",
            scan_target="example.com",
            sections=[
                ReportSection(
                    section_type=ReportSectionType.THREAT_INTELLIGENCE,
                    title="Threats",
                    events=[NormalizedEvent(event_type="MAL", data="bad",
                                           risk_level=RiskLevel.HIGH,
                                           confidence=80, module="m")],
                ),
            ],
        )
        text = ctx.to_text()
        assert "example.com" in text
        assert "scan-123" in text
        assert "Threats" in text

    def test_to_text_with_token_budget(self):
        events = [NormalizedEvent(event_type="X", data=f"data-{i}" * 20,
                                  risk_level=RiskLevel.INFO, confidence=50, module="m")
                  for i in range(100)]
        ctx = ReportContext(
            scan_target="test",
            sections=[
                ReportSection(section_type=ReportSectionType.APPENDIX, title=f"S{i}",
                              events=events[:10])
                for i in range(10)
            ],
        )
        text = ctx.to_text(max_tokens=100)
        assert "truncated" in text


# ===========================================================================
# ReportPreprocessor — full pipeline
# ===========================================================================

class TestReportPreprocessor:
    def test_process_empty(self):
        pp = ReportPreprocessor()
        ctx = pp.process([])
        assert ctx.total_events == 0
        assert ctx.statistics["input_events"] == 0

    def test_process_basic(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events, {"scan_id": "s1", "target": "example.com"})

        assert ctx.scan_id == "s1"
        assert ctx.scan_target == "example.com"
        assert ctx.total_events > 0
        assert ctx.preprocessing_ms > 0
        assert ctx.token_estimate > 0

    def test_deduplication(self):
        pp = ReportPreprocessor()
        events = _sample_events()  # contains duplicates (example.com domain, admin@example.com email)
        ctx = pp.process(events)
        # Should have fewer events than input
        assert ctx.statistics["duplicates_removed"] > 0
        assert ctx.statistics["after_dedup"] < ctx.statistics["input_events"]

    def test_dedup_disabled(self):
        config = PreprocessorConfig(enable_dedup=False)
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        assert ctx.statistics["after_dedup"] == ctx.statistics["input_events"]

    def test_risk_classification(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        risk_dist = ctx.statistics["events_by_risk"]
        # Should have at least one CRITICAL (CVE-2024-1234 risk=95)
        assert risk_dist.get("CRITICAL", 0) >= 1

    def test_category_distribution(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        cats = ctx.statistics["events_by_category"]
        assert "network" in cats
        assert "infrastructure" in cats
        assert "threat" in cats

    def test_sections_populated(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        non_empty = ctx.non_empty_sections
        assert len(non_empty) >= 4  # At least: exec summary, threats, vulns, identity

    def test_executive_summary_has_top_events(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        exec_section = next(
            s for s in ctx.sections
            if s.section_type == ReportSectionType.EXECUTIVE_SUMMARY
        )
        assert exec_section.event_count > 0
        assert exec_section.event_count <= 10
        # Top event should be high priority
        assert exec_section.events[0].priority_score >= 50

    def test_threat_section_contains_malicious(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        threat_section = next(
            (s for s in ctx.sections
             if s.section_type == ReportSectionType.THREAT_INTELLIGENCE),
            None,
        )
        assert threat_section is not None
        types = {e.event_type for e in threat_section.events}
        assert "MALICIOUS_IPADDR" in types

    def test_filter_by_min_confidence(self):
        config = PreprocessorConfig(min_confidence=80)
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        # Some events have confidence < 80 and should be filtered
        assert ctx.statistics["filtered_low_confidence"] > 0

    def test_filter_by_min_risk(self):
        config = PreprocessorConfig(min_risk=50)
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        assert ctx.statistics["filtered_low_risk"] > 0

    def test_filter_exclude_event_types(self):
        config = PreprocessorConfig(exclude_event_types=["IP_ADDRESS"])
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        # IP_ADDRESS events should be removed
        for section in ctx.sections:
            for evt in section.events:
                assert evt.event_type != "IP_ADDRESS"

    def test_filter_include_categories(self):
        config = PreprocessorConfig(include_categories=["threat", "vulnerability"])
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        for section in ctx.sections:
            for evt in section.events:
                assert evt.category in ("threat", "vulnerability")

    def test_max_total_events_cap(self):
        config = PreprocessorConfig(max_total_events=5)
        pp = ReportPreprocessor(config)
        events = _sample_events()
        ctx = pp.process(events)
        # After filtering, only 5 unique events remain (but exec summary
        # copies top events, so total_events counts them across sections)
        assert ctx.statistics["after_filter"] <= 5

    def test_events_sorted_by_priority(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        for section in ctx.non_empty_sections:
            if section.event_count >= 2:
                scores = [e.priority_score for e in section.events]
                assert scores == sorted(scores, reverse=True), \
                    f"Section {section.title} not sorted by priority"

    def test_token_estimate_reasonable(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        # Should be positive and reasonable (not millions)
        assert 10 < ctx.token_estimate < 100000

    def test_statistics_keys(self):
        pp = ReportPreprocessor()
        events = _sample_events()
        ctx = pp.process(events)
        expected_keys = {
            "input_events", "after_dedup", "after_filter",
            "duplicates_removed", "filtered_low_confidence",
            "filtered_low_risk", "events_by_risk",
            "events_by_category", "sections_populated", "token_estimate",
        }
        assert expected_keys.issubset(set(ctx.statistics.keys()))

    def test_legacy_event_keys(self):
        """Test that legacy SpiderFootEvent key names (eventType, hash, etc.) work."""
        pp = ReportPreprocessor()
        events = [
            {
                "eventType": "MALICIOUS_IPADDR",
                "data": "1.2.3.4",
                "module": "sfp_test",
                "confidence": 80,
                "risk": 90,
                "generated": time.time(),
                "hash": "abc123",
                "sourceEventHash": "def456",
            }
        ]
        ctx = pp.process(events)
        assert ctx.total_events > 0


# ===========================================================================
# RiskLevel enum ordering
# ===========================================================================

class TestRiskLevel:
    def test_ordering(self):
        assert RiskLevel.INFO < RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH < RiskLevel.CRITICAL

    def test_values(self):
        assert RiskLevel.INFO == 0
        assert RiskLevel.CRITICAL == 4


# ===========================================================================
# ReportSectionType enum
# ===========================================================================

class TestReportSectionType:
    def test_all_types(self):
        assert len(ReportSectionType) == 12  # 12 section types
        assert ReportSectionType.EXECUTIVE_SUMMARY.value == "executive_summary"
        assert ReportSectionType.RECOMMENDATIONS.value == "recommendations"
