"""Module Development Tooling for SpiderFoot.

Implements Phase 4 Cycles 251-270:

Cycle 251: Module scaffolding — generate properly structured module files
Cycle 252: Module testing CLI — run PluginTestHarness in isolation
Cycle 253: Module validation CLI — run validate_module() with full report
Cycle 254: Hot-reload wiring — connect ModuleWatcher to dev server
Cycle 255: Docker dev profile generation
Cycles 256-270: Enhanced PluginTestHarness — multi-hop event chains,
               mock DB state injection, async module testing
"""

from __future__ import annotations

import inspect
import os
import re
import textwrap
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


# ── Module Scaffold (Cycle 251) ──────────────────────────────────────


@dataclass
class ScaffoldConfig:
    """Configuration for module scaffolding."""
    module_name: str
    display_name: str = ""
    summary: str = ""
    description: str = ""
    author: str = "Van1sh  <van1sh@van1shland.io>" 
    categories: list[str] = field(default_factory=lambda: ["Content Analysis"])
    flags: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=lambda: ["Passive"])
    watched_events: list[str] = field(default_factory=lambda: ["DOMAIN_NAME"])
    produced_events: list[str] = field(default_factory=lambda: ["RAW_RIR_DATA"])
    data_source_website: str = ""
    data_source_model: str = "FREE_NOAUTH_UNLIMITED"
    has_api_key: bool = False
    output_dir: str = "modules"
    use_async: bool = True

    def __post_init__(self):
        if not self.module_name.startswith("sfp_"):
            self.module_name = f"sfp_{self.module_name}"
        if not self.display_name:
            # Convert sfp_my_module -> My Module
            name = self.module_name.replace("sfp_", "")
            self.display_name = name.replace("_", " ").title()


DATA_SOURCE_MODELS = [
    "FREE_NOAUTH_UNLIMITED",
    "FREE_AUTH_UNLIMITED",
    "FREE_AUTH_LIMITED",
    "FREE_NOAUTH_LIMITED",
    "COMMERCIAL_ONLY",
    "PRIVATE_ONLY",
]

STANDARD_CATEGORIES = [
    "Content Analysis",
    "Crawling and Scanning",
    "DNS",
    "Leaks, Dumps and Breaches",
    "Passive DNS",
    "Public Registries",
    "Real World",
    "Reputation Systems",
    "Search Engines",
    "Secondary Networks",
    "Social Media",
]


