"""
Context Windowing for LLM Report Generation.

Manages the allocation of LLM context window budget across report sections,
ensuring that the most important findings receive the most context while
staying within model token limits.

Pipeline:  Preprocess → **Context Window** → LLM Generate → Format

Strategies:
- PROPORTIONAL: Allocate tokens proportionally to section event counts
- PRIORITY_WEIGHTED: Weight allocation by section priority and risk
- FIXED: Equal allocation per section
- ADAPTIVE: Dynamically adjust based on content density

Usage::

    from spiderfoot.context_window import ContextWindowManager, WindowConfig

    manager = ContextWindowManager(WindowConfig(max_tokens=8192))
    windows = manager.create_windows(report_context)
    for window in windows:
        # Each window fits within the LLM's context limit
        prompt = window.to_prompt()
"""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.context_window")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AllocationStrategy(Enum):
    """Token allocation strategies for context windowing."""
    PROPORTIONAL = "proportional"
    PRIORITY_WEIGHTED = "priority_weighted"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


class WindowRole(Enum):
    """The role/purpose of a context window."""
    EXECUTIVE_SUMMARY = "executive_summary"
    SECTION_ANALYSIS = "section_analysis"
    DEEP_DIVE = "deep_dive"
    RECOMMENDATIONS = "recommendations"
    FULL_REPORT = "full_report"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WindowConfig:
    """Configuration for context window management."""
    # Model limits
    max_tokens: int = 8192
    reserved_for_system_prompt: int = 500
    reserved_for_output: int = 2048

    # Strategy
    strategy: AllocationStrategy = AllocationStrategy.PRIORITY_WEIGHTED

    # Section handling
    min_tokens_per_section: int = 100
    max_tokens_per_section: int = 0  # 0 = no limit (uses available budget)
    max_events_per_window: int = 100

    # Multi-window
    enable_multi_window: bool = True
    max_windows: int = 10

    # Truncation
    truncation_suffix: str = "\n[... truncated for context limit ...]"
    include_statistics: bool = True
    include_metadata: bool = True


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SectionAllocation:
    """Token budget allocated to a specific section."""
    section_title: str
    section_priority: int
    allocated_tokens: int
    event_count: int
    events_included: int
    content: str = ""
    truncated: bool = False


