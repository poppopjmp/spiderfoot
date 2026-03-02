"""Tests for module audit framework (Cycles 151-220).

Tests cover:
- ModuleSourceAnalyzer: source-level analysis without imports
- ModuleContractAuditor: class-level validation
- EventDependencyGraph: event flow analysis
- MetadataAuditor: metadata quality scoring
- ModuleDocGenerator: documentation generation
- AsyncExecutionVerifier: async compatibility checks
- ModuleAuditRunner: full audit orchestration
"""
from __future__ import annotations

import os
import textwrap
import tempfile
import shutil

import pytest

from spiderfoot.plugins.module_audit import (
    AsyncExecutionVerifier,
    AuditReport,
    EventDependencyGraph,
    EventEdge,
    EventTypeInfo,
    MetaCompleteness,
    MetadataAuditor,
    MigrationStatus,
    ModuleAuditRunner,
    ModuleContractAuditor,
    ModuleDocGenerator,
    ModuleInfo,
    ModuleSourceAnalyzer,
    STANDARD_CATEGORIES,
    STANDARD_FLAGS,
    STANDARD_USE_CASES,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_modules_dir(tmp_path):
    """Create a temp directory with sample module files."""
    mod_dir = tmp_path / "modules"
    mod_dir.mkdir()

    # Async module with complete meta
    (mod_dir / "sfp_dns_test.py").write_text(textwrap.dedent("""\
        from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

        class sfp_dns_test(SpiderFootAsyncPlugin):
            meta = {
                'name': 'DNS Test',
                'summary': 'Test DNS module.',
                'flags': [],
                'useCases': ['Footprint', 'Investigate'],
                'categories': ['DNS'],
                'dataSource': {
                    'website': 'https://example.com',
                    'model': 'FREE_NOAUTH_UNLIMITED',
                },
            }
            opts = {'timeout': 30}
            optdescs = {'timeout': 'Query timeout in seconds.'}

            def watchedEvents(self):
                return ['DOMAIN_NAME', 'INTERNET_NAME']

            def producedEvents(self):
                return ['IP_ADDRESS', 'IPV6_ADDRESS']

            async def handleEvent(self, event):
                pass
    """), encoding="utf-8")

    # Modern (non-async) storage module
    (mod_dir / "sfp__stor_test.py").write_text(textwrap.dedent("""\
        from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

        class sfp__stor_test(SpiderFootModernPlugin):
            meta = {
                'name': 'Storage Test',
                'summary': 'Test storage module.',
                'flags': [],
                'useCases': ['Footprint'],
                'categories': ['Storage'],
            }
            opts = {}
            optdescs = {}

            def watchedEvents(self):
                return ['*']

            def producedEvents(self):
                return []

            def handleEvent(self, event):
                pass
    """), encoding="utf-8")

    # Legacy module (SpiderFootPlugin)
    (mod_dir / "sfp_legacy.py").write_text(textwrap.dedent("""\
        from spiderfoot import SpiderFootPlugin

        class sfp_legacy(SpiderFootPlugin):
            meta = {
                'name': 'Legacy Test',
                'summary': 'A legacy module.',
            }
            opts = {}
            optdescs = {}

            def watchedEvents(self):
                return ['DOMAIN_NAME']

            def producedEvents(self):
                return ['RAW_DATA']

            def handleEvent(self, event):
                pass
    """), encoding="utf-8")

    # Module with minimal meta
    (mod_dir / "sfp_minimal.py").write_text(textwrap.dedent("""\
        from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

        class sfp_minimal(SpiderFootAsyncPlugin):
            meta = {
                'name': 'Minimal',
            }
            opts = {}
            optdescs = {}

            def watchedEvents(self):
                return ['IP_ADDRESS']

            def producedEvents(self):
                return ['GEOINFO']

            def handleEvent(self, event):
                pass
    """), encoding="utf-8")

    # Module that produces events consumed by dns_test
    (mod_dir / "sfp_producer.py").write_text(textwrap.dedent("""\
        from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

        class sfp_producer(SpiderFootAsyncPlugin):
            meta = {
                'name': 'Producer',
                'summary': 'Produces domain names.',
                'flags': ['slow'],
                'useCases': ['Footprint'],
                'categories': ['Search Engines'],
            }
            opts = {}
            optdescs = {}

            def watchedEvents(self):
                return ['ROOT']

            def producedEvents(self):
                return ['DOMAIN_NAME', 'INTERNET_NAME']

            async def handleEvent(self, event):
                pass
    """), encoding="utf-8")

    return str(mod_dir)


@pytest.fixture
def sample_module_infos():
    """Create sample ModuleInfo objects for testing."""
    dns = ModuleInfo(
        name="sfp_dns",
        file_path="/modules/sfp_dns.py",
        base_class="SpiderFootAsyncPlugin",
        migration_status=MigrationStatus.ASYNC,
        has_async_handle_event=True,
        has_meta=True,
        meta_completeness=MetaCompleteness.COMPLETE,
        meta_fields_present=["name", "summary", "flags", "useCases", "categories", "dataSource"],
        watched_events=["DOMAIN_NAME", "INTERNET_NAME"],
        produced_events=["IP_ADDRESS", "IPV6_ADDRESS"],
        has_opts=True,
        has_optdescs=True,
        has_data_source=True,
        categories=["DNS"],
        flags=[],
        use_cases=["Footprint", "Investigate"],
    )

    shodan = ModuleInfo(
        name="sfp_shodan",
        file_path="/modules/sfp_shodan.py",
        base_class="SpiderFootAsyncPlugin",
        migration_status=MigrationStatus.ASYNC,
        has_async_handle_event=True,
        has_meta=True,
        meta_completeness=MetaCompleteness.COMPLETE,
        meta_fields_present=["name", "summary", "flags", "useCases", "categories", "dataSource"],
        watched_events=["IP_ADDRESS"],
        produced_events=["OPERATING_SYSTEM", "WEBSERVER_BANNER", "RAW_RIR_DATA"],
        has_opts=True,
        has_optdescs=True,
        has_data_source=True,
        categories=["Search Engines"],
        flags=["apikey"],
        use_cases=["Footprint", "Investigate", "Passive"],
    )

    legacy = ModuleInfo(
        name="sfp_old",
        file_path="/modules/sfp_old.py",
        base_class="SpiderFootPlugin",
        migration_status=MigrationStatus.LEGACY,
        has_meta=True,
        meta_completeness=MetaCompleteness.MINIMAL,
        meta_fields_present=["name"],
        meta_fields_missing=["summary", "flags", "useCases", "categories"],
        watched_events=["DOMAIN_NAME"],
        produced_events=["RAW_DATA"],
        categories=[],
        flags=[],
    )

    return [dns, shodan, legacy]


# ── Test Enums ────────────────────────────────────────────────────────


class TestEnums:
    """Test enum values."""

    def test_migration_status_values(self):
        assert MigrationStatus.LEGACY.value == "legacy"
        assert MigrationStatus.ASYNC.value == "async"
        assert MigrationStatus.MODERN.value == "modern"

    def test_meta_completeness_values(self):
        assert MetaCompleteness.COMPLETE.value == "complete"
        assert MetaCompleteness.PARTIAL.value == "partial"
        assert MetaCompleteness.MINIMAL.value == "minimal"
        assert MetaCompleteness.MISSING.value == "missing"


# ── Test Standard Sets ────────────────────────────────────────────────


class TestStandardSets:
    """Test standard category/flag/use-case sets."""

    def test_standard_categories_contains_dns(self):
        assert "DNS" in STANDARD_CATEGORIES

    def test_standard_flags_contains_apikey(self):
        assert "apikey" in STANDARD_FLAGS

    def test_standard_use_cases(self):
        assert "Footprint" in STANDARD_USE_CASES
        assert "Investigate" in STANDARD_USE_CASES
        assert "Passive" in STANDARD_USE_CASES


# ── Test ModuleInfo ──────────────────────────────────────────────────


class TestModuleInfo:
    """Test ModuleInfo dataclass."""

    def test_defaults(self):
        info = ModuleInfo(name="test", file_path="/test.py")
        assert info.migration_status == MigrationStatus.UNKNOWN
        assert info.meta_completeness == MetaCompleteness.MISSING
        assert info.contract_valid is True
        assert info.watched_events == []
        assert info.produced_events == []

    def test_fields(self):
        info = ModuleInfo(
            name="sfp_test",
            file_path="/modules/sfp_test.py",
            base_class="SpiderFootAsyncPlugin",
            migration_status=MigrationStatus.ASYNC,
            has_async_handle_event=True,
            categories=["DNS"],
        )
        assert info.name == "sfp_test"
        assert info.has_async_handle_event is True
        assert info.categories == ["DNS"]


# ── Test EventTypeInfo ────────────────────────────────────────────────


class TestEventTypeInfo:
    """Test EventTypeInfo dataclass."""

    def test_orphan_producer(self):
        info = EventTypeInfo(name="TEST_EVENT", producers=["mod_a"], consumers=[])
        assert info.is_orphan_producer is True
        assert info.is_orphan_consumer is False

    def test_orphan_consumer(self):
        info = EventTypeInfo(name="TEST_EVENT", producers=[], consumers=["mod_b"])
        assert info.is_orphan_consumer is True
        assert info.is_orphan_producer is False

    def test_connected(self):
        info = EventTypeInfo(
            name="TEST_EVENT",
            producers=["mod_a"],
            consumers=["mod_b"],
        )
        assert info.is_orphan_producer is False
        assert info.is_orphan_consumer is False

    def test_empty(self):
        info = EventTypeInfo(name="EMPTY")
        assert info.is_orphan_producer is False
        assert info.is_orphan_consumer is False


# ── Test AuditReport ─────────────────────────────────────────────────


class TestAuditReport:
    """Test AuditReport dataclass."""

    def test_migration_percentage_empty(self):
        report = AuditReport()
        assert report.migration_percentage == 0.0

    def test_migration_percentage(self):
        report = AuditReport(total_modules=100, async_count=75)
        assert report.migration_percentage == 75.0

    def test_meta_completeness_percentage(self):
        report = AuditReport(total_modules=50, meta_complete_count=40)
        assert report.meta_completeness_percentage == 80.0

    def test_summary(self):
        report = AuditReport(
            generated_at="2025-01-01T00:00:00Z",
            total_modules=10,
            async_count=8,
            modern_count=2,
            contract_valid_count=9,
            contract_invalid_count=1,
            meta_complete_count=7,
            meta_partial_count=2,
            meta_minimal_count=1,
        )
        s = report.summary()
        assert s["total_modules"] == 10
        assert s["migration"]["async"] == 8
        assert s["contract_validation"]["valid"] == 9
        assert s["metadata"]["complete"] == 7


# ── Test ModuleSourceAnalyzer ────────────────────────────────────────


class TestModuleSourceAnalyzer:
    """Test source-level module analysis."""

    def test_analyze_async_module(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_dns_test.py"))
        assert info.name == "sfp_dns_test"
        assert info.migration_status == MigrationStatus.ASYNC
        assert info.base_class == "SpiderFootAsyncPlugin"
        assert info.has_async_handle_event is True
        assert info.has_meta is True
        assert info.line_count > 10

    def test_analyze_modern_module(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp__stor_test.py"))
        assert info.migration_status == MigrationStatus.MODERN
        assert info.has_async_handle_event is False

    def test_analyze_legacy_module(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_legacy.py"))
        assert info.migration_status == MigrationStatus.LEGACY

    def test_analyze_complete_meta(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_dns_test.py"))
        assert info.meta_completeness == MetaCompleteness.COMPLETE
        assert "name" in info.meta_fields_present
        assert "summary" in info.meta_fields_present
        assert "categories" in info.meta_fields_present
        assert info.has_data_source is True

    def test_analyze_minimal_meta(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_minimal.py"))
        assert info.meta_completeness == MetaCompleteness.MINIMAL

    def test_analyze_partial_meta(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_legacy.py"))
        # Legacy has name + summary but missing flags, useCases, categories
        assert info.meta_completeness in (MetaCompleteness.MINIMAL, MetaCompleteness.PARTIAL)

    def test_extract_categories(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_dns_test.py"))
        assert "DNS" in info.categories

    def test_extract_flags(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_producer.py"))
        assert "slow" in info.flags

    def test_extract_use_cases(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_dns_test.py"))
        assert "Footprint" in info.use_cases
        assert "Investigate" in info.use_cases

    def test_analyze_directory(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        results = analyzer.analyze_directory(tmp_modules_dir)
        assert len(results) == 5  # 5 test modules
        names = {r.name for r in results}
        assert "sfp_dns_test" in names
        assert "sfp_legacy" in names

    def test_analyze_nonexistent_dir(self):
        analyzer = ModuleSourceAnalyzer()
        results = analyzer.analyze_directory("/nonexistent/path")
        assert results == []

    def test_analyze_nonexistent_file(self):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file("/nonexistent/sfp_test.py")
        assert len(info.contract_errors) > 0

    def test_non_standard_category_detection(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp__stor_test.py"))
        # "Storage" is not in STANDARD_CATEGORIES
        assert "Storage" in info.non_standard_categories

    def test_opts_detection(self, tmp_modules_dir):
        analyzer = ModuleSourceAnalyzer()
        info = analyzer.analyze_file(os.path.join(tmp_modules_dir, "sfp_dns_test.py"))
        assert info.has_opts is True
        assert info.has_optdescs is True


# ── Test EventDependencyGraph ────────────────────────────────────────


class TestEventDependencyGraph:
    """Test event dependency graph operations."""

    def test_add_module(self, sample_module_infos):
        graph = EventDependencyGraph()
        graph.add_module(sample_module_infos[0])  # sfp_dns
        assert "IP_ADDRESS" in graph.event_types
        assert "sfp_dns" in graph.event_types["IP_ADDRESS"].producers

    def test_build_edges(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        edges = graph.build_edges()
        assert len(edges) > 0
        # sfp_dns produces IP_ADDRESS, sfp_shodan consumes IP_ADDRESS
        dns_to_shodan = [
            e for e in edges
            if e.source_module == "sfp_dns" and e.target_module == "sfp_shodan"
        ]
        assert len(dns_to_shodan) > 0

    def test_orphan_producers(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        orphans = graph.orphan_producers()
        # OPERATING_SYSTEM, WEBSERVER_BANNER, RAW_RIR_DATA produced but not consumed
        assert len(orphans) > 0

    def test_orphan_consumers_excludes_root(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        orphans = graph.orphan_consumers()
        # ROOT events should not appear as orphan consumers
        assert "ROOT" not in orphans

    def test_downstream_modules(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        downstream = graph.downstream_modules("sfp_dns")
        assert "sfp_shodan" in downstream

    def test_upstream_modules(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        upstream = graph.upstream_modules("sfp_shodan")
        assert "sfp_dns" in upstream

    def test_fanout(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        assert graph.module_fanout("sfp_dns") >= 1

    def test_fanin(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        assert graph.module_fanin("sfp_shodan") >= 1

    def test_highest_fanout(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        top = graph.highest_fanout(top_n=3)
        assert len(top) == 3
        # Each entry is (name, fanout_count)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in top)

    def test_highest_fanin(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        top = graph.highest_fanin(top_n=3)
        assert len(top) == 3

    def test_to_dot(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        graph.build_edges()
        dot = graph.to_dot()
        assert "digraph EventFlow" in dot
        assert "rankdir=LR" in dot
        assert "->" in dot

    def test_to_dot_truncates(self, sample_module_infos):
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        edges = graph.build_edges()
        # Only test truncation if there are enough edges
        if len(edges) > 1:
            dot = graph.to_dot(max_edges=1)
            assert "truncated" in dot
        else:
            # With few edges, truncation at 0 should always trigger
            dot = graph.to_dot(max_edges=0)
            assert "truncated" in dot

    def test_empty_graph(self):
        graph = EventDependencyGraph()
        assert graph.orphan_producers() == []
        assert graph.orphan_consumers() == []
        assert graph.build_edges() == []


# ── Test MetadataAuditor ─────────────────────────────────────────────


class TestMetadataAuditor:
    """Test metadata quality auditing."""

    def test_audit_complete_module(self):
        auditor = MetadataAuditor()
        info = ModuleInfo(
            name="sfp_test",
            file_path="/test.py",
            has_meta=True,
            meta_completeness=MetaCompleteness.COMPLETE,
            meta_fields_present=["name", "summary", "flags", "useCases", "categories", "dataSource"],
            has_data_source=True,
            categories=["DNS"],
            flags=[],
            use_cases=["Footprint"],
            has_opts=True,
            has_optdescs=True,
        )
        result = auditor.audit_module(info)
        assert result["score"] >= 90
        assert len(result["issues"]) == 0

    def test_audit_missing_meta(self):
        auditor = MetadataAuditor()
        info = ModuleInfo(name="sfp_none", file_path="/test.py", has_meta=False)
        result = auditor.audit_module(info)
        assert result["score"] == 0
        assert "Missing meta dict" in result["issues"][0]

    def test_audit_partial_meta(self):
        auditor = MetadataAuditor()
        info = ModuleInfo(
            name="sfp_partial",
            file_path="/test.py",
            has_meta=True,
            meta_completeness=MetaCompleteness.PARTIAL,
            meta_fields_present=["name", "summary", "flags"],
            meta_fields_missing=["useCases", "categories"],
            categories=[],
            flags=[],
            use_cases=[],
        )
        result = auditor.audit_module(info)
        assert 0 < result["score"] < 100
        assert any("Missing required" in i for i in result["issues"])

    def test_audit_non_standard_categories(self):
        auditor = MetadataAuditor()
        info = ModuleInfo(
            name="sfp_test",
            file_path="/test.py",
            has_meta=True,
            meta_fields_present=["name", "summary", "flags", "useCases", "categories"],
            categories=["Custom Category"],
            non_standard_categories=["Custom Category"],
            flags=[],
            use_cases=["Footprint"],
        )
        result = auditor.audit_module(info)
        assert any("Non-standard categories" in s for s in result["suggestions"])

    def test_audit_batch(self, sample_module_infos):
        auditor = MetadataAuditor()
        result = auditor.audit_batch(sample_module_infos)
        assert result["total_modules"] == 3
        assert "average_score" in result
        assert "worst_modules" in result
        assert "common_issues" in result

    def test_audit_module_no_data_source(self):
        auditor = MetadataAuditor()
        info = ModuleInfo(
            name="sfp_nodatasource",
            file_path="/test.py",
            has_meta=True,
            meta_fields_present=["name", "summary", "flags", "useCases", "categories"],
            has_data_source=False,
            categories=["DNS"],
            flags=[],
            use_cases=["Footprint"],
        )
        result = auditor.audit_module(info)
        assert any("dataSource" in s for s in result["suggestions"])


# ── Test ModuleDocGenerator ──────────────────────────────────────────


class TestModuleDocGenerator:
    """Test documentation generation."""

    def test_generate_module_doc(self):
        gen = ModuleDocGenerator()
        info = ModuleInfo(
            name="sfp_dns",
            file_path="/modules/sfp_dns.py",
            base_class="SpiderFootAsyncPlugin",
            has_async_handle_event=True,
            categories=["DNS"],
            use_cases=["Footprint"],
            flags=["slow"],
            watched_events=["DOMAIN_NAME"],
            produced_events=["IP_ADDRESS"],
        )
        doc = gen.generate_module_doc(info)
        assert "## sfp_dns" in doc
        assert "DNS" in doc
        assert "Footprint" in doc
        assert "DOMAIN_NAME" in doc
        assert "IP_ADDRESS" in doc

    def test_generate_category_index(self, sample_module_infos):
        gen = ModuleDocGenerator()
        index = gen.generate_category_index(sample_module_infos)
        assert "# Module Index by Category" in index
        assert "DNS" in index
        assert "Search Engines" in index

    def test_generate_event_flow_doc(self, sample_module_infos):
        gen = ModuleDocGenerator()
        graph = EventDependencyGraph()
        for mod in sample_module_infos:
            graph.add_module(mod)
        doc = gen.generate_event_flow_doc(graph)
        assert "# Event Type Reference" in doc
        assert "IP_ADDRESS" in doc


# ── Test AsyncExecutionVerifier ──────────────────────────────────────


class TestAsyncExecutionVerifier:
    """Test async compatibility checking."""

    def test_check_sync_class(self):
        class SyncModule:
            meta = {"name": "test"}
            opts = {}
            optdescs = {}

            def handleEvent(self, event):
                pass

        result = AsyncExecutionVerifier.check_async_compatibility(SyncModule)
        assert result["has_async_handle_event"] is False
        assert result["is_async_plugin"] is False

    def test_check_async_class(self):
        class AsyncModule:
            meta = {"name": "test"}
            opts = {}
            optdescs = {}

            async def handleEvent(self, event):
                pass

        result = AsyncExecutionVerifier.check_async_compatibility(AsyncModule)
        assert result["has_async_handle_event"] is True

    def test_lists_async_methods(self):
        class MixedModule:
            async def handleEvent(self, event):
                pass

            async def process(self):
                pass

            def sync_method(self):
                pass

        result = AsyncExecutionVerifier.check_async_compatibility(MixedModule)
        assert "handleEvent" in result["has_async_methods"]
        assert "process" in result["has_async_methods"]
        assert "sync_method" not in result["has_async_methods"]


# ── Test ModuleContractAuditor ───────────────────────────────────────


class TestModuleContractAuditor:
    """Test class-level contract validation."""

    def test_validate_valid_class(self):
        class ValidModule:
            meta = {
                "name": "Test Module",
                "summary": "A test module.",
                "flags": [],
                "useCases": ["Footprint"],
                "categories": ["DNS"],
            }
            opts = {"opt1": True}
            optdescs = {"opt1": "An option."}
            errorState = False

            def setup(self, sfc, userOpts=None):
                pass

            def watchedEvents(self):
                return ["DOMAIN_NAME"]

            def producedEvents(self):
                return ["IP_ADDRESS"]

            def handleEvent(self, event):
                pass

            def finish(self):
                pass

            def setTarget(self, target):
                pass

            def setScanId(self, scanId):
                pass

            def checkForStop(self):
                return False

        auditor = ModuleContractAuditor()
        info = auditor.validate_module_class(ValidModule, name="sfp_valid")
        assert info.name == "sfp_valid"
        assert info.has_meta is True
        assert info.has_opts is True
        assert info.has_optdescs is True
        assert info.meta_completeness == MetaCompleteness.COMPLETE

    def test_validate_minimal_meta(self):
        class MinimalModule:
            meta = {"name": "Minimal"}
            opts = {}
            optdescs = {}
            errorState = False

            def setup(self, sfc, userOpts=None):
                pass

            def watchedEvents(self):
                return []

            def producedEvents(self):
                return []

            def handleEvent(self, event):
                pass

        auditor = ModuleContractAuditor()
        info = auditor.validate_module_class(MinimalModule, name="sfp_min")
        assert info.meta_completeness == MetaCompleteness.MINIMAL

    def test_validate_async_handler_detection(self):
        class AsyncModule:
            meta = {"name": "Async", "summary": "s", "flags": [], "useCases": [], "categories": []}
            opts = {}
            optdescs = {}
            errorState = False

            def setup(self, sfc, userOpts=None):
                pass

            def watchedEvents(self):
                return ["IP_ADDRESS"]

            def producedEvents(self):
                return ["GEOINFO"]

            async def handleEvent(self, event):
                pass

        auditor = ModuleContractAuditor()
        info = auditor.validate_module_class(AsyncModule)
        assert info.has_async_handle_event is True

    def test_inspect_non_standard_flags(self):
        auditor = ModuleContractAuditor()
        info = ModuleInfo(name="test", file_path="/test.py")
        meta = {
            "name": "Test",
            "summary": "s",
            "flags": ["custom_flag"],
            "useCases": ["Footprint"],
            "categories": ["DNS"],
        }
        auditor._inspect_meta(meta, info)
        assert "custom_flag" in info.non_standard_flags

    def test_event_extraction(self):
        class ModWithEvents:
            meta = {"name": "Events"}
            opts = {}
            optdescs = {}
            errorState = False

            def setup(self, sfc, userOpts=None):
                pass

            def watchedEvents(self):
                return ["A", "B"]

            def producedEvents(self):
                return ["C", "D"]

            def handleEvent(self, event):
                pass

        auditor = ModuleContractAuditor()
        info = auditor.validate_module_class(ModWithEvents)
        assert info.watched_events == ["A", "B"]
        assert info.produced_events == ["C", "D"]


# ── Test ModuleAuditRunner ───────────────────────────────────────────


class TestModuleAuditRunner:
    """Test the full audit runner."""

    def test_run_source_audit(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        assert report.total_modules == 5
        assert report.async_count >= 3  # dns_test, minimal, producer
        assert report.modern_count >= 1  # stor_test
        assert report.legacy_count >= 1  # legacy

    def test_source_audit_migration_percentage(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        assert report.migration_percentage > 0

    def test_source_audit_summary(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        s = report.summary()
        assert s["total_modules"] == 5
        assert "migration" in s
        assert "metadata" in s

    def test_run_class_audit(self):
        class Mod1:
            meta = {"name": "Mod1", "summary": "s", "flags": [], "useCases": [], "categories": []}
            opts = {}
            optdescs = {}
            errorState = False
            def setup(self, sfc, userOpts=None): pass
            def watchedEvents(self): return ["A"]
            def producedEvents(self): return ["B"]
            def handleEvent(self, event): pass

        class Mod2:
            meta = {"name": "Mod2", "summary": "s", "flags": [], "useCases": [], "categories": []}
            opts = {}
            optdescs = {}
            errorState = False
            def setup(self, sfc, userOpts=None): pass
            def watchedEvents(self): return ["B"]
            def producedEvents(self): return ["C"]
            async def handleEvent(self, event): pass

        runner = ModuleAuditRunner()
        report = runner.run_class_audit({"mod1": Mod1, "mod2": Mod2})
        assert report.total_modules == 2
        assert report.async_handler_count >= 1  # Mod2

    def test_no_modules_dir_raises(self):
        runner = ModuleAuditRunner()
        with pytest.raises(ValueError, match="modules_dir"):
            runner.run_source_audit()

    def test_event_graph_in_report(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        # Source analysis may not extract events from source
        # but the report structure should have event_types
        assert isinstance(report.event_types, dict)
        assert isinstance(report.event_edges, list)

    def test_accessor_properties(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        assert isinstance(runner.metadata_auditor, MetadataAuditor)
        assert isinstance(runner.doc_generator, ModuleDocGenerator)
        assert isinstance(runner.source_analyzer, ModuleSourceAnalyzer)

    def test_modules_without_datasource(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        # sfp__stor_test should NOT be flagged (starts with sfp__stor)
        assert "sfp__stor_test" not in report.modules_without_data_source

    def test_non_standard_categories_in_report(self, tmp_modules_dir):
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()
        # sfp__stor_test has "Storage" which is non-standard
        assert "sfp__stor_test" in report.modules_with_non_standard_categories


# ── Test EventEdge ───────────────────────────────────────────────────


class TestEventEdge:
    """Test EventEdge dataclass."""

    def test_creation(self):
        edge = EventEdge(
            source_module="sfp_dns",
            target_module="sfp_shodan",
            event_type="IP_ADDRESS",
        )
        assert edge.source_module == "sfp_dns"
        assert edge.target_module == "sfp_shodan"
        assert edge.event_type == "IP_ADDRESS"


# ── Integration-style tests ──────────────────────────────────────────


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_pipeline_source_then_metadata(self, tmp_modules_dir):
        """Run source audit then metadata audit on results."""
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()

        # Run metadata audit on the module infos
        meta_report = runner.metadata_auditor.audit_batch(report.modules)
        assert meta_report["total_modules"] == 5
        assert meta_report["average_score"] > 0

    def test_doc_generation_from_audit(self, tmp_modules_dir):
        """Generate docs from audit results."""
        runner = ModuleAuditRunner(modules_dir=tmp_modules_dir)
        report = runner.run_source_audit()

        # Generate category index
        index = runner.doc_generator.generate_category_index(report.modules)
        assert "Module Index" in index

        # Generate individual module docs
        for mod in report.modules:
            doc = runner.doc_generator.generate_module_doc(mod)
            assert f"## {mod.name}" in doc

    def test_event_graph_from_class_audit(self):
        """Build event graph from class-level audit."""

        class ModA:
            meta = {"name": "A"}
            opts = {}
            optdescs = {}
            errorState = False
            def setup(self, sfc, userOpts=None): pass
            def watchedEvents(self): return ["ROOT"]
            def producedEvents(self): return ["DOMAIN_NAME"]
            def handleEvent(self, event): pass

        class ModB:
            meta = {"name": "B"}
            opts = {}
            optdescs = {}
            errorState = False
            def setup(self, sfc, userOpts=None): pass
            def watchedEvents(self): return ["DOMAIN_NAME"]
            def producedEvents(self): return ["IP_ADDRESS"]
            def handleEvent(self, event): pass

        class ModC:
            meta = {"name": "C"}
            opts = {}
            optdescs = {}
            errorState = False
            def setup(self, sfc, userOpts=None): pass
            def watchedEvents(self): return ["IP_ADDRESS"]
            def producedEvents(self): return ["GEOINFO"]
            def handleEvent(self, event): pass

        runner = ModuleAuditRunner()
        report = runner.run_class_audit({"mod_a": ModA, "mod_b": ModB, "mod_c": ModC})

        # Check graph connectivity: A → B → C
        graph = EventDependencyGraph()
        for mod in report.modules:
            graph.add_module(mod)
        graph.build_edges()

        assert "mod_b" in graph.downstream_modules("mod_a")
        assert "mod_c" in graph.downstream_modules("mod_b")
        assert "mod_a" in graph.upstream_modules("mod_b")
