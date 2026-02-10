"""
LLM Report Preprocessor for SpiderFoot.

Takes raw scan results and prepares structured, deduplicated, prioritized
sections suitable for LLM context windows. This is the first stage of the
LLM-powered reporting pipeline.

Pipeline:  Raw Results → Preprocess → Context Window → LLM Generate → Format

The preprocessor:
1. Deduplicates events using content normalization
2. Classifies events by risk and category
3. Groups events into report sections
4. Estimates token budgets per section
5. Produces a ReportContext ready for LLM prompting

Usage::

    from spiderfoot.report_preprocessor import ReportPreprocessor, PreprocessorConfig

    preprocessor = ReportPreprocessor(PreprocessorConfig())
    context = preprocessor.process(scan_events, scan_metadata)
    # context.sections → list of ReportSection with prioritized events
    # context.token_estimate → total tokens needed
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

log = logging.getLogger("spiderfoot.report_preprocessor")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(IntEnum):
    """Risk levels with numeric ordering (higher = more severe)."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ReportSectionType(Enum):
    """Standard report section types."""
    EXECUTIVE_SUMMARY = "executive_summary"
    THREAT_INTELLIGENCE = "threat_intelligence"
    VULNERABILITY_ASSESSMENT = "vulnerability_assessment"
    INFRASTRUCTURE_ANALYSIS = "infrastructure_analysis"
    IDENTITY_EXPOSURE = "identity_exposure"
    DATA_LEAKS = "data_leaks"
    NETWORK_TOPOLOGY = "network_topology"
    WEB_PRESENCE = "web_presence"
    SOCIAL_MEDIA = "social_media"
    GEOLOCATION = "geolocation"
    RECOMMENDATIONS = "recommendations"
    APPENDIX = "appendix"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NormalizedEvent:
    """A scan event after normalization and deduplication."""
    event_id: str = ""
    event_type: str = ""
    data: str = ""
    module: str = ""
    confidence: int = 50
    risk: int = 0
    risk_level: RiskLevel = RiskLevel.INFO
    category: str = "other"
    timestamp: float = 0.0
    source_event_id: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    dedup_key: str = ""

    @property
    def priority_score(self) -> float:
        """Composite priority score (0-100) for ordering."""
        risk_weight = self.risk * 0.5
        confidence_weight = self.confidence * 0.3
        # Critical categories get a boost
        category_boost = 20 if self.category in ("threat", "vulnerability", "data_leak") else 0
        return min(100.0, risk_weight + confidence_weight + category_boost)


@dataclass
class ReportSection:
    """A section of a report with grouped, prioritized events."""
    section_type: ReportSectionType
    title: str
    description: str = ""
    events: list[NormalizedEvent] = field(default_factory=list)
    subsections: list[ReportSection] = field(default_factory=list)
    token_estimate: int = 0
    priority: int = 0  # Higher = more important
    max_events: int = 50  # Cap per section for LLM context

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def has_content(self) -> bool:
        return len(self.events) > 0 or len(self.subsections) > 0

    def to_text(self) -> str:
        """Serialize section events to text for LLM context."""
        lines = [f"## {self.title}"]
        if self.description:
            lines.append(self.description)
        lines.append("")
        for evt in self.events[:self.max_events]:
            risk_label = evt.risk_level.name
            lines.append(
                f"- [{risk_label}] {evt.event_type}: {evt.data} "
                f"(confidence: {evt.confidence}%, source: {evt.module})"
            )
        if len(self.events) > self.max_events:
            lines.append(f"  ... and {len(self.events) - self.max_events} more events")
        for sub in self.subsections:
            lines.append("")
            lines.append(sub.to_text())
        return "\n".join(lines)


