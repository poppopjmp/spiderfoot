"""
Report Output Formatters for SpiderFoot.

Renders GeneratedReport objects into multiple output formats:
  - Markdown (enhanced with TOC, anchors)
  - HTML (professional standalone page with inline CSS)
  - JSON (structured with schema metadata)
  - Plain text (clean, no markup)
  - CSV summary (finding-level tabular export)

Usage::

    from spiderfoot.report_formatter import ReportFormatter
    from spiderfoot.report_generator import GeneratedReport

    formatter = ReportFormatter()
    html = formatter.to_html(report)
    md = formatter.to_markdown(report)
    csv = formatter.to_csv(report)
"""

from __future__ import annotations

import csv
import html
import io
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from spiderfoot.report_generator import GeneratedReport, GeneratedSection

log = logging.getLogger("spiderfoot.report_formatter")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Theme(Enum):
    """Visual theme for HTML output."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"  # Respects prefers-color-scheme


@dataclass
class FormatterConfig:
    """Configuration for report formatting."""
    # HTML options
    theme: Theme = Theme.AUTO
    include_toc: bool = True
    include_metadata_header: bool = True
    include_generation_footer: bool = True
    custom_css: str = ""
    company_name: str = "SpiderFoot"
    logo_url: str = ""

    # Markdown options
    heading_offset: int = 0  # Add to heading levels (0 = H1 for title)

    # JSON options
    json_indent: int = 2
    include_raw_sections: bool = True

    # CSV options
    csv_delimiter: str = ","


# ---------------------------------------------------------------------------
# CSS Themes
# ---------------------------------------------------------------------------

_CSS_BASE = """
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --bg-code: #f1f3f5;
    --text-primary: #212529;
    --text-secondary: #6c757d;
    --border-color: #dee2e6;
    --accent: #059cd7;
    --risk-critical: #dc3545;
    --risk-high: #fd7e14;
    --risk-medium: #ffc107;
    --risk-low: #28a745;
    --risk-info: #17a2b8;
    --link-color: #059cd7;
}
@media (prefers-color-scheme: dark) {
    :root.theme-auto {
        --bg-primary: #1b1b1b;
        --bg-secondary: #2d2d2d;
        --bg-code: #2d2d2d;
        --text-primary: #e0e0e0;
        --text-secondary: #a0a0a0;
        --border-color: #444444;
        --link-color: #4db8e8;
    }
}
:root.theme-dark {
    --bg-primary: #1b1b1b;
    --bg-secondary: #2d2d2d;
    --bg-code: #2d2d2d;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0a0;
    --border-color: #444444;
    --link-color: #4db8e8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}
a { color: var(--link-color); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 1.8rem; margin: 1.5rem 0 0.5rem; border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; }
h2 { font-size: 1.4rem; margin: 1.5rem 0 0.5rem; color: var(--accent); }
h3 { font-size: 1.15rem; margin: 1rem 0 0.3rem; }
p { margin: 0.5rem 0; }
pre, code { font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; }
pre { background: var(--bg-code); padding: 1rem; border-radius: 6px; overflow-x: auto; margin: 0.8rem 0; }
code { background: var(--bg-code); padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.9em; }
.report-header {
    border-bottom: 3px solid var(--accent);
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
}
.meta-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0 1rem;
}
.meta-table td {
    padding: 0.3rem 0.8rem;
    border-bottom: 1px solid var(--border-color);
}
.meta-table td:first-child {
    font-weight: 600;
    width: 160px;
    color: var(--text-secondary);
}
.toc {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem 1.5rem;
    margin: 1rem 0 1.5rem;
}
.toc h3 { margin: 0 0 0.5rem; font-size: 1rem; }
.toc ol { padding-left: 1.5rem; }
.toc li { margin: 0.25rem 0; }
.section { margin: 1.5rem 0; }
.section-content {
    background: var(--bg-secondary);
    border-left: 4px solid var(--accent);
    padding: 1rem 1.2rem;
    border-radius: 0 6px 6px 0;
    margin: 0.5rem 0;
    white-space: pre-wrap;
}
.risk-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 3px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #fff;
}
.risk-critical { background: var(--risk-critical); }
.risk-high { background: var(--risk-high); }
.risk-medium { background: var(--risk-medium); color: #212529; }
.risk-low { background: var(--risk-low); }
.risk-info { background: var(--risk-info); }
.risk-distribution {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 0.5rem 0;
}
.footer {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
    font-size: 0.85rem;
    color: var(--text-secondary);
    text-align: center;
}
ul, ol { padding-left: 1.5rem; margin: 0.5rem 0; }
li { margin: 0.25rem 0; }
table:not(.meta-table) {
    width: 100%;
    border-collapse: collapse;
    margin: 0.8rem 0;
}
table:not(.meta-table) th, table:not(.meta-table) td {
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--border-color);
    text-align: left;
}
table:not(.meta-table) th {
    background: var(--bg-secondary);
    font-weight: 600;
}
"""


# ---------------------------------------------------------------------------
# ReportFormatter
# ---------------------------------------------------------------------------

class ReportFormatter:
    """Renders GeneratedReport objects into various output formats."""

    def __init__(self, config: FormatterConfig | None = None) -> None:
        self.config = config or FormatterConfig()

    # -----------------------------------------------------------------------
    # HTML
    # -----------------------------------------------------------------------

    def to_html(self, report: GeneratedReport) -> str:
        """Render a full standalone HTML page from a report."""
        t0 = time.monotonic()
        theme_class = {
            Theme.LIGHT: "theme-light",
            Theme.DARK: "theme-dark",
            Theme.AUTO: "theme-auto",
        }[self.config.theme]

        parts: list[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append(f'<html lang="en" class="{theme_class}">')
        parts.append("<head>")
        parts.append('<meta charset="UTF-8">')
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        parts.append(f"<title>{_esc(report.title)}</title>")
        parts.append(f"<style>{_CSS_BASE}")
        if self.config.custom_css:
            parts.append(self.config.custom_css)
        parts.append("</style>")
        parts.append("</head>")
        parts.append("<body>")

        # Header
        parts.append('<div class="report-header">')
        parts.append(f"<h1>{_esc(report.title)}</h1>")
        if self.config.include_metadata_header:
            parts.append(self._html_metadata_table(report))
        parts.append("</div>")

        # Table of contents
        if self.config.include_toc:
            parts.append(self._html_toc(report))

        # Executive Summary
        if report.executive_summary:
            parts.append('<div class="section" id="executive-summary">')
            parts.append("<h2>Executive Summary</h2>")
            parts.append(f'<div class="section-content">{_esc(report.executive_summary)}</div>')
            parts.append("</div>")

        # Sections
        for i, section in enumerate(report.sections):
            anchor = _slugify(section.title)
            parts.append(f'<div class="section" id="{anchor}">')
            parts.append(f"<h2>{_esc(section.title)}</h2>")
            parts.append(f'<div class="section-content">{_esc(section.content)}</div>')
            parts.append("</div>")

        # Recommendations
        if report.recommendations:
            parts.append('<div class="section" id="recommendations">')
            parts.append("<h2>Recommendations</h2>")
            parts.append(f'<div class="section-content">{_esc(report.recommendations)}</div>')
            parts.append("</div>")

        # Footer
        if self.config.include_generation_footer:
            elapsed = (time.monotonic() - t0) * 1000
            parts.append('<div class="footer">')
            parts.append(
                f"Generated by {_esc(self.config.company_name)} "
                f"| Report generation: {report.generation_time_ms:.0f}ms "
                f"| {report.total_tokens_used} tokens "
                f"| Format rendering: {elapsed:.0f}ms"
            )
            parts.append("</div>")

        parts.append("</body>")
        parts.append("</html>")

        result = "\n".join(parts)
        log.info("Rendered HTML report: %d chars", len(result))
        return result

    def _html_metadata_table(self, report: GeneratedReport) -> str:
        rows = []
        if report.scan_target:
            rows.append(("Target", _esc(report.scan_target)))
        if report.scan_id:
            rows.append(("Scan ID", _esc(report.scan_id)))

        stats = report.metadata.get("statistics", {})
        if stats.get("after_filter"):
            rows.append(("Total Findings", str(stats["after_filter"])))

        risk_dist = stats.get("events_by_risk", {})
        if risk_dist:
            badges = []
            for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                count = risk_dist.get(level, 0)
                if count:
                    css_class = f"risk-{level.lower()}"
                    badges.append(
                        f'<span class="risk-badge {css_class}">'
                        f"{level}: {count}</span>"
                    )
            if badges:
                rows.append(("Risk Distribution", '<div class="risk-distribution">' + " ".join(badges) + "</div>"))

        if not rows:
            return ""

        cells = "".join(
            f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows
        )
        return f'<table class="meta-table"><tbody>{cells}</tbody></table>'

    def _html_toc(self, report: GeneratedReport) -> str:
        items = []
        if report.executive_summary:
            items.append('<li><a href="#executive-summary">Executive Summary</a></li>')
        for section in report.sections:
            anchor = _slugify(section.title)
            items.append(f'<li><a href="#{anchor}">{_esc(section.title)}</a></li>')
        if report.recommendations:
            items.append('<li><a href="#recommendations">Recommendations</a></li>')
        if not items:
            return ""
        return (
            '<div class="toc"><h3>Table of Contents</h3>'
            f'<ol>{"".join(items)}</ol></div>'
        )

    # -----------------------------------------------------------------------
    # Markdown (enhanced)
    # -----------------------------------------------------------------------

    def to_markdown(self, report: GeneratedReport) -> str:
        """Render an enhanced Markdown report with TOC and metadata."""
        offset = self.config.heading_offset
        h1 = "#" * (1 + offset)
        h2 = "#" * (2 + offset)
        h3 = "#" * (3 + offset)

        parts: list[str] = []
        parts.append(f"{h1} {report.title}")
        parts.append("")

        # Metadata
        if self.config.include_metadata_header:
            if report.scan_target:
                parts.append(f"**Target:** {report.scan_target}  ")
            if report.scan_id:
                parts.append(f"**Scan ID:** {report.scan_id}  ")
            stats = report.metadata.get("statistics", {})
            if stats.get("after_filter"):
                parts.append(f"**Total Findings:** {stats['after_filter']}  ")
            risk_dist = stats.get("events_by_risk", {})
            if risk_dist:
                risk_str = " | ".join(
                    f"**{k}:** {v}" for k, v in sorted(risk_dist.items())
                )
                parts.append(f"**Risk:** {risk_str}  ")
            parts.append("")
            parts.append("---")
            parts.append("")

        # TOC
        if self.config.include_toc:
            toc = self._markdown_toc(report)
            if toc:
                parts.append(f"{h2} Table of Contents")
                parts.append("")
                parts.append(toc)
                parts.append("")

        # Executive Summary
        if report.executive_summary:
            parts.append(f"{h2} Executive Summary")
            parts.append("")
            parts.append(report.executive_summary)
            parts.append("")

        # Sections
        for section in report.sections:
            parts.append(f"{h2} {section.title}")
            parts.append("")
            parts.append(section.content)
            parts.append("")

        # Recommendations
        if report.recommendations:
            parts.append(f"{h2} Recommendations")
            parts.append("")
            parts.append(report.recommendations)
            parts.append("")

        # Footer
        if self.config.include_generation_footer:
            parts.append("---")
            parts.append("")
            parts.append(
                f"*Generated by {self.config.company_name} "
                f"| {report.generation_time_ms:.0f}ms "
                f"| {report.total_tokens_used} tokens*"
            )

        return "\n".join(parts)

    def _markdown_toc(self, report: GeneratedReport) -> str:
        items = []
        idx = 1
        if report.executive_summary:
            items.append(f"{idx}. [Executive Summary](#executive-summary)")
            idx += 1
        for section in report.sections:
            anchor = _slugify(section.title)
            items.append(f"{idx}. [{section.title}](#{anchor})")
            idx += 1
        if report.recommendations:
            items.append(f"{idx}. [Recommendations](#recommendations)")
        return "\n".join(items) if items else ""

    # -----------------------------------------------------------------------
    # JSON
    # -----------------------------------------------------------------------

    def to_json(self, report: GeneratedReport) -> str:
        """Render report as structured JSON with schema metadata."""
        data: dict[str, Any] = {
            "schema_version": "1.0.0",
            "generator": self.config.company_name,
            "report": {
                "title": report.title,
                "scan_id": report.scan_id,
                "scan_target": report.scan_target,
                "report_type": report.report_type.value,
                "format": "json",
            },
            "executive_summary": report.executive_summary or None,
            "recommendations": report.recommendations or None,
            "metadata": {
                "generation_time_ms": report.generation_time_ms,
                "total_tokens_used": report.total_tokens_used,
                **report.metadata,
            },
        }

        if self.config.include_raw_sections:
            data["sections"] = [
                {
                    "title": s.title,
                    "content": s.content,
                    "section_type": s.section_type,
                    "source_event_count": s.source_event_count,
                    "token_count": s.token_count,
                    "model": s.model,
                    "latency_ms": s.latency_ms,
                }
                for s in report.sections
            ]
        else:
            data["sections"] = [
                {"title": s.title, "content": s.content}
                for s in report.sections
            ]

        return json.dumps(data, indent=self.config.json_indent, default=str)

    # -----------------------------------------------------------------------
    # Plain text
    # -----------------------------------------------------------------------

    def to_plain_text(self, report: GeneratedReport) -> str:
        """Render report as clean plain text with no markup."""
        parts: list[str] = []
        width = 72

        parts.append("=" * width)
        parts.append(report.title.upper())
        parts.append("=" * width)
        parts.append("")

        if report.scan_target:
            parts.append(f"Target:         {report.scan_target}")
        if report.scan_id:
            parts.append(f"Scan ID:        {report.scan_id}")
        stats = report.metadata.get("statistics", {})
        if stats.get("after_filter"):
            parts.append(f"Total Findings: {stats['after_filter']}")
        parts.append("")

        if report.executive_summary:
            parts.append("-" * width)
            parts.append("EXECUTIVE SUMMARY")
            parts.append("-" * width)
            parts.append("")
            parts.append(report.executive_summary)
            parts.append("")

        for section in report.sections:
            parts.append("-" * width)
            parts.append(section.title.upper())
            parts.append("-" * width)
            parts.append("")
            parts.append(section.content)
            parts.append("")

        if report.recommendations:
            parts.append("-" * width)
            parts.append("RECOMMENDATIONS")
            parts.append("-" * width)
            parts.append("")
            parts.append(report.recommendations)
            parts.append("")

        parts.append("=" * width)
        parts.append(
            f"Generated in {report.generation_time_ms:.0f}ms "
            f"| {report.total_tokens_used} tokens"
        )

        return "\n".join(parts)

    # -----------------------------------------------------------------------
    # CSV summary
    # -----------------------------------------------------------------------

    def to_csv(self, report: GeneratedReport) -> str:
        """Render a CSV summary of report sections.

        Produces a table with section title, type, event count,
        token count, and content excerpt.
        """
        output = io.StringIO()
        writer = csv.writer(output, delimiter=self.config.csv_delimiter)
        writer.writerow([
            "Section", "Type", "Events", "Tokens", "Content (excerpt)"
        ])

        if report.executive_summary:
            excerpt = report.executive_summary[:200].replace("\n", " ")
            writer.writerow([
                "Executive Summary", "executive_summary", "", "", excerpt
            ])

        for section in report.sections:
            excerpt = section.content[:200].replace("\n", " ")
            writer.writerow([
                section.title,
                section.section_type,
                section.source_event_count,
                section.token_count,
                excerpt,
            ])

        if report.recommendations:
            excerpt = report.recommendations[:200].replace("\n", " ")
            writer.writerow([
                "Recommendations", "recommendations", "", "", excerpt
            ])

        return output.getvalue()

    # -----------------------------------------------------------------------
    # Dispatch helper
    # -----------------------------------------------------------------------

    def render(self, report: GeneratedReport, fmt: str = "markdown") -> str:
        """Render a report in the specified format.

        Args:
            report: The generated report.
            fmt: One of 'markdown', 'html', 'json', 'plain_text', 'csv'.

        Returns:
            Rendered output string.

        Raises:
            ValueError: If the format is not supported.
        """
        renderers = {
            "markdown": self.to_markdown,
            "html": self.to_html,
            "json": self.to_json,
            "plain_text": self.to_plain_text,
            "csv": self.to_csv,
        }
        renderer = renderers.get(fmt.lower())
        if renderer is None:
            raise ValueError(
                f"Unsupported format: {fmt!r}. "
                f"Choose from: {', '.join(renderers)}"
            )
        return renderer(report)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape text."""
    return html.escape(str(text))


def _slugify(text: str) -> str:
    """Create a URL-safe anchor from text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")
