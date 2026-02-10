"""Tests for spiderfoot.scan_progress module."""
from __future__ import annotations

import threading
import time
import unittest

from spiderfoot.scan_progress import (
    ModuleProgress,
    ModuleStatus,
    ProgressSnapshot,
    ScanProgressTracker,
)


class TestModuleStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ModuleStatus.PENDING.value, "pending")
        self.assertEqual(ModuleStatus.RUNNING.value, "running")
        self.assertEqual(ModuleStatus.COMPLETED.value, "completed")
        self.assertEqual(ModuleStatus.FAILED.value, "failed")
        self.assertEqual(ModuleStatus.SKIPPED.value, "skipped")


class TestModuleProgress(unittest.TestCase):
    def test_defaults(self):
        mp = ModuleProgress(module_name="sfp_dns")
        self.assertEqual(mp.module_name, "sfp_dns")
        self.assertEqual(mp.status, ModuleStatus.PENDING)
        self.assertEqual(mp.events_produced, 0)
        self.assertEqual(mp.elapsed, 0.0)
        self.assertFalse(mp.is_terminal)

    def test_elapsed(self):
        mp = ModuleProgress(module_name="sfp_dns")
        mp.started_at = time.time() - 5.0
        self.assertGreaterEqual(mp.elapsed, 4.9)

    def test_elapsed_completed(self):
        mp = ModuleProgress(module_name="sfp_dns")
        mp.started_at = 100.0
        mp.completed_at = 105.0
        self.assertAlmostEqual(mp.elapsed, 5.0, places=1)

    def test_terminal_states(self):
        for status in (ModuleStatus.COMPLETED, ModuleStatus.FAILED, ModuleStatus.SKIPPED):
            mp = ModuleProgress(module_name="test", status=status)
            self.assertTrue(mp.is_terminal)

    def test_non_terminal_states(self):
        for status in (ModuleStatus.PENDING, ModuleStatus.RUNNING):
            mp = ModuleProgress(module_name="test", status=status)
            self.assertFalse(mp.is_terminal)

    def test_to_dict(self):
        mp = ModuleProgress(module_name="sfp_dns", status=ModuleStatus.RUNNING)
        mp.events_produced = 10
        d = mp.to_dict()
        self.assertEqual(d["module"], "sfp_dns")
        self.assertEqual(d["status"], "running")
        self.assertEqual(d["events_produced"], 10)


class TestProgressSnapshot(unittest.TestCase):
    def test_to_dict(self):
        snap = ProgressSnapshot(
            timestamp=1000.0,
            overall_pct=50.0,
            modules_completed=2,
            modules_total=4,
            events_total=100,
            throughput_eps=10.0,
            eta_seconds=30.5,
        )
        d = snap.to_dict()
        self.assertEqual(d["overall_pct"], 50.0)
        self.assertEqual(d["modules_completed"], 2)
        self.assertEqual(d["eta_seconds"], 30.5)

    def test_null_eta(self):
        snap = ProgressSnapshot(
            timestamp=1000.0,
            overall_pct=0.0,
            modules_completed=0,
            modules_total=4,
            events_total=0,
            throughput_eps=0.0,
            eta_seconds=None,
        )
        d = snap.to_dict()
        self.assertIsNone(d["eta_seconds"])