@dataclass
class ContextWindow:
    """A single context window ready for LLM consumption."""
    window_id: int = 0
    role: WindowRole = WindowRole.FULL_REPORT
    system_prompt: str = ""
    user_prompt: str = ""
    sections: list[SectionAllocation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    total_tokens: int = 0
    budget_tokens: int = 0
    utilization_pct: float = 0.0

    def to_prompt(self) -> dict[str, str]:
        """Return system + user prompt pair for LLM API."""
        return {
            "system": self.system_prompt,
            "user": self.user_prompt,
        }


@dataclass
class WindowingResult:
    """Result of context windowing across a full report."""
    windows: list[ContextWindow] = field(default_factory=list)
    strategy: AllocationStrategy = AllocationStrategy.PRIORITY_WEIGHTED
    total_events: int = 0
    events_included: int = 0
    events_truncated: int = 0
    coverage_pct: float = 0.0

    @property
    def window_count(self) -> int:
        return len(self.windows)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPTS: dict[WindowRole, str] = {
    WindowRole.EXECUTIVE_SUMMARY: textwrap.dedent("""\
        You are a senior cybersecurity analyst writing an executive summary
        of an OSINT (Open Source Intelligence) scan. Be concise, highlight
        the most critical findings, and provide a risk assessment.
        Focus on business impact and actionable items.
        Use professional language suitable for C-level executives."""),

    WindowRole.SECTION_ANALYSIS: textwrap.dedent("""\
        You are a cybersecurity analyst writing a detailed section of an
        OSINT report. Analyze the findings provided, identify patterns,
        and explain their significance. Include specific technical details
        while maintaining readability."""),

    WindowRole.DEEP_DIVE: textwrap.dedent("""\
        You are a cybersecurity researcher performing deep technical analysis
        of OSINT findings. Provide detailed technical explanations, correlate
        indicators, identify attack patterns, and suggest specific remediation
        steps with implementation details."""),

    WindowRole.RECOMMENDATIONS: textwrap.dedent("""\
        You are a cybersecurity consultant generating actionable security
        recommendations based on OSINT scan findings. Prioritize recommendations
        by severity and ease of implementation. Include specific steps,
        tools, and configurations where applicable."""),

    WindowRole.FULL_REPORT: textwrap.dedent("""\
        You are a senior cybersecurity analyst generating a comprehensive
        OSINT scan report. Cover all findings systematically, starting with
        an executive summary, followed by detailed analysis per category,
        and ending with prioritized recommendations."""),
}


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    """Rough token count estimate."""
    return max(1, len(text) // chars_per_token)


def _truncate_to_tokens(text: str, max_tokens: int, suffix: str = "") -> tuple[str, bool]:
    """Truncate text to fit within a token budget.

    Returns:
        (truncated_text, was_truncated)
    """
    current_tokens = _estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text, False

    # Approximate character limit
    max_chars = max_tokens * 4
    suffix_chars = len(suffix)
    truncated = text[:max_chars - suffix_chars] + suffix
    return truncated, True


# ---------------------------------------------------------------------------
# Main windowing manager
# ---------------------------------------------------------------------------

class ContextWindowManager:
    """Manages context window allocation for LLM report generation.

    Takes a ReportContext (from ReportPreprocessor) and produces one or more
    ContextWindow objects, each fitting within the configured token budget.
    """

    def __init__(self, config: WindowConfig | None = None) -> None:
        self.config = config or WindowConfig()

    @property
    def available_budget(self) -> int:
        """Tokens available for content (after system prompt and output reserve)."""
        return max(
            0,
            self.config.max_tokens
            - self.config.reserved_for_system_prompt
            - self.config.reserved_for_output,
        )

    def create_windows(self, report_context: Any) -> WindowingResult:
        """Create context windows from a preprocessed report context.

        Args:
            report_context: A ReportContext from ReportPreprocessor with
                .non_empty_sections, .scan_target, .scan_id, .statistics, .total_events

        Returns:
            WindowingResult with one or more ContextWindow objects.
        """
        sections = report_context.non_empty_sections
        if not sections:
            return WindowingResult(strategy=self.config.strategy)

        total_events = sum(s.event_count for s in sections)

        # Calculate allocations
        allocations = self._allocate_tokens(sections)

        # Decide: single window or multi-window
        total_content_tokens = sum(a.allocated_tokens for a in allocations)

        if total_content_tokens <= self.available_budget or not self.config.enable_multi_window:
            # Single window
            window = self._build_single_window(
                allocations, report_context, WindowRole.FULL_REPORT
            )
            result = WindowingResult(
                windows=[window],
                strategy=self.config.strategy,
                total_events=total_events,
                events_included=sum(a.events_included for a in allocations),
            )
        else:
            # Multi-window
            windows = self._build_multi_windows(allocations, report_context)
            result = WindowingResult(
                windows=windows,
                strategy=self.config.strategy,
                total_events=total_events,
                events_included=sum(
                    sum(a.events_included for a in w.sections)
                    for w in windows
                ),
            )

        result.events_truncated = result.total_events - result.events_included
        result.coverage_pct = (
            (result.events_included / result.total_events * 100)
            if result.total_events > 0
            else 0.0
        )

        log.info(
            "Created %d context window(s) using %s strategy, "
            "%.1f%% event coverage (%d/%d events)",
            result.window_count,
            self.config.strategy.value,
            result.coverage_pct,
            result.events_included,
            result.total_events,
        )

        return result

    def create_executive_window(self, report_context: Any) -> ContextWindow:
        """Create a dedicated executive summary window.

        Includes only the top-priority events across all sections.
        """
        sections = report_context.non_empty_sections
        # Get executive summary section, or use top events from all sections
        exec_sections = [s for s in sections if s.title == "Executive Summary"]
        if not exec_sections:
            exec_sections = sections[:3]

        allocations = self._allocate_tokens(exec_sections)
        return self._build_single_window(
            allocations, report_context, WindowRole.EXECUTIVE_SUMMARY
        )

    def create_recommendations_window(self, report_context: Any) -> ContextWindow:
        """Create a window focused on generating recommendations.

        Includes high-risk findings as context for recommendation generation.
        """
        sections = report_context.non_empty_sections
        # Filter to high-priority sections
        high_priority = [s for s in sections if s.priority >= 70]
        if not high_priority:
            high_priority = sections[:3]

        allocations = self._allocate_tokens(high_priority)
        return self._build_single_window(
            allocations, report_context, WindowRole.RECOMMENDATIONS
        )

    # -----------------------------------------------------------------------
    # Allocation strategies
    # -----------------------------------------------------------------------

    def _allocate_tokens(self, sections: list) -> list[SectionAllocation]:
        """Allocate token budget across sections using the configured strategy."""
        strategy = self.config.strategy
        budget = self.available_budget

        if strategy == AllocationStrategy.FIXED:
            return self._allocate_fixed(sections, budget)
        elif strategy == AllocationStrategy.PROPORTIONAL:
            return self._allocate_proportional(sections, budget)
        elif strategy == AllocationStrategy.PRIORITY_WEIGHTED:
            return self._allocate_priority_weighted(sections, budget)
        elif strategy == AllocationStrategy.ADAPTIVE:
            return self._allocate_adaptive(sections, budget)
        else:
            return self._allocate_priority_weighted(sections, budget)

    def _allocate_fixed(self, sections: list, budget: int) -> list[SectionAllocation]:
        """Equal allocation per section."""
        if not sections:
            return []
        per_section = max(self.config.min_tokens_per_section, budget // len(sections))
        return [
            self._make_allocation(s, per_section)
            for s in sections
        ]

    def _allocate_proportional(self, sections: list, budget: int) -> list[SectionAllocation]:
        """Allocate proportionally to event count."""
        total_events = sum(s.event_count for s in sections)
        if total_events == 0:
            return self._allocate_fixed(sections, budget)

        return [
            self._make_allocation(
                s,
                max(
                    self.config.min_tokens_per_section,
                    int(budget * s.event_count / total_events),
                ),
            )
            for s in sections
        ]

    def _allocate_priority_weighted(self, sections: list, budget: int) -> list[SectionAllocation]:
        """Weight allocation by section priority (higher priority = more tokens)."""
        total_priority = sum(s.priority for s in sections)
        if total_priority == 0:
            return self._allocate_fixed(sections, budget)

        allocations = []
        for s in sections:
            weight = s.priority / total_priority
            tokens = max(
                self.config.min_tokens_per_section,
                int(budget * weight),
            )
            if self.config.max_tokens_per_section > 0:
                tokens = min(tokens, self.config.max_tokens_per_section)
            allocations.append(self._make_allocation(s, tokens))

        return allocations

    def _allocate_adaptive(self, sections: list, budget: int) -> list[SectionAllocation]:
        """Adaptive allocation: starts with priority weighting, then redistributes
        unused budget from small sections to large ones."""
        # Start with priority-weighted
        allocations = self._allocate_priority_weighted(sections, budget)

        # Check if any section's content is smaller than its allocation
        used = 0
        surplus = 0
        for alloc in allocations:
            actual = _estimate_tokens(alloc.content)
            if actual < alloc.allocated_tokens:
                surplus += alloc.allocated_tokens - actual
                alloc.allocated_tokens = actual
            used += alloc.allocated_tokens

        # Redistribute surplus to truncated sections
        if surplus > 0:
            truncated = [a for a in allocations if a.truncated]
            if truncated:
                bonus = surplus // len(truncated)
                for alloc in truncated:
                    alloc.allocated_tokens += bonus

        return allocations

    # -----------------------------------------------------------------------
    # Window builders
    # -----------------------------------------------------------------------

    def _make_allocation(self, section: Any, tokens: int) -> SectionAllocation:
        """Create a SectionAllocation from a ReportSection."""
        # Generate content text
        content_lines = [f"### {section.title}"]
        if section.description:
            content_lines.append(section.description)
        content_lines.append("")

        events_included = 0
        for evt in section.events:
            line = (
                f"- [{evt.risk_level.name}] {evt.event_type}: {evt.data} "
                f"(confidence: {evt.confidence}%, source: {evt.module})"
            )
            line_tokens = _estimate_tokens(line)
            if _estimate_tokens("\n".join(content_lines)) + line_tokens > tokens:
                break
            content_lines.append(line)
            events_included += 1

        content = "\n".join(content_lines)
        content, was_truncated = _truncate_to_tokens(
            content, tokens, self.config.truncation_suffix
        )

        return SectionAllocation(
            section_title=section.title,
            section_priority=section.priority,
            allocated_tokens=tokens,
            event_count=section.event_count,
            events_included=events_included,
            content=content,
            truncated=was_truncated or events_included < section.event_count,
        )

    def _build_single_window(
        self,
        allocations: list[SectionAllocation],
        report_context: Any,
        role: WindowRole,
    ) -> ContextWindow:
        """Build a single context window from allocations."""
        system_prompt = _SYSTEM_PROMPTS.get(role, _SYSTEM_PROMPTS[WindowRole.FULL_REPORT])

        # Build user prompt
        parts = [f"# OSINT Scan Report: {report_context.scan_target}"]
        if report_context.scan_id:
            parts.append(f"Scan ID: {report_context.scan_id}")

        if self.config.include_statistics and hasattr(report_context, 'statistics'):
            stats = report_context.statistics
            parts.append(f"Total findings: {stats.get('after_filter', 0)}")
            risk_dist = stats.get('events_by_risk', {})
            if risk_dist:
                parts.append(f"Risk distribution: {risk_dist}")

        parts.append("")

        for alloc in allocations:
            if alloc.content.strip():
                parts.append(alloc.content)
                parts.append("")

        user_prompt = "\n".join(parts)
        total_tokens = (
            _estimate_tokens(system_prompt)
            + _estimate_tokens(user_prompt)
        )

        return ContextWindow(
            window_id=0,
            role=role,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            sections=allocations,
            metadata={
                "scan_target": report_context.scan_target,
                "scan_id": report_context.scan_id,
            },
            total_tokens=total_tokens,
            budget_tokens=self.config.max_tokens,
            utilization_pct=(total_tokens / self.config.max_tokens * 100)
            if self.config.max_tokens > 0
            else 0.0,
        )

    def _build_multi_windows(
        self,
        allocations: list[SectionAllocation],
        report_context: Any,
    ) -> list[ContextWindow]:
        """Split allocations across multiple windows when content exceeds budget."""
        windows = []
        current_allocs: list[SectionAllocation] = []
        current_tokens = 0
        budget = self.available_budget
        window_id = 0

        # Sort by priority (highest first for first window)
        sorted_allocs = sorted(allocations, key=lambda a: a.section_priority, reverse=True)

        for alloc in sorted_allocs:
            alloc_tokens = _estimate_tokens(alloc.content)
            if current_tokens + alloc_tokens > budget and current_allocs:
                # Build window from accumulated allocations
                role = (
                    WindowRole.EXECUTIVE_SUMMARY
                    if window_id == 0
                    else WindowRole.SECTION_ANALYSIS
                )
                window = self._build_single_window(
                    current_allocs, report_context, role
                )
                window.window_id = window_id
                windows.append(window)
                window_id += 1

                current_allocs = []
                current_tokens = 0

                if len(windows) >= self.config.max_windows:
                    break

            current_allocs.append(alloc)
            current_tokens += alloc_tokens

        # Remaining allocations
        if current_allocs and len(windows) < self.config.max_windows:
            role = (
                WindowRole.EXECUTIVE_SUMMARY
                if window_id == 0
                else WindowRole.SECTION_ANALYSIS
            )
            window = self._build_single_window(
                current_allocs, report_context, role
            )
            window.window_id = window_id
            windows.append(window)

        return windows
