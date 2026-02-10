"""Tests for spiderfoot.module_profiler."""

from __future__ import annotations

import time
import threading
import unittest

from spiderfoot.module_profiler import (
    MethodProfile,
    ModuleProfile,
    ModuleProfiler,
    get_module_profiler,
)


class TestMethodProfile(unittest.TestCase):
    """Tests for MethodProfile."""

    def test_initial_state(self):
        mp = MethodProfile(method_name="handleEvent")
        self.assertEqual(mp.method_name, "handleEvent")
        self.assertEqual(mp.call_count, 0)
        self.assertEqual(mp.total_time, 0.0)
        self.assertEqual(mp.min_time, float("inf"))
        self.assertEqual(mp.max_time, 0.0)
        self.assertEqual(mp.avg_time, 0.0)

    def test_record_single(self):
        mp = MethodProfile(method_name="test")
        mp.record(0.5)
        self.assertEqual(mp.call_count, 1)
        self.assertAlmostEqual(mp.total_time, 0.5)
        self.assertAlmostEqual(mp.min_time, 0.5)
        self.assertAlmostEqual(mp.max_time, 0.5)
        self.assertAlmostEqual(mp.avg_time, 0.5)

    def test_record_multiple(self):
        mp = MethodProfile(method_name="test")
        mp.record(0.1)
        mp.record(0.3)
        mp.record(0.5)
        self.assertEqual(mp.call_count, 3)
        self.assertAlmostEqual(mp.total_time, 0.9)
        self.assertAlmostEqual(mp.min_time, 0.1)
        self.assertAlmostEqual(mp.max_time, 0.5)
        self.assertAlmostEqual(mp.avg_time, 0.3)

    def test_percentiles(self):
        mp = MethodProfile(method_name="test")
        for v in range(1, 101):
            mp.record(v / 100.0)  # 0.01 to 1.00
        self.assertAlmostEqual(mp.p50, 0.505, places=2)
        self.assertGreater(mp.p95, 0.9)
        self.assertGreater(mp.p99, 0.95)

    def test_stddev(self):
        mp = MethodProfile(method_name="test")
        for v in [1.0, 1.0, 1.0]:
            mp.record(v)
        self.assertAlmostEqual(mp.stddev, 0.0)

    def test_stddev_single_sample(self):
        mp = MethodProfile(method_name="test")
        mp.record(1.0)
        self.assertEqual(mp.stddev, 0.0)

    def test_to_dict(self):
        mp = MethodProfile(method_name="handleEvent")
        mp.record(0.1)
        d = mp.to_dict()
        self.assertEqual(d["method"], "handleEvent")
        self.assertEqual(d["calls"], 1)
        self.assertIn("avg_ms", d)
        self.assertIn("p50_ms", d)
        self.assertIn("p95_ms", d)
        self.assertIn("p99_ms", d)
        self.assertIn("stddev_ms", d)

    def test_percentile_empty(self):
        mp = MethodProfile(method_name="test")
        self.assertEqual(mp.p50, 0.0)
        self.assertEqual(mp.p95, 0.0)
        self.assertEqual(mp.p99, 0.0)


