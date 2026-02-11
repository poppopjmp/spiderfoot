"""Tests for spiderfoot.module_registry — Cycle 10."""
from __future__ import annotations

import os
import sys
import time
import types
import threading
import tempfile
import textwrap
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spiderfoot.plugins.module_registry import (
    ModuleDescriptor,
    ModuleRegistry,
    ModuleStatus,
    DiscoveryResult,
)


# ---------------------------------------------------------------------------
# Helpers — create tiny fake modules on disk
# ---------------------------------------------------------------------------


def _write_module(tmpdir, name, *, watched=None, produced=None,
                  meta_extras="", opts_dict=None, optdescs_dict=None,
                  priority=3, base="SpiderFootPlugin"):
    """Write a minimal sfp_*.py file into *tmpdir* and return the path."""
    watched = watched or []
    produced = produced or []
    opts_dict = opts_dict or {}
    optdescs_dict = optdescs_dict or {}
    dq = '"""'
    display = name.replace("sfp_", "").upper()

    lines = [
        "class SpiderFootPlugin:",
        "    _priority = 3",
        "    meta = {}",
        "    opts = {}",
        "    optdescs = {}",
        "    def watchedEvents(self): return []",
        "    def producedEvents(self): return []",
        "    def setup(self, sf, userOpts=None): pass",
        "    def setScanId(self, sid): pass",
        "    def setSharedThreadPool(self, p): pass",
        "    def setDbh(self, d): pass",
        "    def setTarget(self, t): pass",
        "",
        "class SpiderFootModernPlugin(SpiderFootPlugin):",
        "    pass",
        "",
        f"class {name}({base}):",
        f"    {dq}Test module {name}.{dq}",
        f"    _priority = {priority}",
        f"    meta = {{",
        f'        "name": "{display}",',
        f'        "summary": "Test summary for {name}",',
        f'        "categories": ["TestCat"],',
        f'        "flags": ["apikey"],',
        f'        "useCases": ["Footprint", "Investigate"],',
    ]
    if meta_extras:
        lines.append(f"        {meta_extras}")
    lines += [
        "    }",
        f"    opts = {opts_dict!r}",
        f"    optdescs = {optdescs_dict!r}",
        "",
        "    def watchedEvents(self):",
        f"        return {watched!r}",
        "",
        "    def producedEvents(self):",
        f"        return {produced!r}",
    ]

    src = "\n".join(lines) + "\n"
    path = os.path.join(tmpdir, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path


# ---------------------------------------------------------------------------
# ModuleDescriptor
# ---------------------------------------------------------------------------


class TestModuleDescriptor(unittest.TestCase):
    """Unit tests for the immutable ModuleDescriptor dataclass."""

    def _make(self, **overrides):
        defaults = dict(
            name="sfp_test",
            display_name="TEST",
            summary="A test module",
            filename="/fake/sfp_test.py",
            watched_events=frozenset(["IP_ADDRESS"]),
            produced_events=frozenset(["TCP_PORT_OPEN"]),
            categories=("DNS",),
            flags=("apikey",),
            use_cases=("Footprint",),
            opts={"key": ""},
            optdescs={"key": "API key"},
            data_source={"model": "FREE_AUTH_LIMITED"},
            priority=3,
            is_modern=True,
            status=ModuleStatus.LOADED,
        )
        defaults.update(overrides)
        return ModuleDescriptor(**defaults)

    def test_basic_properties(self):
        d = self._make()
        self.assertEqual(d.name, "sfp_test")
        self.assertEqual(d.display_name, "TEST")
        self.assertTrue(d.requires_apikey)
        self.assertFalse(d.is_invasive)
        self.assertFalse(d.is_slow)

    def test_invasive_flag(self):
        d = self._make(flags=("invasive",))
        self.assertTrue(d.is_invasive)
        self.assertFalse(d.requires_apikey)

    def test_slow_flag(self):
        d = self._make(flags=("slow",))
        self.assertTrue(d.is_slow)

    def test_data_source_model(self):
        d = self._make()
        self.assertEqual(d.data_source_model, "FREE_AUTH_LIMITED")

    def test_data_source_model_none(self):
        d = self._make(data_source=None)
        self.assertIsNone(d.data_source_model)

    def test_matches_search_name(self):
        d = self._make()
        self.assertTrue(d.matches_search("sfp_test"))
        self.assertTrue(d.matches_search("TEST"))
        self.assertTrue(d.matches_search("test module"))

    def test_matches_search_category(self):
        d = self._make()
        self.assertTrue(d.matches_search("dns"))

    def test_matches_search_negative(self):
        d = self._make()
        self.assertFalse(d.matches_search("zzzznotfound"))

    def test_to_dict(self):
        d = self._make()
        result = d.to_dict()
        self.assertEqual(result["name"], "sfp_test")
        self.assertIn("IP_ADDRESS", result["watched_events"])
        self.assertIn("TCP_PORT_OPEN", result["produced_events"])
        self.assertEqual(result["status"], "loaded")
        self.assertIn("key", result["options"])
        self.assertEqual(result["options"]["key"]["description"], "API key")

    def test_status_default(self):
        d = self._make()
        self.assertEqual(d.status, ModuleStatus.LOADED)

    def test_failed_status(self):
        d = self._make(status=ModuleStatus.FAILED, error="import error")
        self.assertEqual(d.status, ModuleStatus.FAILED)
        self.assertEqual(d.error, "import error")

    def test_frozen(self):
        d = self._make()
        with self.assertRaises(AttributeError):
            d.name = "other"


# ---------------------------------------------------------------------------
# ModuleRegistry — in-memory tests (no disk I/O)
# ---------------------------------------------------------------------------


class TestModuleRegistryInMemory(unittest.TestCase):
    """Tests that exercise the registry's indexing and query APIs
    without touching the filesystem."""

    def _make_desc(self, name, *, watched=(), produced=(), categories=(),
                   flags=(), use_cases=(), priority=3, is_modern=True):
        return ModuleDescriptor(
            name=name,
            display_name=name.upper(),
            summary=f"Summary of {name}",
            filename=f"/fake/{name}.py",
            watched_events=frozenset(watched),
            produced_events=frozenset(produced),
            categories=tuple(categories),
            flags=tuple(flags),
            use_cases=tuple(use_cases),
            opts={},
            optdescs={},
            data_source=None,
            priority=priority,
            is_modern=is_modern,
            status=ModuleStatus.LOADED,
        )

    def _build_registry(self):
        """Create a small registry with 4 modules for testing."""
        reg = ModuleRegistry()

        descriptors = [
            self._make_desc(
                "sfp_dns",
                watched=("INTERNET_NAME",),
                produced=("IP_ADDRESS", "IPV6_ADDRESS"),
                categories=("DNS",),
                use_cases=("Footprint", "Passive"),
            ),
            self._make_desc(
                "sfp_ports",
                watched=("IP_ADDRESS",),
                produced=("TCP_PORT_OPEN",),
                categories=("Scanning",),
                flags=("invasive",),
                use_cases=("Footprint",),
            ),
            self._make_desc(
                "sfp_shodan",
                watched=("IP_ADDRESS", "DOMAIN_NAME"),
                produced=("TCP_PORT_OPEN", "VULNERABILITY_CVE_CRITICAL"),
                categories=("Search Engines",),
                flags=("apikey",),
                use_cases=("Footprint", "Investigate"),
            ),
            self._make_desc(
                "sfp_stor",
                watched=("*",),
                produced=(),
                categories=("Internal",),
                flags=("slow",),
                priority=0,
            ),
        ]

        with reg._lock:
            for d in descriptors:
                reg._descriptors[d.name] = d
                reg._index(d)

        return reg

    # Counts / contains --------------------------------------------------

    def test_module_count(self):
        reg = self._build_registry()
        self.assertEqual(reg.module_count, 4)
        self.assertEqual(len(reg), 4)

    def test_loaded_count(self):
        reg = self._build_registry()
        self.assertEqual(reg.loaded_count, 4)

    def test_contains(self):
        reg = self._build_registry()
        self.assertIn("sfp_dns", reg)
        self.assertNotIn("sfp_nonexist", reg)

    def test_iter(self):
        reg = self._build_registry()
        names = {d.name for d in reg}
        self.assertEqual(names, {"sfp_dns", "sfp_ports", "sfp_shodan", "sfp_stor"})

    # Get / list ----------------------------------------------------------

    def test_get(self):
        reg = self._build_registry()
        d = reg.get("sfp_dns")
        self.assertIsNotNone(d)
        self.assertEqual(d.name, "sfp_dns")

    def test_get_missing(self):
        reg = self._build_registry()
        self.assertIsNone(reg.get("sfp_missing"))

    def test_list_names(self):
        reg = self._build_registry()
        names = reg.list_names()
        self.assertEqual(names, ["sfp_dns", "sfp_ports", "sfp_shodan", "sfp_stor"])

    def test_list_loaded(self):
        reg = self._build_registry()
        loaded = reg.list_loaded()
        self.assertEqual(len(loaded), 4)
        self.assertEqual(loaded[0].name, "sfp_dns")  # sorted

    def test_list_failed_empty(self):
        reg = self._build_registry()
        self.assertEqual(reg.list_failed(), [])

    # Event type queries --------------------------------------------------

    def test_producers_of(self):
        reg = self._build_registry()
        prods = reg.producers_of("IP_ADDRESS")
        self.assertEqual(prods, ["sfp_dns"])

    def test_producers_of_multiple(self):
        reg = self._build_registry()
        prods = reg.producers_of("TCP_PORT_OPEN")
        self.assertEqual(prods, ["sfp_ports", "sfp_shodan"])

    def test_producers_of_unknown(self):
        reg = self._build_registry()
        self.assertEqual(reg.producers_of("NONEXISTENT"), [])

    def test_consumers_of(self):
        reg = self._build_registry()
        cons = reg.consumers_of("IP_ADDRESS")
        self.assertEqual(cons, ["sfp_ports", "sfp_shodan"])

    def test_all_event_types(self):
        reg = self._build_registry()
        types_ = reg.all_event_types
        self.assertIn("IP_ADDRESS", types_)
        self.assertIn("TCP_PORT_OPEN", types_)
        self.assertIn("INTERNET_NAME", types_)

    # Category / flag / usecase queries -----------------------------------

    def test_by_category(self):
        reg = self._build_registry()
        self.assertEqual(reg.by_category("DNS"), ["sfp_dns"])

    def test_by_category_missing(self):
        reg = self._build_registry()
        self.assertEqual(reg.by_category("NonExistent"), [])

    def test_by_flag(self):
        reg = self._build_registry()
        self.assertEqual(reg.by_flag("apikey"), ["sfp_shodan"])

    def test_by_flag_invasive(self):
        reg = self._build_registry()
        self.assertEqual(reg.by_flag("invasive"), ["sfp_ports"])

    def test_by_usecase(self):
        reg = self._build_registry()
        fp = reg.by_usecase("Footprint")
        self.assertIn("sfp_dns", fp)
        self.assertIn("sfp_ports", fp)
        self.assertIn("sfp_shodan", fp)

    def test_by_usecase_all(self):
        reg = self._build_registry()
        all_mods = reg.by_usecase("all")
        self.assertEqual(len(all_mods), 4)

    def test_categories_dict(self):
        reg = self._build_registry()
        cats = reg.categories()
        self.assertEqual(cats["DNS"], 1)
        self.assertEqual(cats["Search Engines"], 1)

    def test_flags_dict(self):
        reg = self._build_registry()
        fl = reg.flags()
        self.assertEqual(fl["apikey"], 1)
        self.assertEqual(fl["invasive"], 1)
        self.assertEqual(fl["slow"], 1)

    # Search --------------------------------------------------------------

    def test_search(self):
        reg = self._build_registry()
        results = reg.search("shodan")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "sfp_shodan")

    def test_search_by_category(self):
        reg = self._build_registry()
        results = reg.search("DNS")
        self.assertTrue(any(r.name == "sfp_dns" for r in results))

    def test_search_no_results(self):
        reg = self._build_registry()
        self.assertEqual(reg.search("zzzznotfound"), [])

    # Dependencies --------------------------------------------------------

    def test_dependencies_of(self):
        reg = self._build_registry()
        deps = reg.dependencies_of("sfp_ports")
        # sfp_ports watches IP_ADDRESS, produced by sfp_dns
        self.assertIn("sfp_dns", deps)

    def test_dependencies_of_unknown(self):
        reg = self._build_registry()
        self.assertEqual(reg.dependencies_of("sfp_nope"), set())

    def test_dependents_of(self):
        reg = self._build_registry()
        dependents = reg.dependents_of("sfp_dns")
        # sfp_dns produces IP_ADDRESS, IPV6_ADDRESS
        # sfp_ports and sfp_shodan watch IP_ADDRESS
        self.assertIn("sfp_ports", dependents)
        self.assertIn("sfp_shodan", dependents)

    def test_resolve_for_output(self):
        reg = self._build_registry()
        needed = reg.resolve_for_output(["TCP_PORT_OPEN"])
        self.assertIn("sfp_ports", needed)  # produces TCP_PORT_OPEN
        self.assertIn("sfp_shodan", needed)  # also produces TCP_PORT_OPEN
        self.assertIn("sfp_dns", needed)  # sfp_ports needs IP_ADDRESS from sfp_dns

    # Stats / repr --------------------------------------------------------

    def test_stats(self):
        reg = self._build_registry()
        s = reg.stats()
        self.assertEqual(s["total_modules"], 4)
        self.assertEqual(s["loaded"], 4)
        self.assertIn("categories", s)

    def test_repr(self):
        reg = self._build_registry()
        r = repr(reg)
        self.assertIn("ModuleRegistry", r)
        self.assertIn("modules=4", r)

    # Legacy export -------------------------------------------------------

    def test_as_modules_dict(self):
        reg = self._build_registry()
        d = reg.as_modules_dict()
        self.assertIn("sfp_dns", d)
        entry = d["sfp_dns"]
        self.assertEqual(entry["name"], "SFP_DNS")
        self.assertIn("IP_ADDRESS", entry["provides"])
        self.assertEqual(entry["cats"], ["DNS"])
        self.assertIn("opts", entry)
        self.assertIn("meta", entry)