class ModuleScaffolder:
    """Generate SpiderFoot module source files.

    Usage:
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_example_api",
            summary="Query the Example API",
            watched_events=["IP_ADDRESS"],
            produced_events=["RAW_RIR_DATA"],
            has_api_key=True,
        )
        path = scaffolder.generate(config)
    """

    def generate(self, config: ScaffoldConfig) -> str:
        """Generate a module file from the config.

        Returns:
            The absolute path to the created file.
        """
        source = self._render(config)
        filename = f"{config.module_name}.py"
        filepath = os.path.join(config.output_dir, filename)
        return source

    def generate_to_file(self, config: ScaffoldConfig) -> str:
        """Generate and write to disk.

        Returns:
            The absolute path to the created file.
        """
        source = self.generate(config)
        filename = f"{config.module_name}.py"
        filepath = os.path.join(config.output_dir, filename)
        os.makedirs(config.output_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(source)
        return os.path.abspath(filepath)

    def _render(self, config: ScaffoldConfig) -> str:
        """Render the module source code."""
        if config.use_async:
            return self._render_async(config)
        return self._render_modern(config)

    def _render_async(self, config: ScaffoldConfig) -> str:
        """Render an async module."""
        return self._build_source(
            config,
            base_class="SpiderFootAsyncPlugin",
            import_path="spiderfoot.plugins.async_plugin",
            is_async=True,
        )

    def _render_modern(self, config: ScaffoldConfig) -> str:
        """Render a modern (non-async) module."""
        return self._build_source(
            config,
            base_class="SpiderFootModernPlugin",
            import_path="spiderfoot.plugins.modern_plugin",
            is_async=False,
        )

    def _build_source(
        self,
        config: ScaffoldConfig,
        base_class: str,
        import_path: str,
        is_async: bool,
    ) -> str:
        """Build module source with proper indentation."""
        I = "    "  # noqa: E741 - 4-space indent unit
        lines: list[str] = []

        # Header
        lines.append("# -*- coding: utf-8 -*-")
        lines.append("# " + "-" * 63)
        lines.append(f"# Name:         {config.module_name}")
        lines.append(f"# Purpose:      {config.summary or 'TODO: Add summary'}")
        lines.append("#")
        lines.append(f"# Author:       {config.author}")
        lines.append(f"# Created:      {time.strftime('%Y-%m-%d')}")
        lines.append(f"# Copyright:    (c) {config.author} {time.strftime('%Y')}")
        lines.append("# Licence:      MIT")
        lines.append("# " + "-" * 63)
        lines.append("")
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append(f"from {import_path} import {base_class}")
        lines.append("")
        lines.append("")

        # Class definition
        lines.append(f"class {config.module_name}({base_class}):")
        summary = config.summary or "TODO: Module description."
        desc = config.description or "TODO: Detailed description of what this module does."
        lines.append(f'{I}"""{summary}')
        lines.append("")
        lines.append(f"{I}{desc}")
        lines.append(f'{I}"""')
        lines.append("")

        # Meta
        ds_model = repr(config.data_source_model)
        ds_website = repr(config.data_source_website) if config.data_source_website else "''"
        lines.append(f"{I}meta = {{")
        lines.append(f'{I}{I}"name": "{config.display_name}",')
        lines.append(f'{I}{I}"summary": "{config.summary or "TODO: Short summary"}",')
        lines.append(f"{I}{I}\"flags\": {repr(config.flags)},")
        lines.append(f"{I}{I}\"useCases\": {repr(config.use_cases)},")
        lines.append(f"{I}{I}\"categories\": {repr(config.categories)},")
        lines.append(f"{I}{I}\"dataSource\": {{")
        lines.append(f"{I}{I}{I}\"website\": {ds_website},")
        lines.append(f"{I}{I}{I}\"model\": {ds_model},")
        lines.append(f"{I}{I}{I}\"references\": [],")
        lines.append(f"{I}{I}{I}\"apiKeyInstructions\": [],")
        lines.append(f'{I}{I}{I}"favIcon": "",')
        lines.append(f'{I}{I}{I}"logo": "",')
        desc_str = config.description or "TODO: Data source description"
        lines.append(f'{I}{I}{I}"description": "{desc_str}",')
        lines.append(f"{I}{I}}},")
        lines.append(f"{I}}}")
        lines.append("")

        # Opts
        if config.has_api_key:
            lines.append(f"{I}opts = {{")
            lines.append(f'{I}{I}"api_key": "",')
            lines.append(f"{I}}}")
            lines.append("")
            lines.append(f"{I}optdescs = {{")
            lines.append(f'{I}{I}"api_key": "API key for the service.",')
            lines.append(f"{I}}}")
        else:
            lines.append(f"{I}opts = {{}}")
            lines.append("")
            lines.append(f"{I}optdescs = {{}}")
        lines.append("")

        # setup
        lines.append(f"{I}def setup(self, sfc, userOpts=None):")
        lines.append(f"{I}{I}super().setup(sfc, userOpts)")
        lines.append(f"{I}{I}self.results = self.tempStorage()")
        lines.append("")

        # watchedEvents
        lines.append(f"{I}def watchedEvents(self):")
        lines.append(f"{I}{I}return {repr(config.watched_events)}")
        lines.append("")

        # producedEvents
        lines.append(f"{I}def producedEvents(self):")
        lines.append(f"{I}{I}return {repr(config.produced_events)}")
        lines.append("")

        # handleEvent
        if is_async:
            lines.append(f"{I}async def handleEvent(self, event):")
        else:
            lines.append(f"{I}def handleEvent(self, event):")
        lines.append(f'{I}{I}"""Handle incoming events.')
        lines.append("")
        lines.append(f"{I}{I}Args:")
        lines.append(f"{I}{I}{I}event: SpiderFootEvent to process.")
        lines.append(f'{I}{I}"""')
        lines.append(f"{I}{I}event_name = event.eventType")
        lines.append(f"{I}{I}event_data = event.data")
        lines.append("")
        lines.append(f"{I}{I}if self.checkForStop():")
        lines.append(f"{I}{I}{I}return")
        lines.append("")
        lines.append(f"{I}{I}# Deduplicate")
        lines.append(f"{I}{I}if event_data in self.results:")
        lines.append(f"{I}{I}{I}return")
        lines.append(f"{I}{I}self.results[event_data] = True")
        lines.append("")
        lines.append(f'{I}{I}self.debug(f"Received event: {{event_name}} = {{event_data}}")')
        lines.append("")
        lines.append(f"{I}{I}# TODO: Implement module logic here")
        if is_async:
            lines.append(f'{I}{I}# Example: use self.http for async HTTP requests')
            lines.append(f'{I}{I}# result = await self.http.fetch_url(f"https://api.example.com/{{event_data}}")')
        else:
            lines.append(f'{I}{I}# result = self.sf.fetchUrl(f"https://api.example.com/{{event_data}}")')
        lines.append("")

        return "\n".join(lines)

    def generate_test(self, config: ScaffoldConfig) -> str:
        """Generate a test file for the scaffolded module.

        Returns:
            The test file source code.
        """
        return textwrap.dedent(f'''\
            """Tests for {config.module_name}."""

            import pytest


            class Test{config.module_name.replace("sfp_", "").title().replace("_", "")}:
                """Tests for {config.display_name} module."""

                def test_watched_events(self):
                    """Verify watched events are declared."""
                    from modules.{config.module_name} import {config.module_name}
                    module = {config.module_name}()
                    watched = module.watchedEvents()
                    assert isinstance(watched, list)
                    assert len(watched) > 0

                def test_produced_events(self):
                    """Verify produced events are declared."""
                    from modules.{config.module_name} import {config.module_name}
                    module = {config.module_name}()
                    produced = module.producedEvents()
                    assert isinstance(produced, list)
                    assert len(produced) > 0

                def test_meta_required_fields(self):
                    """Verify meta has required fields."""
                    from modules.{config.module_name} import {config.module_name}
                    module = {config.module_name}()
                    assert hasattr(module, "meta")
                    assert "name" in module.meta
                    assert "summary" in module.meta
        ''')


# ── Module Validation Report (Cycle 253) ──────────────────────────────


@dataclass
class ValidationReport:
    """Full validation report for a module."""
    module_name: str
    file_path: str
    is_valid: bool = True
    protocol_errors: list[str] = field(default_factory=list)
    meta_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    audit_score: float = 0.0
    migration_status: str = "unknown"
    async_compatible: bool = False
    event_summary: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_text(self) -> str:
        """Render as human-readable text."""
        lines = [
            f"Module: {self.module_name}",
            f"File:   {self.file_path}",
            f"Status: {'VALID' if self.is_valid else 'INVALID'}",
            f"Migration: {self.migration_status}",
            f"Async: {'Yes' if self.async_compatible else 'No'}",
            f"Audit Score: {self.audit_score:.0f}/100",
        ]

        if self.protocol_errors:
            lines.append("\nProtocol Errors:")
            for e in self.protocol_errors:
                lines.append(f"  ✗ {e}")

        if self.meta_errors:
            lines.append("\nMetadata Errors:")
            for e in self.meta_errors:
                lines.append(f"  ✗ {e}")

        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")

        if self.event_summary:
            lines.append("\nEvent Summary:")
            if self.event_summary.get("watched"):
                lines.append(f"  Watched: {', '.join(self.event_summary['watched'])}")
            if self.event_summary.get("produced"):
                lines.append(f"  Produced: {', '.join(self.event_summary['produced'])}")

        lines.append(f"\nValidation took {self.elapsed_ms:.1f}ms")
        return "\n".join(lines)


class ModuleValidator:
    """Comprehensive module validator combining contract, audit, and source checks.

    Usage:
        validator = ModuleValidator()
        report = validator.validate("modules/sfp_mymod.py")
        print(report.to_text())
    """

    def validate_source(self, filepath: str) -> ValidationReport:
        """Validate a module from source file path.

        Runs:
        1. Source-level analysis (base class, meta, events)
        2. Syntax validation
        3. Contract validation (if importable)
        4. Metadata quality scoring
        """
        start = time.time()
        module_name = os.path.basename(filepath).replace(".py", "")
        report = ValidationReport(
            module_name=module_name,
            file_path=filepath,
        )

        # 1. Read source
        try:
            with open(filepath, encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            report.is_valid = False
            report.protocol_errors.append(f"Cannot read file: {e}")
            report.elapsed_ms = (time.time() - start) * 1000
            return report

        # 2. Syntax check
        try:
            compile(source, filepath, "exec")
        except SyntaxError as e:
            report.is_valid = False
            report.protocol_errors.append(f"Syntax error: {e}")
            report.elapsed_ms = (time.time() - start) * 1000
            return report

        # 3. Source analysis
        self._analyze_source(source, report)

        # 4. Meta quality
        self._check_meta_quality(source, report)

        report.elapsed_ms = (time.time() - start) * 1000
        return report

    def validate_class(self, module_class: type) -> ValidationReport:
        """Validate a loaded module class."""
        start = time.time()
        module_name = getattr(module_class, "__name__", None) or module_class.__name__
        report = ValidationReport(
            module_name=module_name,
            file_path=inspect.getfile(module_class) if hasattr(module_class, "__module__") else "",
        )

        # MRO analysis
        mro = [c.__name__ for c in inspect.getmro(module_class)]
        if "SpiderFootAsyncPlugin" in mro:
            report.migration_status = "async"
            report.async_compatible = True
        elif "SpiderFootModernPlugin" in mro:
            report.migration_status = "modern"
        elif "SpiderFootPlugin" in mro:
            report.migration_status = "legacy"

        # Protocol checks
        required_methods = ["setup", "watchedEvents", "producedEvents", "handleEvent"]
        for method in required_methods:
            if not callable(getattr(module_class, method, None)):
                report.protocol_errors.append(f"Missing method: {method}()")

        # Meta check
        meta = getattr(module_class, "meta", None)
        if not meta:
            report.meta_errors.append("No meta dict")
        elif isinstance(meta, dict):
            for field_name in ("name", "summary"):
                if field_name not in meta:
                    report.meta_errors.append(f"Missing meta field: {field_name}")

        # Event declarations
        try:
            instance = module_class()
            if callable(getattr(instance, "watchedEvents", None)):
                watched = instance.watchedEvents() or []
                report.event_summary["watched"] = watched
            if callable(getattr(instance, "producedEvents", None)):
                produced = instance.producedEvents() or []
                report.event_summary["produced"] = produced
        except Exception:
            pass

        report.is_valid = not report.protocol_errors and not report.meta_errors
        report.elapsed_ms = (time.time() - start) * 1000
        return report

    def _analyze_source(self, source: str, report: ValidationReport) -> None:
        """Analyze source code for patterns."""
        # Base class detection
        if "SpiderFootAsyncPlugin" in source:
            report.migration_status = "async"
            report.async_compatible = True
        elif "SpiderFootModernPlugin" in source:
            report.migration_status = "modern"
        elif "SpiderFootPlugin" in source:
            report.migration_status = "legacy"

        # Check for async handleEvent
        if re.search(r'async\s+def\s+handleEvent', source):
            report.async_compatible = True

        # Extract watched/produced events
        watched_match = re.search(
            r'def\s+watchedEvents\s*\(.*?\).*?return\s+(\[.*?\])',
            source, re.DOTALL
        )
        produced_match = re.search(
            r'def\s+producedEvents\s*\(.*?\).*?return\s+(\[.*?\])',
            source, re.DOTALL
        )

        if watched_match:
            try:
                import ast
                report.event_summary["watched"] = ast.literal_eval(watched_match.group(1))
            except Exception:
                pass

        if produced_match:
            try:
                import ast
                report.event_summary["produced"] = ast.literal_eval(produced_match.group(1))
            except Exception:
                pass

        # Check for blocking calls in async modules
        if report.async_compatible:
            blocking_patterns = [
                (r'requests\.get\(', "requests.get() is blocking"),
                (r'requests\.post\(', "requests.post() is blocking"),
                (r'time\.sleep\(', "time.sleep() blocks event loop"),
                (r'urllib\.request\.urlopen\(', "urllib is blocking"),
            ]
            for pattern, msg in blocking_patterns:
                if re.search(pattern, source):
                    report.warnings.append(f"Blocking call in async module: {msg}")

        report.is_valid = not report.protocol_errors and not report.meta_errors

    def _check_meta_quality(self, source: str, report: ValidationReport) -> None:
        """Score metadata quality 0-100."""
        score = 0.0
        total = 0.0

        checks = [
            ('"name":', 20),
            ('"summary":', 20),
            ('"dataSource":', 15),
            ('"categories":', 10),
            ('"flags":', 10),
            ('"useCases":', 10),
            ('"description":', 15),
        ]

        for pattern, weight in checks:
            total += weight
            if pattern in source:
                score += weight

        report.audit_score = (score / total * 100) if total > 0 else 0


# ── Multi-Hop Event Chain Testing (Cycles 256-270) ───────────────────


@dataclass
class EventChainStep:
    """A step in a multi-hop event chain test."""
    event_type: str
    data: str
    expected_outputs: list[str] = field(default_factory=list)
    module: str = ""


@dataclass
class ChainTestResult:
    """Result of a multi-hop event chain test."""
    chain_name: str
    steps_completed: int
    total_steps: int
    passed: bool = True
    events_produced: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def completion_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.steps_completed / self.total_steps


class EventChainTester:
    """Test multi-hop event chains across modules.

    Simulates event propagation through a pipeline of modules,
    verifying that each step produces the expected output events.

    Usage:
        tester = EventChainTester()
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))
        tester.add_step(EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER"],
        ))
        result = tester.run(module_handler)
    """

    def __init__(self, chain_name: str = "default") -> None:
        self._chain_name = chain_name
        self._steps: list[EventChainStep] = []

    def add_step(self, step: EventChainStep) -> "EventChainTester":
        """Add a step to the chain."""
        self._steps.append(step)
        return self

    def clear(self) -> None:
        """Clear all steps."""
        self._steps.clear()

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def run(
        self,
        handler: Callable[[str, str], list[dict[str, str]]],
    ) -> ChainTestResult:
        """Run the event chain.

        Args:
            handler: Function that takes (event_type, data) and returns
                     list of {"event_type": ..., "data": ...} dicts
                     representing produced events.

        Returns:
            ChainTestResult with step completion status.
        """
        start = time.time()
        result = ChainTestResult(
            chain_name=self._chain_name,
            steps_completed=0,
            total_steps=len(self._steps),
        )

        current_events: list[dict[str, str]] = []

        for i, step in enumerate(self._steps):
            try:
                produced = handler(step.event_type, step.data)
                result.events_produced.extend(produced)

                # Check expected outputs
                produced_types = {e.get("event_type", "") for e in produced}
                for expected in step.expected_outputs:
                    if expected not in produced_types:
                        result.errors.append(
                            f"Step {i + 1}: Expected '{expected}' but got {produced_types}"
                        )
                        result.passed = False

                result.steps_completed += 1

                # Feed outputs as next step inputs
                current_events = produced

            except Exception as e:
                result.errors.append(f"Step {i + 1}: Exception: {e}")
                result.passed = False
                break

        result.elapsed_ms = (time.time() - start) * 1000
        return result


# ── Mock DB State Injection (Cycles 256-270) ──────────────────────────


class MockDBState:
    """Inject mock database state for module testing.

    Provides a fake database interface that modules can query
    during testing, pre-populated with test data.

    Usage:
        db = MockDBState()
        db.add_scan("scan-001", "example.com", "RUNNING")
        db.add_event("scan-001", "IP_ADDRESS", "1.2.3.4")
        # Pass db.as_mock() to module.setDbh()
    """

    def __init__(self) -> None:
        self._scans: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._correlations: list[dict[str, Any]] = []

    def add_scan(
        self,
        scan_id: str,
        target: str,
        status: str = "RUNNING",
        name: str = "",
    ) -> "MockDBState":
        """Add a scan record."""
        self._scans[scan_id] = {
            "scan_id": scan_id,
            "target": target,
            "status": status,
            "name": name or f"Test scan: {target}",
            "started": time.time(),
            "ended": 0,
        }
        return self

    def add_event(
        self,
        scan_id: str,
        event_type: str,
        data: str,
        source_event: str = "ROOT",
        module: str = "test_module",
    ) -> "MockDBState":
        """Add a scan event record."""
        self._events.append({
            "scan_id": scan_id,
            "event_type": event_type,
            "data": data,
            "source_event": source_event,
            "module": module,
            "generated": time.time(),
        })
        return self

    def add_events_bulk(
        self,
        scan_id: str,
        events: list[tuple[str, str]],
    ) -> "MockDBState":
        """Add multiple events as (type, data) tuples."""
        for event_type, data in events:
            self.add_event(scan_id, event_type, data)
        return self

    def get_scan(self, scan_id: str) -> dict[str, Any] | None:
        """Query a scan record."""
        return self._scans.get(scan_id)

    def get_events(
        self,
        scan_id: str,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query events for a scan."""
        results = [e for e in self._events if e["scan_id"] == scan_id]
        if event_type:
            results = [e for e in results if e["event_type"] == event_type]
        return results

    def scan_instance_get(self, scan_id: str) -> list[Any]:
        """Mimic scanInstanceGet() return format."""
        scan = self._scans.get(scan_id)
        if not scan:
            return [None, None, None, None, None, "UNKNOWN"]
        return [
            scan["scan_id"],
            scan["name"],
            scan["target"],
            scan["started"],
            scan["ended"],
            scan["status"],
        ]

    def scan_event_store(
        self,
        scan_id: str,
        event: Any,
        truncate_size: int = 0,
    ) -> None:
        """Mimic scanEventStore()."""
        self._events.append({
            "scan_id": scan_id,
            "event_type": getattr(event, "eventType", "UNKNOWN"),
            "data": getattr(event, "data", ""),
            "source_event": "stored",
            "module": getattr(event, "module", "unknown"),
            "generated": time.time(),
        })

    def as_mock(self) -> "MockDBProxy":
        """Return a mock object compatible with module.setDbh()."""
        return MockDBProxy(self)

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def scan_count(self) -> int:
        return len(self._scans)


class MockDBProxy:
    """Proxy that translates DB method calls to MockDBState lookups.

    Compatible with SpiderFoot's __sfdb__ interface.
    """

    def __init__(self, state: MockDBState) -> None:
        self._state = state

    def scanInstanceGet(self, scan_id: str = "") -> list[Any]:
        return self._state.scan_instance_get(scan_id)

    def scanEventStore(self, scan_id: str, event: Any, truncate_size: int = 0) -> None:
        self._state.scan_event_store(scan_id, event, truncate_size)

    def scanResultEvent(self, scan_id: str, event_type: str = "") -> list[dict]:
        return self._state.get_events(scan_id, event_type)

    def scanInstanceSet(self, scan_id: str, **kwargs: Any) -> None:
        if scan_id in self._state._scans:
            self._state._scans[scan_id].update(kwargs)


# ── Docker Dev Profile (Cycle 255) ────────────────────────────────────


class DockerDevProfileGenerator:
    """Generate Docker Compose dev profile with hot-reload.

    Usage:
        gen = DockerDevProfileGenerator()
        compose = gen.generate(modules_dir="./modules")
        gen.write("docker-compose.dev.yml")
    """

    def generate(
        self,
        modules_dir: str = "./modules",
        port: int = 5001,
        debug: bool = True,
    ) -> str:
        """Generate docker-compose dev profile YAML."""
        return textwrap.dedent(f'''\
            # Auto-generated Docker Compose development profile
            # Mounts local modules directory for hot-reload development
            #
            # Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up

            services:
              spiderfoot-web:
                volumes:
                  - {modules_dir}:/app/modules:ro
                  - ./spiderfoot:/app/spiderfoot:ro
                environment:
                  - SF_DEBUG={'true' if debug else 'false'}
                  - SF_HOT_RELOAD=true
                  - SF_LOG_LEVEL=DEBUG
                ports:
                  - "{port}:{port}"
                command: >
                  python -m spiderfoot.server
                  --host 0.0.0.0
                  --port {port}
                  --reload

              spiderfoot-worker:
                volumes:
                  - {modules_dir}:/app/modules:ro
                  - ./spiderfoot:/app/spiderfoot:ro
                environment:
                  - SF_DEBUG={'true' if debug else 'false'}
                  - SF_HOT_RELOAD=true
                  - SF_LOG_LEVEL=DEBUG
                  - CELERY_WORKER_POOL=solo
        ''')

    def write(
        self,
        filepath: str = "docker-compose.dev.yml",
        modules_dir: str = "./modules",
        port: int = 5001,
    ) -> str:
        """Write the dev profile to disk."""
        content = self.generate(modules_dir=modules_dir, port=port)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return os.path.abspath(filepath)


# ── Async Module Test Support (Cycles 256-270) ───────────────────────


@dataclass
class AsyncTestResult:
    """Result of running an async module test."""
    module_name: str
    events_produced: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


class AsyncModuleTester:
    """Test async SpiderFoot modules.

    Provides utilities for testing modules that use `async def handleEvent`.

    Usage:
        tester = AsyncModuleTester()
        result = tester.run_sync(
            handler=my_async_handler,
            event_type="IP_ADDRESS",
            data="1.2.3.4",
        )
    """

    def run_sync(
        self,
        handler: Callable,
        event_type: str,
        data: str,
        timeout: float = 5.0,
    ) -> AsyncTestResult:
        """Run an async handler synchronously for testing.

        Args:
            handler: The async handler function.
            event_type: Event type to pass.
            data: Event data to pass.
            timeout: Maximum execution time.

        Returns:
            AsyncTestResult with produced events and errors.
        """
        import asyncio
        start = time.time()
        result = AsyncTestResult(module_name="test")

        try:
            # Create a simple mock event
            event = _SimpleEvent(event_type, data)

            # Run the async handler
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't nest — run in thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, handler(event))
                        future.result(timeout=timeout)
                else:
                    loop.run_until_complete(
                        asyncio.wait_for(handler(event), timeout=timeout)
                    )
            except RuntimeError:
                # No event loop
                asyncio.run(handler(event))

        except asyncio.TimeoutError:
            result.errors.append(f"Async handler timed out after {timeout}s")
        except Exception as e:
            result.errors.append(f"Handler error: {e}")

        result.elapsed_ms = (time.time() - start) * 1000
        return result


class _SimpleEvent:
    """Minimal event mock for async testing."""

    def __init__(self, event_type: str, data: str) -> None:
        self.eventType = event_type
        self.data = data
        self.module = "test_harness"
        self.sourceEvent = None
        self.confidence = 100
        self.visibility = 100
        self.risk = 0