class TestModuleProfile(unittest.TestCase):
    """Tests for ModuleProfile."""

    def test_initial_state(self):
        profile = ModuleProfile(module_name="sfp_dns")
        self.assertEqual(profile.module_name, "sfp_dns")
        self.assertEqual(profile.total_calls, 0)
        self.assertEqual(profile.total_time, 0.0)
        self.assertIsNone(profile.hottest_method)
        self.assertIsNone(profile.slowest_method)

    def test_get_method(self):
        profile = ModuleProfile(module_name="sfp_dns")
        mp = profile.get_method("handleEvent")
        self.assertIsInstance(mp, MethodProfile)
        self.assertEqual(mp.method_name, "handleEvent")
        # Same instance on second call
        mp2 = profile.get_method("handleEvent")
        self.assertIs(mp, mp2)

    def test_total_calls_and_time(self):
        profile = ModuleProfile(module_name="sfp_dns")
        profile.get_method("handleEvent").record(0.1)
        profile.get_method("handleEvent").record(0.2)
        profile.get_method("setup").record(0.5)
        self.assertEqual(profile.total_calls, 3)
        self.assertAlmostEqual(profile.total_time, 0.8)

    def test_hottest_method(self):
        profile = ModuleProfile(module_name="sfp_dns")
        profile.get_method("handleEvent").record(0.1)
        profile.get_method("handleEvent").record(0.2)
        profile.get_method("setup").record(0.5)
        # handleEvent total=0.3, setup total=0.5
        self.assertEqual(profile.hottest_method, "setup")

    def test_slowest_method(self):
        profile = ModuleProfile(module_name="sfp_dns")
        profile.get_method("handleEvent").record(0.1)
        profile.get_method("handleEvent").record(0.2)
        profile.get_method("setup").record(0.5)
        # handleEvent avg=0.15, setup avg=0.5
        self.assertEqual(profile.slowest_method, "setup")

    def test_take_snapshot(self):
        profile = ModuleProfile(module_name="sfp_dns")
        profile.get_method("handleEvent").record(0.1)
        snap = profile.take_snapshot("test_snap")
        self.assertEqual(snap["label"], "test_snap")
        self.assertEqual(snap["total_calls"], 1)
        self.assertIn("methods", snap)
        self.assertEqual(len(profile._snapshots), 1)

    def test_to_dict(self):
        profile = ModuleProfile(module_name="sfp_dns")
        profile.get_method("handleEvent").record(0.1)
        d = profile.to_dict()
        self.assertEqual(d["module_name"], "sfp_dns")
        self.assertEqual(d["total_calls"], 1)
        self.assertIn("methods", d)
        self.assertIn("handleEvent", d["methods"])


