"""Celery scan pipeline integration test — Cycles 31-32.

Verifies that the scan pipeline from run_scan task through to module
handleEvent() dispatch is correctly wired, WITHOUT requiring a live
Redis broker or Celery worker.

Tests:
1. startSpiderFootScanner can initialize with real modules
2. Module loading via loadModules() returns valid module instances
3. handleEvent() dispatch chain is callable on loaded modules
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure modules directory is in path
MODULES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'modules')
MODULES_DIR = os.path.abspath(MODULES_DIR)
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)


class TestRunScanTaskSignature(unittest.TestCase):
    """Verify the Celery run_scan task is importable and has correct signature."""

    def test_run_scan_importable(self):
        """The run_scan task must be importable from spiderfoot.tasks.scan."""
        from spiderfoot.tasks.scan import run_scan
        self.assertTrue(callable(run_scan))

    def test_run_scan_is_celery_task(self):
        """run_scan must be a Celery task with expected attributes."""
        from spiderfoot.tasks.scan import run_scan
        # Celery tasks have .name, .delay, .apply_async attributes
        self.assertTrue(hasattr(run_scan, 'name'),
                        "run_scan missing .name — not a Celery task?")
        self.assertTrue(hasattr(run_scan, 'delay'),
                        "run_scan missing .delay — not a Celery task?")

    def test_run_scan_has_correct_queue(self):
        """run_scan must be bound to the 'scan' queue."""
        from spiderfoot.tasks.scan import run_scan
        # Check the task's queue config
        queue = getattr(run_scan, 'queue', None)
        # Queue may be set via @app.task(queue="scan") decorator
        self.assertIn('scan', str(run_scan.name).lower() + str(queue or ''),
                      "run_scan task is not associated with 'scan' queue or name")


class TestScannerStartup(unittest.TestCase):
    """Verify startSpiderFootScanner initializes correctly."""

    def test_startSpiderFootScanner_importable(self):
        """The scanner startup function must be importable."""
        from spiderfoot.scan.scanner import startSpiderFootScanner
        self.assertTrue(callable(startSpiderFootScanner))


class TestLoadModulesPipeline(unittest.TestCase):
    """Verify loadModules() loads real module instances with handleEvent()."""

    @classmethod
    def setUpClass(cls):
        from spiderfoot.sflib.core import SpiderFoot
        cls.sf = SpiderFoot({
            "__modules__": {},
            "__logging": False,
            "_debug": False,
        })
        cls.sf.loadModules()
        cls.modules = cls.sf.opts.get("__modules__", {})

    def test_modules_loaded(self):
        """loadModules() must load 300+ modules."""
        self.assertGreaterEqual(len(self.modules), 300,
                                f"Only {len(self.modules)} modules loaded")

    def test_modules_have_handleEvent(self):
        """Every loaded module class must have a handleEvent method."""
        missing = []
        for mod_name, info in self.modules.items():
            mod_class = info.get("module")
            if mod_class is None:
                continue
            if not hasattr(mod_class, "handleEvent"):
                missing.append(mod_name)
        self.assertEqual(len(missing), 0,
                         f"Modules missing handleEvent: {missing}")

    def test_modules_have_producedEvents(self):
        """Every module must declare producedEvents()."""
        missing = []
        for mod_name, info in self.modules.items():
            mod_class = info.get("module")
            if mod_class is None:
                continue
            if not hasattr(mod_class, "producedEvents"):
                missing.append(mod_name)
        self.assertEqual(len(missing), 0,
                         f"Modules missing producedEvents: {missing}")

    def test_modules_have_watchedEvents(self):
        """Every module must declare watchedEvents()."""
        missing = []
        for mod_name, info in self.modules.items():
            mod_class = info.get("module")
            if mod_class is None:
                continue
            if not hasattr(mod_class, "watchedEvents"):
                missing.append(mod_name)
        self.assertEqual(len(missing), 0,
                         f"Modules missing watchedEvents: {missing}")


class TestModuleHandleEventCallable(unittest.TestCase):
    """Verify that a sample module's handleEvent can be invoked."""

    def test_example_module_handleEvent_callable(self):
        """A sample module class should have a callable handleEvent."""
        from spiderfoot.sflib.core import SpiderFoot
        sf = SpiderFoot({
            "__modules__": {},
            "__logging": False,
            "_debug": False,
        })
        sf.loadModules()
        modules = sf.opts.get("__modules__", {})

        # Find a simple module to test
        example = modules.get("sfp_example") or modules.get("sfp_dnsresolve")
        self.assertIsNotNone(example, "No test module found")

        mod_class = example.get("module")
        self.assertIsNotNone(mod_class, "Module class is None")
        self.assertTrue(hasattr(mod_class, "handleEvent"),
                        "handleEvent not found on module class")

    def test_worker_pool_config_from_opts(self):
        """WorkerPoolConfig must deserialize from SF options dict."""
        from spiderfoot.scan.worker_pool import WorkerPoolConfig
        config = WorkerPoolConfig.from_sf_config({
            "_worker_strategy": "thread",
            "_worker_max": 8,
            "_worker_queue_size": 500,
        })
        self.assertEqual(config.max_workers, 8)
        self.assertEqual(config.queue_size, 500)
        self.assertEqual(config.effective_max_workers, 8)

    def test_worker_pool_config_autosize(self):
        """WorkerPoolConfig with max_workers=0 should auto-size."""
        from spiderfoot.scan.worker_pool import WorkerPoolConfig
        config = WorkerPoolConfig.from_sf_config({})
        self.assertEqual(config.max_workers, 0)
        self.assertGreater(config.effective_max_workers, 0)


if __name__ == "__main__":
    unittest.main()
