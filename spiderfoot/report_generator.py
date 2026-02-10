"""
Report Generator Service for SpiderFoot.

Orchestrates the full LLM-powered report generation pipeline:
   Raw Events → Preprocess → Context Window → LLM Generate → Assemble

This is the main entry point for generating OSINT scan reports.
It coordinates the preprocessor, context window manager, and LLM client
to produce coherent, multi-section reports.

Usage::

    from spiderfoot.report_generator import ReportGenerator, ReportGeneratorConfig

    generator = ReportGenerator(ReportGeneratorConfig())
    report = generator.generate(scan_events, scan_metadata)
    print(report.markdown)  # Full report in Markdown
    print(report.sections)  # Individual sections
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from spiderfoot.context_window import (
    ContextWindow,
    ContextWindowManager,
    WindowConfig,
)
from spiderfoot.llm_client import LLMClient, LLMConfig, LLMProvider
from spiderfoot.report_preprocessor import (
    PreprocessorConfig,
    ReportContext,
    ReportPreprocessor,
)

log = logging.getLogger("spiderfoot.report_generator")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReportFormat(Enum):
    """Output format for the generated report."""
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN_TEXT = "plain_text"
    JSON = "json"


class ReportType(Enum):
    """Type of report to generate."""
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    FULL = "full"
    RISK_ASSESSMENT = "risk_assessment"
    RECOMMENDATIONS = "recommendations"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ReportGeneratorConfig:
    """Configuration for the report generator."""
    # Report type
    report_type: ReportType = ReportType.FULL
    report_format: ReportFormat = ReportFormat.MARKDOWN

    # Component configs
    preprocessor_config: Optional[PreprocessorConfig] = None
    window_config: Optional[WindowConfig] = None
    llm_config: Optional[LLMConfig] = None

    # Generation settings
    generate_executive_summary: bool = True
    generate_recommendations: bool = True
    generate_section_analysis: bool = True

    # Customization
    report_title: str = ""
    custom_instructions: str = ""
    language: str = "English"

    # Callbacks
    on_section_complete: Optional[Callable[[str, str], None]] = None

    def __post_init__(self):
        if self.preprocessor_config is None:
            self.preprocessor_config = PreprocessorConfig()
        if self.window_config is None:
            self.window_config = WindowConfig()
        if self.llm_config is None:
            self.llm_config = LLMConfig(provider=LLMProvider.MOCK)


# ---------------------------------------------------------------------------
# Report data structures
# ---------------------------------------------------------------------------

@dataclass
class GeneratedSection:
    """A single generated report section."""
    title: str = ""
    content: str = ""
    section_type: str = ""
    token_count: int = 0
    latency_ms: float = 0.0
    model: str = ""
    source_event_count: int = 0


@dataclass
class GeneratedReport:
    """The complete generated report."""
    title: str = ""
    scan_id: str = ""
    scan_target: str = ""
    sections: List[GeneratedSection] = field(default_factory=list)
    executive_summary: str = ""
    recommendations: str = ""
    report_type: ReportType = ReportType.FULL
    format: ReportFormat = ReportFormat.MARKDOWN
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time_ms: float = 0.0
    total_tokens_used: int = 0

    @property
    def markdown(self) -> str:
        """Render the full report as Markdown."""
        parts = [f"# {self.title}", ""]

        if self.scan_target:
            parts.append(f"**Target:** {self.scan_target}  ")
        if self.scan_id:
            parts.append(f"**Scan ID:** {self.scan_id}  ")

        stats = self.metadata.get("statistics", {})
        if stats:
            parts.append(f"**Total Findings:** {stats.get('after_filter', 'N/A')}  ")
            risk_dist = stats.get("events_by_risk", {})
            if risk_dist:
                risk_str = ", ".join(f"{k}: {v}" for k, v in sorted(risk_dist.items()))
                parts.append(f"**Risk Distribution:** {risk_str}  ")
        parts.append("")
        parts.append("---")
        parts.append("")

        if self.executive_summary:
            parts.append("## Executive Summary")
            parts.append("")
            parts.append(self.executive_summary)
            parts.append("")

        for section in self.sections:
            parts.append(f"## {section.title}")
            parts.append("")
            parts.append(section.content)
            parts.append("")

        if self.recommendations:
            parts.append("## Recommendations")
            parts.append("")
            parts.append(self.recommendations)
            parts.append("")

        parts.append("---")
        parts.append(
            f"*Report generated in {self.generation_time_ms:.0f}ms "
            f"using {self.total_tokens_used} tokens*"
        )

        return "\n".join(parts)

    @property
    def plain_text(self) -> str:
        """Render as plain text (strips markdown formatting)."""
        text = self.markdown
        # Simple markdown stripping
        text = text.replace("# ", "").replace("## ", "").replace("### ", "")
        text = text.replace("**", "").replace("*", "").replace("---", "")
        return text

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "title": self.title,
            "scan_id": self.scan_id,
            "scan_target": self.scan_target,
            "executive_summary": self.executive_summary,
            "recommendations": self.recommendations,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "section_type": s.section_type,
                    "source_event_count": s.source_event_count,
                }
                for s in self.sections
            ],
            "metadata": self.metadata,
            "generation_time_ms": self.generation_time_ms,
            "total_tokens_used": self.total_tokens_used,
        }


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SECTION_PROMPTS: Dict[str, str] = {
    "Threat Intelligence": (
        "Analyze the threat intelligence findings below. Identify threat actors, "
        "attack patterns, and indicators of compromise (IOCs). Assess the severity "
        "of each threat and explain potential impact."
    ),
    "Vulnerability Assessment": (
        "Analyze the vulnerabilities identified below. For each vulnerability, "
        "explain: severity, exploitability, affected systems, and recommended "
        "remediation steps. Prioritize by risk."
    ),
    "Data Leak Exposure": (
        "Analyze the data leak findings below. Assess the sensitivity of leaked "
        "data, potential impact of exposure, and recommend immediate actions to "
        "mitigate damage."
    ),
    "Identity Exposure": (
        "Analyze the identity-related findings below. Identify exposed personal "
        "information, assess privacy risks, and recommend protective measures."
    ),
    "Infrastructure Analysis": (
        "Analyze the infrastructure findings below. Map the target's digital "
        "footprint, identify misconfigurations, and assess the attack surface."
    ),
    "Network Topology": (
        "Analyze the network-related findings below. Identify open services, "
        "potential entry points, and network security posture."
    ),
    "Web Presence": (
        "Analyze the web presence findings below. Identify web technologies, "
        "potential web vulnerabilities, and information disclosure issues."
    ),
    "Social Media": (
        "Analyze the social media findings below. Identify exposed accounts, "
        "potential social engineering vectors, and privacy concerns."
    ),
    "Geolocation": (
        "Analyze the geolocation findings below. Map the geographic distribution "
        "of the target's infrastructure and assess regional risk factors."
    ),
}

_EXECUTIVE_PROMPT = (
    "Based on the OSINT scan findings provided below, write a concise executive "
    "summary. Cover:\n"
    "1. Overall risk assessment (Critical/High/Medium/Low)\n"
    "2. Key findings (top 3-5 most significant)\n"
    "3. Immediate actions required\n"
    "4. Strategic recommendations\n\n"
    "Be concise, professional, and actionable. Target audience: C-level executives."
)

_RECOMMENDATIONS_PROMPT = (
    "Based on the OSINT scan findings provided below, generate prioritized "
    "security recommendations. For each recommendation:\n"
    "1. Priority level (Critical/High/Medium/Low)\n"
    "2. Description of the issue\n"
    "3. Specific remediation steps\n"
    "4. Estimated effort (Quick win / Short-term / Long-term)\n\n"
    "Order recommendations by priority. Be specific and actionable."
)


# ---------------------------------------------------------------------------
# Main Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Orchestrates the full report generation pipeline.

    Pipeline:
    1. Preprocess scan events (dedup, normalize, classify, section)
    2. Create context windows (token budgeting, allocation)
    3. Generate each section via LLM
    4. Assemble into a coherent report
    """

    def __init__(self, config: Optional[ReportGeneratorConfig] = None):
        self.config = config or ReportGeneratorConfig()
        self._preprocessor = ReportPreprocessor(self.config.preprocessor_config)
        self._window_manager = ContextWindowManager(self.config.window_config)
        self._llm_client = LLMClient(self.config.llm_config)

    @classmethod
    def from_env(cls) -> "ReportGenerator":
        """Create a generator using environment variable configuration."""
        return cls(ReportGeneratorConfig(
            llm_config=LLMConfig.from_env(),
        ))

    def generate(
        self,
        events: List[Dict[str, Any]],
        scan_metadata: Optional[Dict[str, Any]] = None,
    ) -> GeneratedReport:
        """Generate a complete report from raw scan events.

        Args:
            events: Raw scan event dicts.
            scan_metadata: Optional dict with scan_id, target, etc.

        Returns:
            GeneratedReport with all sections.
        """
        t0 = time.monotonic()
        metadata = scan_metadata or {}
        report = GeneratedReport(
            title=self.config.report_title or f"OSINT Report: {metadata.get('target', 'Unknown')}",
            scan_id=metadata.get("scan_id", ""),
            scan_target=metadata.get("target", ""),
            report_type=self.config.report_type,
            format=self.config.report_format,
        )

        # Step 1: Preprocess
        log.info("Step 1/4: Preprocessing %d events...", len(events))
        report_context = self._preprocessor.process(events, metadata)
        report.metadata["statistics"] = report_context.statistics
        report.metadata["preprocessing_ms"] = report_context.preprocessing_ms

        if report_context.total_events == 0:
            report.executive_summary = "No findings to report."
            report.generation_time_ms = (time.monotonic() - t0) * 1000
            return report

        # Step 2: Create context windows
        log.info("Step 2/4: Creating context windows...")
        windowing_result = self._window_manager.create_windows(report_context)

        # Step 3: Generate sections via LLM
        log.info("Step 3/4: Generating report sections...")
        sections = []

        # Executive summary
        if self.config.generate_executive_summary:
            exec_window = self._window_manager.create_executive_window(report_context)
            exec_section = self._generate_section(
                exec_window, "Executive Summary", _EXECUTIVE_PROMPT
            )
            report.executive_summary = exec_section.content
            self._notify_section("Executive Summary", exec_section.content)

        # Section-by-section analysis
        if self.config.generate_section_analysis:
            for window in windowing_result.windows:
                for alloc in window.sections:
                    if not alloc.content.strip():
                        continue
                    prompt = _SECTION_PROMPTS.get(
                        alloc.section_title,
                        f"Analyze the {alloc.section_title} findings below. "
                        f"Provide detailed analysis and insights."
                    )
                    section = self._generate_section_from_allocation(
                        alloc, report_context, prompt
                    )
                    sections.append(section)
                    self._notify_section(section.title, section.content)

        report.sections = sections

        # Recommendations
        if self.config.generate_recommendations:
            rec_window = self._window_manager.create_recommendations_window(report_context)
            rec_section = self._generate_section(
                rec_window, "Recommendations", _RECOMMENDATIONS_PROMPT
            )
            report.recommendations = rec_section.content
            self._notify_section("Recommendations", rec_section.content)

        # Step 4: Finalize
        report.total_tokens_used = sum(s.token_count for s in sections)
        if report.executive_summary:
            report.total_tokens_used += len(report.executive_summary) // 4
        if report.recommendations:
            report.total_tokens_used += len(report.recommendations) // 4

        report.generation_time_ms = (time.monotonic() - t0) * 1000
        report.metadata["windowing"] = {
            "windows": windowing_result.window_count,
            "coverage_pct": windowing_result.coverage_pct,
            "events_included": windowing_result.events_included,
        }

        log.info(
            "Report generated: %d sections, %d tokens, %.0fms",
            len(report.sections) + (1 if report.executive_summary else 0),
            report.total_tokens_used,
            report.generation_time_ms,
        )

        return report

    def generate_executive_only(
        self,
        events: List[Dict[str, Any]],
        scan_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate only the executive summary.

        Returns:
            Executive summary text.
        """
        config = ReportGeneratorConfig(
            preprocessor_config=self.config.preprocessor_config,
            window_config=self.config.window_config,
            llm_config=self.config.llm_config,
            generate_executive_summary=True,
            generate_recommendations=False,
            generate_section_analysis=False,
        )
        gen = ReportGenerator(config)
        report = gen.generate(events, scan_metadata)
        return report.executive_summary

    def generate_recommendations_only(
        self,
        events: List[Dict[str, Any]],
        scan_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate only recommendations.

        Returns:
            Recommendations text.
        """
        config = ReportGeneratorConfig(
            preprocessor_config=self.config.preprocessor_config,
            window_config=self.config.window_config,
            llm_config=self.config.llm_config,
            generate_executive_summary=False,
            generate_recommendations=True,
            generate_section_analysis=False,
        )
        gen = ReportGenerator(config)
        report = gen.generate(events, scan_metadata)
        return report.recommendations

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _generate_section(
        self,
        window: ContextWindow,
        title: str,
        user_instructions: str,
    ) -> GeneratedSection:
        """Generate a report section from a context window."""
        t0 = time.monotonic()

        system_prompt = window.system_prompt
        if self.config.custom_instructions:
            system_prompt += f"\n\nAdditional instructions: {self.config.custom_instructions}"
        if self.config.language != "English":
            system_prompt += f"\n\nWrite the report in {self.config.language}."

        user_prompt = f"{user_instructions}\n\n{window.user_prompt}"

        response = self._llm_client.chat(
            user_message=user_prompt,
            system_message=system_prompt,
        )

        return GeneratedSection(
            title=title,
            content=response.content,
            section_type=title.lower().replace(" ", "_"),
            token_count=response.total_tokens,
            latency_ms=(time.monotonic() - t0) * 1000,
            model=response.model,
            source_event_count=sum(a.event_count for a in window.sections),
        )

    def _generate_section_from_allocation(
        self,
        allocation: Any,
        report_context: ReportContext,
        user_instructions: str,
    ) -> GeneratedSection:
        """Generate a report section from a section allocation."""
        t0 = time.monotonic()

        system_prompt = (
            "You are a cybersecurity analyst writing a detailed section of an "
            "OSINT report. Analyze the findings, identify patterns, and explain "
            "their significance. Be thorough but concise."
        )
        if self.config.custom_instructions:
            system_prompt += f"\n\nAdditional instructions: {self.config.custom_instructions}"
        if self.config.language != "English":
            system_prompt += f"\n\nWrite the report in {self.config.language}."

        user_prompt = (
            f"{user_instructions}\n\n"
            f"Target: {report_context.scan_target}\n\n"
            f"{allocation.content}"
        )

        response = self._llm_client.chat(
            user_message=user_prompt,
            system_message=system_prompt,
        )

        return GeneratedSection(
            title=allocation.section_title,
            content=response.content,
            section_type=allocation.section_title.lower().replace(" ", "_"),
            token_count=response.total_tokens,
            latency_ms=(time.monotonic() - t0) * 1000,
            model=response.model,
            source_event_count=allocation.event_count,
        )

    def _notify_section(self, title: str, content: str) -> None:
        """Notify via callback when a section is completed."""
        if self.config.on_section_complete:
            try:
                self.config.on_section_complete(title, content)
            except Exception as e:
                log.warning("Section callback error: %s", e)
