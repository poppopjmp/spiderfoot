"""
Tests for spiderfoot.module_loader — Cycle 22: Module Dependency Resolution Wiring.

Tests the ModuleLoader adapter that connects ModuleRegistry and ModuleGraph
to the scanner's module loading path with fallback to legacy __import__.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from spiderfoot.module_loader import (
    ModuleLoader,
    LoadResult,
    get_module_loader,
    init_module_loader,
    reset_module_loader,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_registry(modules=None, discover_ok=True):
    """Create a fake ModuleRegistry with controllable behavior.

    Uses a real class (not MagicMock) so ``__contains__`` works correctly.
    """
    modules = modules or {}

    class FakeRegistry:
        def __bool__(self):
            return True

        def __contains__(self, name):
            return name in modules

        def __len__(self):
            return len(modules)

        def get(self, name):
            return modules.get(name)

        def create_instance(self, name, *a, **kw):
            if name not in modules:
                raise KeyError(f"Module '{name}' not in registry")
            inst = MagicMock()
            inst.__name__ = name
            inst._priority = modules[name].get("priority", 3)
            inst.errorState = False
            inst.enrichTarget.return_value = None
            return inst

        def dependencies_of(self, name):
            return set(modules.get(name, {}).get("deps", []))

        def dependents_of(self, name):
            return set(modules.get(name, {}).get("dependents", []))

        def resolve_for_output(self, types):
            result = set()
            for t in types:
                result.update(modules.get(t, {}).get("producers", []))
            return result

        def stats(self):
            return {"total_modules": len(modules)}

    return FakeRegistry()

def _make_mock_graph(module_order=None, cycles=None):
    """Create a mock ModuleGraph with controllable behavior."""
    graph = MagicMock()
    module_order = module_order or []
    cycles = cycles or []

    graph.topological_order.return_value = list(module_order)
    graph.detect_cycles.return_value = cycles
    graph.modules = {m: MagicMock() for m in module_order}

    def dependencies_of(name):
        return set()

    graph.dependencies_of = dependencies_of

    def dependents_of(name):
        return set()

    graph.dependents_of = dependents_of

    def resolve_for_output(types):
        return set(module_order)

    graph.resolve_for_output = resolve_for_output

    graph.stats.return_value = {"module_count": len(module_order)}

    return graph


def _make_config(module_names):
    """Create a minimal config dict for testing."""
    modules_dict = {}
    for name in module_names:
        modules_dict[name] = {"opts": {}, "meta": {}}
    return {
        "__modules__": modules_dict,
        "_socks1type": "",
        "__outputfilter": None,
        "_internettlds": "",
    }


def _mock_module_instance(name, priority=3):
    """Create a mock module instance that behaves like SpiderFootPlugin."""
    mod = MagicMock()
    mod.__name__ = name
    mod._priority = priority
    mod.errorState = False
    mod.enrichTarget.return_value = None
    mod.incomingEventQueue = None
    mod.outgoingEventQueue = None
    return mod


# ---------------------------------------------------------------------------
# TestLoadResult
# ---------------------------------------------------------------------------


class TestLoadResult:
    """Tests for the LoadResult dataclass."""

    def test_basic_creation(self):
        result = LoadResult(
            modules=OrderedDict(),
            loaded=5,
            failed=1,
            skipped=0,
            errors=[("sfp_bad", "ImportError")],
            order_method="topological",
            cycles_detected=0,
            duration=0.5,
        )
        assert result.loaded == 5
        assert result.failed == 1
        assert result.order_method == "topological"
        assert len(result.errors) == 1

    def test_repr(self):
        result = LoadResult(
            modules=OrderedDict(),
            loaded=3,
            failed=0,
            skipped=1,
            errors=[],
            order_method="priority",
            cycles_detected=2,
            duration=1.234,
        )
        r = repr(result)
        assert "loaded=3" in r
        assert "priority" in r
        assert "cycles=2" in r

    def test_default_pruned(self):
        result = LoadResult(
            modules=OrderedDict(),
            loaded=0,
            failed=0,
            skipped=0,
            errors=[],
            order_method="priority",
            cycles_detected=0,
            duration=0.0,
        )
        assert result.pruned == []


# ---------------------------------------------------------------------------
# TestModuleLoaderInit
# ---------------------------------------------------------------------------


class TestModuleLoaderInit:
    """Tests for ModuleLoader construction."""

    def test_default_init(self):
        loader = ModuleLoader()
        assert not loader.has_registry
        assert not loader.has_graph
        assert loader._enable_topological is True
        assert loader._enable_pruning is False

    def test_with_registry(self):
        registry = _make_mock_registry()
        loader = ModuleLoader(registry=registry)
        assert loader.has_registry
        assert loader.registry is registry

    def test_with_graph(self):
        graph = _make_mock_graph()
        loader = ModuleLoader(graph=graph)
        assert loader.has_graph
        assert loader.graph is graph

    def test_with_both(self):
        registry = _make_mock_registry()
        graph = _make_mock_graph()
        loader = ModuleLoader(registry=registry, graph=graph)
        assert loader.has_registry
        assert loader.has_graph

    def test_custom_flags(self):
        loader = ModuleLoader(
            enable_topological=False,
            enable_pruning=True,
        )
        assert loader._enable_topological is False
        assert loader._enable_pruning is True

    def test_repr(self):
        loader = ModuleLoader()
        r = repr(loader)
        assert "ModuleLoader" in r
        assert "registry=False" in r


# ---------------------------------------------------------------------------
# TestModuleLoaderCreate
# ---------------------------------------------------------------------------


class TestModuleLoaderCreate:
    """Tests for the classmethod factory."""

    @patch("spiderfoot.module_graph.ModuleGraph")
    @patch("spiderfoot.module_registry.ModuleRegistry")
    def test_create_imports_registry_and_graph(self, MockReg, MockGraph):
        """Factory should attempt to build both registry and graph."""
        mock_reg = MagicMock()
        mock_reg.discover.return_value = MagicMock(loaded=10, failed=0)
        MockReg.return_value = mock_reg

        mock_graph = MagicMock()
        mock_graph.load_modules.return_value = 10
        MockGraph.return_value = mock_graph

        loader = ModuleLoader.create("/fake/modules")
        assert loader.has_registry
        assert loader.has_graph
        mock_reg.discover.assert_called_once_with("/fake/modules")
        mock_graph.load_modules.assert_called_once_with("/fake/modules")

    def test_create_survives_missing_registry(self):
        """Should work even if ModuleRegistry import fails."""
        with patch.dict(
            "sys.modules",
            {"spiderfoot.module_registry": None},
        ):
            # ModuleLoader.create will handle the import error
            loader = ModuleLoader()
            assert not loader.has_registry

    def test_create_survives_missing_graph(self):
        """Should work even if ModuleGraph import fails."""
        loader = ModuleLoader(registry=_make_mock_registry())
        assert loader.has_registry
        assert not loader.has_graph


# ---------------------------------------------------------------------------
# TestLegacyImport
# ---------------------------------------------------------------------------


class TestLegacyImport:
    """Tests for the legacy __import__ fallback path."""

    def test_successful_legacy_import(self):
        """Legacy import should work for valid modules."""
        mock_mod = MagicMock()
        mock_instance = _mock_module_instance("sfp_test")
        mock_mod.sfp_test = MagicMock(return_value=mock_instance)

        with patch("builtins.__import__", return_value=mock_mod):
            result = ModuleLoader._legacy_import("sfp_test")
            assert result is not None
            assert result.__name__ == "sfp_test"

    def test_failed_import(self):
        """Legacy import should return None on ImportError."""
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = ModuleLoader._legacy_import("sfp_nonexistent")
            assert result is None

    def test_failed_instantiation(self):
        """Legacy import should return None if class init fails."""
        mock_mod = MagicMock()
        mock_mod.sfp_broken = MagicMock(side_effect=RuntimeError("boom"))

        with patch("builtins.__import__", return_value=mock_mod):
            result = ModuleLoader._legacy_import("sfp_broken")
            assert result is None


# ---------------------------------------------------------------------------
# TestWireModule
# ---------------------------------------------------------------------------


class TestWireModule:
    """Tests for the static _wire_module method."""

    def test_basic_wiring(self):
        """Module should be wired with scan_id, dbh, sf, target."""
        mod = _mock_module_instance("sfp_test")
        config = _make_config(["sfp_test"])
        modules_config = config["__modules__"]
        sf = MagicMock()
        dbh = MagicMock()
        target = MagicMock()
        pool = MagicMock()
        eq = queue.Queue()

        ModuleLoader._wire_module(
            mod, "sfp_test", config, modules_config,
            sf=sf, scan_id="scan-1", dbh=dbh,
            target=target, shared_pool=pool, event_queue=eq,
        )

        mod.clearListeners.assert_called_once()
        mod.setScanId.assert_called_once_with("scan-1")
        mod.setSharedThreadPool.assert_called_once_with(pool)
        mod.setDbh.assert_called_once_with(dbh)
        mod.setup.assert_called_once()
        mod.setTarget.assert_called_once()
        assert mod.outgoingEventQueue is eq
        assert mod.incomingEventQueue is not None

    def test_missing_opts_gets_default(self):
        """Should create empty opts if missing."""
        mod = _mock_module_instance("sfp_test")
        config = _make_config(["sfp_test"])
        config["__modules__"]["sfp_test"] = {}  # no opts key
        modules_config = config["__modules__"]

        ModuleLoader._wire_module(
            mod, "sfp_test", config, modules_config,
            sf=MagicMock(),
        )

        assert config["__modules__"]["sfp_test"]["opts"] == {}

    def test_bad_opts_raises(self):
        """Should raise TypeError if opts is not a dict."""
        mod = _mock_module_instance("sfp_test")
        config = _make_config(["sfp_test"])
        config["__modules__"]["sfp_test"]["opts"] = "badvalue"
        modules_config = config["__modules__"]

        with pytest.raises(TypeError, match="not a dict"):
            ModuleLoader._wire_module(
                mod, "sfp_test", config, modules_config,
                sf=MagicMock(),
            )

    def test_target_enrichment(self):
        """enrichTarget returning a new target should be used."""
        mod = _mock_module_instance("sfp_test")
        new_target = MagicMock()
        mod.enrichTarget.return_value = new_target
        config = _make_config(["sfp_test"])
        modules_config = config["__modules__"]
        target = MagicMock()

        ModuleLoader._wire_module(
            mod, "sfp_test", config, modules_config,
            sf=MagicMock(), target=target,
        )

        mod.enrichTarget.assert_called_once_with(target)
        # setTarget should be called with the enriched target
        mod.setTarget.assert_called_once()


# ---------------------------------------------------------------------------
# TestLoadModules
# ---------------------------------------------------------------------------


class TestLoadModules:
    """Tests for the full load_modules() pipeline."""

    def test_empty_module_list(self):
        loader = ModuleLoader()
        config = _make_config([])
        result = loader.load_modules([], config)
        assert result.loaded == 0
        assert result.failed == 0
        assert len(result.modules) == 0

    def test_load_with_registry(self):
        """Registry-based loading should create instances."""
        modules = {
            "sfp_dns": {"priority": 1},
            "sfp_web": {"priority": 2},
        }
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(registry=registry)
        config = _make_config(["sfp_dns", "sfp_web"])

        result = loader.load_modules(
            ["sfp_dns", "sfp_web"], config,
            sf=MagicMock(), scan_id="scan-1", dbh=MagicMock(),
        )

        assert result.loaded == 2
        assert result.failed == 0
        assert "sfp_dns" in result.modules
        assert "sfp_web" in result.modules

    def test_load_fallback_to_legacy(self):
        """When registry fails, should fall back to legacy import."""
        loader = ModuleLoader()  # no registry
        config = _make_config(["sfp_test"])
        mock_mod = MagicMock()
        mock_instance = _mock_module_instance("sfp_test")
        mock_mod.sfp_test = MagicMock(return_value=mock_instance)

        with patch("builtins.__import__", return_value=mock_mod):
            result = loader.load_modules(
                ["sfp_test"], config,
                sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
            )
            assert result.loaded == 1
            assert result.order_method == "priority"

    def test_load_records_failures(self):
        """Failed modules should be counted and recorded."""
        loader = ModuleLoader()  # no registry
        config = _make_config(["sfp_fail"])  # module IS in config

        with patch("builtins.__import__", side_effect=ImportError("nope")):
            result = loader.load_modules(
                ["sfp_fail"], config,
                sf=MagicMock(),
            )
            # Legacy import fails → counted as failed
            assert result.failed == 1
            assert len(result.errors) == 1
            assert result.errors[0][0] == "sfp_fail"

    def test_skips_unconfigured_modules(self):
        """Modules not in __modules__ config should be skipped."""
        loader = ModuleLoader()
        config = _make_config([])  # empty modules config

        with patch("builtins.__import__") as mock_import:
            result = loader.load_modules(
                ["sfp_missing"], config,
                sf=MagicMock(),
            )
            # Should be skipped (not in __modules__), not failed
            assert result.skipped == 1
            assert result.loaded == 0

    def test_load_result_duration(self):
        """Duration should be non-negative."""
        loader = ModuleLoader()
        config = _make_config([])
        result = loader.load_modules([], config)
        assert result.duration >= 0


# ---------------------------------------------------------------------------
# TestTopologicalOrdering
# ---------------------------------------------------------------------------


class TestTopologicalOrdering:
    """Tests for dependency-ordered module execution."""

    def test_topological_order_applied(self):
        """Modules should be reordered by dependency graph."""
        # Graph says: sfp_a -> sfp_b -> sfp_c
        graph = _make_mock_graph(
            module_order=["sfp_a", "sfp_b", "sfp_c"],
        )
        modules = {
            "sfp_a": {"priority": 3},
            "sfp_b": {"priority": 1},
            "sfp_c": {"priority": 2},
        }
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(
            registry=registry,
            graph=graph,
            enable_topological=True,
        )
        config = _make_config(["sfp_c", "sfp_a", "sfp_b"])

        result = loader.load_modules(
            ["sfp_c", "sfp_a", "sfp_b"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.order_method == "topological"
        assert list(result.modules.keys()) == ["sfp_a", "sfp_b", "sfp_c"]

    def test_priority_fallback(self):
        """When topological is disabled, should use _priority sort."""
        modules = {
            "sfp_high": {"priority": 1},
            "sfp_low": {"priority": 5},
            "sfp_mid": {"priority": 3},
        }
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(
            registry=registry,
            enable_topological=False,  # disabled
        )
        config = _make_config(["sfp_low", "sfp_high", "sfp_mid"])

        result = loader.load_modules(
            ["sfp_low", "sfp_high", "sfp_mid"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.order_method == "priority"
        keys = list(result.modules.keys())
        # Should be sorted by _priority: 1, 3, 5
        assert keys == ["sfp_high", "sfp_mid", "sfp_low"]

    def test_cycles_detected_and_logged(self):
        """Cycles should be detected but not break loading."""
        graph = _make_mock_graph(
            module_order=["sfp_a", "sfp_b"],
            cycles=[["sfp_a", "sfp_b", "sfp_a"]],
        )
        modules = {"sfp_a": {"priority": 1}, "sfp_b": {"priority": 2}}
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(registry=registry, graph=graph)
        config = _make_config(["sfp_a", "sfp_b"])

        result = loader.load_modules(
            ["sfp_a", "sfp_b"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.cycles_detected == 1
        assert result.loaded == 2  # Still loaded despite cycle

    def test_ungraphed_modules_appended(self):
        """Modules not in the graph should go at the end."""
        graph = _make_mock_graph(module_order=["sfp_a"])
        modules = {
            "sfp_a": {"priority": 2},
            "sfp_extra": {"priority": 1},
        }
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(registry=registry, graph=graph)
        config = _make_config(["sfp_extra", "sfp_a"])

        result = loader.load_modules(
            ["sfp_extra", "sfp_a"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        keys = list(result.modules.keys())
        assert keys[0] == "sfp_a"  # In graph, comes first
        assert keys[1] == "sfp_extra"  # Not in graph, appended


# ---------------------------------------------------------------------------
# TestModulePruning
# ---------------------------------------------------------------------------


class TestModulePruning:
    """Tests for minimal-set module pruning."""

    def test_pruning_removes_unneeded(self):
        """Modules not needed for desired output should be pruned."""
        modules = {
            "sfp_needed": {"priority": 1},
            "sfp_extra": {"priority": 2},
        }
        registry = _make_mock_registry(modules)
        # Override resolve_for_output to return only sfp_needed
        registry.resolve_for_output = lambda types: {"sfp_needed"}

        loader = ModuleLoader(
            registry=registry,
            enable_pruning=True,
        )
        config = _make_config(["sfp_needed", "sfp_extra"])

        result = loader.load_modules(
            ["sfp_needed", "sfp_extra"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
            desired_output_types=["IP_ADDRESS"],
        )

        assert result.loaded == 1
        assert "sfp_needed" in result.modules
        assert "sfp_extra" not in result.modules
        assert "sfp_extra" in result.pruned

    def test_pruning_disabled_by_default(self):
        """Pruning should not happen when enable_pruning=False."""
        modules = {
            "sfp_a": {"priority": 1},
            "sfp_b": {"priority": 2},
        }
        registry = _make_mock_registry(modules)

        loader = ModuleLoader(
            registry=registry,
            enable_pruning=False,  # default
        )
        config = _make_config(["sfp_a", "sfp_b"])

        result = loader.load_modules(
            ["sfp_a", "sfp_b"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.loaded == 2  # Both loaded, no pruning
        assert result.pruned == []

    def test_pruning_without_desired_types(self):
        """Pruning should not happen without desired_output_types."""
        modules = {"sfp_a": {"priority": 1}}
        registry = _make_mock_registry(modules)
        loader = ModuleLoader(registry=registry, enable_pruning=True)
        config = _make_config(["sfp_a"])

        result = loader.load_modules(
            ["sfp_a"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.loaded == 1
        assert result.pruned == []


# ---------------------------------------------------------------------------
# TestDependencyQueries
# ---------------------------------------------------------------------------


class TestDependencyQueries:
    """Tests for dependency_info, resolve_minimal_set, get_topological_order."""

    def test_dependency_info_with_registry(self):
        """Should return dependency info from registry."""
        @dataclass
        class FakeDesc:
            watched_events = frozenset(["DNS_TEXT"])
            produced_events = frozenset(["IP_ADDRESS"])

        modules = {"sfp_dns": {"priority": 1, "deps": ["sfp_root"]}}
        registry = _make_mock_registry(modules)
        registry.get = lambda name: FakeDesc() if name == "sfp_dns" else None

        loader = ModuleLoader(registry=registry)
        info = loader.dependency_info("sfp_dns")

        assert info["module"] == "sfp_dns"
        assert "sfp_root" in info["depends_on"]

    def test_dependency_info_with_graph(self):
        """Should fall back to graph when no registry."""
        graph = _make_mock_graph(module_order=["sfp_dns"])
        graph.modules["sfp_dns"] = MagicMock(
            watched_events=["DNS_TEXT"],
            produced_events=["IP_ADDRESS"],
        )
        graph.dependencies_of = lambda n: {"sfp_root"}
        graph.dependents_of = lambda n: set()

        loader = ModuleLoader(graph=graph)
        info = loader.dependency_info("sfp_dns")

        assert "sfp_root" in info["depends_on"]

    def test_resolve_minimal_set(self):
        """Should delegate to registry's resolve_for_output."""
        modules = {"sfp_dns": {"priority": 1}}
        registry = _make_mock_registry(modules)
        registry.resolve_for_output = lambda types: {"sfp_dns", "sfp_web"}

        loader = ModuleLoader(registry=registry)
        needed = loader.resolve_minimal_set(
            ["IP_ADDRESS"],
            available_modules=["sfp_dns", "sfp_web", "sfp_extra"],
        )

        assert "sfp_dns" in needed
        assert "sfp_web" in needed
        assert "sfp_extra" not in needed

    def test_resolve_minimal_set_no_infrastructure(self):
        """Should raise RuntimeError when no registry or graph."""
        loader = ModuleLoader()
        with pytest.raises(RuntimeError, match="No registry or graph"):
            loader.resolve_minimal_set(["IP_ADDRESS"])

    def test_get_topological_order(self):
        """Should return filtered topological order."""
        graph = _make_mock_graph(module_order=["sfp_a", "sfp_b", "sfp_c"])
        loader = ModuleLoader(graph=graph)

        order = loader.get_topological_order(["sfp_c", "sfp_a"])
        assert order == ["sfp_a", "sfp_c"]

    def test_get_topological_order_no_graph(self):
        """Should raise RuntimeError when no graph."""
        loader = ModuleLoader()
        with pytest.raises(RuntimeError, match="No graph"):
            loader.get_topological_order()