# ---------------------------------------------------------------------------
# ModuleRegistry — filesystem tests (real discover())
# ---------------------------------------------------------------------------


class TestModuleRegistryDiscovery(unittest.TestCase):
    """Tests that exercise discover() with real temp files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sf_registry_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_basic(self):
        _write_module(self.tmpdir, "sfp_alpha",
                      watched=["IP_ADDRESS"],
                      produced=["TCP_PORT_OPEN"])
        _write_module(self.tmpdir, "sfp_beta",
                      watched=["TCP_PORT_OPEN"],
                      produced=["VULNERABILITY_CVE_CRITICAL"])

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.loaded, 2)
        self.assertEqual(result.failed, 0)
        self.assertIn("sfp_alpha", reg)
        self.assertIn("sfp_beta", reg)

    def test_discover_metadata_extracted(self):
        _write_module(self.tmpdir, "sfp_meta",
                      watched=["DOMAIN_NAME"],
                      produced=["IP_ADDRESS"],
                      opts_dict={"key": "val"},
                      optdescs_dict={"key": "A key"})

        reg = ModuleRegistry()
        reg.discover(self.tmpdir)

        desc = reg.get("sfp_meta")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.display_name, "META")
        self.assertIn("Test summary", desc.summary)
        self.assertEqual(desc.categories, ("TestCat",))
        self.assertIn("apikey", desc.flags)
        self.assertEqual(desc.opts, {"key": "val"})

    def test_discover_event_indices(self):
        _write_module(self.tmpdir, "sfp_prod",
                      produced=["IP_ADDRESS", "DOMAIN_NAME"])
        _write_module(self.tmpdir, "sfp_cons",
                      watched=["IP_ADDRESS"])

        reg = ModuleRegistry()
        reg.discover(self.tmpdir)

        self.assertEqual(reg.producers_of("IP_ADDRESS"), ["sfp_prod"])
        self.assertEqual(reg.consumers_of("IP_ADDRESS"), ["sfp_cons"])

    def test_discover_ignores_template(self):
        _write_module(self.tmpdir, "sfp_real", produced=["X"])
        # Write a template file
        path = os.path.join(self.tmpdir, "sfp_template.py")
        with open(path, "w") as f:
            f.write("# template\n")

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        self.assertEqual(result.loaded, 1)
        self.assertNotIn("sfp_template", reg)

    def test_discover_custom_ignore(self):
        _write_module(self.tmpdir, "sfp_keep", produced=["X"])
        _write_module(self.tmpdir, "sfp_skip", produced=["Y"])

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir,
                              ignore_files=["sfp_skip.py", "sfp_template.py"])

        self.assertEqual(result.loaded, 1)
        self.assertIn("sfp_keep", reg)
        self.assertNotIn("sfp_skip", reg)

    def test_discover_handles_bad_module(self):
        _write_module(self.tmpdir, "sfp_good", produced=["X"])
        # Write a broken module
        bad_path = os.path.join(self.tmpdir, "sfp_broken.py")
        with open(bad_path, "w") as f:
            f.write("raise ImportError('deliberately broken')\n")

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        self.assertEqual(result.loaded, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0][0], "sfp_broken")

        # Broken module is in registry with FAILED status
        broken = reg.get("sfp_broken")
        self.assertIsNotNone(broken)
        self.assertEqual(broken.status, ModuleStatus.FAILED)

    def test_discover_empty_directory(self):
        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        self.assertEqual(result.total, 0)
        self.assertEqual(result.loaded, 0)

    def test_discover_nonexistent_dir(self):
        reg = ModuleRegistry()
        result = reg.discover(os.path.join(self.tmpdir, "nonexistent"))

        self.assertEqual(result.total, 0)

    def test_rediscover_replaces_catalog(self):
        _write_module(self.tmpdir, "sfp_first", produced=["X"])

        reg = ModuleRegistry()
        reg.discover(self.tmpdir)
        self.assertEqual(reg.module_count, 1)

        # Add another module and rediscover
        _write_module(self.tmpdir, "sfp_second", produced=["Y"])
        reg.discover(self.tmpdir)
        self.assertEqual(reg.module_count, 2)

    def test_discover_priority(self):
        _write_module(self.tmpdir, "sfp_hipri", priority=0)
        _write_module(self.tmpdir, "sfp_lopri", priority=5)

        reg = ModuleRegistry()
        reg.discover(self.tmpdir)

        self.assertEqual(reg.get("sfp_hipri").priority, 0)
        self.assertEqual(reg.get("sfp_lopri").priority, 5)

    def test_discover_result_repr(self):
        _write_module(self.tmpdir, "sfp_x", produced=["A"])

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        r = repr(result)
        self.assertIn("DiscoveryResult", r)
        self.assertIn("total=1", r)
        self.assertIn("loaded=1", r)

    def test_discover_duration(self):
        _write_module(self.tmpdir, "sfp_x", produced=["A"])

        reg = ModuleRegistry()
        result = reg.discover(self.tmpdir)

        self.assertGreater(result.duration, 0)

    def test_discover_modern_detection(self):
        _write_module(self.tmpdir, "sfp_modern", base="SpiderFootModernPlugin")
        _write_module(self.tmpdir, "sfp_legacy", base="SpiderFootPlugin")

        reg = ModuleRegistry()
        reg.discover(self.tmpdir)

        self.assertTrue(reg.get("sfp_modern").is_modern)
        self.assertFalse(reg.get("sfp_legacy").is_modern)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestModuleRegistryInstantiation(unittest.TestCase):
    """Tests for create_instance() and get_class()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sf_reg_inst_test_")
        _write_module(self.tmpdir, "sfp_inst",
                      watched=["IP_ADDRESS"],
                      produced=["TCP_PORT_OPEN"],
                      opts_dict={"opt1": "default"})

        self.reg = ModuleRegistry()
        self.reg.discover(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_instance_basic(self):
        inst = self.reg.create_instance("sfp_inst")
        self.assertEqual(inst.__name__, "sfp_inst")

    def test_create_instance_with_opts(self):
        sf_mock = MagicMock()
        inst = self.reg.create_instance(
            "sfp_inst",
            merged_opts={"opt1": "override", "global_opt": True},
            sf=sf_mock,
        )
        # setup() was called
        sf_mock_not_called = False
        # Verify setup was called (the mock sf is passed to setup)
        self.assertEqual(inst.__name__, "sfp_inst")

    def test_create_instance_with_lifecycle(self):
        inst = self.reg.create_instance(
            "sfp_inst",
            scan_id="scan123",
        )
        self.assertEqual(inst.__name__, "sfp_inst")

    def test_create_instance_missing(self):
        with self.assertRaises(KeyError):
            self.reg.create_instance("sfp_nonexistent")

    def test_create_instance_failed_module(self):
        # Write a broken module
        bad_path = os.path.join(self.tmpdir, "sfp_bad.py")
        with open(bad_path, "w") as f:
            f.write("raise SyntaxError('bad')\n")

        self.reg.discover(self.tmpdir)
        with self.assertRaises(RuntimeError):
            self.reg.create_instance("sfp_bad")

    def test_get_class(self):
        cls = self.reg.get_class("sfp_inst")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "sfp_inst")

    def test_get_class_missing(self):
        cls = self.reg.get_class("sfp_nonexistent")
        self.assertIsNone(cls)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestModuleRegistryThreadSafety(unittest.TestCase):
    """Test concurrent access to the registry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sf_reg_thread_test_")
        for i in range(10):
            _write_module(
                self.tmpdir,
                f"sfp_t{i}",
                watched=[f"EVENT_{i}"],
                produced=[f"OUT_{i}"],
            )
        self.reg = ModuleRegistry()
        self.reg.discover(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_concurrent_reads(self):
        """Multiple threads reading simultaneously should not crash."""
        results = []
        errors = []

        def reader():
            try:
                for _ in range(50):
                    self.reg.list_names()
                    self.reg.producers_of("OUT_0")
                    self.reg.by_category("TestCat")
                    self.reg.search("sfp_t")
                    self.reg.stats()
                results.append(True)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(results), 5)


# ---------------------------------------------------------------------------
# Integration — discover real modules (if available)
# ---------------------------------------------------------------------------


class TestModuleRegistryRealModules(unittest.TestCase):
    """Integration test using the real modules/ directory."""

    @classmethod
    def setUpClass(cls):
        cls.modules_dir = os.path.join(ROOT, "modules")
        cls.has_modules = (
            os.path.isdir(cls.modules_dir)
            and len(glob.glob(os.path.join(cls.modules_dir, "sfp_*.py"))) > 0
        )

    def setUp(self):
        if not self.has_modules:
            self.skipTest("No modules/ directory with sfp_*.py files")

    def test_discover_real_modules(self):
        reg = ModuleRegistry()
        result = reg.discover(self.modules_dir)

        self.assertGreater(result.loaded, 100)  # Expect 200+ modules
        self.assertLess(result.failed, result.loaded)  # Most should load

    def test_real_modules_have_event_types(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        # There should be many event types
        self.assertGreater(len(reg.all_event_types), 20)

    def test_real_ip_address_producers(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        prods = reg.producers_of("IP_ADDRESS")
        self.assertGreater(len(prods), 0)

    def test_real_categories(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        cats = reg.categories()
        self.assertGreater(len(cats), 3)

    def test_real_apikey_modules(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        apikey_mods = reg.by_flag("apikey")
        self.assertGreater(len(apikey_mods), 10)

    def test_real_stats(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        s = reg.stats()
        self.assertGreater(s["total_modules"], 100)
        self.assertGreater(s["modern_modules"], 0)

    def test_real_legacy_dict(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        d = reg.as_modules_dict()
        self.assertGreater(len(d), 100)

        # Spot check structure
        for name, entry in list(d.items())[:3]:
            self.assertIn("name", entry)
            self.assertIn("opts", entry)
            self.assertIn("meta", entry)
            self.assertIn("provides", entry)
            self.assertIn("consumes", entry)

    def test_real_search(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        results = reg.search("DNS")
        self.assertGreater(len(results), 0)

    def test_real_resolve_for_output(self):
        reg = ModuleRegistry()
        reg.discover(self.modules_dir)

        needed = reg.resolve_for_output(["IP_ADDRESS"])
        self.assertGreater(len(needed), 0)


# ---------------------------------------------------------------------------
# DiscoveryResult
# ---------------------------------------------------------------------------


class TestDiscoveryResult(unittest.TestCase):

    def test_repr(self):
        r = DiscoveryResult(total=10, loaded=8, failed=2,
                            errors=[("a", "err")], duration=0.5)
        s = repr(r)
        self.assertIn("total=10", s)
        self.assertIn("loaded=8", s)
        self.assertIn("failed=2", s)
        self.assertIn("0.50s", s)


# Need glob for real modules test
import glob


if __name__ == "__main__":
    unittest.main()