class TestModuleProfiler(unittest.TestCase):
    """Tests for ModuleProfiler."""

    def setUp(self):
        self.profiler = ModuleProfiler()

    def test_trace_context_manager(self):
        with self.profiler.trace("sfp_dns", "handleEvent"):
            time.sleep(0.01)

        p = self.profiler.get_profile("sfp_dns")
        self.assertIsNotNone(p)
        self.assertEqual(p["total_calls"], 1)
        self.assertGreater(p["methods"]["handleEvent"]["avg_ms"], 0)

    def test_record_manual(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.5)
        p = self.profiler.get_profile("sfp_dns")
        self.assertEqual(p["total_calls"], 1)
        self.assertAlmostEqual(
            p["methods"]["handleEvent"]["avg_ms"], 500.0, places=0
        )

    def test_profile_decorator(self):
        @self.profiler.profile("sfp_dns")
        def do_work():
            return 42

        result = do_work()
        self.assertEqual(result, 42)

        p = self.profiler.get_profile("sfp_dns")
        self.assertEqual(p["total_calls"], 1)

    def test_profile_decorator_custom_name(self):
        @self.profiler.profile("sfp_dns", "custom_op")
        def do_work():
            pass

        do_work()
        p = self.profiler.get_profile("sfp_dns")
        self.assertIn("custom_op", p["methods"])

    def test_disabled_profiler(self):
        self.profiler.enabled = False
        self.profiler.record("sfp_dns", "handleEvent", 0.5)
        p = self.profiler.get_profile("sfp_dns")
        self.assertIsNone(p)

    def test_disabled_trace(self):
        self.profiler.enabled = False
        with self.profiler.trace("sfp_dns", "handleEvent"):
            pass
        p = self.profiler.get_profile("sfp_dns")
        self.assertIsNone(p)

    def test_get_all_profiles(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.record("sfp_http", "handleEvent", 0.2)
        profiles = self.profiler.get_all_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertIn("sfp_dns", profiles)
        self.assertIn("sfp_http", profiles)

    def test_get_top_modules_by_time(self):
        self.profiler.record("sfp_slow", "handleEvent", 5.0)
        self.profiler.record("sfp_fast", "handleEvent", 0.01)
        top = self.profiler.get_top_modules(by="total_time", limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["module_name"], "sfp_slow")

    def test_get_top_modules_by_calls(self):
        for _ in range(100):
            self.profiler.record("sfp_busy", "handleEvent", 0.001)
        self.profiler.record("sfp_idle", "handleEvent", 1.0)
        top = self.profiler.get_top_modules(by="total_calls", limit=1)
        self.assertEqual(top[0]["module_name"], "sfp_busy")

    def test_get_slow_methods(self):
        self.profiler.record("sfp_dns", "slow_method", 2.0)  # 2000ms
        self.profiler.record("sfp_dns", "fast_method", 0.001)  # 1ms
        slow = self.profiler.get_slow_methods(threshold_ms=1000.0)
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0]["method"], "slow_method")
        self.assertEqual(slow[0]["module"], "sfp_dns")

    def test_update_memory(self):
        self.profiler.update_memory("sfp_dns", current_kb=1024, peak_kb=2048)
        p = self.profiler.get_profile("sfp_dns")
        self.assertEqual(p["memory_current_kb"], 1024)
        self.assertEqual(p["memory_peak_kb"], 2048)

    def test_snapshot(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        snap = self.profiler.snapshot("sfp_dns", "before_change")
        self.assertEqual(snap["label"], "before_change")
        self.assertEqual(snap["total_calls"], 1)

    def test_compare_snapshots(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.snapshot("sfp_dns", "snap_a")

        self.profiler.record("sfp_dns", "handleEvent", 0.2)
        self.profiler.snapshot("sfp_dns", "snap_b")

        diff = self.profiler.compare_snapshots("sfp_dns")
        self.assertIsNotNone(diff)
        self.assertEqual(diff["calls_delta"], 1)
        self.assertIn("methods", diff)
        self.assertIn("handleEvent", diff["methods"])

    def test_compare_snapshots_insufficient(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.snapshot("sfp_dns")
        # Only one snapshot
        diff = self.profiler.compare_snapshots("sfp_dns")
        self.assertIsNone(diff)

    def test_compare_snapshots_no_module(self):
        diff = self.profiler.compare_snapshots("nonexistent")
        self.assertIsNone(diff)

    def test_reset_specific(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.record("sfp_http", "handleEvent", 0.1)
        self.profiler.reset("sfp_dns")
        self.assertIsNone(self.profiler.get_profile("sfp_dns"))
        self.assertIsNotNone(self.profiler.get_profile("sfp_http"))

    def test_reset_all(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.record("sfp_http", "handleEvent", 0.1)
        self.profiler.reset()
        self.assertEqual(len(self.profiler.get_all_profiles()), 0)

    def test_get_summary(self):
        self.profiler.record("sfp_dns", "handleEvent", 0.1)
        self.profiler.record("sfp_dns", "setup", 0.2)
        self.profiler.record("sfp_http", "handleEvent", 0.3)
        summary = self.profiler.get_summary()
        self.assertEqual(summary["modules_profiled"], 2)
        self.assertEqual(summary["total_methods"], 3)
        self.assertEqual(summary["total_calls"], 3)
        self.assertTrue(summary["enabled"])

    def test_thread_safety(self):
        """Profile from multiple threads concurrently."""
        errors = []

        def worker(mod_name: str, n: int):
            try:
                for _ in range(n):
                    with self.profiler.trace(mod_name, "handleEvent"):
                        pass
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"sfp_{i}", 100))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        profiles = self.profiler.get_all_profiles()
        self.assertEqual(len(profiles), 10)
        for i in range(10):
            self.assertEqual(profiles[f"sfp_{i}"]["total_calls"], 100)

    def test_get_profile_nonexistent(self):
        self.assertIsNone(self.profiler.get_profile("nonexistent"))


class TestSingleton(unittest.TestCase):
    """Test singleton behavior."""

    def test_get_module_profiler(self):
        p1 = get_module_profiler()
        p2 = get_module_profiler()
        self.assertIs(p1, p2)
        self.assertIsInstance(p1, ModuleProfiler)


if __name__ == "__main__":
    unittest.main()
