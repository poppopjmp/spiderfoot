# -------------------------------------------------------------------------------
# Name:         Concurrency Performance Tests
# Purpose:      Unit tests for Cycles 91-110 (Concurrency & Worker Performance)
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Tests for concurrency and worker performance features:
- Cycle 91:  WorkStealingScheduler
- Cycle 92:  ModulePriorityScheduler
- Cycle 93:  ModulePreloader
- Cycle 94:  EventDeduplicator
- Cycle 95:  BackpressureController
- Cycle 96:  WorkerAutoScaler
- Cycle 97:  TracingMiddleware
- Cycle 98:  celery_retry_config
- Cycle 99:  ModuleTimeoutEnforcer
- Cycles 100-110: ScanSplitter
"""
import time
import threading
import unittest
from unittest.mock import MagicMock, patch


# ====================================================================== #
# Cycle 91: Work-Stealing Scheduler Tests                                #
# ====================================================================== #

class TestWorkStealingScheduler(unittest.TestCase):

    def test_register_unregister(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        self.assertEqual(s.worker_count, 1)
        s.unregister_worker("w1")
        self.assertEqual(s.worker_count, 0)

    def test_submit_and_get(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.submit("w1", "task_a")
        s.submit("w1", "task_b")
        self.assertEqual(s.queue_depth("w1"), 2)
        self.assertEqual(s.get("w1"), "task_a")  # FIFO
        self.assertEqual(s.get("w1"), "task_b")
        self.assertIsNone(s.get("w1"))

    def test_submit_nonexistent_worker(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        self.assertFalse(s.submit("ghost", "task"))

    def test_steal_from_busiest(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.register_worker("w2")
        for i in range(10):
            s.submit("w1", f"task_{i}")
        self.assertEqual(s.queue_depth("w1"), 10)
        stolen = s.steal("w2")
        self.assertIsNotNone(stolen)
        self.assertEqual(s.queue_depth("w1"), 9)
        # Stolen from tail
        self.assertEqual(stolen, "task_9")

    def test_steal_nothing_available(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.register_worker("w2")
        self.assertIsNone(s.steal("w1"))

    def test_total_pending(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.register_worker("w2")
        s.submit("w1", "t1")
        s.submit("w1", "t2")
        s.submit("w2", "t3")
        self.assertEqual(s.total_pending(), 3)

    def test_stats(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.register_worker("w2")
        s.submit("w1", "t1")
        s.get("w1")
        stats = s.stats()
        self.assertEqual(stats["w1"]["completed"], 1)
        self.assertEqual(stats["w1"]["pending"], 0)

    def test_steal_updates_stats(self):
        from spiderfoot.scan.concurrency import WorkStealingScheduler
        s = WorkStealingScheduler()
        s.register_worker("w1")
        s.register_worker("w2")
        s.submit("w1", "task")
        s.steal("w2")
        stats = s.stats()
        self.assertEqual(stats["w1"]["stolen_from"], 1)
        self.assertEqual(stats["w2"]["stolen_to"], 1)


# ====================================================================== #
# Cycle 92: Module Priority Scheduler Tests                              #
# ====================================================================== #

class TestModulePriorityScheduler(unittest.TestCase):

    def test_execution_order(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("sfp_spider", priority=10)
        s.register("sfp_dnsresolve", priority=1)
        s.register("sfp_hackertarget", priority=5)
        order = s.get_execution_order()
        self.assertEqual(order, ["sfp_dnsresolve", "sfp_hackertarget", "sfp_spider"])

    def test_same_priority_preserves_order(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("mod_a", priority=5)
        s.register("mod_b", priority=5)
        s.register("mod_c", priority=5)
        order = s.get_execution_order()
        self.assertEqual(order, ["mod_a", "mod_b", "mod_c"])

    def test_set_priority(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("mod_a", priority=10)
        s.register("mod_b", priority=1)
        self.assertEqual(s.get_execution_order(), ["mod_b", "mod_a"])
        # Promote mod_a to same priority as mod_b
        s.set_priority("mod_a", 1)
        order = s.get_execution_order()
        # Both priority 1 — mod_a first because registered earlier
        self.assertEqual(order[0], "mod_a")
        self.assertEqual(order[1], "mod_b")

    def test_unregister(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("mod_a", priority=1)
        s.register("mod_b", priority=2)
        s.unregister("mod_a")
        self.assertEqual(s.module_count, 1)
        self.assertEqual(s.get_execution_order(), ["mod_b"])

    def test_priority_groups(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("m1", 1)
        s.register("m2", 1)
        s.register("m3", 5)
        groups = s.get_priority_groups()
        self.assertEqual(len(groups[1]), 2)
        self.assertEqual(len(groups[5]), 1)

    def test_priority_clamped(self):
        from spiderfoot.scan.concurrency import ModulePriorityScheduler
        s = ModulePriorityScheduler()
        s.register("low", priority=0)   # should clamp to 1
        s.register("high", priority=99)  # should clamp to 10
        order = s.get_execution_order()
        self.assertEqual(order, ["low", "high"])


# ====================================================================== #
# Cycle 93: Module Preloader Tests                                       #
# ====================================================================== #

class TestModulePreloader(unittest.TestCase):

    def test_preload_builtin(self):
        from spiderfoot.scan.concurrency import ModulePreloader
        p = ModulePreloader(module_dir="json")
        # json is a stdlib module — won't have submodules but the import succeeds
        results = p.preload(["decoder"])
        # json.decoder should be importable
        self.assertTrue(results.get("decoder", False))
        self.assertEqual(p.loaded_count, 1)

    def test_preload_nonexistent(self):
        from spiderfoot.scan.concurrency import ModulePreloader
        p = ModulePreloader(module_dir="nonexistent_package_xyz")
        results = p.preload(["fake_module"])
        self.assertFalse(results.get("fake_module", True))

    def test_get_module(self):
        from spiderfoot.scan.concurrency import ModulePreloader
        p = ModulePreloader(module_dir="json")
        p.preload(["decoder"])
        mod = p.get_module("decoder")
        self.assertIsNotNone(mod)
        self.assertIsNone(p.get_module("nonexistent"))

    def test_clear(self):
        from spiderfoot.scan.concurrency import ModulePreloader
        p = ModulePreloader(module_dir="json")
        p.preload(["decoder"])
        self.assertEqual(p.loaded_count, 1)
        p.clear()
        self.assertEqual(p.loaded_count, 0)


# ====================================================================== #
# Cycle 94: Event Deduplicator Tests                                     #
# ====================================================================== #

class TestEventDeduplicator(unittest.TestCase):

    def test_first_event_not_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=100)
        self.assertFalse(d.is_duplicate("IP", "1.2.3.4", "s1"))

    def test_same_event_within_window_is_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)  # 1 second window
        d.is_duplicate("IP", "1.2.3.4", "s1")
        self.assertTrue(d.is_duplicate("IP", "1.2.3.4", "s1"))

    def test_same_event_after_window_not_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=50)
        d.is_duplicate("IP", "1.2.3.4", "s1")
        time.sleep(0.08)  # wait past window
        self.assertFalse(d.is_duplicate("IP", "1.2.3.4", "s1"))

    def test_different_event_not_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)
        d.is_duplicate("IP", "1.2.3.4", "s1")
        self.assertFalse(d.is_duplicate("IP", "5.6.7.8", "s1"))

    def test_different_type_not_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)
        d.is_duplicate("IP", "1.2.3.4", "s1")
        self.assertFalse(d.is_duplicate("DOMAIN", "1.2.3.4", "s1"))

    def test_different_scan_not_duplicate(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)
        d.is_duplicate("IP", "1.2.3.4", "s1")
        self.assertFalse(d.is_duplicate("IP", "1.2.3.4", "s2"))

    def test_stats(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)
        d.is_duplicate("IP", "1.2.3.4")
        d.is_duplicate("IP", "1.2.3.4")
        d.is_duplicate("IP", "5.6.7.8")
        stats = d.stats
        self.assertEqual(stats["checked"], 3)
        self.assertEqual(stats["duplicates"], 1)

    def test_active_entries(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=1000)
        d.is_duplicate("IP", "1.2.3.4")
        d.is_duplicate("IP", "5.6.7.8")
        self.assertEqual(d.active_entries, 2)

    def test_max_entries_eviction(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=10000, max_entries=10)
        for i in range(15):
            d.is_duplicate("IP", f"10.0.0.{i}")
        self.assertLessEqual(d.active_entries, 11)

    def test_start_stop(self):
        from spiderfoot.scan.concurrency import EventDeduplicator
        d = EventDeduplicator(window_ms=100, reap_interval=0.1)
        d.start()
        d.is_duplicate("IP", "1.2.3.4")
        time.sleep(0.3)  # wait for reaper
        d.stop()
        self.assertEqual(d.active_entries, 0)


# ====================================================================== #
# Cycle 95: Backpressure Controller Tests                                #
# ====================================================================== #

class TestBackpressureController(unittest.TestCase):

    def test_normal_state(self):
        from spiderfoot.scan.concurrency import BackpressureController, PressureState
        bp = BackpressureController(depth_fn=lambda: 100, capacity=10000)
        self.assertEqual(bp.get_state(), PressureState.NORMAL)
        self.assertTrue(bp.should_accept())

    def test_warning_state(self):
        from spiderfoot.scan.concurrency import BackpressureController, PressureState
        bp = BackpressureController(depth_fn=lambda: 5500, capacity=10000)
        self.assertEqual(bp.get_state(), PressureState.WARNING)
        self.assertTrue(bp.should_accept())

    def test_critical_state(self):
        from spiderfoot.scan.concurrency import BackpressureController, PressureState
        bp = BackpressureController(depth_fn=lambda: 8000, capacity=10000)
        self.assertEqual(bp.get_state(), PressureState.CRITICAL)
        self.assertTrue(bp.should_accept())

    def test_blocked_state(self):
        from spiderfoot.scan.concurrency import BackpressureController, PressureState
        bp = BackpressureController(depth_fn=lambda: 9500, capacity=10000)
        self.assertEqual(bp.get_state(), PressureState.BLOCKED)
        self.assertFalse(bp.should_accept())

    def test_depth_fn_required(self):
        from spiderfoot.scan.concurrency import BackpressureController
        with self.assertRaises(ValueError):
            BackpressureController(depth_fn="not_callable")

    def test_state_change_callback(self):
        from spiderfoot.scan.concurrency import BackpressureController
        depth = [0]
        states = []
        bp = BackpressureController(depth_fn=lambda: depth[0], capacity=100)
        bp.on_state_change(lambda s: states.append(s))
        depth[0] = 10
        bp.get_state()  # NORMAL
        depth[0] = 95
        bp.get_state()  # BLOCKED
        self.assertEqual(len(states), 1)  # Only fires on change

    def test_stats(self):
        from spiderfoot.scan.concurrency import BackpressureController
        bp = BackpressureController(depth_fn=lambda: 50, capacity=10000)
        bp.should_accept()
        bp.should_accept()
        stats = bp.stats
        self.assertEqual(stats["accepted"], 2)
        self.assertEqual(stats["rejected"], 0)

    def test_utilization(self):
        from spiderfoot.scan.concurrency import BackpressureController
        bp = BackpressureController(depth_fn=lambda: 5000, capacity=10000)
        self.assertAlmostEqual(bp.utilization, 0.5, places=2)


# ====================================================================== #
# Cycle 96: Worker Auto-Scaler Tests                                     #
# ====================================================================== #

class TestScaleSignal(unittest.TestCase):
    def test_to_dict(self):
        from spiderfoot.scan.concurrency import ScaleSignal
        s = ScaleSignal(action="scale_up", current_workers=2,
                        recommended_workers=5, reason="test")
        d = s.to_dict()
        self.assertEqual(d["action"], "scale_up")
        self.assertEqual(d["recommended_workers"], 5)


class TestWorkerAutoScaler(unittest.TestCase):

    def test_scale_up(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 2000,
            min_workers=1,
            max_workers=10,
            scale_up_threshold=1000,
            tasks_per_worker=200,
            cooldown_seconds=0,
        )
        signal = scaler.evaluate(current_workers=2)
        self.assertEqual(signal.action, "scale_up")
        self.assertGreater(signal.recommended_workers, 2)

    def test_scale_down(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 5,
            min_workers=1,
            max_workers=10,
            scale_down_threshold=10,
            cooldown_seconds=0,
        )
        signal = scaler.evaluate(current_workers=5)
        self.assertEqual(signal.action, "scale_down")
        self.assertLess(signal.recommended_workers, 5)

    def test_no_change(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 500,
            scale_up_threshold=1000,
            scale_down_threshold=10,
            cooldown_seconds=0,
        )
        signal = scaler.evaluate(current_workers=3)
        self.assertEqual(signal.action, "no_change")

    def test_cooldown(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 5000,
            scale_up_threshold=1000,
            cooldown_seconds=60,
        )
        s1 = scaler.evaluate(current_workers=2)
        self.assertEqual(s1.action, "scale_up")
        s2 = scaler.evaluate(current_workers=2)
        self.assertEqual(s2.action, "no_change")
        self.assertIn("Cooldown", s2.reason)

    def test_respects_max(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 100000,
            max_workers=5,
            tasks_per_worker=100,
            scale_up_threshold=50,
            cooldown_seconds=0,
        )
        signal = scaler.evaluate(current_workers=2)
        self.assertLessEqual(signal.recommended_workers, 5)

    def test_respects_min(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 0,
            min_workers=2,
            scale_down_threshold=10,
            cooldown_seconds=0,
        )
        signal = scaler.evaluate(current_workers=2)
        # Already at min — no change
        self.assertEqual(signal.action, "no_change")

    def test_history(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        scaler = WorkerAutoScaler(
            depth_fn=lambda: 5000,
            scale_up_threshold=1000,
            cooldown_seconds=0,
        )
        scaler.evaluate(current_workers=1)
        self.assertEqual(len(scaler.history), 1)

    def test_depth_fn_required(self):
        from spiderfoot.scan.concurrency import WorkerAutoScaler
        with self.assertRaises(ValueError):
            WorkerAutoScaler(depth_fn=42)


# ====================================================================== #
# Cycle 97: Tracing Middleware Tests                                     #
# ====================================================================== #

class TestSpanRecord(unittest.TestCase):

    def test_finish(self):
        from spiderfoot.scan.concurrency import SpanRecord
        span = SpanRecord(
            trace_id="t1", span_id="s1", operation="handleEvent",
            module_name="sfp_dns", scan_id="scan-1", start_time=time.time() - 1
        )
        span.finish()
        self.assertAlmostEqual(span.duration_ms, 1000, delta=100)
        self.assertEqual(span.status, "ok")

    def test_finish_with_error(self):
        from spiderfoot.scan.concurrency import SpanRecord
        span = SpanRecord(
            trace_id="t1", span_id="s1", operation="op",
            module_name="m1", scan_id="s1", start_time=time.time()
        )
        span.finish(error="timeout")
        self.assertEqual(span.status, "error")
        self.assertEqual(span.error, "timeout")

    def test_to_dict(self):
        from spiderfoot.scan.concurrency import SpanRecord
        span = SpanRecord(
            trace_id="t1", span_id="s1", operation="op",
            module_name="m1", scan_id="s1", start_time=time.time()
        )
        span.finish()
        d = span.to_dict()
        self.assertIn("duration_ms", d)
        self.assertIn("trace_id", d)


class TestTracingMiddleware(unittest.TestCase):

    def test_start_and_finish_span(self):
        from spiderfoot.scan.concurrency import TracingMiddleware
        t = TracingMiddleware(scan_id="scan-1")
        span = t.start_span("handleEvent", "sfp_dns")
        time.sleep(0.01)
        t.finish_span(span)
        self.assertEqual(t.span_count(), 1)
        self.assertGreater(span.duration_ms, 0)

    def test_error_spans(self):
        from spiderfoot.scan.concurrency import TracingMiddleware
        t = TracingMiddleware(scan_id="scan-1")
        span = t.start_span("handleEvent", "sfp_dns")
        t.finish_span(span, error="connection failed")
        errors = t.get_error_spans()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error"], "connection failed")

    def test_slow_spans(self):
        from spiderfoot.scan.concurrency import TracingMiddleware
        t = TracingMiddleware(scan_id="scan-1")
        span = t.start_span("handleEvent", "sfp_spider")
        span.start_time -= 2.0  # pretend it started 2s ago
        t.finish_span(span)
        slow = t.get_slow_spans(threshold_ms=1000)
        self.assertEqual(len(slow), 1)

    def test_summary(self):
        from spiderfoot.scan.concurrency import TracingMiddleware
        t = TracingMiddleware(scan_id="scan-1")
        for mod in ["sfp_dns", "sfp_dns", "sfp_spider"]:
            span = t.start_span("handleEvent", mod)
            t.finish_span(span)
        summary = t.summary()
        self.assertEqual(summary["total_spans"], 3)
        self.assertIn("sfp_dns", summary["modules"])
        self.assertEqual(summary["modules"]["sfp_dns"]["count"], 2)


# ====================================================================== #
# Cycle 98: Celery Retry Config Tests                                    #
# ====================================================================== #

class TestCeleryRetryConfig(unittest.TestCase):

    def test_default_config(self):
        from spiderfoot.scan.concurrency import celery_retry_config
        config = celery_retry_config()
        self.assertEqual(config["max_retries"], 3)
        self.assertTrue(config["retry_jitter"])
        self.assertTrue(config["acks_late"])
        self.assertIsInstance(config["autoretry_for"], tuple)

    def test_custom_config(self):
        from spiderfoot.scan.concurrency import celery_retry_config
        config = celery_retry_config(
            max_retries=5,
            backoff_base=3.0,
            backoff_max=120.0,
            retryable_exceptions=[ValueError, IOError],
        )
        self.assertEqual(config["max_retries"], 5)
        self.assertEqual(config["retry_backoff"], 3.0)
        self.assertEqual(config["retry_backoff_max"], 120.0)
        self.assertIn(ValueError, config["autoretry_for"])
        self.assertIn(IOError, config["autoretry_for"])

    def test_contains_required_keys(self):
        from spiderfoot.scan.concurrency import celery_retry_config
        config = celery_retry_config()
        required_keys = ["autoretry_for", "max_retries", "retry_backoff",
                         "retry_backoff_max", "retry_jitter", "acks_late"]
        for key in required_keys:
            self.assertIn(key, config)


# ====================================================================== #
# Cycle 99: Module Timeout Enforcer Tests                                #
# ====================================================================== #

class TestModuleTimeoutEnforcer(unittest.TestCase):

    def test_default_timeout(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=300)
        self.assertEqual(e.get_timeout("sfp_dns"), 300)

    def test_custom_timeout(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=300)
        e.set_timeout("sfp_spider", 600)
        self.assertEqual(e.get_timeout("sfp_spider"), 600)
        self.assertEqual(e.get_timeout("sfp_dns"), 300)

    def test_tracking(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=300)
        e.start_tracking("sfp_dns", "ev-1")
        self.assertEqual(e.active_count, 1)
        elapsed = e.stop_tracking("sfp_dns", "ev-1")
        self.assertEqual(e.active_count, 0)
        self.assertGreaterEqual(elapsed, 0)

    def test_timeout_violation(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        callback_called = []
        e = ModuleTimeoutEnforcer(
            default_timeout=0.05,
            on_timeout=lambda m, eid, el: callback_called.append((m, eid)),
        )
        e.start_tracking("sfp_slow", "ev-1")
        time.sleep(0.1)
        e.stop_tracking("sfp_slow", "ev-1")
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0][0], "sfp_slow")
        self.assertEqual(len(e.violations), 1)

    def test_no_violation_within_timeout(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=10)
        e.start_tracking("sfp_dns", "ev-1")
        e.stop_tracking("sfp_dns", "ev-1")
        self.assertEqual(len(e.violations), 0)

    def test_check_active(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=0.05)
        e.start_tracking("sfp_slow", "ev-1")
        time.sleep(0.1)
        exceeded = e.check_active()
        self.assertEqual(len(exceeded), 1)
        self.assertEqual(exceeded[0]["module"], "sfp_slow")

    def test_celery_limits(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer(default_timeout=300)
        limits = e.get_celery_limits("sfp_dns")
        self.assertEqual(limits["soft_time_limit"], 300)
        self.assertEqual(limits["time_limit"], 360)

    def test_stop_untracked_returns_zero(self):
        from spiderfoot.scan.concurrency import ModuleTimeoutEnforcer
        e = ModuleTimeoutEnforcer()
        self.assertEqual(e.stop_tracking("sfp_unknown", "ev-1"), 0.0)


# ====================================================================== #
# Cycles 100-110: Scan Splitter Tests                                    #
# ====================================================================== #

class TestScanChunk(unittest.TestCase):

    def test_to_dict(self):
        from spiderfoot.scan.concurrency import ScanChunk, SplitStrategy
        c = ScanChunk(
            chunk_id="c1", scan_id="s1", target="10.0.0.0/24",
            target_type="NETBLOCK_OWNER", modules=["sfp_dns"],
            strategy=SplitStrategy.IP_RANGE,
        )
        d = c.to_dict()
        self.assertEqual(d["chunk_id"], "c1")
        self.assertEqual(d["strategy"], "ip_range")


class TestScanSplitter(unittest.TestCase):

    def test_split_single_ip(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        chunks = s.split_by_ip_range("s1", "192.168.1.1/32", ["sfp_dns"])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].target, "192.168.1.1/32")

    def test_split_slash24(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        chunks = s.split_by_ip_range("s1", "10.0.0.0/24", ["sfp_dns"],
                                     max_hosts_per_chunk=256)
        self.assertEqual(len(chunks), 1)

    def test_split_slash16(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        chunks = s.split_by_ip_range("s1", "10.0.0.0/16", ["sfp_dns"],
                                     max_hosts_per_chunk=256)
        self.assertEqual(len(chunks), 256)  # 65536/256 = 256 chunks

    def test_split_invalid_cidr(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        with self.assertRaises(ValueError):
            s.split_by_ip_range("s1", "not-a-cidr", ["sfp_dns"])

    def test_split_by_module_category(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        modules = ["sfp_dnsresolve", "sfp_portscan_basic", "sfp_shodan",
                    "sfp_virustotal", "sfp_custom_module"]
        chunks = s.split_by_module_category("s1", "example.com", "DOMAIN_NAME", modules)
        # Should have at least 4 categories + uncategorized
        self.assertGreaterEqual(len(chunks), 4)
        # Custom module should be in uncategorized
        uncat = [c for c in chunks if c.metadata.get("category") == "uncategorized"]
        self.assertEqual(len(uncat), 1)
        self.assertIn("sfp_custom_module", uncat[0].modules)

    def test_split_subdomains(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        subs = [f"sub{i}.example.com" for i in range(120)]
        chunks = s.split_subdomains("s1", subs, ["sfp_dns"], max_per_chunk=50)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].metadata["subdomain_count"], 50)
        self.assertEqual(chunks[2].metadata["subdomain_count"], 20)

    def test_estimate_chunks_ip(self):
        from spiderfoot.scan.concurrency import ScanSplitter, SplitStrategy
        s = ScanSplitter()
        n = s.estimate_chunks("10.0.0.0/16", SplitStrategy.IP_RANGE, max_per_chunk=256)
        self.assertEqual(n, 256)

    def test_estimate_chunks_invalid(self):
        from spiderfoot.scan.concurrency import ScanSplitter, SplitStrategy
        s = ScanSplitter()
        n = s.estimate_chunks("invalid", SplitStrategy.IP_RANGE)
        self.assertEqual(n, 1)

    def test_chunk_metadata(self):
        from spiderfoot.scan.concurrency import ScanSplitter
        s = ScanSplitter()
        chunks = s.split_by_ip_range("s1", "10.0.0.0/22", ["sfp_dns"],
                                     max_hosts_per_chunk=256)
        self.assertEqual(len(chunks), 4)  # /22 = 1024 hosts, 1024/256 = 4
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.metadata["index"], i)
            self.assertEqual(chunk.metadata["total"], 4)


if __name__ == "__main__":
    unittest.main()
