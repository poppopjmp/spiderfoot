"""Tests for Module Development Tooling (Phase 4, Cycles 251-270).

Tests cover:
- ModuleScaffolder (Cycle 251): scaffold generation, config, templates
- ModuleValidator (Cycle 253): validation reports, scoring, source analysis
- EventChainTester (Cycles 256-270): multi-hop event chain testing
- MockDBState (Cycles 256-270): mock database state injection
- DockerDevProfileGenerator (Cycle 255): Docker dev profile generation
- AsyncModuleTester (Cycles 256-270): async module testing support
"""

from __future__ import annotations

import asyncio
import os
import re
import textwrap
import time

import pytest

from spiderfoot.plugins.module_devtools import (
    AsyncModuleTester,
    AsyncTestResult,
    ChainTestResult,
    DockerDevProfileGenerator,
    EventChainStep,
    EventChainTester,
    MockDBProxy,
    MockDBState,
    ModuleScaffolder,
    ModuleValidator,
    ScaffoldConfig,
    ValidationReport,
    _SimpleEvent,
    DATA_SOURCE_MODELS,
    STANDARD_CATEGORIES,
)


# ── ScaffoldConfig Tests ──────────────────────────────────────────────


class TestScaffoldConfig:
    """Tests for ScaffoldConfig dataclass."""

    def test_auto_prefix_sfp(self):
        """Module name gets sfp_ prefix automatically."""
        config = ScaffoldConfig(module_name="test_module")
        assert config.module_name == "sfp_test_module"

    def test_sfp_prefix_preserved(self):
        """Existing sfp_ prefix is not duplicated."""
        config = ScaffoldConfig(module_name="sfp_existing")
        assert config.module_name == "sfp_existing"

    def test_display_name_auto(self):
        """Display name is auto-generated from module name."""
        config = ScaffoldConfig(module_name="sfp_my_api")
        assert config.display_name == "My Api"

    def test_display_name_override(self):
        """Display name can be explicitly set."""
        config = ScaffoldConfig(module_name="sfp_test", display_name="My Custom Name")
        assert config.display_name == "My Custom Name"

    def test_default_categories(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.categories == ["Content Analysis"]

    def test_default_use_cases(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.use_cases == ["Passive"]

    def test_default_watched_events(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.watched_events == ["DOMAIN_NAME"]

    def test_default_produced_events(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.produced_events == ["RAW_RIR_DATA"]

    def test_default_data_source_model(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.data_source_model == "FREE_NOAUTH_UNLIMITED"

    def test_has_api_key_default(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.has_api_key is False

    def test_use_async_default(self):
        config = ScaffoldConfig(module_name="sfp_test")
        assert config.use_async is True


# ── ModuleScaffolder Tests ────────────────────────────────────────────


class TestModuleScaffolder:
    """Tests for ModuleScaffolder."""

    def test_generate_returns_source(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_gen")
        source = scaffolder.generate(config)
        assert isinstance(source, str)
        assert "sfp_test_gen" in source

    def test_async_module_has_async_def(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_async", use_async=True)
        source = scaffolder.generate(config)
        assert "async def handleEvent" in source
        assert "SpiderFootAsyncPlugin" in source

    def test_modern_module_has_sync_def(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_modern", use_async=False)
        source = scaffolder.generate(config)
        assert "def handleEvent" in source
        assert "async def handleEvent" not in source
        assert "SpiderFootModernPlugin" in source

    def test_has_meta_dict(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_meta",
            summary="Test summary",
            display_name="Test Meta",
        )
        source = scaffolder.generate(config)
        assert '"Test Meta"' in source
        assert '"Test summary"' in source
        assert '"name":' in source
        assert '"summary":' in source

    def test_has_watched_events(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_events",
            watched_events=["IP_ADDRESS", "DOMAIN_NAME"],
        )
        source = scaffolder.generate(config)
        assert "'IP_ADDRESS'" in source
        assert "'DOMAIN_NAME'" in source
        assert "def watchedEvents" in source

    def test_has_produced_events(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_produced",
            produced_events=["WEBSERVER_BANNER"],
        )
        source = scaffolder.generate(config)
        assert "'WEBSERVER_BANNER'" in source
        assert "def producedEvents" in source

    def test_api_key_opts(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_apikey",
            has_api_key=True,
        )
        source = scaffolder.generate(config)
        assert '"api_key"' in source
        assert "optdescs" in source

    def test_no_api_key_empty_opts(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_nokey",
            has_api_key=False,
        )
        source = scaffolder.generate(config)
        assert "opts = {}" in source
        assert "optdescs = {}" in source

    def test_has_setup_method(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_setup")
        source = scaffolder.generate(config)
        assert "def setup" in source
        assert "super().setup" in source
        assert "self.results = self.tempStorage()" in source

    def test_has_docstring(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_docstring",
            summary="Module docstring test",
        )
        source = scaffolder.generate(config)
        assert '"""Module docstring test' in source

    def test_has_copyright_header(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_header",
            author="Test Author",
        )
        source = scaffolder.generate(config)
        assert "Test Author" in source
        assert "copyright" in source.lower()

    def test_custom_categories(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_cat",
            categories=["DNS", "Passive DNS"],
        )
        source = scaffolder.generate(config)
        assert "'DNS'" in source
        assert "'Passive DNS'" in source

    def test_data_source_website(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_ds",
            data_source_website="https://example.com",
        )
        source = scaffolder.generate(config)
        assert "'https://example.com'" in source

    def test_compiles_successfully(self):
        """Generated source code must be valid Python."""
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_compile",
            summary="Compilation test module",
            watched_events=["IP_ADDRESS"],
            produced_events=["RAW_RIR_DATA"],
            has_api_key=True,
        )
        source = scaffolder.generate(config)
        # Must not raise
        compile(source, "<test>", "exec")

    def test_compiles_modern(self):
        """Generated modern source must be valid Python."""
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_test_compile_modern",
            use_async=False,
        )
        source = scaffolder.generate(config)
        compile(source, "<test>", "exec")

    def test_has_deduplication(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_dedup")
        source = scaffolder.generate(config)
        assert "self.results" in source
        assert "event_data in self.results" in source

    def test_has_stop_check(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_stop")
        source = scaffolder.generate(config)
        assert "checkForStop" in source


class TestModuleScaffolderTestGeneration:
    """Tests for test file generation."""

    def test_generate_test_returns_string(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_gen")
        test_source = scaffolder.generate_test(config)
        assert isinstance(test_source, str)

    def test_test_imports_module(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_import")
        test_source = scaffolder.generate_test(config)
        assert "from modules.sfp_test_import" in test_source

    def test_test_has_assertions(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_test_assert")
        test_source = scaffolder.generate_test(config)
        assert "assert " in test_source

    def test_test_checks_watched(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_check_w")
        test_source = scaffolder.generate_test(config)
        assert "watchedEvents" in test_source

    def test_test_checks_produced(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_check_p")
        test_source = scaffolder.generate_test(config)
        assert "producedEvents" in test_source

    def test_test_checks_meta(self):
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(module_name="sfp_check_meta")
        test_source = scaffolder.generate_test(config)
        assert "meta" in test_source


# ── Constants Tests ───────────────────────────────────────────────────


class TestConstants:
    """Tests for module constants."""

    def test_data_source_models_populated(self):
        assert len(DATA_SOURCE_MODELS) >= 5

    def test_standard_categories_populated(self):
        assert len(STANDARD_CATEGORIES) >= 8

    def test_content_analysis_in_categories(self):
        assert "Content Analysis" in STANDARD_CATEGORIES

    def test_dns_in_categories(self):
        assert "DNS" in STANDARD_CATEGORIES


# ── ValidationReport Tests ────────────────────────────────────────────


class TestValidationReport:
    """Tests for ValidationReport."""

    def test_default_valid(self):
        report = ValidationReport(module_name="test", file_path="test.py")
        assert report.is_valid is True

    def test_to_text_contains_name(self):
        report = ValidationReport(module_name="sfp_test", file_path="test.py")
        text = report.to_text()
        assert "sfp_test" in text

    def test_to_text_shows_valid(self):
        report = ValidationReport(module_name="sfp_test", file_path="test.py")
        text = report.to_text()
        assert "VALID" in text

    def test_to_text_shows_invalid(self):
        report = ValidationReport(
            module_name="sfp_test",
            file_path="test.py",
            is_valid=False,
            protocol_errors=["Missing method"],
        )
        text = report.to_text()
        assert "INVALID" in text
        assert "Missing method" in text

    def test_to_text_shows_warnings(self):
        report = ValidationReport(
            module_name="sfp_test",
            file_path="test.py",
            warnings=["Blocking call detected"],
        )
        text = report.to_text()
        assert "Blocking call detected" in text

    def test_to_text_shows_events(self):
        report = ValidationReport(
            module_name="sfp_test",
            file_path="test.py",
            event_summary={
                "watched": ["DOMAIN_NAME"],
                "produced": ["IP_ADDRESS"],
            },
        )
        text = report.to_text()
        assert "DOMAIN_NAME" in text
        assert "IP_ADDRESS" in text

    def test_to_text_shows_elapsed(self):
        report = ValidationReport(
            module_name="sfp_test",
            file_path="test.py",
            elapsed_ms=42.5,
        )
        text = report.to_text()
        assert "42.5" in text

    def test_meta_errors_make_invalid(self):
        report = ValidationReport(
            module_name="sfp_test",
            file_path="test.py",
            meta_errors=["Missing name field"],
        )
        text = report.to_text()
        assert "Missing name field" in text


# ── ModuleValidator Tests ─────────────────────────────────────────────


class TestModuleValidator:
    """Tests for ModuleValidator."""

    def test_validate_valid_async_source(self, tmp_path):
        source = textwrap.dedent('''\
            from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

            class sfp_test(SpiderFootAsyncPlugin):
                meta = {
                    'name': 'Test',
                    'summary': 'Test module',
                    'flags': [],
                    'useCases': ['Passive'],
                    'categories': ['Content Analysis'],
                    'dataSource': {
                        'website': 'https://example.com',
                        'model': 'FREE_NOAUTH_UNLIMITED',
                        'description': 'Test data source',
                    },
                }
                opts = {}
                optdescs = {}

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME']

                def producedEvents(self):
                    return ['IP_ADDRESS']

                async def handleEvent(self, event):
                    pass
        ''')
        path = tmp_path / "sfp_test.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert report.is_valid is True
        assert report.migration_status == "async"
        assert report.async_compatible is True

    def test_validate_source_detects_legacy(self, tmp_path):
        source = textwrap.dedent('''\
            from spiderfoot import SpiderFootPlugin

            class sfp_legacy(SpiderFootPlugin):
                meta = {'name': 'Legacy', 'summary': 'Legacy module'}
                opts = {}
                optdescs = {}

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME']

                def producedEvents(self):
                    return ['IP_ADDRESS']

                def handleEvent(self, event):
                    pass
        ''')
        path = tmp_path / "sfp_legacy.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert report.migration_status == "legacy"

    def test_validate_source_syntax_error(self, tmp_path):
        path = tmp_path / "sfp_bad.py"
        path.write_text("def broken(:\n  pass", encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert report.is_valid is False
        assert any("Syntax error" in e for e in report.protocol_errors)

    def test_validate_source_file_not_found(self):
        validator = ModuleValidator()
        report = validator.validate_source("/nonexistent/sfp_nothing.py")
        assert report.is_valid is False
        assert len(report.protocol_errors) > 0

    def test_validate_source_detects_blocking_calls(self, tmp_path):
        source = textwrap.dedent('''\
            from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin
            import requests

            class sfp_blocking(SpiderFootAsyncPlugin):
                meta = {'name': 'Blocking', 'summary': 'Test'}

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME']

                def producedEvents(self):
                    return ['IP_ADDRESS']

                async def handleEvent(self, event):
                    r = requests.get("http://example.com")
        ''')
        path = tmp_path / "sfp_blocking.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert any("blocking" in w.lower() for w in report.warnings)

    def test_validate_source_meta_scoring(self, tmp_path):
        source = textwrap.dedent('''\
            from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

            class sfp_scored(SpiderFootAsyncPlugin):
                meta = {
                    "name": "Scored",
                    "summary": "Test scoring",
                    "categories": ["DNS"],
                    "flags": [],
                    "useCases": ["Passive"],
                    "dataSource": {
                        "description": "Test description",
                    },
                }

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME']

                def producedEvents(self):
                    return ['IP_ADDRESS']

                async def handleEvent(self, event):
                    pass
        ''')
        path = tmp_path / "sfp_scored.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert report.audit_score > 50  # Has most meta fields

    def test_validate_source_extracts_events(self, tmp_path):
        source = textwrap.dedent('''\
            from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

            class sfp_events(SpiderFootAsyncPlugin):
                meta = {'name': 'Events', 'summary': 'Test'}

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME', 'IP_ADDRESS']

                def producedEvents(self):
                    return ['BGP_AS_OWNER']

                async def handleEvent(self, event):
                    pass
        ''')
        path = tmp_path / "sfp_events.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert "DOMAIN_NAME" in report.event_summary.get("watched", [])
        assert "IP_ADDRESS" in report.event_summary.get("watched", [])
        assert "BGP_AS_OWNER" in report.event_summary.get("produced", [])

    def test_validate_class_protocol(self):
        """Validate a class with required protocol methods."""
        class GoodModule:
            meta = {"name": "Good", "summary": "Good module"}

            def setup(self, sfc, userOpts=None):
                pass

            def watchedEvents(self):
                return ["DOMAIN_NAME"]

            def producedEvents(self):
                return ["IP_ADDRESS"]

            def handleEvent(self, event):
                pass

        validator = ModuleValidator()
        report = validator.validate_class(GoodModule)
        assert report.is_valid is True

    def test_validate_class_missing_method(self):
        """Detect missing protocol methods."""
        class BadModule:
            meta = {"name": "Bad", "summary": "Bad module"}

            def setup(self, sfc, userOpts=None):
                pass

        validator = ModuleValidator()
        report = validator.validate_class(BadModule)
        assert report.is_valid is False
        assert any("handleEvent" in e for e in report.protocol_errors)

    def test_validate_class_no_meta(self):
        class NoMetaModule:
            def setup(self, sfc, userOpts=None):
                pass
            def watchedEvents(self):
                return []
            def producedEvents(self):
                return []
            def handleEvent(self, event):
                pass

        validator = ModuleValidator()
        report = validator.validate_class(NoMetaModule)
        assert report.is_valid is False
        assert any("meta" in e.lower() for e in report.meta_errors)

    def test_validate_class_elapsed_ms(self):
        class SimpleModule:
            meta = {"name": "Simple", "summary": "Fast module"}
            def setup(self, sfc, userOpts=None):
                pass
            def watchedEvents(self):
                return ["DOMAIN_NAME"]
            def producedEvents(self):
                return ["IP_ADDRESS"]
            def handleEvent(self, event):
                pass

        validator = ModuleValidator()
        report = validator.validate_class(SimpleModule)
        assert report.elapsed_ms >= 0

    def test_validate_time_sleep_warning(self, tmp_path):
        """Detect time.sleep in async modules."""
        source = textwrap.dedent('''\
            import time
            from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

            class sfp_sleepy(SpiderFootAsyncPlugin):
                meta = {'name': 'Sleepy', 'summary': 'Test'}

                def setup(self, sfc, userOpts=None):
                    pass

                def watchedEvents(self):
                    return ['DOMAIN_NAME']

                def producedEvents(self):
                    return ['IP_ADDRESS']

                async def handleEvent(self, event):
                    time.sleep(1)
        ''')
        path = tmp_path / "sfp_sleepy.py"
        path.write_text(source, encoding="utf-8")

        validator = ModuleValidator()
        report = validator.validate_source(str(path))
        assert any("time.sleep" in w for w in report.warnings)


# ── EventChainStep Tests ──────────────────────────────────────────────


class TestEventChainStep:
    """Tests for EventChainStep dataclass."""

    def test_basic_step(self):
        step = EventChainStep("DOMAIN_NAME", "example.com")
        assert step.event_type == "DOMAIN_NAME"
        assert step.data == "example.com"
        assert step.expected_outputs == []

    def test_step_with_outputs(self):
        step = EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER", "GEOINFO"],
        )
        assert len(step.expected_outputs) == 2


# ── ChainTestResult Tests ────────────────────────────────────────────


class TestChainTestResult:
    """Tests for ChainTestResult."""

    def test_completion_rate_zero_steps(self):
        result = ChainTestResult(chain_name="empty", steps_completed=0, total_steps=0)
        assert result.completion_rate == 0.0

    def test_completion_rate_partial(self):
        result = ChainTestResult(chain_name="partial", steps_completed=2, total_steps=4)
        assert result.completion_rate == 0.5

    def test_completion_rate_full(self):
        result = ChainTestResult(chain_name="full", steps_completed=5, total_steps=5)
        assert result.completion_rate == 1.0

    def test_default_passed(self):
        result = ChainTestResult(chain_name="test", steps_completed=0, total_steps=0)
        assert result.passed is True


# ── EventChainTester Tests ────────────────────────────────────────────


class TestEventChainTester:
    """Tests for EventChainTester."""

    def test_add_step(self):
        tester = EventChainTester("test")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        assert tester.step_count == 1

    def test_chaining_add_step(self):
        tester = EventChainTester("test")
        result = tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        assert result is tester

    def test_clear(self):
        tester = EventChainTester("test")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        tester.clear()
        assert tester.step_count == 0

    def test_run_empty_chain(self):
        tester = EventChainTester("empty")
        result = tester.run(lambda t, d: [])
        assert result.passed is True
        assert result.steps_completed == 0
        assert result.total_steps == 0

    def test_run_single_step_pass(self):
        tester = EventChainTester("single")
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))

        def handler(event_type, data):
            return [{"event_type": "IP_ADDRESS", "data": "1.2.3.4"}]

        result = tester.run(handler)
        assert result.passed is True
        assert result.steps_completed == 1

    def test_run_single_step_fail(self):
        tester = EventChainTester("fail")
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))

        result = tester.run(lambda t, d: [])
        assert result.passed is False
        assert len(result.errors) > 0

    def test_run_multi_step(self):
        tester = EventChainTester("multi")
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))
        tester.add_step(EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER"],
        ))

        def handler(event_type, data):
            if event_type == "DOMAIN_NAME":
                return [{"event_type": "IP_ADDRESS", "data": "1.2.3.4"}]
            elif event_type == "IP_ADDRESS":
                return [{"event_type": "BGP_AS_OWNER", "data": "AS12345"}]
            return []

        result = tester.run(handler)
        assert result.passed is True
        assert result.steps_completed == 2
        assert len(result.events_produced) == 2

    def test_run_handler_exception(self):
        tester = EventChainTester("error")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))

        def bad_handler(t, d):
            raise ValueError("Test error")

        result = tester.run(bad_handler)
        assert result.passed is False
        assert any("Exception" in e for e in result.errors)

    def test_run_elapsed_ms(self):
        tester = EventChainTester("timer")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        result = tester.run(lambda t, d: [])
        assert result.elapsed_ms >= 0

    def test_run_no_expected_outputs_passes(self):
        """Steps with no expected outputs always pass."""
        tester = EventChainTester("noexpect")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        result = tester.run(lambda t, d: [])
        assert result.passed is True
        assert result.steps_completed == 1

    def test_chain_name(self):
        tester = EventChainTester("my_chain")
        tester.add_step(EventChainStep("DOMAIN_NAME", "example.com"))
        result = tester.run(lambda t, d: [])
        assert result.chain_name == "my_chain"

    def test_multiple_expected_outputs(self):
        """All expected outputs must be present."""
        tester = EventChainTester("multi_output")
        tester.add_step(EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER", "GEOINFO"],
        ))

        def handler(t, d):
            return [
                {"event_type": "BGP_AS_OWNER", "data": "AS12345"},
                {"event_type": "GEOINFO", "data": "US"},
            ]

        result = tester.run(handler)
        assert result.passed is True

    def test_partial_expected_outputs_fails(self):
        """Missing any expected output should fail."""
        tester = EventChainTester("partial_output")
        tester.add_step(EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER", "GEOINFO"],
        ))

        def handler(t, d):
            return [{"event_type": "BGP_AS_OWNER", "data": "AS12345"}]

        result = tester.run(handler)
        assert result.passed is False


# ── MockDBState Tests ─────────────────────────────────────────────────


class TestMockDBState:
    """Tests for MockDBState."""

    def test_add_scan(self):
        db = MockDBState()
        db.add_scan("scan-001", "example.com")
        assert db.scan_count == 1

    def test_get_scan(self):
        db = MockDBState()
        db.add_scan("scan-001", "example.com", status="RUNNING")
        scan = db.get_scan("scan-001")
        assert scan is not None
        assert scan["target"] == "example.com"
        assert scan["status"] == "RUNNING"

    def test_get_scan_not_found(self):
        db = MockDBState()
        assert db.get_scan("nonexistent") is None

    def test_add_event(self):
        db = MockDBState()
        db.add_event("scan-001", "IP_ADDRESS", "1.2.3.4")
        assert db.event_count == 1

    def test_get_events(self):
        db = MockDBState()
        db.add_event("scan-001", "IP_ADDRESS", "1.2.3.4")
        db.add_event("scan-001", "DOMAIN_NAME", "example.com")
        events = db.get_events("scan-001")
        assert len(events) == 2

    def test_get_events_by_type(self):
        db = MockDBState()
        db.add_event("scan-001", "IP_ADDRESS", "1.2.3.4")
        db.add_event("scan-001", "DOMAIN_NAME", "example.com")
        events = db.get_events("scan-001", event_type="IP_ADDRESS")
        assert len(events) == 1
        assert events[0]["data"] == "1.2.3.4"

    def test_add_events_bulk(self):
        db = MockDBState()
        db.add_events_bulk("scan-001", [
            ("IP_ADDRESS", "1.2.3.4"),
            ("IP_ADDRESS", "5.6.7.8"),
            ("DOMAIN_NAME", "example.com"),
        ])
        assert db.event_count == 3

    def test_scan_instance_get(self):
        db = MockDBState()
        db.add_scan("scan-001", "example.com", status="FINISHED")
        result = db.scan_instance_get("scan-001")
        assert result[0] == "scan-001"
        assert result[5] == "FINISHED"

    def test_scan_instance_get_not_found(self):
        db = MockDBState()
        result = db.scan_instance_get("nonexistent")
        assert result[5] == "UNKNOWN"

    def test_scan_event_store(self):
        db = MockDBState()

        class FakeEvent:
            eventType = "IP_ADDRESS"
            data = "1.2.3.4"
            module = "sfp_test"

        db.scan_event_store("scan-001", FakeEvent())
        assert db.event_count == 1

    def test_chaining(self):
        """Method chaining is supported."""
        db = MockDBState()
        result = db.add_scan("s1", "t1").add_event("s1", "IP_ADDRESS", "1.2.3.4")
        assert result is db

    def test_empty_counts(self):
        db = MockDBState()
        assert db.scan_count == 0
        assert db.event_count == 0


# ── MockDBProxy Tests ─────────────────────────────────────────────────


class TestMockDBProxy:
    """Tests for MockDBProxy (DB interface compatibility)."""

    def test_scan_instance_get(self):
        db = MockDBState()
        db.add_scan("scan-001", "example.com")
        proxy = db.as_mock()
        result = proxy.scanInstanceGet("scan-001")
        assert result[0] == "scan-001"

    def test_scan_event_store(self):
        db = MockDBState()
        proxy = db.as_mock()

        class FakeEvent:
            eventType = "IP_ADDRESS"
            data = "1.2.3.4"
            module = "sfp_test"

        proxy.scanEventStore("scan-001", FakeEvent())
        assert db.event_count == 1

    def test_scan_result_event(self):
        db = MockDBState()
        db.add_event("scan-001", "IP_ADDRESS", "1.2.3.4")
        proxy = db.as_mock()
        results = proxy.scanResultEvent("scan-001", "IP_ADDRESS")
        assert len(results) == 1

    def test_scan_instance_set(self):
        db = MockDBState()
        db.add_scan("scan-001", "example.com", status="RUNNING")
        proxy = db.as_mock()
        proxy.scanInstanceSet("scan-001", status="FINISHED")
        assert db.get_scan("scan-001")["status"] == "FINISHED"

    def test_as_mock_returns_proxy(self):
        db = MockDBState()
        proxy = db.as_mock()
        assert isinstance(proxy, MockDBProxy)


# ── DockerDevProfileGenerator Tests ───────────────────────────────────


class TestDockerDevProfileGenerator:
    """Tests for DockerDevProfileGenerator."""

    def test_generate_returns_yaml(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "services:" in content

    def test_generate_has_web_service(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "spiderfoot-web:" in content

    def test_generate_has_worker_service(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "spiderfoot-worker:" in content

    def test_generate_has_hot_reload(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "SF_HOT_RELOAD=true" in content

    def test_generate_custom_port(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate(port=8080)
        assert "8080:8080" in content

    def test_generate_custom_modules_dir(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate(modules_dir="/my/modules")
        assert "/my/modules" in content

    def test_generate_debug_off(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate(debug=False)
        assert "SF_DEBUG=false" in content

    def test_generate_has_volumes(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "volumes:" in content

    def test_generate_has_reload_command(self):
        gen = DockerDevProfileGenerator()
        content = gen.generate()
        assert "--reload" in content

    def test_write_to_file(self, tmp_path):
        gen = DockerDevProfileGenerator()
        filepath = str(tmp_path / "docker-compose.dev.yml")
        result = gen.write(filepath)
        assert os.path.exists(result)
        with open(result, encoding="utf-8") as f:
            content = f.read()
        assert "services:" in content


# ── AsyncTestResult Tests ─────────────────────────────────────────────


class TestAsyncTestResult:
    """Tests for AsyncTestResult."""

    def test_passed_no_errors(self):
        result = AsyncTestResult(module_name="test")
        assert result.passed is True

    def test_failed_with_errors(self):
        result = AsyncTestResult(module_name="test", errors=["fail"])
        assert result.passed is False

    def test_default_events_empty(self):
        result = AsyncTestResult(module_name="test")
        assert result.events_produced == []


# ── _SimpleEvent Tests ────────────────────────────────────────────────


class TestSimpleEvent:
    """Tests for _SimpleEvent mock."""

    def test_event_attributes(self):
        event = _SimpleEvent("IP_ADDRESS", "1.2.3.4")
        assert event.eventType == "IP_ADDRESS"
        assert event.data == "1.2.3.4"
        assert event.module == "test_harness"
        assert event.sourceEvent is None
        assert event.confidence == 100
        assert event.visibility == 100
        assert event.risk == 0


# ── AsyncModuleTester Tests ───────────────────────────────────────────


class TestAsyncModuleTester:
    """Tests for AsyncModuleTester."""

    def test_run_sync_simple_handler(self):
        async def handler(event):
            pass

        tester = AsyncModuleTester()
        result = tester.run_sync(handler, "IP_ADDRESS", "1.2.3.4")
        assert result.passed

    def test_run_sync_exception_handler(self):
        async def handler(event):
            raise ValueError("Test error")

        tester = AsyncModuleTester()
        result = tester.run_sync(handler, "IP_ADDRESS", "1.2.3.4")
        assert not result.passed
        assert len(result.errors) > 0

    def test_run_sync_elapsed(self):
        async def handler(event):
            pass

        tester = AsyncModuleTester()
        result = tester.run_sync(handler, "IP_ADDRESS", "1.2.3.4")
        assert result.elapsed_ms >= 0

    def test_run_sync_event_passed(self):
        """Handler receives event with correct attributes."""
        captured = {}

        async def handler(event):
            captured["type"] = event.eventType
            captured["data"] = event.data

        tester = AsyncModuleTester()
        tester.run_sync(handler, "DOMAIN_NAME", "example.com")
        assert captured["type"] == "DOMAIN_NAME"
        assert captured["data"] == "example.com"


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_scaffold_then_validate(self, tmp_path):
        """Scaffold a module then validate it."""
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_integration_test",
            summary="Integration test module",
            watched_events=["IP_ADDRESS"],
            produced_events=["RAW_RIR_DATA"],
            has_api_key=True,
            output_dir=str(tmp_path),
        )

        # Generate to file
        path = scaffolder.generate_to_file(config)
        assert os.path.exists(path)

        # Validate
        validator = ModuleValidator()
        report = validator.validate_source(path)
        assert report.is_valid is True
        assert report.migration_status == "async"
        assert report.audit_score > 50

    def test_scaffold_modern_then_validate(self, tmp_path):
        """Scaffold a modern module then validate it."""
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_modern_int",
            summary="Modern integration test",
            use_async=False,
            output_dir=str(tmp_path),
        )
        path = scaffolder.generate_to_file(config)
        validator = ModuleValidator()
        report = validator.validate_source(path)
        assert report.is_valid is True
        assert report.migration_status == "modern"

    def test_mock_db_with_chain_tester(self):
        """Use mock DB state with an event chain."""
        db = MockDBState()
        db.add_scan("scan-001", "example.com")

        tester = EventChainTester("db_chain")
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))

        def handler(event_type, data):
            # Store in mock DB
            db.add_event("scan-001", event_type, data)
            # Produce events
            if event_type == "DOMAIN_NAME":
                return [{"event_type": "IP_ADDRESS", "data": "1.2.3.4"}]
            return []

        result = tester.run(handler)
        assert result.passed is True
        assert db.event_count == 1  # Input event stored

    def test_full_chain_with_mock_db(self):
        """Full multi-hop chain with DB state tracking."""
        db = MockDBState()
        db.add_scan("scan-001", "example.com")

        tester = EventChainTester("full")
        tester.add_step(EventChainStep(
            "DOMAIN_NAME", "example.com",
            expected_outputs=["IP_ADDRESS"],
        ))
        tester.add_step(EventChainStep(
            "IP_ADDRESS", "1.2.3.4",
            expected_outputs=["BGP_AS_OWNER"],
        ))
        tester.add_step(EventChainStep(
            "BGP_AS_OWNER", "AS12345",
            expected_outputs=["RAW_RIR_DATA"],
        ))

        def handler(event_type, data):
            db.add_event("scan-001", event_type, data)
            mapping = {
                "DOMAIN_NAME": [{"event_type": "IP_ADDRESS", "data": "1.2.3.4"}],
                "IP_ADDRESS": [{"event_type": "BGP_AS_OWNER", "data": "AS12345"}],
                "BGP_AS_OWNER": [{"event_type": "RAW_RIR_DATA", "data": "whois data"}],
            }
            return mapping.get(event_type, [])

        result = tester.run(handler)
        assert result.passed is True
        assert result.steps_completed == 3
        assert db.event_count == 3

    def test_validator_report_formatting(self, tmp_path):
        """ValidationReport formatting is complete."""
        scaffolder = ModuleScaffolder()
        config = ScaffoldConfig(
            module_name="sfp_format_test",
            summary="Format test",
            watched_events=["DOMAIN_NAME"],
            produced_events=["IP_ADDRESS"],
            output_dir=str(tmp_path),
        )
        path = scaffolder.generate_to_file(config)

        validator = ModuleValidator()
        report = validator.validate_source(path)
        text = report.to_text()

        assert "sfp_format_test" in text
        assert "VALID" in text
        assert "async" in text
        assert "ms" in text
