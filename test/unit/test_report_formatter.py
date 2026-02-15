"""
Tests for spiderfoot.report_formatter — Report Output Formatters.

Covers HTML, Markdown, JSON, Plain Text, CSV rendering.
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from spiderfoot.reporting.report_formatter import (
    FormatterConfig,
    ReportFormatter,
    Theme,
    _esc,
    _slugify,
)
from spiderfoot.reporting.report_generator import (
    GeneratedReport,
    GeneratedSection,
    ReportFormat,
    ReportType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_report() -> GeneratedReport:
    """Create a realistic sample report for testing."""
    return GeneratedReport(
        title="OSINT Report: example.com",
        scan_id="SCAN-001",
        scan_target="example.com",
        executive_summary="Critical vulnerabilities found in nginx.",
        recommendations="1. Patch nginx\n2. Rotate credentials",
        report_type=ReportType.FULL,
        format=ReportFormat.MARKDOWN,
        sections=[
            GeneratedSection(
                title="Threat Intelligence",
                content="APT28 activity detected targeting web servers.",
                section_type="threat_intelligence",
                token_count=120,
                latency_ms=450.0,
                model="gpt-4",
                source_event_count=8,
            ),
            GeneratedSection(
                title="Infrastructure Analysis",
                content="3 open ports: 80, 443, 8080.",
                section_type="infrastructure_analysis",
                token_count=90,
                latency_ms=320.0,
                model="gpt-4",
                source_event_count=5,
            ),
        ],
        metadata={
            "statistics": {
                "after_filter": 25,
                "events_by_risk": {
                    "CRITICAL": 3,
                    "HIGH": 7,
                    "MEDIUM": 10,
                    "LOW": 5,
                },
            }
        },
        total_tokens_used=500,
        generation_time_ms=1200.0,
    )


def _empty_report() -> GeneratedReport:
    return GeneratedReport(title="Empty Report")


def _minimal_report() -> GeneratedReport:
    return GeneratedReport(
        title="Minimal",
        executive_summary="Short summary.",
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_esc_basic(self):
        assert _esc("<script>") == "&lt;script&gt;"
        assert _esc("a & b") == "a &amp; b"
        assert _esc('"quoted"') == "&quot;quoted&quot;"

    def test_esc_plain(self):
        assert _esc("hello world") == "hello world"

    def test_slugify_basic(self):
        assert _slugify("Threat Intelligence") == "threat-intelligence"
        assert _slugify("Infrastructure Analysis") == "infrastructure-analysis"

    def test_slugify_special_chars(self):
        assert _slugify("Data & Leak (Exposure)") == "data-leak-exposure"
        assert _slugify("Test!!!") == "test"

    def test_slugify_already_slug(self):
        assert _slugify("simple") == "simple"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestFormatterConfig:
    def test_defaults(self):
        cfg = FormatterConfig()
        assert cfg.theme == Theme.AUTO
        assert cfg.include_toc is True
        assert cfg.include_metadata_header is True
        assert cfg.include_generation_footer is True
        assert cfg.json_indent == 2
        assert cfg.csv_delimiter == ","
        assert cfg.company_name == "SpiderFoot"

    def test_custom(self):
        cfg = FormatterConfig(
            theme=Theme.DARK,
            include_toc=False,
            company_name="ACME Corp",
            custom_css="body { font-size: 14px; }",
        )
        assert cfg.theme == Theme.DARK
        assert cfg.include_toc is False
        assert cfg.company_name == "ACME Corp"


class TestThemeEnum:
    def test_values(self):
        assert Theme.LIGHT.value == "light"
        assert Theme.DARK.value == "dark"
        assert Theme.AUTO.value == "auto"


# ---------------------------------------------------------------------------
# HTML rendering tests
# ---------------------------------------------------------------------------

class TestHTMLRendering:
    def test_full_html_structure(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "<!DOCTYPE html>" in html_out
        assert "<html" in html_out
        assert "</html>" in html_out
        assert "<head>" in html_out
        assert "<body>" in html_out

    def test_html_title(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "<title>OSINT Report: example.com</title>" in html_out
        assert "<h1>OSINT Report: example.com</h1>" in html_out

    def test_html_metadata(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "example.com" in html_out
        assert "SCAN-001" in html_out
        assert "25" in html_out  # after_filter

    def test_html_risk_badges(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "risk-critical" in html_out
        assert "risk-high" in html_out
        assert "CRITICAL: 3" in html_out

    def test_html_toc(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "Table of Contents" in html_out
        assert "#executive-summary" in html_out
        assert "#threat-intelligence" in html_out
        assert "#recommendations" in html_out

    def test_html_no_toc(self):
        formatter = ReportFormatter(FormatterConfig(include_toc=False))
        html_out = formatter.to_html(_sample_report())
        assert "Table of Contents" not in html_out

    def test_html_sections(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "Threat Intelligence" in html_out
        assert "APT28 activity" in html_out
        assert "Infrastructure Analysis" in html_out

    def test_html_executive_summary(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "Executive Summary" in html_out
        assert "Critical vulnerabilities" in html_out

    def test_html_recommendations(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "Recommendations" in html_out
        assert "Patch nginx" in html_out

    def test_html_footer(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_sample_report())
        assert "500 tokens" in html_out
        assert "SpiderFoot" in html_out

    def test_html_no_footer(self):
        formatter = ReportFormatter(FormatterConfig(include_generation_footer=False))
        html_out = formatter.to_html(_sample_report())
        assert '<div class="footer">' not in html_out

    def test_html_dark_theme(self):
        formatter = ReportFormatter(FormatterConfig(theme=Theme.DARK))
        html_out = formatter.to_html(_sample_report())
        assert "theme-dark" in html_out

    def test_html_light_theme(self):
        formatter = ReportFormatter(FormatterConfig(theme=Theme.LIGHT))
        html_out = formatter.to_html(_sample_report())
        assert "theme-light" in html_out

    def test_html_auto_theme(self):
        formatter = ReportFormatter(FormatterConfig(theme=Theme.AUTO))
        html_out = formatter.to_html(_sample_report())
        assert "theme-auto" in html_out
        assert "prefers-color-scheme" in html_out

    def test_html_custom_css(self):
        formatter = ReportFormatter(FormatterConfig(
            custom_css="body { font-size: 18px; }"
        ))
        html_out = formatter.to_html(_sample_report())
        assert "font-size: 18px" in html_out

    def test_html_custom_company_name(self):
        formatter = ReportFormatter(FormatterConfig(company_name="ACME"))
        html_out = formatter.to_html(_sample_report())
        assert "ACME" in html_out

    def test_html_escapes_xss(self):
        report = GeneratedReport(
            title='<script>alert("xss")</script>',
            executive_summary='<img onerror="hack">',
        )
        formatter = ReportFormatter()
        html_out = formatter.to_html(report)
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out
        assert '<img onerror' not in html_out

    def test_html_empty_report(self):
        formatter = ReportFormatter()
        html_out = formatter.to_html(_empty_report())
        assert "Empty Report" in html_out
        assert "Executive Summary" not in html_out

    def test_html_no_metadata(self):
        formatter = ReportFormatter(FormatterConfig(include_metadata_header=False))
        html_out = formatter.to_html(_sample_report())
        # meta-table class appears in CSS but no actual <table class="meta-table"> in body
        assert '<table class="meta-table">' not in html_out


# ---------------------------------------------------------------------------
# Markdown rendering tests
# ---------------------------------------------------------------------------

class TestMarkdownRendering:
    def test_markdown_title(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert md.startswith("# OSINT Report: example.com")

    def test_markdown_metadata(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "**Target:** example.com" in md
        assert "**Scan ID:** SCAN-001" in md
        assert "**Total Findings:** 25" in md

    def test_markdown_toc(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "## Table of Contents" in md
        assert "[Executive Summary](#executive-summary)" in md
        assert "[Threat Intelligence](#threat-intelligence)" in md

    def test_markdown_no_toc(self):
        formatter = ReportFormatter(FormatterConfig(include_toc=False))
        md = formatter.to_markdown(_sample_report())
        assert "Table of Contents" not in md

    def test_markdown_sections(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "## Threat Intelligence" in md
        assert "APT28 activity" in md
        assert "## Infrastructure Analysis" in md

    def test_markdown_executive_summary(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "## Executive Summary" in md
        assert "Critical vulnerabilities" in md

    def test_markdown_recommendations(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "## Recommendations" in md
        assert "Patch nginx" in md

    def test_markdown_footer(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_sample_report())
        assert "500 tokens" in md
        assert "SpiderFoot" in md

    def test_markdown_heading_offset(self):
        formatter = ReportFormatter(FormatterConfig(heading_offset=2))
        md = formatter.to_markdown(_sample_report())
        assert "### OSINT Report:" in md  # H1 + 2 = H3
        assert "#### Table of Contents" in md  # H2 + 2 = H4

    def test_markdown_empty_report(self):
        formatter = ReportFormatter()
        md = formatter.to_markdown(_empty_report())
        assert "# Empty Report" in md

    def test_markdown_no_metadata(self):
        formatter = ReportFormatter(FormatterConfig(include_metadata_header=False))
        md = formatter.to_markdown(_sample_report())
        assert "**Target:**" not in md


# ---------------------------------------------------------------------------
# JSON rendering tests
# ---------------------------------------------------------------------------

class TestJSONRendering:
    def test_valid_json(self):
        formatter = ReportFormatter()
        result = formatter.to_json(_sample_report())
        parsed = json.loads(result)
        assert parsed is not None

    def test_json_schema_version(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_sample_report()))
        assert parsed["schema_version"] == "1.0.0"

    def test_json_report_info(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_sample_report()))
        assert parsed["report"]["title"] == "OSINT Report: example.com"
        assert parsed["report"]["scan_id"] == "SCAN-001"
        assert parsed["report"]["scan_target"] == "example.com"
        assert parsed["report"]["report_type"] == "full"

    def test_json_sections(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_sample_report()))
        sections = parsed["sections"]
        assert len(sections) == 2
        assert sections[0]["title"] == "Threat Intelligence"
        assert sections[0]["token_count"] == 120
        assert sections[0]["model"] == "gpt-4"

    def test_json_no_raw_sections(self):
        formatter = ReportFormatter(FormatterConfig(include_raw_sections=False))
        parsed = json.loads(formatter.to_json(_sample_report()))
        sections = parsed["sections"]
        assert len(sections) == 2
        # Should only have title and content
        assert "token_count" not in sections[0]
        assert "model" not in sections[0]

    def test_json_executive_summary(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_sample_report()))
        assert parsed["executive_summary"] == "Critical vulnerabilities found in nginx."

    def test_json_metadata(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_sample_report()))
        assert parsed["metadata"]["total_tokens_used"] == 500
        assert parsed["metadata"]["generation_time_ms"] == 1200.0

    def test_json_indent(self):
        formatter = ReportFormatter(FormatterConfig(json_indent=4))
        result = formatter.to_json(_sample_report())
        # 4-space indent should be present
        assert "    " in result

    def test_json_empty_report(self):
        formatter = ReportFormatter()
        parsed = json.loads(formatter.to_json(_empty_report()))
        assert parsed["executive_summary"] is None
        assert parsed["recommendations"] is None
        assert len(parsed["sections"]) == 0

    def test_json_generator_name(self):
        formatter = ReportFormatter(FormatterConfig(company_name="ACME"))
        parsed = json.loads(formatter.to_json(_sample_report()))
        assert parsed["generator"] == "ACME"


# ---------------------------------------------------------------------------
# Plain text rendering tests
# ---------------------------------------------------------------------------

class TestPlainTextRendering:
    def test_plain_text_title(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "OSINT REPORT: EXAMPLE.COM" in txt

    def test_plain_text_metadata(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "Target:         example.com" in txt
        assert "Scan ID:        SCAN-001" in txt
        assert "Total Findings: 25" in txt

    def test_plain_text_sections(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "EXECUTIVE SUMMARY" in txt
        assert "Critical vulnerabilities" in txt
        assert "THREAT INTELLIGENCE" in txt
        assert "INFRASTRUCTURE ANALYSIS" in txt
        assert "RECOMMENDATIONS" in txt

    def test_plain_text_no_markup(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "##" not in txt
        assert "<h" not in txt
        assert "<div" not in txt

    def test_plain_text_footer(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "500 tokens" in txt

    def test_plain_text_separators(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_sample_report())
        assert "=" * 72 in txt
        assert "-" * 72 in txt

    def test_plain_text_empty(self):
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(_empty_report())
        assert "EMPTY REPORT" in txt


# ---------------------------------------------------------------------------
# CSV rendering tests
# ---------------------------------------------------------------------------

class TestCSVRendering:
    def test_csv_header(self):
        formatter = ReportFormatter()
        result = formatter.to_csv(_sample_report())
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == ["Section", "Type", "Events", "Tokens", "Content (excerpt)"]

    def test_csv_rows(self):
        formatter = ReportFormatter()
        result = formatter.to_csv(_sample_report())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        # Header + executive + 2 sections + recommendations = 5
        assert len(rows) == 5
        assert rows[1][0] == "Executive Summary"
        assert rows[2][0] == "Threat Intelligence"
        assert rows[3][0] == "Infrastructure Analysis"
        assert rows[4][0] == "Recommendations"

    def test_csv_event_counts(self):
        formatter = ReportFormatter()
        result = formatter.to_csv(_sample_report())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert rows[2][2] == "8"  # Threat Intelligence events
        assert rows[3][2] == "5"  # Infrastructure events

    def test_csv_custom_delimiter(self):
        formatter = ReportFormatter(FormatterConfig(csv_delimiter="\t"))
        result = formatter.to_csv(_sample_report())
        reader = csv.reader(io.StringIO(result), delimiter="\t")
        rows = list(reader)
        assert len(rows) == 5

    def test_csv_empty_report(self):
        formatter = ReportFormatter()
        result = formatter.to_csv(_empty_report())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1  # Header only

    def test_csv_excerpt_truncated(self):
        long_content = "A" * 500
        report = GeneratedReport(
            title="Test",
            sections=[
                GeneratedSection(
                    title="Long Section",
                    content=long_content,
                    section_type="test",
                    source_event_count=1,
                )
            ],
        )
        formatter = ReportFormatter()
        result = formatter.to_csv(report)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        # Excerpt should be max 200 chars
        assert len(rows[1][4]) <= 200


# ---------------------------------------------------------------------------
# Dispatch render() tests
# ---------------------------------------------------------------------------

class TestRenderDispatch:
    def test_render_markdown(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "markdown")
        assert "# OSINT Report" in result

    def test_render_html(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "html")
        assert "<!DOCTYPE html>" in result

    def test_render_json(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "json")
        parsed = json.loads(result)
        assert parsed["schema_version"] == "1.0.0"

    def test_render_plain_text(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "plain_text")
        assert "OSINT REPORT" in result

    def test_render_csv(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "csv")
        assert "Section,Type" in result

    def test_render_case_insensitive(self):
        formatter = ReportFormatter()
        result = formatter.render(_sample_report(), "HTML")
        assert "<!DOCTYPE html>" in result

    def test_render_unsupported_format(self):
        formatter = ReportFormatter()
        with pytest.raises(ValueError, match="Unsupported format"):
            formatter.render(_sample_report(), "pdf")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_formats_work_for_empty_report(self):
        report = _empty_report()
        formatter = ReportFormatter()
        for fmt in ["markdown", "html", "json", "plain_text", "csv"]:
            result = formatter.render(report, fmt)
            assert len(result) > 0

    def test_report_with_only_executive(self):
        report = _minimal_report()
        formatter = ReportFormatter()
        html_out = formatter.to_html(report)
        assert "Executive Summary" in html_out
        assert "Short summary." in html_out
        assert "Recommendations" not in html_out

    def test_special_chars_in_section_titles(self):
        report = GeneratedReport(
            title="Test & <Report>",
            sections=[
                GeneratedSection(
                    title="O'Brien's Analysis",
                    content="Content here",
                )
            ],
        )
        formatter = ReportFormatter()
        html_out = formatter.to_html(report)
        assert "&amp;" in html_out
        assert "O&#x27;Brien" in html_out or "O'Brien" in html_out  # varies

    def test_unicode_content(self):
        report = GeneratedReport(
            title="Unicode Test",
            executive_summary="Findings: \u2022 bullet \u2013 dash \u00e9 accent",
        )
        formatter = ReportFormatter()
        md = formatter.to_markdown(report)
        assert "\u2022" in md
        html_out = formatter.to_html(report)
        assert "Unicode Test" in html_out

    def test_multiline_content_preserved(self):
        report = GeneratedReport(
            title="Test",
            executive_summary="Line 1\nLine 2\nLine 3",
        )
        formatter = ReportFormatter()
        txt = formatter.to_plain_text(report)
        assert "Line 1\nLine 2\nLine 3" in txt