class TestScanProgressTracker(unittest.TestCase):
    def _make_tracker(self, modules=None):
        t = ScanProgressTracker(scan_id="test-001")
        if modules:
            t.register_modules(modules)
        return t

    def test_initial_state(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        self.assertEqual(t.overall_progress, 0.0)
        self.assertEqual(t.elapsed, 0.0)

    def test_empty_progress(self):
        t = ScanProgressTracker(scan_id="test")
        self.assertEqual(t.overall_progress, 0.0)

    def test_register_modules(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl", "sfp_portscan"])
        self.assertEqual(len(t.get_all_module_progress()), 3)

    def test_module_started(self):
        t = self._make_tracker(["sfp_dns"])
        t.module_started("sfp_dns")
        mp = t.get_module_progress("sfp_dns")
        self.assertEqual(mp.status, ModuleStatus.RUNNING)
        self.assertIsNotNone(mp.started_at)

    def test_module_started_auto_register(self):
        t = ScanProgressTracker(scan_id="test")
        t.module_started("sfp_new")
        mp = t.get_module_progress("sfp_new")
        self.assertIsNotNone(mp)
        self.assertEqual(mp.status, ModuleStatus.RUNNING)

    def test_module_completed(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_started("sfp_dns")
        t.module_completed("sfp_dns")
        self.assertAlmostEqual(t.overall_progress, 50.0)

    def test_all_modules_completed(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_started("sfp_dns")
        t.module_completed("sfp_dns")
        t.module_started("sfp_ssl")
        t.module_completed("sfp_ssl")
        self.assertAlmostEqual(t.overall_progress, 100.0)

    def test_module_failed(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_started("sfp_dns")
        t.module_failed("sfp_dns", "Connection timeout")
        mp = t.get_module_progress("sfp_dns")
        self.assertEqual(mp.status, ModuleStatus.FAILED)
        self.assertEqual(mp.error_message, "Connection timeout")
        # Failed counts as terminal for progress
        self.assertAlmostEqual(t.overall_progress, 50.0)

    def test_module_skipped(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_skipped("sfp_dns")
        self.assertAlmostEqual(t.overall_progress, 50.0)

    def test_record_event(self):
        t = self._make_tracker(["sfp_dns"])
        t.start()
        t.module_started("sfp_dns")
        t.record_event("sfp_dns", produced=True)
        t.record_event("sfp_dns", produced=True)
        t.record_event("sfp_dns", produced=False)

        mp = t.get_module_progress("sfp_dns")
        self.assertEqual(mp.events_produced, 2)
        self.assertEqual(mp.events_consumed, 1)

    def test_throughput(self):
        t = self._make_tracker(["sfp_dns"])
        t._started_at = time.time() - 10.0
        t._total_events = 100
        self.assertAlmostEqual(t.throughput, 10.0, delta=1.0)

    def test_throughput_no_elapsed(self):
        t = ScanProgressTracker(scan_id="test")
        self.assertEqual(t.throughput, 0.0)

    def test_eta_no_progress(self):
        t = ScanProgressTracker(scan_id="test")
        self.assertIsNone(t.eta_seconds)

    def test_eta_with_progress(self):
        t = self._make_tracker(["m1", "m2", "m3", "m4"])
        t._started_at = time.time() - 10.0
        t.module_started("m1")
        t.module_completed("m1")
        # 25% done in 10s → total ~40s → remaining ~30s
        eta = t.eta_seconds
        self.assertIsNotNone(eta)
        self.assertGreater(eta, 20)
        self.assertLess(eta, 40)

    def test_get_snapshot(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.start()
        t.module_started("sfp_dns")
        t.record_event("sfp_dns")
        t.module_completed("sfp_dns")

        snap = t.get_snapshot()
        self.assertAlmostEqual(snap.overall_pct, 50.0)
        self.assertEqual(snap.modules_completed, 1)
        self.assertEqual(snap.modules_total, 2)
        self.assertEqual(snap.events_total, 1)

    def test_get_running_modules(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl", "sfp_portscan"])
        t.module_started("sfp_dns")
        t.module_started("sfp_ssl")
        t.module_completed("sfp_dns")

        running = t.get_running_modules()
        self.assertEqual(running, ["sfp_ssl"])

    def test_get_failed_modules(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_started("sfp_dns")
        t.module_failed("sfp_dns", "error")
        self.assertEqual(t.get_failed_modules(), ["sfp_dns"])

    def test_get_pending_modules(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.module_started("sfp_dns")
        self.assertEqual(t.get_pending_modules(), ["sfp_ssl"])

    def test_milestone_callback(self):
        t = self._make_tracker(["m1", "m2", "m3", "m4"])
        milestones = []
        t.on_milestone(lambda sid, pct, snap: milestones.append(pct))

        t.module_started("m1")
        t.module_completed("m1")  # 25%
        self.assertIn(25, milestones)

        t.module_started("m2")
        t.module_completed("m2")  # 50%
        self.assertIn(50, milestones)

    def test_milestone_fires_once(self):
        t = self._make_tracker(["m1", "m2"])
        milestones = []
        t.on_milestone(lambda sid, pct, snap: milestones.append(pct))

        t.module_completed("m1")  # 50%
        t.module_completed("m2")  # 100%
        # 50 should appear only once
        self.assertEqual(milestones.count(50), 1)

    def test_milestone_callback_error_handled(self):
        t = self._make_tracker(["m1", "m2", "m3", "m4"])
        t.on_milestone(lambda *a: 1 / 0)
        # Should not raise
        t.module_completed("m1")

    def test_complete(self):
        t = self._make_tracker(["sfp_dns"])
        t.start()
        time.sleep(0.01)
        t.complete()
        elapsed = t.elapsed
        time.sleep(0.01)
        # Elapsed should be frozen
        self.assertAlmostEqual(t.elapsed, elapsed, places=1)

    def test_get_history(self):
        t = self._make_tracker(["sfp_dns"])
        t.start()
        t.get_snapshot()
        t.get_snapshot()
        history = t.get_history()
        self.assertEqual(len(history), 2)

    def test_to_dict(self):
        t = self._make_tracker(["sfp_dns", "sfp_ssl"])
        t.start()
        t.module_started("sfp_dns")
        t.record_event("sfp_dns")
        t.module_completed("sfp_dns")

        d = t.to_dict()
        self.assertEqual(d["scan_id"], "test-001")
        self.assertAlmostEqual(d["overall_pct"], 50.0)
        self.assertEqual(d["total_events"], 1)
        self.assertIn("sfp_dns", d["modules"])
        self.assertIn("running", d)
        self.assertIn("failed", d)

    def test_thread_safety(self):
        t = self._make_tracker([f"mod_{i}" for i in range(20)])
        t.start()
        errors = []

        def run_module(name):
            try:
                t.module_started(name)
                for _ in range(10):
                    t.record_event(name)
                t.module_completed(name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=run_module, args=(f"mod_{i}",))
            for i in range(20)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(len(errors), 0)
        self.assertAlmostEqual(t.overall_progress, 100.0)
        self.assertEqual(t._total_events, 200)


if __name__ == "__main__":
    unittest.main()
