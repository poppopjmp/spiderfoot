"""
Tests for spiderfoot.report_generator — Report Generator Service.

Covers the full pipeline: preprocess → context window → LLM → assemble.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.reporting.report_generator import (
    GeneratedReport,
    GeneratedSection,
    ReportFormat,
    ReportGenerator,
    ReportGeneratorConfig,
    ReportType,
    _EXECUTIVE_PROMPT,
    _RECOMMENDATIONS_PROMPT,
    _SECTION_PROMPTS,
)
from spiderfoot.llm_client import LLMConfig, LLMProvider, LLMResponse, LLMUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_events(count=20, target="example.com"):
    """Generate synthetic scan events for testing."""
    event_types = [
        ("VULNERABILITY_CVE_CRITICAL", "CVE-2024-9999 in nginx"),
        ("IP_ADDRESS", "192.168.1.1"),
        ("EMAILADDR", "admin@example.com"),
        ("DOMAIN_NAME", "sub.example.com"),
        ("TCP_PORT_OPEN", "80/tcp open"),
        ("WEBSERVER_BANNER", "nginx/1.24.0"),
        ("SOCIAL_MEDIA", "Twitter: @example"),
        ("LEAKSITE_CONTENT", "Credentials found"),
        ("PHONE_NUMBER", "+1-555-0100"),
        ("RAW_RIR_DATA", "AS12345"),
    ]

    events = []
    for i in range(count):
        etype, edata = event_types[i % len(event_types)]
        events.append({
            "type": etype,
            "data": f"{edata} #{i}",
            "module": f"sfp_test_{i % 5}",
            "source_event": target,
            "confidence": 80 + (i % 20),
        })
    return events


def _scan_metadata(target="example.com"):
    return {
        "scan_id": "SCAN-001",
        "target": target,
        "started": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestReportGeneratorConfig:
    """Tests for ReportGeneratorConfig."""

    def test_default_config(self):
        cfg = ReportGeneratorConfig()
        assert cfg.report_type == ReportType.FULL
        assert cfg.report_format == ReportFormat.MARKDOWN
        assert cfg.generate_executive_summary is True
        assert cfg.generate_recommendations is True
        assert cfg.generate_section_analysis is True
        assert cfg.language == "English"
        assert cfg.preprocessor_config is not None
        assert cfg.window_config is not None
        assert cfg.llm_config is not None
        assert cfg.llm_config.provider == LLMProvider.MOCK

    def test_custom_config(self):
        cfg = ReportGeneratorConfig(
            report_type=ReportType.EXECUTIVE,
            report_format=ReportFormat.JSON,
            language="French",
            custom_instructions="Focus on APT activity.",
            report_title="Custom Report",
        )
        assert cfg.report_type == ReportType.EXECUTIVE
        assert cfg.language == "French"
        assert cfg.custom_instructions == "Focus on APT activity."
        assert cfg.report_title == "Custom Report"

    def test_none_sub_configs_get_defaults(self):
        cfg = ReportGeneratorConfig(
            preprocessor_config=None,
            window_config=None,
            llm_config=None,
        )
        assert cfg.preprocessor_config is not None
        assert cfg.window_config is not None
        assert cfg.llm_config is not None


# ---------------------------------------------------------------------------
# ReportFormat / ReportType enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_report_format_values(self):
        assert ReportFormat.MARKDOWN.value == "markdown"
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PLAIN_TEXT.value == "plain_text"
        assert ReportFormat.JSON.value == "json"

    def test_report_type_values(self):
        assert ReportType.EXECUTIVE.value == "executive"
        assert ReportType.TECHNICAL.value == "technical"
        assert ReportType.FULL.value == "full"
        assert ReportType.RISK_ASSESSMENT.value == "risk_assessment"
        assert ReportType.RECOMMENDATIONS.value == "recommendations"


# ---------------------------------------------------------------------------
# GeneratedSection tests
# ---------------------------------------------------------------------------

class TestGeneratedSection:
    def test_default_section(self):
        s = GeneratedSection()
        assert s.title == ""
        assert s.content == ""
        assert s.token_count == 0
        assert s.latency_ms == 0.0

    def test_populated_section(self):
        s = GeneratedSection(
            title="Threat Intelligence",
            content="Critical threats found...",
            section_type="threat_intelligence",
            token_count=150,
            latency_ms=500.0,
            model="gpt-4",
            source_event_count=10,
        )
        assert s.title == "Threat Intelligence"
        assert s.token_count == 150
        assert s.source_event_count == 10


# ---------------------------------------------------------------------------
# GeneratedReport tests
# ---------------------------------------------------------------------------

class TestGeneratedReport:
    def _make_report(self):
        report = GeneratedReport(
            title="OSINT Report: example.com",
            scan_id="SCAN-001",
            scan_target="example.com",
            executive_summary="Critical risks identified.",
            recommendations="1. Patch nginx immediately.",
            sections=[
                GeneratedSection(
                    title="Threat Intelligence",
                    content="APT activity detected.",
                    section_type="threat_intelligence",
                    token_count=100,
                    source_event_count=5,
                ),
                GeneratedSection(
                    title="Infrastructure",
                    content="3 open ports found.",
                    section_type="infrastructure",
                    token_count=80,
                    source_event_count=3,
                ),
            ],
            metadata={
                "statistics": {
                    "after_filter": 20,
                    "events_by_risk": {"CRITICAL": 2, "HIGH": 5, "LOW": 13},
                }
            },
            total_tokens_used=250,
            generation_time_ms=1500.0,
        )
        return report

    def test_markdown_output(self):
        report = self._make_report()
        md = report.markdown
        assert "# OSINT Report: example.com" in md
        assert "**Target:** example.com" in md
        assert "**Scan ID:** SCAN-001" in md
        assert "## Executive Summary" in md
        assert "Critical risks identified." in md
        assert "## Threat Intelligence" in md
        assert "APT activity detected." in md
        assert "## Infrastructure" in md
        assert "## Recommendations" in md
        assert "1500ms" in md
        assert "250 tokens" in md

    def test_plain_text_output(self):
        report = self._make_report()
        txt = report.plain_text
        assert "OSINT Report: example.com" in txt
        # Markdown symbols stripped
        assert "# " not in txt
        assert "## " not in txt

    def test_as_dict_output(self):
        report = self._make_report()
        d = report.as_dict
        assert d["title"] == "OSINT Report: example.com"
        assert d["scan_id"] == "SCAN-001"
        assert d["scan_target"] == "example.com"
        assert d["executive_summary"] == "Critical risks identified."
        assert d["recommendations"] == "1. Patch nginx immediately."
        assert len(d["sections"]) == 2
        assert d["sections"][0]["title"] == "Threat Intelligence"
        assert d["total_tokens_used"] == 250

    def test_markdown_with_no_summary(self):
        report = GeneratedReport(title="Test Report")
        md = report.markdown
        assert "# Test Report" in md
        assert "Executive Summary" not in md

    def test_markdown_with_empty_sections(self):
        report = GeneratedReport(title="Empty", sections=[])
        md = report.markdown
        assert "# Empty" in md

    def test_metadata_statistics_displayed(self):
        report = self._make_report()
        md = report.markdown
        assert "Total Findings" in md
        assert "Risk Distribution" in md
        assert "CRITICAL" in md

    def test_as_dict_serializable(self):
        report = self._make_report()
        # Must be JSON-serializable
        serialized = json.dumps(report.as_dict)
        assert serialized
        parsed = json.loads(serialized)
        assert parsed["title"] == "OSINT Report: example.com"


# ---------------------------------------------------------------------------
# Prompt templates tests
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_section_prompts_exist(self):
        assert "Threat Intelligence" in _SECTION_PROMPTS
        assert "Vulnerability Assessment" in _SECTION_PROMPTS
        assert "Data Leak Exposure" in _SECTION_PROMPTS
        assert "Infrastructure Analysis" in _SECTION_PROMPTS

    def test_executive_prompt_non_empty(self):
        assert len(_EXECUTIVE_PROMPT) > 50
        assert "executive" in _EXECUTIVE_PROMPT.lower()

    def test_recommendations_prompt_has_structure(self):
        assert "Priority" in _RECOMMENDATIONS_PROMPT
        assert "remediation" in _RECOMMENDATIONS_PROMPT


# ---------------------------------------------------------------------------
# ReportGenerator — integration with mock LLM
# ---------------------------------------------------------------------------

class TestReportGeneratorGenerate:
    """Tests that exercise the full pipeline with MOCK LLM provider."""

    def test_full_report_generation(self):
        generator = ReportGenerator()
        events = _make_events(30)
        report = generator.generate(events, _scan_metadata())

        assert report.title == "OSINT Report: example.com"
        assert report.scan_id == "SCAN-001"
        assert report.scan_target == "example.com"
        assert report.executive_summary != ""
        assert report.recommendations != ""
        assert report.generation_time_ms > 0
        assert report.metadata.get("statistics") is not None

    def test_empty_events(self):
        generator = ReportGenerator()
        report = generator.generate([], _scan_metadata())
        assert report.executive_summary == "No findings to report."
        assert len(report.sections) == 0

    def test_no_metadata(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(5))
        assert report.scan_target == ""
        assert "Unknown" in report.title

    def test_executive_only_mode(self):
        cfg = ReportGeneratorConfig(
            generate_executive_summary=True,
            generate_recommendations=False,
            generate_section_analysis=False,
        )
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(15), _scan_metadata())
        assert report.executive_summary != ""
        assert len(report.sections) == 0
        assert report.recommendations == ""

    def test_recommendations_only_mode(self):
        cfg = ReportGeneratorConfig(
            generate_executive_summary=False,
            generate_recommendations=True,
            generate_section_analysis=False,
        )
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(15), _scan_metadata())
        assert report.executive_summary == ""
        assert report.recommendations != ""

    def test_section_analysis_only_mode(self):
        cfg = ReportGeneratorConfig(
            generate_executive_summary=False,
            generate_recommendations=False,
            generate_section_analysis=True,
        )
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(15), _scan_metadata())
        assert report.executive_summary == ""
        assert report.recommendations == ""
        # May or may not have sections depending on windowing

    def test_custom_title(self):
        cfg = ReportGeneratorConfig(report_title="My Custom Report")
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(10), _scan_metadata())
        assert report.title == "My Custom Report"

    def test_report_type_stored(self):
        cfg = ReportGeneratorConfig(report_type=ReportType.RISK_ASSESSMENT)
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(5), _scan_metadata())
        assert report.report_type == ReportType.RISK_ASSESSMENT

    def test_report_format_stored(self):
        cfg = ReportGeneratorConfig(report_format=ReportFormat.HTML)
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(5), _scan_metadata())
        assert report.format == ReportFormat.HTML

    def test_custom_instructions_included(self):
        cfg = ReportGeneratorConfig(custom_instructions="Focus on APT28.")
        generator = ReportGenerator(cfg)
        # Generate will pass custom instructions to LLM
        report = generator.generate(_make_events(5), _scan_metadata())
        assert report.executive_summary != ""

    def test_non_english_language(self):
        cfg = ReportGeneratorConfig(language="Japanese")
        generator = ReportGenerator(cfg)
        report = generator.generate(_make_events(5), _scan_metadata())
        assert report.executive_summary != ""

    def test_metadata_contains_statistics(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(20), _scan_metadata())
        stats = report.metadata.get("statistics", {})
        assert "before" in stats or "after_filter" in stats

    def test_metadata_contains_windowing(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(20), _scan_metadata())
        windowing = report.metadata.get("windowing", {})
        assert "windows" in windowing
        assert "coverage_pct" in windowing

    def test_total_tokens_tracked(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(20), _scan_metadata())
        assert report.total_tokens_used > 0

    def test_callback_invoked(self):
        sections_seen = []

        def on_section(title, content):
            sections_seen.append(title)

        cfg = ReportGeneratorConfig(on_section_complete=on_section)
        generator = ReportGenerator(cfg)
        generator.generate(_make_events(15), _scan_metadata())
        assert "Executive Summary" in sections_seen
        assert "Recommendations" in sections_seen

    def test_callback_error_handled(self):
        def bad_callback(title, content):
            raise ValueError("oops")

        cfg = ReportGeneratorConfig(on_section_complete=bad_callback)
        generator = ReportGenerator(cfg)
        # Should not raise
        report = generator.generate(_make_events(10), _scan_metadata())
        assert report is not None


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------

class TestConvenienceMethods:
    def test_generate_executive_only(self):
        generator = ReportGenerator()
        summary = generator.generate_executive_only(_make_events(10), _scan_metadata())
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_recommendations_only(self):
        generator = ReportGenerator()
        recs = generator.generate_recommendations_only(_make_events(10), _scan_metadata())
        assert isinstance(recs, str)
        assert len(recs) > 0

    def test_executive_empty_events(self):
        generator = ReportGenerator()
        summary = generator.generate_executive_only([], _scan_metadata())
        assert summary == "No findings to report."

    def test_recommendations_empty_events(self):
        generator = ReportGenerator()
        recs = generator.generate_recommendations_only([], _scan_metadata())
        # Empty events -> no findings
        assert recs == ""


# ---------------------------------------------------------------------------
# from_env factory
# ---------------------------------------------------------------------------

class TestFromEnv:
    def test_from_env_creates_generator(self):
        with patch.dict("os.environ", {
            "SF_LLM_PROVIDER": "mock",
            "SF_LLM_MODEL": "test-model",
        }):
            generator = ReportGenerator.from_env()
            assert generator is not None
            assert generator.config.llm_config.provider == LLMProvider.MOCK


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_event(self):
        generator = ReportGenerator()
        events = [{"type": "IP_ADDRESS", "data": "1.2.3.4", "module": "sfp_test"}]
        report = generator.generate(events, _scan_metadata())
        assert report is not None
        assert report.generation_time_ms > 0

    def test_all_same_type_events(self):
        generator = ReportGenerator()
        events = [
            {"type": "IP_ADDRESS", "data": f"10.0.0.{i}", "module": "sfp_test"}
            for i in range(50)
        ]
        report = generator.generate(events, _scan_metadata())
        assert report is not None

    def test_large_event_count(self):
        generator = ReportGenerator()
        events = _make_events(200)
        report = generator.generate(events, _scan_metadata())
        assert report is not None
        # Preprocessor caps at max_total_events (default 500)
        assert report.metadata.get("statistics") is not None

    def test_report_markdown_property_idempotent(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(10), _scan_metadata())
        md1 = report.markdown
        md2 = report.markdown
        assert md1 == md2

    def test_report_as_dict_is_json_safe(self):
        generator = ReportGenerator()
        report = generator.generate(_make_events(10), _scan_metadata())
        # Should not raise
        serialized = json.dumps(report.as_dict, default=str)
        assert serialized
