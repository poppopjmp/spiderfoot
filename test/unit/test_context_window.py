"""Tests for LLM context windowing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from spiderfoot.context_window import (
    AllocationStrategy,
    ContextWindow,
    ContextWindowManager,
    SectionAllocation,
    WindowConfig,
    WindowingResult,
    WindowRole,
    _estimate_tokens,
    _truncate_to_tokens,
)
from spiderfoot.reporting.report_preprocessor import (
    NormalizedEvent,
    PreprocessorConfig,
    ReportContext,
    ReportPreprocessor,
    ReportSection,
    ReportSectionType,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_normalized_event(
    event_type="IP_ADDRESS", data="10.0.0.1", module="sfp_test",
    confidence=80, risk=50, risk_level=RiskLevel.MEDIUM, category="network",
):
    return NormalizedEvent(
        event_type=event_type, data=data, module=module,
        confidence=confidence, risk=risk, risk_level=risk_level,
        category=category, timestamp=time.time(),
    )


def _make_section(title="Test Section", priority=50, events=None, section_type=None):
    if events is None:
        events = [_make_normalized_event()]
    return ReportSection(
        section_type=section_type or ReportSectionType.APPENDIX,
        title=title,
        description="Test section description.",
        events=events,
        priority=priority,
    )


def _make_report_context(sections=None, target="example.com", scan_id="scan-1"):
    if sections is None:
        sections = [
            _make_section("Threats", priority=90, events=[
                _make_normalized_event("MALICIOUS_IP", "1.2.3.4", risk=80,
                                       risk_level=RiskLevel.CRITICAL, category="threat"),
            ], section_type=ReportSectionType.THREAT_INTELLIGENCE),
            _make_section("Vulnerabilities", priority=85, events=[
                _make_normalized_event("VULNERABILITY_CVE", "CVE-2024-1234",
                                       risk=95, risk_level=RiskLevel.CRITICAL,
                                       category="vulnerability"),
                _make_normalized_event("VULNERABILITY_CVE", "CVE-2024-5678",
                                       risk=70, risk_level=RiskLevel.HIGH,
                                       category="vulnerability"),
            ], section_type=ReportSectionType.VULNERABILITY_ASSESSMENT),
            _make_section("Network", priority=55, events=[
                _make_normalized_event("IP_ADDRESS", "10.0.0.1", risk=20,
                                       risk_level=RiskLevel.LOW),
                _make_normalized_event("TCP_PORT_OPEN", "443", risk=10,
                                       risk_level=RiskLevel.INFO),
                _make_normalized_event("TCP_PORT_OPEN", "22", risk=30,
                                       risk_level=RiskLevel.LOW),
            ], section_type=ReportSectionType.NETWORK_TOPOLOGY),
        ]
    return ReportContext(
        scan_id=scan_id,
        scan_target=target,
        sections=sections,
        statistics={"after_filter": 6, "events_by_risk": {"CRITICAL": 2, "HIGH": 1, "LOW": 2, "INFO": 1}},
    )


# ===========================================================================
# Token utilities
# ===========================================================================

class TestEstimateTokens:
    def test_basic(self):
        assert _estimate_tokens("x" * 100) == 25

    def test_empty(self):
        assert _estimate_tokens("") == 1


class TestTruncateToTokens:
    def test_no_truncation(self):
        text, truncated = _truncate_to_tokens("short", max_tokens=100)
        assert text == "short"
        assert truncated is False

    def test_truncation(self):
        text, truncated = _truncate_to_tokens("x" * 1000, max_tokens=10, suffix="...")
        assert len(text) <= 40 + 3  # 10 tokens * 4 chars + suffix
        assert truncated is True
        assert text.endswith("...")


# ===========================================================================
# WindowConfig
# ===========================================================================

class TestWindowConfig:
    def test_defaults(self):
        cfg = WindowConfig()
        assert cfg.max_tokens == 8192
        assert cfg.reserved_for_system_prompt == 500
        assert cfg.reserved_for_output == 2048
        assert cfg.strategy == AllocationStrategy.PRIORITY_WEIGHTED

    def test_custom(self):
        cfg = WindowConfig(max_tokens=4096, strategy=AllocationStrategy.FIXED)
        assert cfg.max_tokens == 4096
        assert cfg.strategy == AllocationStrategy.FIXED


# ===========================================================================
# ContextWindow
# ===========================================================================

class TestContextWindow:
    def test_to_prompt(self):
        window = ContextWindow(
            system_prompt="You are an analyst",
            user_prompt="Analyze these findings",
        )
        prompt = window.to_prompt()
        assert prompt["system"] == "You are an analyst"
        assert prompt["user"] == "Analyze these findings"


# ===========================================================================
# WindowingResult
# ===========================================================================

class TestWindowingResult:
    def test_window_count(self):
        result = WindowingResult(windows=[ContextWindow(), ContextWindow()])
        assert result.window_count == 2

    def test_empty(self):
        result = WindowingResult()
        assert result.window_count == 0
        assert result.coverage_pct == 0.0


# ===========================================================================
# ContextWindowManager — available_budget
# ===========================================================================

class TestAvailableBudget:
    def test_default_budget(self):
        mgr = ContextWindowManager()
        # 8192 - 500 - 2048 = 5644
        assert mgr.available_budget == 5644

    def test_custom_budget(self):
        mgr = ContextWindowManager(WindowConfig(
            max_tokens=4096,
            reserved_for_system_prompt=200,
            reserved_for_output=1000,
        ))
        assert mgr.available_budget == 2896

    def test_zero_budget(self):
        mgr = ContextWindowManager(WindowConfig(
            max_tokens=100,
            reserved_for_system_prompt=50,
            reserved_for_output=60,
        ))
        assert mgr.available_budget == 0


# ===========================================================================
# ContextWindowManager — create_windows
# ===========================================================================

class TestCreateWindows:
    def test_empty_context(self):
        mgr = ContextWindowManager()
        ctx = _make_report_context(sections=[])
        result = mgr.create_windows(ctx)
        assert result.window_count == 0

    def test_single_window(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1
        assert result.events_included > 0
        assert result.coverage_pct > 0

    def test_window_has_prompts(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        window = result.windows[0]
        prompt = window.to_prompt()
        assert len(prompt["system"]) > 0
        assert len(prompt["user"]) > 0
        assert "example.com" in prompt["user"]

    def test_window_includes_statistics(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert "after_filter" in result.windows[0].user_prompt or \
               "findings" in result.windows[0].user_prompt

    def test_window_metadata(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.windows[0].metadata["scan_target"] == "example.com"

    def test_multi_window_on_small_budget(self):
        """Force multi-windowing with a very small budget."""
        mgr = ContextWindowManager(WindowConfig(
            max_tokens=500,
            reserved_for_system_prompt=50,
            reserved_for_output=100,
            enable_multi_window=True,
        ))
        # Create sections with lots of content
        events = [
            _make_normalized_event(f"TYPE_{i}", f"data-{i}" * 10, risk=50)
            for i in range(50)
        ]
        sections = [
            _make_section(f"Section {i}", priority=50 + i, events=events[i*10:(i+1)*10])
            for i in range(5)
        ]
        ctx = _make_report_context(sections=sections)
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1

    def test_multi_window_disabled(self):
        mgr = ContextWindowManager(WindowConfig(
            max_tokens=500,
            reserved_for_system_prompt=50,
            reserved_for_output=100,
            enable_multi_window=False,
        ))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count == 1


# ===========================================================================
# Allocation strategies
# ===========================================================================

class TestAllocationStrategies:
    def test_fixed_allocation(self):
        mgr = ContextWindowManager(WindowConfig(
            strategy=AllocationStrategy.FIXED,
            max_tokens=16000,
        ))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1
        # All sections should get similar token allocations
        if len(result.windows[0].sections) >= 2:
            tokens = [s.allocated_tokens for s in result.windows[0].sections]
            assert max(tokens) - min(tokens) < tokens[0] * 0.1  # Within 10%

    def test_proportional_allocation(self):
        mgr = ContextWindowManager(WindowConfig(
            strategy=AllocationStrategy.PROPORTIONAL,
            max_tokens=16000,
        ))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1

    def test_priority_weighted_allocation(self):
        mgr = ContextWindowManager(WindowConfig(
            strategy=AllocationStrategy.PRIORITY_WEIGHTED,
            max_tokens=16000,
        ))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1
        # Higher priority sections should get more tokens
        sections = result.windows[0].sections
        if len(sections) >= 2:
            high_prio = next((s for s in sections if s.section_priority >= 85), None)
            low_prio = next((s for s in sections if s.section_priority <= 55), None)
            if high_prio and low_prio:
                assert high_prio.allocated_tokens >= low_prio.allocated_tokens

    def test_adaptive_allocation(self):
        mgr = ContextWindowManager(WindowConfig(
            strategy=AllocationStrategy.ADAPTIVE,
            max_tokens=16000,
        ))
        ctx = _make_report_context()
        result = mgr.create_windows(ctx)
        assert result.window_count >= 1


# ===========================================================================
# Specialized windows
# ===========================================================================

class TestExecutiveWindow:
    def test_executive_window(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        window = mgr.create_executive_window(ctx)
        assert window.role == WindowRole.EXECUTIVE_SUMMARY
        assert "executive" in window.system_prompt.lower()
        assert len(window.user_prompt) > 0


class TestRecommendationsWindow:
    def test_recommendations_window(self):
        mgr = ContextWindowManager(WindowConfig(max_tokens=16000))
        ctx = _make_report_context()
        window = mgr.create_recommendations_window(ctx)
        assert window.role == WindowRole.RECOMMENDATIONS
        assert "recommend" in window.system_prompt.lower()


# ===========================================================================
# Integration with ReportPreprocessor
# ===========================================================================

class TestPreprocessorIntegration:
    def test_end_to_end(self):
        """Full pipeline: raw events → preprocess → window."""
        events = [
            {"event_type": "MALICIOUS_IPADDR", "data": "1.2.3.4",
             "module": "sfp_test", "confidence": 90, "risk": 85,
             "timestamp": time.time()},
            {"event_type": "VULNERABILITY_CVE_CRITICAL", "data": "CVE-2024-9999",
             "module": "sfp_vulndb", "confidence": 95, "risk": 95,
             "timestamp": time.time()},
            {"event_type": "EMAIL_ADDRESS", "data": "admin@example.com",
             "module": "sfp_email", "confidence": 80, "risk": 30,
             "timestamp": time.time()},
            {"event_type": "IP_ADDRESS", "data": "10.0.0.1",
             "module": "sfp_dns", "confidence": 90, "risk": 10,
             "timestamp": time.time()},
        ]

        # Preprocess
        preprocessor = ReportPreprocessor(PreprocessorConfig())
        report_ctx = preprocessor.process(events, {"scan_id": "s1", "target": "test.com"})

        # Window
        manager = ContextWindowManager(WindowConfig(max_tokens=8192))
        result = manager.create_windows(report_ctx)

        assert result.window_count >= 1
        assert result.events_included > 0
        prompt = result.windows[0].to_prompt()
        assert "test.com" in prompt["user"]
        assert len(prompt["system"]) > 50  # Non-trivial system prompt


# ===========================================================================
# Enums
# ===========================================================================

class TestEnums:
    def test_allocation_strategies(self):
        assert len(AllocationStrategy) == 4

    def test_window_roles(self):
        assert len(WindowRole) == 5
        assert WindowRole.FULL_REPORT.value == "full_report"