@dataclass
class ReportContext:
    """Full preprocessed context ready for LLM generation."""
    scan_id: str = ""
    scan_target: str = ""
    scan_start: float = 0.0
    scan_end: float = 0.0
    sections: list[ReportSection] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    token_estimate: int = 0
    preprocessing_ms: float = 0.0

    @property
    def total_events(self) -> int:
        return sum(s.event_count for s in self.sections)

    @property
    def non_empty_sections(self) -> list[ReportSection]:
        return [s for s in self.sections if s.has_content]

    def to_text(self, max_tokens: int = 0) -> str:
        """Serialize to text, optionally truncating to a token budget.

        Args:
            max_tokens: If > 0, stop adding sections when budget is reached.
        """
        parts = [
            f"# OSINT Scan Report: {self.scan_target}",
            f"Scan ID: {self.scan_id}",
            f"Total findings: {self.total_events}",
            "",
        ]

        used_tokens = _estimate_tokens("\n".join(parts))

        for section in self.non_empty_sections:
            section_text = section.to_text()
            section_tokens = _estimate_tokens(section_text)

            if max_tokens > 0 and used_tokens + section_tokens > max_tokens:
                parts.append(f"\n[Remaining {len(self.non_empty_sections)} sections "
                             f"truncated due to token budget]")
                break

            parts.append("")
            parts.append(section_text)
            used_tokens += section_tokens

        return "\n".join(parts)


@dataclass
class PreprocessorConfig:
    """Configuration for the report preprocessor."""
    # Deduplication
    enable_dedup: bool = True
    dedup_normalize_urls: bool = True
    dedup_normalize_ips: bool = True
    dedup_normalize_emails: bool = True

    # Risk classification
    risk_thresholds: dict[str, int] = field(default_factory=lambda: {
        "critical": 80,
        "high": 60,
        "medium": 40,
        "low": 20,
    })

    # Section limits
    max_events_per_section: int = 50
    max_total_events: int = 500

    # Token budgeting
    estimated_chars_per_token: int = 4
    max_context_tokens: int = 8192

    # Filtering
    min_confidence: int = 0
    min_risk: int = 0
    exclude_event_types: list[str] = field(default_factory=list)
    include_categories: list[str] = field(default_factory=list)  # empty = all


@dataclass
class PreprocessorStats:
    """Statistics from the preprocessing run."""
    total_input_events: int = 0
    total_after_dedup: int = 0
    total_after_filter: int = 0
    duplicates_removed: int = 0
    filtered_low_confidence: int = 0
    filtered_low_risk: int = 0
    filtered_excluded_type: int = 0
    events_by_risk: dict[str, int] = field(default_factory=dict)
    events_by_category: dict[str, int] = field(default_factory=dict)
    sections_populated: int = 0
    token_estimate: int = 0


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

# Maps event type prefixes to report categories
_CATEGORY_MAP: dict[str, str] = {
    "MALICIOUS": "threat",
    "VULNERABILITY": "vulnerability",
    "BLACKLISTED": "threat",
    "DARKNET": "threat",
    "LEAKED": "data_leak",
    "PASSWORD": "data_leak",
    "CREDENTIAL": "data_leak",
    "IP_ADDRESS": "network",
    "NETBLOCK": "network",
    "BGP": "network",
    "TCP_PORT": "network",
    "UDP_PORT": "network",
    "DOMAIN": "infrastructure",
    "INTERNET_NAME": "infrastructure",
    "DNS": "infrastructure",
    "AFFILIATE": "infrastructure",
    "WEBSERVER": "web",
    "URL": "web",
    "HTTP": "web",
    "WEB_TECHNOLOGY": "web",
    "SSL": "infrastructure",
    "CERTIFICATE": "infrastructure",
    "EMAIL": "identity",
    "USERNAME": "identity",
    "HUMAN_NAME": "identity",
    "PHONE": "identity",
    "ACCOUNT_EXTERNAL": "identity",
    "SOCIAL_MEDIA": "social",
    "GEOINFO": "geolocation",
    "PHYSICAL_ADDRESS": "geolocation",
    "PHYSICAL_COORDINATES": "geolocation",
    "COUNTRY": "geolocation",
    "CLOUD": "infrastructure",
    "PROVIDER": "infrastructure",
    "OPERATING_SYSTEM": "infrastructure",
    "SOFTWARE": "infrastructure",
    "HASH": "other",
    "RAW_RIR": "other",
    "RAW_DNS": "other",
    "RAW_FILE": "other",
}

