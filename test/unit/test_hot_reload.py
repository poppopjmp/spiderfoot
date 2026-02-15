#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.hot_reload."""
from __future__ import annotations

import os
import tempfile
import time
import unittest

from spiderfoot.hot_reload import ModuleWatcher, ModuleState, ReloadEvent


class TestModuleState(unittest.TestCase):
    """Test ModuleState dataclass."""

    def test_defaults(self):
        s = ModuleState(filepath="sfp_test.py", module_name="sfp_test")
        self.assertEqual(s.reload_count, 0)
        self.assertIsNone(s.last_error)
        self.assertIsNone(s.module_obj)


class TestReloadEvent(unittest.TestCase):
    """Test ReloadEvent dataclass."""

    def test_success_event(self):
        e = ReloadEvent(
            module_name="sfp_test",
            filepath="sfp_test.py",
            timestamp=time.time(),
            success=True,
            duration_ms=5.0)
        self.assertTrue(e.success)
        self.assertIsNone(e.error)

    def test_failure_event(self):
        e = ReloadEvent(
            module_name="sfp_test",
            filepath="sfp_test.py",
            timestamp=time.time(),
            success=False,
            error="Syntax error")
        self.assertFalse(e.success)
        self.assertEqual(e.error, "Syntax error")


class TestModuleWatcher(unittest.TestCase):
    """Test ModuleWatcher."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_module(self, name, content=None):
        """Write a test module file."""
        if content is None:
            content = (
                f"class {name}:\n"
                f"    meta = {{'name': '{name}'}}\n"
                f"    def watchedEvents(self): return []\n"
                f"    def producedEvents(self): return []\n"
            )
        filepath = os.path.join(self.tmpdir, f"{name}.py")
        with open(filepath, "w") as f:
            f.write(content)
        return filepath

    def test_scan_files(self):
        self._write_module("sfp_test1")
        self._write_module("sfp_test2")

        watcher = ModuleWatcher(self.tmpdir)
        self.assertEqual(len(watcher.tracked_modules()), 2)
        self.assertIn("sfp_test1", watcher.tracked_modules())
        self.assertIn("sfp_test2", watcher.tracked_modules())

    def test_nonexistent_dir(self):
        watcher = ModuleWatcher("/nonexistent/dir")
        self.assertEqual(len(watcher.tracked_modules()), 0)

    def test_reload_module(self):
        self._write_module("sfp_test_reload")
        watcher = ModuleWatcher(self.tmpdir)

        success = watcher.reload_module("sfp_test_reload")
        self.assertTrue(success)

        state = watcher.get_state("sfp_test_reload")
        self.assertEqual(state.reload_count, 1)
        self.assertIsNone(state.last_error)

    def test_reload_unknown(self):
        watcher = ModuleWatcher(self.tmpdir)
        self.assertFalse(watcher.reload_module("nonexistent"))

    def test_reload_syntax_error(self):
        self._write_module("sfp_bad", "def broken(\n")
        watcher = ModuleWatcher(self.tmpdir)

        success = watcher.reload_module("sfp_bad")
        self.assertFalse(success)

        state = watcher.get_state("sfp_bad")
        self.assertIsNotNone(state.last_error)
        self.assertIn("Syntax error", state.last_error)

    def test_reload_all(self):
        self._write_module("sfp_a")
        self._write_module("sfp_b")
        watcher = ModuleWatcher(self.tmpdir)

        results = watcher.reload_all()
        self.assertTrue(results["sfp_a"])
        self.assertTrue(results["sfp_b"])

    def test_callback_on_reload(self):
        self._write_module("sfp_cb_test")
        watcher = ModuleWatcher(self.tmpdir)

        reloaded = []
        watcher.on_reload(lambda name, mod: reloaded.append(name))

        watcher.reload_module("sfp_cb_test")
        self.assertIn("sfp_cb_test", reloaded)

    def test_error_callback(self):
        self._write_module("sfp_err", "invalid python {{{")
        watcher = ModuleWatcher(self.tmpdir)

        errors = []
        watcher.on_error(lambda name, err: errors.append((name, err)))

        watcher.reload_module("sfp_err")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], "sfp_err")

    def test_history(self):
        self._write_module("sfp_hist")
        watcher = ModuleWatcher(self.tmpdir)

        watcher.reload_module("sfp_hist")
        watcher.reload_module("sfp_hist")

        history = watcher.get_history()
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0].success)

    def test_trim_history(self):
        self._write_module("sfp_trim")
        watcher = ModuleWatcher(self.tmpdir)

        for _ in range(10):
            watcher.reload_module("sfp_trim")

        self.assertEqual(len(watcher.get_history(limit=100)), 10)
        removed = watcher.trim_history(keep=3)
        self.assertEqual(removed, 7)
        self.assertEqual(len(watcher.get_history(limit=100)), 3)

    def test_stats(self):
        self._write_module("sfp_stats")
        watcher = ModuleWatcher(self.tmpdir)

        stats = watcher.stats
        self.assertEqual(stats["modules_tracked"], 1)
        self.assertEqual(stats["total_reloads"], 0)
        self.assertFalse(stats["is_running"])

    def test_detect_change(self):
        filepath = self._write_module("sfp_change")
        watcher = ModuleWatcher(self.tmpdir)

        # Simulate file change
        time.sleep(0.1)
        with open(filepath, "a") as f:
            f.write("\n# changed\n")

        reloaded = watcher.check_now()
        self.assertIn("sfp_change", reloaded)

    def test_start_stop(self):
        self._write_module("sfp_watch")
        watcher = ModuleWatcher(self.tmpdir, poll_interval=0.1)

        watcher.start()
        self.assertTrue(watcher.is_running)

        watcher.stop()
        self.assertFalse(watcher.is_running)

    def test_start_idempotent(self):
        watcher = ModuleWatcher(self.tmpdir, poll_interval=0.1)
        watcher.start()
        watcher.start()  # Should not raise
        watcher.stop()

    def test_new_file_detected(self):
        watcher = ModuleWatcher(self.tmpdir)
        self.assertEqual(len(watcher.tracked_modules()), 0)

        self._write_module("sfp_new")
        watcher.check_now()
        self.assertIn("sfp_new", watcher.tracked_modules())


if __name__ == "__main__":
    unittest.main()
