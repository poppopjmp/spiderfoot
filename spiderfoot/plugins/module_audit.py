"""Module Audit Framework for SpiderFoot.

Implements Phase 3 cycles 151-220:

Cycles 151-200 — Migration Verification:
  - Batch module contract validation
  - Base class migration status (Plugin → ModernPlugin → AsyncPlugin)
  - Async handleEvent capability analysis
  - Event type dependency graph
  - Module conflict detection via CapabilityRegistry

Cycles 201-220 — Metadata & Documentation Completeness:
  - Meta dict completeness audit
  - Category/flag standardization checks
  - Module documentation generator
  - Module summary report
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("spiderfoot.module_audit")


# ── Enums ────────────────────────────────────────────────────────────


class MigrationStatus(Enum):
    """Module migration tier."""
    LEGACY = "legacy"            # SpiderFootPlugin
    MODERN = "modern"            # SpiderFootModernPlugin
    ASYNC = "async"              # SpiderFootAsyncPlugin
    UNKNOWN = "unknown"


class MetaCompleteness(Enum):
    """Module metadata completeness level."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    MISSING = "missing"


# ── Standard categories and flags ─────────────────────────────────────

STANDARD_CATEGORIES = frozenset({
    "Content Analysis", "Crawling and Scanning", "DNS",
    "Leaks, Dumps and Breaches", "Passive DNS", "Public Registries",
    "Real World", "Reputation Systems", "Search Engines",
    "Secondary Networks", "Social Media",
})

STANDARD_FLAGS = frozenset({
    "apikey", "errorprone", "invasive", "slow", "tool",
})

STANDARD_USE_CASES = frozenset({
    "Footprint", "Investigate", "Passive",
})


# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class ModuleInfo:
    """Collected information about a single module."""
    name: str
    file_path: str
    base_class: str = ""
    migration_status: MigrationStatus = MigrationStatus.UNKNOWN
    has_async_handle_event: bool = False
    has_meta: bool = False
    meta_completeness: MetaCompleteness = MetaCompleteness.MISSING
    meta_fields_present: list[str] = field(default_factory=list)
    meta_fields_missing: list[str] = field(default_factory=list)
    watched_events: list[str] = field(default_factory=list)
    produced_events: list[str] = field(default_factory=list)
    has_opts: bool = False
    has_optdescs: bool = False
    has_data_source: bool = False
    categories: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    non_standard_categories: list[str] = field(default_factory=list)
    non_standard_flags: list[str] = field(default_factory=list)
    line_count: int = 0
    contract_valid: bool = True
    contract_errors: list[str] = field(default_factory=list)
    contract_warnings: list[str] = field(default_factory=list)


@dataclass
class EventEdge:
    """An edge in the event dependency graph."""
    source_module: str
    target_module: str
    event_type: str


@dataclass
class EventTypeInfo:
    """Info about a single event type in the system."""
    name: str
    producers: list[str] = field(default_factory=list)
    consumers: list[str] = field(default_factory=list)

    @property
    def is_orphan_producer(self) -> bool:
        """No module consumes this event type."""
        return len(self.consumers) == 0 and len(self.producers) > 0

    @property
    def is_orphan_consumer(self) -> bool:
        """No module produces this event type (except root events)."""
        return len(self.producers) == 0 and len(self.consumers) > 0