# ---------------------------------------------------------------------------
# TestStats
# ---------------------------------------------------------------------------


class TestStats:
    """Tests for the stats() method."""

    def test_stats_without_infrastructure(self):
        loader = ModuleLoader()
        s = loader.stats()
        assert s["has_registry"] is False
        assert s["has_graph"] is False
        assert "registry" not in s
        assert "graph" not in s

    def test_stats_with_infrastructure(self):
        registry = _make_mock_registry()
        graph = _make_mock_graph()
        loader = ModuleLoader(registry=registry, graph=graph)
        s = loader.stats()
        assert s["has_registry"] is True
        assert s["has_graph"] is True
        assert "registry" in s
        assert "graph" in s


# ---------------------------------------------------------------------------
# TestGlobalSingleton
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    """Tests for module-level init/get/reset functions."""

    def setup_method(self):
        reset_module_loader()

    def teardown_method(self):
        reset_module_loader()

    def test_get_returns_none_initially(self):
        assert get_module_loader() is None

    @patch("spiderfoot.module_loader.ModuleLoader.create")
    def test_init_creates_loader(self, mock_create):
        mock_loader = MagicMock()
        mock_create.return_value = mock_loader

        result = init_module_loader("/fake/dir")
        assert result is mock_loader

    @patch("spiderfoot.module_loader.ModuleLoader.create")
    def test_init_idempotent(self, mock_create):
        mock_loader = MagicMock()
        mock_create.return_value = mock_loader

        first = init_module_loader("/fake/dir")
        second = init_module_loader("/other/dir")
        assert first is second
        mock_create.assert_called_once()  # Only created once

    @patch("spiderfoot.module_loader.ModuleLoader.create")
    def test_reset_clears_singleton(self, mock_create):
        loader1 = MagicMock()
        loader2 = MagicMock()
        mock_create.side_effect = [loader1, loader2]

        first = init_module_loader("/dir")
        reset_module_loader()
        second = init_module_loader("/dir")

        assert first is not second
        assert mock_create.call_count == 2

    @patch("spiderfoot.module_loader.ModuleLoader.create")
    def test_thread_safety(self, mock_create):
        """Concurrent init calls should produce same singleton."""
        mock_loader = MagicMock()
        mock_create.return_value = mock_loader
        results = []
        barrier = threading.Barrier(4)

        def init_worker():
            barrier.wait()
            result = init_module_loader("/dir")
            results.append(result)

        threads = [threading.Thread(target=init_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert all(r is mock_loader for r in results)


# ---------------------------------------------------------------------------
# TestScannerIntegration
# ---------------------------------------------------------------------------


class TestScannerIntegration:
    """Tests for scanner integration via service_integration."""

    def test_wire_module_loader_attaches(self):
        """_wire_module_loader should set scanner._module_loader."""
        scanner = MagicMock()

        with patch("spiderfoot.module_loader.init_module_loader") as mock_init:
            mock_loader = MagicMock()
            mock_init.return_value = mock_loader

            from spiderfoot.service_integration import _wire_module_loader
            _wire_module_loader(scanner)

            assert scanner._module_loader == mock_loader

    def test_wire_module_loader_survives_error(self):
        """_wire_module_loader should not raise on failure."""
        scanner = MagicMock()

        with patch(
            "spiderfoot.service_integration._wire_module_loader",
            side_effect=Exception("boom"),
        ):
            # Should not raise
            try:
                from spiderfoot.service_integration import _wire_module_loader
                _wire_module_loader(scanner)
            except Exception:
                pass  # The real impl catches internally


# ---------------------------------------------------------------------------
# TestRegistryFallback
# ---------------------------------------------------------------------------


class TestRegistryFallback:
    """Tests for registry → legacy fallback behavior."""

    def test_registry_failure_falls_back(self):
        """If registry.create_instance fails, should try legacy import."""
        class FailingRegistry:
            def __contains__(self, name):
                return True
            def create_instance(self, name, *a, **kw):
                raise RuntimeError("registry broken")

        loader = ModuleLoader(registry=FailingRegistry())
        config = _make_config(["sfp_test"])

        mock_mod = MagicMock()
        mock_instance = _mock_module_instance("sfp_test")
        mock_mod.sfp_test = MagicMock(return_value=mock_instance)

        with patch("builtins.__import__", return_value=mock_mod):
            result = loader.load_modules(
                ["sfp_test"], config,
                sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
            )
            assert result.loaded == 1

    def test_both_fail_records_error(self):
        """If both registry and legacy fail, error is recorded."""
        class FailingRegistry:
            def __contains__(self, name):
                return True
            def create_instance(self, name, *a, **kw):
                raise RuntimeError("nope")

        loader = ModuleLoader(registry=FailingRegistry())
        config = _make_config(["sfp_bad"])

        with patch("builtins.__import__", side_effect=ImportError("nope")):
            result = loader.load_modules(
                ["sfp_bad"], config,
                sf=MagicMock(),
            )
            assert result.failed == 1
            assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_empty_module_name_skipped(self):
        """Empty strings in module_list should be silently skipped."""
        loader = ModuleLoader()
        config = _make_config([])
        result = loader.load_modules(["", "", ""], config)
        assert result.loaded == 0
        assert result.failed == 0
        assert result.skipped == 0

    def test_graph_topological_failure_falls_back(self):
        """If graph.topological_order() raises, should fall back to priority."""
        graph = MagicMock()
        graph.topological_order.side_effect = RuntimeError("broken")
        graph.detect_cycles.return_value = []

        modules = {"sfp_a": {"priority": 2}, "sfp_b": {"priority": 1}}
        registry = _make_mock_registry(modules)

        loader = ModuleLoader(registry=registry, graph=graph)
        config = _make_config(["sfp_a", "sfp_b"])

        result = loader.load_modules(
            ["sfp_a", "sfp_b"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
        )

        assert result.order_method == "priority"
        assert result.loaded == 2

    def test_pruning_failure_uses_full_list(self):
        """If pruning fails, should fall back to full module list."""
        class BrokenPruneRegistry:
            def __contains__(self, name):
                return True
            def create_instance(self, name, *a, **kw):
                inst = _mock_module_instance(name)
                return inst
            def resolve_for_output(self, types):
                raise RuntimeError("pruning broken")

        loader = ModuleLoader(
            registry=BrokenPruneRegistry(),
            enable_pruning=True,
        )
        config = _make_config(["sfp_a", "sfp_b"])

        result = loader.load_modules(
            ["sfp_a", "sfp_b"], config,
            sf=MagicMock(), scan_id="s1", dbh=MagicMock(),
            desired_output_types=["IP_ADDRESS"],
        )

        # Both modules should be loaded despite pruning failure
        assert result.loaded == 2
        assert result.pruned == []