# Maps categories to report sections
_SECTION_MAP: dict[str, ReportSectionType] = {
    "threat": ReportSectionType.THREAT_INTELLIGENCE,
    "vulnerability": ReportSectionType.VULNERABILITY_ASSESSMENT,
    "network": ReportSectionType.NETWORK_TOPOLOGY,
    "infrastructure": ReportSectionType.INFRASTRUCTURE_ANALYSIS,
    "web": ReportSectionType.WEB_PRESENCE,
    "identity": ReportSectionType.IDENTITY_EXPOSURE,
    "data_leak": ReportSectionType.DATA_LEAKS,
    "social": ReportSectionType.SOCIAL_MEDIA,
    "geolocation": ReportSectionType.GEOLOCATION,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // chars_per_token)


def _classify_risk(risk_value: int, thresholds: dict[str, int]) -> RiskLevel:
    """Classify a numeric risk value into a RiskLevel."""
    if risk_value >= thresholds.get("critical", 80):
        return RiskLevel.CRITICAL
    elif risk_value >= thresholds.get("high", 60):
        return RiskLevel.HIGH
    elif risk_value >= thresholds.get("medium", 40):
        return RiskLevel.MEDIUM
    elif risk_value >= thresholds.get("low", 20):
        return RiskLevel.LOW
    return RiskLevel.INFO


def _categorize_event_type(event_type: str) -> str:
    """Map an event type string to a category."""
    for prefix, category in _CATEGORY_MAP.items():
        if event_type.startswith(prefix):
            return category
    return "other"


def _normalize_data(data: str, event_type: str) -> str:
    """Normalize event data for deduplication.

    - Strip whitespace
    - Lowercase domains, emails
    - Normalize IP addresses (strip leading zeros)
    - Normalize URLs (strip fragments)
    """
    data = data.strip()

    if "EMAIL" in event_type:
        data = data.lower().strip()
    elif "DOMAIN" in event_type or "INTERNET_NAME" in event_type:
        data = data.lower().strip().rstrip(".")
    elif "URL" in event_type:
        # Remove fragment
        data = re.sub(r"#.*$", "", data)
        # Remove trailing slash
        data = data.rstrip("/")
    elif "IP_ADDRESS" in event_type:
        # Remove leading zeros in octets for IPv4
        parts = data.split(".")
        if len(parts) == 4:
            try:
                data = ".".join(str(int(p)) for p in parts)
            except ValueError:
                pass

    return data


def _make_dedup_key(event_type: str, data: str) -> str:
    """Create a deduplication key from type + normalized data."""
    content = f"{event_type}:{data}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

_SECTION_DEFINITIONS: list[tuple[ReportSectionType, str, str, int]] = [
    (ReportSectionType.EXECUTIVE_SUMMARY,
     "Executive Summary",
     "High-level overview of key findings across all categories.",
     100),
    (ReportSectionType.THREAT_INTELLIGENCE,
     "Threat Intelligence",
     "Malicious indicators, blacklisted entities, and dark web mentions.",
     90),
    (ReportSectionType.VULNERABILITY_ASSESSMENT,
     "Vulnerability Assessment",
     "Discovered vulnerabilities and security weaknesses.",
     85),
    (ReportSectionType.DATA_LEAKS,
     "Data Leak Exposure",
     "Leaked credentials, passwords, and sensitive data.",
     80),
    (ReportSectionType.IDENTITY_EXPOSURE,
     "Identity Exposure",
     "Email addresses, usernames, phone numbers, and personal information.",
     70),
    (ReportSectionType.INFRASTRUCTURE_ANALYSIS,
     "Infrastructure Analysis",
     "Domains, DNS records, SSL certificates, and cloud services.",
     60),
    (ReportSectionType.NETWORK_TOPOLOGY,
     "Network Topology",
     "IP addresses, netblocks, open ports, and BGP information.",
     55),
    (ReportSectionType.WEB_PRESENCE,
     "Web Presence",
     "Web servers, technologies, URLs, and HTTP details.",
     50),
    (ReportSectionType.SOCIAL_MEDIA,
     "Social Media",
     "Social media accounts, profiles, and mentions.",
     40),
    (ReportSectionType.GEOLOCATION,
     "Geolocation",
     "Physical locations, coordinates, and country information.",
     30),
    (ReportSectionType.RECOMMENDATIONS,
     "Recommendations",
     "Actionable remediation steps based on findings.",
     95),
    (ReportSectionType.APPENDIX,
     "Appendix",
     "Complete data reference and raw findings.",
     10),
]


# ---------------------------------------------------------------------------
# Main preprocessor
# ---------------------------------------------------------------------------

class ReportPreprocessor:
    """Preprocess scan events into structured report context for LLM generation.

    Steps:
    1. Normalize event data (lowercase, strip, format)
    2. Deduplicate by type + normalized data
    3. Classify risk level and category
    4. Filter by confidence, risk, and exclusion rules
    5. Group into report sections
    6. Sort by priority within sections
    7. Estimate token budgets
    8. Build ReportContext with statistics
    """

    def __init__(self, config: PreprocessorConfig | None = None) -> None:
        self.config = config or PreprocessorConfig()

    def process(
        self,
        events: list[dict[str, Any]],
        scan_metadata: dict[str, Any] | None = None,
    ) -> ReportContext:
        """Process raw scan events into a report context.

        Args:
            events: List of event dicts with keys: event_type, data, module,
                confidence, risk, timestamp, event_id, source_event_id, tags, metadata.
            scan_metadata: Optional dict with scan_id, target, start_time, end_time.

        Returns:
            ReportContext with structured, prioritized sections.
        """
        t0 = time.monotonic()
        metadata = scan_metadata or {}
        stats = PreprocessorStats(total_input_events=len(events))

        # Step 1-2: Normalize and deduplicate
        normalized = self._normalize_events(events)
        if self.config.enable_dedup:
            normalized = self._deduplicate(normalized, stats)

        stats.total_after_dedup = len(normalized)

        # Step 3: Classify risk and category
        for evt in normalized:
            evt.risk_level = _classify_risk(evt.risk, self.config.risk_thresholds)
            evt.category = _categorize_event_type(evt.event_type)

        # Step 4: Filter
        filtered = self._filter_events(normalized, stats)
        stats.total_after_filter = len(filtered)

        # Step 5-6: Group into sections and sort
        sections = self._build_sections(filtered)

        # Count stats
        stats.events_by_risk = dict(Counter(e.risk_level.name for e in filtered))
        stats.events_by_category = dict(Counter(e.category for e in filtered))
        stats.sections_populated = sum(1 for s in sections if s.has_content)

        # Step 7: Build context
        context = ReportContext(
            scan_id=metadata.get("scan_id", ""),
            scan_target=metadata.get("target", ""),
            scan_start=metadata.get("start_time", 0.0),
            scan_end=metadata.get("end_time", 0.0),
            sections=sections,
        )

        # Token estimation
        context.token_estimate = _estimate_tokens(
            context.to_text(), self.config.estimated_chars_per_token
        )
        stats.token_estimate = context.token_estimate
        context.statistics = {
            "input_events": stats.total_input_events,
            "after_dedup": stats.total_after_dedup,
            "after_filter": stats.total_after_filter,
            "duplicates_removed": stats.duplicates_removed,
            "filtered_low_confidence": stats.filtered_low_confidence,
            "filtered_low_risk": stats.filtered_low_risk,
            "events_by_risk": stats.events_by_risk,
            "events_by_category": stats.events_by_category,
            "sections_populated": stats.sections_populated,
            "token_estimate": stats.token_estimate,
        }

        context.preprocessing_ms = (time.monotonic() - t0) * 1000
        log.info(
            "Preprocessed %d events → %d unique → %d filtered → %d sections (%.1fms)",
            stats.total_input_events,
            stats.total_after_dedup,
            stats.total_after_filter,
            stats.sections_populated,
            context.preprocessing_ms,
        )

        return context

    # -----------------------------------------------------------------------
    # Internal steps
    # -----------------------------------------------------------------------

    def _normalize_events(self, events: list[dict[str, Any]]) -> list[NormalizedEvent]:
        """Convert raw dicts to normalized events."""
        result = []
        for evt in events:
            event_type = evt.get("event_type", evt.get("eventType", "UNKNOWN"))
            raw_data = str(evt.get("data", ""))
            normalized_data = _normalize_data(raw_data, event_type)

            ne = NormalizedEvent(
                event_id=str(evt.get("event_id", evt.get("hash", ""))),
                event_type=event_type,
                data=normalized_data,
                module=evt.get("module", ""),
                confidence=int(evt.get("confidence", 50)),
                risk=int(evt.get("risk", 0)),
                timestamp=float(evt.get("timestamp", evt.get("generated", 0.0))),
                source_event_id=str(evt.get("source_event_id", evt.get("sourceEventHash", ""))),
                tags=evt.get("tags", []),
                metadata=evt.get("metadata", {}),
                dedup_key=_make_dedup_key(event_type, normalized_data),
            )
            result.append(ne)
        return result

    def _deduplicate(
        self,
        events: list[NormalizedEvent],
        stats: PreprocessorStats,
    ) -> list[NormalizedEvent]:
        """Remove duplicate events, keeping highest-confidence version."""
        seen: dict[str, NormalizedEvent] = {}
        for evt in events:
            key = evt.dedup_key
            if key in seen:
                # Keep the one with higher confidence/risk
                existing = seen[key]
                if evt.priority_score > existing.priority_score:
                    seen[key] = evt
                stats.duplicates_removed += 1
            else:
                seen[key] = evt
        return list(seen.values())

    def _filter_events(
        self,
        events: list[NormalizedEvent],
        stats: PreprocessorStats,
    ) -> list[NormalizedEvent]:
        """Filter events by confidence, risk, and exclusion rules."""
        result = []
        for evt in events:
            if evt.confidence < self.config.min_confidence:
                stats.filtered_low_confidence += 1
                continue
            if evt.risk < self.config.min_risk:
                stats.filtered_low_risk += 1
                continue
            if evt.event_type in self.config.exclude_event_types:
                stats.filtered_excluded_type += 1
                continue
            if (self.config.include_categories
                    and evt.category not in self.config.include_categories):
                continue
            result.append(evt)

        # Cap total events
        if len(result) > self.config.max_total_events:
            result.sort(key=lambda e: e.priority_score, reverse=True)
            result = result[:self.config.max_total_events]

        return result

    def _build_sections(self, events: list[NormalizedEvent]) -> list[ReportSection]:
        """Group events into report sections."""
        # Group events by category → section
        categorized: dict[ReportSectionType, list[NormalizedEvent]] = defaultdict(list)

        for evt in events:
            section_type = _SECTION_MAP.get(evt.category, ReportSectionType.APPENDIX)
            categorized[section_type].append(evt)

        # Build section objects from definitions
        sections = []
        for section_type, title, description, priority in _SECTION_DEFINITIONS:
            section_events = categorized.get(section_type, [])

            # Sort events by priority (highest first)
            section_events.sort(key=lambda e: e.priority_score, reverse=True)

            section = ReportSection(
                section_type=section_type,
                title=title,
                description=description,
                events=section_events,
                priority=priority,
                max_events=self.config.max_events_per_section,
            )

            # Token estimate for the section
            if section.has_content:
                section.token_estimate = _estimate_tokens(
                    section.to_text(), self.config.estimated_chars_per_token
                )

            sections.append(section)

        # Executive summary gets top events from all categories
        exec_section = next(
            (s for s in sections if s.section_type == ReportSectionType.EXECUTIVE_SUMMARY),
            None,
        )
        if exec_section is not None:
            # Gather top 10 highest-priority events across all categories
            all_events = sorted(events, key=lambda e: e.priority_score, reverse=True)
            exec_section.events = all_events[:10]
            exec_section.token_estimate = _estimate_tokens(
                exec_section.to_text(), self.config.estimated_chars_per_token
            )

        # Recommendations section stays empty (LLM generates it)

        return sections