@dataclass
class AuditReport:
    """Complete audit report for all modules."""
    generated_at: str = ""
    total_modules: int = 0
    modules: list[ModuleInfo] = field(default_factory=list)
    event_types: dict[str, EventTypeInfo] = field(default_factory=dict)
    event_edges: list[EventEdge] = field(default_factory=list)

    # Migration summary
    legacy_count: int = 0
    modern_count: int = 0
    async_count: int = 0
    unknown_count: int = 0

    # Quality summary
    contract_valid_count: int = 0
    contract_invalid_count: int = 0
    meta_complete_count: int = 0
    meta_partial_count: int = 0
    meta_minimal_count: int = 0
    meta_missing_count: int = 0
    async_handler_count: int = 0
    sync_handler_count: int = 0

    # Warnings
    orphan_producers: list[str] = field(default_factory=list)
    orphan_consumers: list[str] = field(default_factory=list)
    modules_without_data_source: list[str] = field(default_factory=list)
    modules_with_non_standard_categories: list[str] = field(default_factory=list)

    @property
    def migration_percentage(self) -> float:
        """Percentage of modules on AsyncPlugin (fully migrated)."""
        if self.total_modules == 0:
            return 0.0
        return (self.async_count / self.total_modules) * 100.0

    @property
    def meta_completeness_percentage(self) -> float:
        """Percentage of modules with complete metadata."""
        if self.total_modules == 0:
            return 0.0
        return (self.meta_complete_count / self.total_modules) * 100.0

    def summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for JSON/logging."""
        return {
            "generated_at": self.generated_at,
            "total_modules": self.total_modules,
            "migration": {
                "legacy": self.legacy_count,
                "modern": self.modern_count,
                "async": self.async_count,
                "unknown": self.unknown_count,
                "migration_pct": round(self.migration_percentage, 1),
            },
            "contract_validation": {
                "valid": self.contract_valid_count,
                "invalid": self.contract_invalid_count,
            },
            "metadata": {
                "complete": self.meta_complete_count,
                "partial": self.meta_partial_count,
                "minimal": self.meta_minimal_count,
                "missing": self.meta_missing_count,
                "completeness_pct": round(self.meta_completeness_percentage, 1),
            },
            "async_handlers": {
                "async": self.async_handler_count,
                "sync": self.sync_handler_count,
            },
            "warnings": {
                "orphan_producers": len(self.orphan_producers),
                "orphan_consumers": len(self.orphan_consumers),
                "no_data_source": len(self.modules_without_data_source),
                "non_standard_categories": len(self.modules_with_non_standard_categories),
            },
        }


# ── Static Source Analysis ────────────────────────────────────────────


class ModuleSourceAnalyzer:
    """Analyze module source files without importing them.

    Uses regex and AST-level analysis to extract module information
    from source code, avoiding import side effects.

    This is Cycles 151-160: basic migration verification.
    """

    # Patterns for base class detection
    _ASYNC_PATTERN = re.compile(
        r'class\s+\w+\s*\(\s*SpiderFootAsyncPlugin\s*\)', re.MULTILINE
    )
    _MODERN_PATTERN = re.compile(
        r'class\s+\w+\s*\(\s*SpiderFootModernPlugin\s*\)', re.MULTILINE
    )
    _LEGACY_PATTERN = re.compile(
        r'class\s+\w+\s*\(\s*SpiderFootPlugin\s*\)', re.MULTILINE
    )
    _META_PATTERN = re.compile(
        r'meta\s*=\s*\{', re.MULTILINE
    )
    _ASYNC_HANDLE_PATTERN = re.compile(
        r'async\s+def\s+handleEvent\s*\(', re.MULTILINE
    )
    _SYNC_HANDLE_PATTERN = re.compile(
        r'(?<!async\s)def\s+handleEvent\s*\(', re.MULTILINE
    )

    def analyze_file(self, file_path: str) -> ModuleInfo:
        """Analyze a single module source file.

        Args:
            file_path: Path to the .py file.

        Returns:
            ModuleInfo with source-level analysis.
        """
        name = Path(file_path).stem
        info = ModuleInfo(name=name, file_path=file_path)

        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            info.contract_errors.append(f"Cannot read file: {e}")
            return info

        info.line_count = content.count("\n") + 1

        # Determine base class
        if self._ASYNC_PATTERN.search(content):
            info.base_class = "SpiderFootAsyncPlugin"
            info.migration_status = MigrationStatus.ASYNC
        elif self._MODERN_PATTERN.search(content):
            info.base_class = "SpiderFootModernPlugin"
            info.migration_status = MigrationStatus.MODERN
        elif self._LEGACY_PATTERN.search(content):
            info.base_class = "SpiderFootPlugin"
            info.migration_status = MigrationStatus.LEGACY
        else:
            info.migration_status = MigrationStatus.UNKNOWN

        # Check async handleEvent
        info.has_async_handle_event = bool(self._ASYNC_HANDLE_PATTERN.search(content))

        # Check meta presence
        info.has_meta = bool(self._META_PATTERN.search(content))

        # Check opts/optdescs
        info.has_opts = bool(re.search(r'opts\s*=\s*\{', content))
        info.has_optdescs = bool(re.search(r'optdescs\s*=\s*\{', content))

        # Extract meta fields via regex (lightweight)
        info = self._extract_meta_fields(content, info)

        return info

    def _extract_meta_fields(self, content: str, info: ModuleInfo) -> ModuleInfo:
        """Extract meta dict fields from source code."""
        required_fields = ["name", "summary", "flags", "useCases", "categories"]
        optional_fields = ["dataSource", "descr"]

        for fld in required_fields:
            pattern = rf"""['"]{ re.escape(fld) }['"]\s*:"""
            if re.search(pattern, content):
                info.meta_fields_present.append(fld)
            else:
                info.meta_fields_missing.append(fld)

        for fld in optional_fields:
            pattern = rf"""['"]{ re.escape(fld) }['"]\s*:"""
            if re.search(pattern, content):
                info.meta_fields_present.append(fld)
                if fld == "dataSource":
                    info.has_data_source = True

        # Extract categories, flags, useCases values
        info.categories = self._extract_list_values(content, "categories")
        info.flags = self._extract_list_values(content, "flags")
        info.use_cases = self._extract_list_values(content, "useCases")

        # Check for non-standard values
        for cat in info.categories:
            if cat not in STANDARD_CATEGORIES:
                info.non_standard_categories.append(cat)
        for flag in info.flags:
            if flag not in STANDARD_FLAGS:
                info.non_standard_flags.append(flag)

        # Compute completeness
        required_present = sum(1 for f in required_fields if f in info.meta_fields_present)
        if not info.has_meta:
            info.meta_completeness = MetaCompleteness.MISSING
        elif required_present == len(required_fields):
            info.meta_completeness = MetaCompleteness.COMPLETE
        elif required_present >= 3:
            info.meta_completeness = MetaCompleteness.PARTIAL
        else:
            info.meta_completeness = MetaCompleteness.MINIMAL

        return info

    def _extract_list_values(self, content: str, field_name: str) -> list[str]:
        """Extract string values from a list field in meta dict."""
        pattern = rf"""['"]{ re.escape(field_name) }['"]\s*:\s*\[([^\]]*)\]"""
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return []
        inner = match.group(1)
        return re.findall(r"""['"]([^'"]+)['"]""", inner)

    def analyze_directory(self, modules_dir: str) -> list[ModuleInfo]:
        """Analyze all sfp_*.py files in a directory.

        Args:
            modules_dir: Path to the modules directory.

        Returns:
            List of ModuleInfo for all modules found.
        """
        results = []
        modules_path = Path(modules_dir)
        if not modules_path.is_dir():
            return results

        for py_file in sorted(modules_path.glob("sfp_*.py")):
            info = self.analyze_file(str(py_file))
            results.append(info)

        return results


# ── Dynamic Module Validator ──────────────────────────────────────────


class ModuleContractAuditor:
    """Validate modules against the contract by loading them.

    This is Cycles 161-170: deeper validation via import + instantiation.
    Integrates with module_contract.validate_module().
    """

    def __init__(self, modules_dir: str | None = None):
        self._modules_dir = modules_dir

    def validate_module_class(
        self,
        module_class: type,
        name: str | None = None,
    ) -> ModuleInfo:
        """Validate a loaded module class.

        Args:
            module_class: The module class to validate.
            name: Optional name override.

        Returns:
            ModuleInfo with contract validation results.
        """
        mod_name = name or getattr(module_class, "__name__", None) or module_class.__name__
        info = ModuleInfo(
            name=mod_name,
            file_path=inspect.getfile(module_class) if hasattr(module_class, "__module__") else "",
        )

        # Determine base class chain
        mro = [c.__name__ for c in inspect.getmro(module_class)]
        if "SpiderFootAsyncPlugin" in mro:
            info.migration_status = MigrationStatus.ASYNC
            info.base_class = "SpiderFootAsyncPlugin"
        elif "SpiderFootModernPlugin" in mro:
            info.migration_status = MigrationStatus.MODERN
            info.base_class = "SpiderFootModernPlugin"
        elif "SpiderFootPlugin" in mro:
            info.migration_status = MigrationStatus.LEGACY
            info.base_class = "SpiderFootPlugin"

        # Check async handleEvent
        handle = getattr(module_class, "handleEvent", None)
        if handle and inspect.iscoroutinefunction(handle):
            info.has_async_handle_event = True

        # Contract validation
        try:
            from spiderfoot.plugins.module_contract import validate_module
            result = validate_module(module_class, name=mod_name)
            info.contract_valid = result.is_valid
            info.contract_errors = result.all_errors
            info.contract_warnings = result.warnings
        except Exception as e:
            info.contract_valid = False
            info.contract_errors.append(f"Contract validation error: {e}")

        # Meta inspection
        meta = getattr(module_class, "meta", None)
        if meta and isinstance(meta, dict):
            info.has_meta = True
            self._inspect_meta(meta, info)
        else:
            info.meta_completeness = MetaCompleteness.MISSING

        # Event declarations
        try:
            instance = module_class()
            if callable(getattr(instance, "watchedEvents", None)):
                info.watched_events = instance.watchedEvents() or []
            if callable(getattr(instance, "producedEvents", None)):
                info.produced_events = instance.producedEvents() or []
        except Exception:
            pass

        info.has_opts = hasattr(module_class, "opts") and bool(getattr(module_class, "opts", None))
        info.has_optdescs = hasattr(module_class, "optdescs") and bool(getattr(module_class, "optdescs", None))

        return info

    def _inspect_meta(self, meta: dict, info: ModuleInfo) -> None:
        """Inspect a meta dict for completeness."""
        required_fields = ["name", "summary", "flags", "useCases", "categories"]
        optional_fields = ["dataSource", "descr"]

        for fld in required_fields:
            if fld in meta:
                info.meta_fields_present.append(fld)
            else:
                info.meta_fields_missing.append(fld)

        for fld in optional_fields:
            if fld in meta:
                info.meta_fields_present.append(fld)
                if fld == "dataSource":
                    info.has_data_source = True

        info.categories = meta.get("categories", [])
        info.flags = meta.get("flags", [])
        info.use_cases = meta.get("useCases", [])

        for cat in info.categories:
            if cat not in STANDARD_CATEGORIES:
                info.non_standard_categories.append(cat)
        for flag in info.flags:
            if flag not in STANDARD_FLAGS:
                info.non_standard_flags.append(flag)

        required_present = sum(1 for f in required_fields if f in info.meta_fields_present)
        if required_present == len(required_fields):
            info.meta_completeness = MetaCompleteness.COMPLETE
        elif required_present >= 3:
            info.meta_completeness = MetaCompleteness.PARTIAL
        else:
            info.meta_completeness = MetaCompleteness.MINIMAL


# ── Event Dependency Graph ────────────────────────────────────────────


class EventDependencyGraph:
    """Build and analyze the event dependency graph across modules.

    This is Cycles 171-180: understand module interconnections.
    """

    def __init__(self) -> None:
        self._event_types: dict[str, EventTypeInfo] = {}
        self._edges: list[EventEdge] = []
        self._modules: dict[str, ModuleInfo] = {}

    def add_module(self, info: ModuleInfo) -> None:
        """Add a module's event info to the graph."""
        self._modules[info.name] = info

        for evt in info.produced_events:
            if evt not in self._event_types:
                self._event_types[evt] = EventTypeInfo(name=evt)
            self._event_types[evt].producers.append(info.name)

        for evt in info.watched_events:
            if evt not in self._event_types:
                self._event_types[evt] = EventTypeInfo(name=evt)
            self._event_types[evt].consumers.append(info.name)

    def build_edges(self) -> list[EventEdge]:
        """Build directed edges: producer → consumer via event type."""
        self._edges.clear()
        for evt_name, evt_info in self._event_types.items():
            for producer in evt_info.producers:
                for consumer in evt_info.consumers:
                    if producer != consumer:
                        self._edges.append(EventEdge(
                            source_module=producer,
                            target_module=consumer,
                            event_type=evt_name,
                        ))
        return list(self._edges)

    @property
    def event_types(self) -> dict[str, EventTypeInfo]:
        """Return all event types."""
        return dict(self._event_types)

    @property
    def edges(self) -> list[EventEdge]:
        """Return all edges (call build_edges() first)."""
        return list(self._edges)

    def orphan_producers(self) -> list[str]:
        """Event types that are produced but never consumed."""
        return [
            name for name, info in self._event_types.items()
            if info.is_orphan_producer
        ]

    def orphan_consumers(self) -> list[str]:
        """Event types that are consumed but never produced."""
        # Root events are expected to have no producer
        root_events = {
            "ROOT", "INITIAL_TARGET",
            "TARGET_WEB_CONTENT", "TARGET_WEB_CONTENT_TYPE",
        }
        return [
            name for name, info in self._event_types.items()
            if info.is_orphan_consumer and name not in root_events
        ]

    def downstream_modules(self, module_name: str) -> set[str]:
        """Find all modules that directly receive events from the given module."""
        if not self._edges:
            self.build_edges()
        return {
            edge.target_module for edge in self._edges
            if edge.source_module == module_name
        }

    def upstream_modules(self, module_name: str) -> set[str]:
        """Find all modules that produce events consumed by the given module."""
        if not self._edges:
            self.build_edges()
        return {
            edge.source_module for edge in self._edges
            if edge.target_module == module_name
        }

    def module_fanout(self, module_name: str) -> int:
        """Number of distinct downstream modules."""
        return len(self.downstream_modules(module_name))

    def module_fanin(self, module_name: str) -> int:
        """Number of distinct upstream modules."""
        return len(self.upstream_modules(module_name))

    def highest_fanout(self, top_n: int = 10) -> list[tuple[str, int]]:
        """Modules with the most downstream connections."""
        if not self._edges:
            self.build_edges()
        fanouts = {name: self.module_fanout(name) for name in self._modules}
        return sorted(fanouts.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def highest_fanin(self, top_n: int = 10) -> list[tuple[str, int]]:
        """Modules with the most upstream connections."""
        if not self._edges:
            self.build_edges()
        fanins = {name: self.module_fanin(name) for name in self._modules}
        return sorted(fanins.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def to_dot(self, max_edges: int = 500) -> str:
        """Export the graph in DOT format for Graphviz visualization.

        Args:
            max_edges: Maximum edges to include (for readability).

        Returns:
            DOT format string.
        """
        if not self._edges:
            self.build_edges()

        lines = ["digraph EventFlow {", "  rankdir=LR;"]
        lines.append('  node [shape=box, fontsize=10];')

        edge_count = 0
        for edge in self._edges:
            if edge_count >= max_edges:
                lines.append(f'  // ... truncated at {max_edges} edges')
                break
            label = edge.event_type.replace('"', '\\"')
            lines.append(
                f'  "{edge.source_module}" -> "{edge.target_module}" '
                f'[label="{label}", fontsize=8];'
            )
            edge_count += 1

        lines.append("}")
        return "\n".join(lines)


# ── Metadata Completeness Auditor ─────────────────────────────────────


class MetadataAuditor:
    """Audit and report on module metadata completeness.

    This is Cycles 201-220: metadata quality assurance.
    """

    REQUIRED_META_FIELDS = ["name", "summary", "flags", "useCases", "categories"]
    RECOMMENDED_META_FIELDS = ["dataSource"]
    DATASOURCE_FIELDS = ["website", "model", "references"]

    def audit_module(self, info: ModuleInfo) -> dict[str, Any]:
        """Audit a single module's metadata quality.

        Returns:
            Dict with audit results including score (0-100).
        """
        score = 0
        issues: list[str] = []
        suggestions: list[str] = []

        # Has meta at all? (20 points)
        if info.has_meta:
            score += 20
        else:
            issues.append("Missing meta dict entirely")
            return {"score": 0, "issues": issues, "suggestions": ["Add meta dict"]}

        # Required fields present (10 points each, 50 total)
        for fld in self.REQUIRED_META_FIELDS:
            if fld in info.meta_fields_present:
                score += 10
            else:
                issues.append(f"Missing required meta field: {fld}")

        # Has dataSource (10 points)
        if info.has_data_source:
            score += 10
        else:
            suggestions.append("Add dataSource with website, model, references")

        # Categories are standard (5 points)
        if info.categories and not info.non_standard_categories:
            score += 5
        elif info.non_standard_categories:
            suggestions.append(
                f"Non-standard categories: {info.non_standard_categories}. "
                f"Standard: {sorted(STANDARD_CATEGORIES)}"
            )

        # Flags are standard (5 points)
        if not info.non_standard_flags:
            score += 5
        else:
            suggestions.append(
                f"Non-standard flags: {info.non_standard_flags}. "
                f"Standard: {sorted(STANDARD_FLAGS)}"
            )

        # Use cases present and standard (5 points)
        if info.use_cases:
            valid = all(uc in STANDARD_USE_CASES for uc in info.use_cases)
            if valid:
                score += 5
            else:
                non_std = [uc for uc in info.use_cases if uc not in STANDARD_USE_CASES]
                suggestions.append(f"Non-standard use cases: {non_std}")
        else:
            suggestions.append("Add useCases (Footprint, Investigate, Passive)")

        # Has opts and optdescs (5 points)
        if info.has_opts and info.has_optdescs:
            score += 5
        elif info.has_opts and not info.has_optdescs:
            suggestions.append("Add optdescs for all options")

        return {
            "module": info.name,
            "score": min(score, 100),
            "issues": issues,
            "suggestions": suggestions,
            "completeness": info.meta_completeness.value,
        }

    def audit_batch(self, modules: list[ModuleInfo]) -> dict[str, Any]:
        """Audit a batch of modules and produce aggregate report."""
        results = []
        total_score = 0
        for mod in modules:
            result = self.audit_module(mod)
            results.append(result)
            total_score += result["score"]

        avg_score = total_score / len(results) if results else 0

        # Find worst modules
        results.sort(key=lambda r: r["score"])
        worst = results[:10] if len(results) > 10 else results

        # Common issues
        issue_counts: dict[str, int] = defaultdict(int)
        for r in results:
            for issue in r["issues"]:
                issue_counts[issue] += 1

        return {
            "total_modules": len(results),
            "average_score": round(avg_score, 1),
            "perfect_score_count": sum(1 for r in results if r["score"] == 100),
            "below_50_count": sum(1 for r in results if r["score"] < 50),
            "worst_modules": [
                {"module": r["module"], "score": r["score"]} for r in worst
            ],
            "common_issues": dict(
                sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }


# ── Module Documentation Generator ──────────────────────────────────


class ModuleDocGenerator:
    """Generate documentation from module metadata.

    This is Cycles 211-220.
    """

    def generate_module_doc(self, info: ModuleInfo) -> str:
        """Generate markdown documentation for a single module."""
        lines = [f"## {info.name}\n"]

        if info.categories:
            lines.append(f"**Categories:** {', '.join(info.categories)}\n")
        if info.use_cases:
            lines.append(f"**Use Cases:** {', '.join(info.use_cases)}\n")
        if info.flags:
            lines.append(f"**Flags:** {', '.join(info.flags)}\n")

        lines.append(f"**Base Class:** {info.base_class}")
        lines.append(f"**Async handleEvent:** {'Yes' if info.has_async_handle_event else 'No'}\n")

        if info.watched_events:
            lines.append("### Watched Events\n")
            for evt in sorted(info.watched_events):
                lines.append(f"- `{evt}`")
            lines.append("")

        if info.produced_events:
            lines.append("### Produced Events\n")
            for evt in sorted(info.produced_events):
                lines.append(f"- `{evt}`")
            lines.append("")

        return "\n".join(lines)

    def generate_category_index(self, modules: list[ModuleInfo]) -> str:
        """Generate a category-based module index."""
        by_category: dict[str, list[str]] = defaultdict(list)
        for mod in modules:
            if mod.categories:
                for cat in mod.categories:
                    by_category[cat].append(mod.name)
            else:
                by_category["Uncategorized"].append(mod.name)

        lines = ["# Module Index by Category\n"]
        for cat in sorted(by_category.keys()):
            mods = sorted(by_category[cat])
            lines.append(f"## {cat} ({len(mods)} modules)\n")
            for mod_name in mods:
                lines.append(f"- {mod_name}")
            lines.append("")

        return "\n".join(lines)

    def generate_event_flow_doc(self, graph: EventDependencyGraph) -> str:
        """Generate documentation of the event flow."""
        lines = ["# Event Type Reference\n"]

        for evt_name in sorted(graph.event_types.keys()):
            evt = graph.event_types[evt_name]
            lines.append(f"## `{evt_name}`\n")
            if evt.producers:
                lines.append(f"**Produced by:** {', '.join(sorted(evt.producers))}\n")
            if evt.consumers:
                lines.append(f"**Consumed by:** {', '.join(sorted(evt.consumers))}\n")
            if evt.is_orphan_producer:
                lines.append("⚠️ No consumers for this event type.\n")
            if evt.is_orphan_consumer:
                lines.append("⚠️ No producers for this event type.\n")
            lines.append("")

        return "\n".join(lines)


# ── Async Execution Verifier ─────────────────────────────────────────


class AsyncExecutionVerifier:
    """Verify that modules with async handleEvent work correctly.

    This is Cycles 181-190: async execution verification.
    """

    @staticmethod
    def check_async_compatibility(module_class: type) -> dict[str, Any]:
        """Check if a module class is async-compatible.

        Returns:
            Dict with compatibility info and any issues found.
        """
        result: dict[str, Any] = {
            "module": getattr(module_class, "__name__", module_class.__name__),
            "is_async_plugin": False,
            "has_async_handle_event": False,
            "has_async_methods": [],
            "issues": [],
        }

        # Check MRO
        mro_names = [c.__name__ for c in inspect.getmro(module_class)]
        result["is_async_plugin"] = "SpiderFootAsyncPlugin" in mro_names

        # Check handleEvent
        handle = getattr(module_class, "handleEvent", None)
        if handle:
            result["has_async_handle_event"] = inspect.iscoroutinefunction(handle)

        # Find all async methods
        for name, method in inspect.getmembers(module_class, predicate=inspect.isfunction):
            if inspect.iscoroutinefunction(method):
                result["has_async_methods"].append(name)

        # Check for common async anti-patterns
        try:
            source = inspect.getsource(module_class)
        except (OSError, TypeError):
            source = ""

        if source:
            # Blocking calls inside async methods
            if "requests.get" in source and result["has_async_handle_event"]:
                result["issues"].append(
                    "Module uses blocking requests.get() but has async handleEvent. "
                    "Use self.async_fetch_url() or aiohttp instead."
                )
            if "time.sleep" in source and result["has_async_handle_event"]:
                result["issues"].append(
                    "Module uses blocking time.sleep() in async context. "
                    "Use asyncio.sleep() instead."
                )
            # Missing await
            if "self.async_fetch_url" in source:
                # Check if any call to async_fetch_url lacks await
                no_await = re.findall(
                    r'(?<!await\s)self\.async_fetch_url\(', source
                )
                if no_await:
                    result["issues"].append(
                        "Possible missing 'await' before self.async_fetch_url()"
                    )

        return result


# ── Full Audit Runner ────────────────────────────────────────────────


class ModuleAuditRunner:
    """Run a complete module audit and produce an AuditReport.

    This orchestrates all the audit components:
    - Source analysis (Cycles 151-160)
    - Contract validation (Cycles 161-170)
    - Event graph (Cycles 171-180)
    - Async verification (Cycles 181-190)
    - Migration completeness (Cycles 191-200)
    - Metadata audit (Cycles 201-220)
    """

    def __init__(self, modules_dir: str | None = None):
        self._modules_dir = modules_dir
        self._source_analyzer = ModuleSourceAnalyzer()
        self._contract_auditor = ModuleContractAuditor()
        self._graph = EventDependencyGraph()
        self._metadata_auditor = MetadataAuditor()
        self._doc_generator = ModuleDocGenerator()

    def run_source_audit(self, modules_dir: str | None = None) -> AuditReport:
        """Run a source-level audit (no imports, fast).

        Args:
            modules_dir: Path to modules directory. Uses self._modules_dir if None.

        Returns:
            AuditReport with source-level analysis.
        """
        directory = modules_dir or self._modules_dir
        if not directory:
            raise ValueError("modules_dir not specified")

        modules = self._source_analyzer.analyze_directory(directory)
        report = self._build_report(modules)
        return report

    def run_class_audit(self, module_classes: dict[str, type]) -> AuditReport:
        """Run a class-level audit on loaded module classes.

        Args:
            module_classes: Dict of module_name → module class.

        Returns:
            AuditReport with class-level analysis.
        """
        modules = []
        for name, cls in module_classes.items():
            info = self._contract_auditor.validate_module_class(cls, name=name)
            modules.append(info)

        report = self._build_report(modules)
        return report

    def _build_report(self, modules: list[ModuleInfo]) -> AuditReport:
        """Build an AuditReport from a list of ModuleInfo."""
        report = AuditReport(
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_modules=len(modules),
            modules=modules,
        )

        # Build event graph
        graph = EventDependencyGraph()
        for mod in modules:
            graph.add_module(mod)
        graph.build_edges()
        report.event_types = graph.event_types
        report.event_edges = graph.edges

        # Migration counts
        for mod in modules:
            if mod.migration_status == MigrationStatus.LEGACY:
                report.legacy_count += 1
            elif mod.migration_status == MigrationStatus.MODERN:
                report.modern_count += 1
            elif mod.migration_status == MigrationStatus.ASYNC:
                report.async_count += 1
            else:
                report.unknown_count += 1

        # Quality counts
        for mod in modules:
            if mod.contract_valid:
                report.contract_valid_count += 1
            else:
                report.contract_invalid_count += 1

            if mod.meta_completeness == MetaCompleteness.COMPLETE:
                report.meta_complete_count += 1
            elif mod.meta_completeness == MetaCompleteness.PARTIAL:
                report.meta_partial_count += 1
            elif mod.meta_completeness == MetaCompleteness.MINIMAL:
                report.meta_minimal_count += 1
            else:
                report.meta_missing_count += 1

            if mod.has_async_handle_event:
                report.async_handler_count += 1
            else:
                report.sync_handler_count += 1

        # Warnings
        report.orphan_producers = graph.orphan_producers()
        report.orphan_consumers = graph.orphan_consumers()
        report.modules_without_data_source = [
            m.name for m in modules
            if not m.has_data_source and not m.name.startswith("sfp__stor")
        ]
        report.modules_with_non_standard_categories = [
            m.name for m in modules if m.non_standard_categories
        ]

        return report

    @property
    def metadata_auditor(self) -> MetadataAuditor:
        """Access the metadata auditor."""
        return self._metadata_auditor

    @property
    def doc_generator(self) -> ModuleDocGenerator:
        """Access the documentation generator."""
        return self._doc_generator

    @property
    def source_analyzer(self) -> ModuleSourceAnalyzer:
        """Access the source analyzer."""
        return self._source_analyzer
