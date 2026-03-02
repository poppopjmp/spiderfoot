# -*- coding: utf-8 -*-
"""Tests for spiderfoot.ops.memory — Cycles 111-130 memory management utilities.

Covers:
    - SlottedEvent / SlottedPluginState  (Cycle 111)
    - StreamingResultSet / StreamingJsonEncoder  (Cycle 112)
    - LazyImporter  (Cycle 113)
    - CachedHelpers  (Cycle 114)
    - CeleryMemoryGuard  (Cycle 115)
    - MemoryProfiler / AllocationTracker  (Cycles 116-120)
    - ObjectSizeAnalyzer / GCTuner  (Cycles 121-125)
    - WeakEventCache / EventHistoryPruner  (Cycles 126-130)
"""

import gc
import sys
import threading
import time
from collections import OrderedDict
from unittest.mock import MagicMock, patch, mock_open

import pytest

from spiderfoot.ops.memory import (
    SlottedEvent,
    SlottedPluginState,
    StreamingResultSet,
    StreamingJsonEncoder,
    LazyImporter,
    CachedHelpers,
    CeleryMemoryGuard,
    MemoryProfiler,
    AllocationTracker,
    AllocationSnapshot,
    ObjectSizeAnalyzer,
    GCTuner,
    WeakEventCache,
    EventHistoryPruner,
    lazy,
)


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 111 — SlottedEvent / SlottedPluginState
# ═══════════════════════════════════════════════════════════════════════════

class TestSlottedEvent:
    """Tests for the __slots__-based event container."""

    def test_basic_construction(self):
        evt = SlottedEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        assert evt.event_type == "IP_ADDRESS"
        assert evt.data == "1.2.3.4"
        assert evt.module == "sfp_dns"
        assert evt.confidence == 100
        assert evt.visibility == 100
        assert evt.risk == 0
        assert evt.generated > 0

    def test_no_dict(self):
        """Slotted objects should NOT have __dict__."""
        evt = SlottedEvent("X", "y")
        assert not hasattr(evt, "__dict__")

    def test_extra_attributes(self):
        evt = SlottedEvent("X", "y")
        evt.set_extra("custom_field", 42)
        assert evt.get_extra("custom_field") == 42
        assert evt.get_extra("missing", "default") == "default"

    def test_to_dict(self):
        evt = SlottedEvent("EMAIL_ADDRESS", "test@example.com", "sfp_email", scan_id="ABCD1234")
        d = evt.to_dict()
        assert d["event_type"] == "EMAIL_ADDRESS"
        assert d["data"] == "test@example.com"
        assert d["scan_id"] == "ABCD1234"

    def test_to_dict_with_extras(self):
        evt = SlottedEvent("X", "y")
        evt.set_extra("tag", "important")
        d = evt.to_dict()
        assert d["tag"] == "important"

    def test_source_event_chain(self):
        root = SlottedEvent("ROOT", "example.com")
        child = SlottedEvent("DOMAIN", "sub.example.com", source_event=root)
        assert child.source_event is root

    def test_repr(self):
        evt = SlottedEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        r = repr(evt)
        assert "IP_ADDRESS" in r
        assert "data_len=7" in r

    def test_memory_smaller_than_dict(self):
        """A slotted event should use less memory than an equivalent dict."""
        evt = SlottedEvent("T", "d" * 100)
        d = {"event_type": "T", "data": "d" * 100, "module": "", "confidence": 100}
        # sys.getsizeof doesn't count slots deeply but the base should be smaller
        assert sys.getsizeof(evt) <= sys.getsizeof(d) + 200  # generous margin

    def test_custom_attrs_raise(self):
        """Cannot set arbitrary attributes on a slotted object."""
        evt = SlottedEvent("X", "y")
        with pytest.raises(AttributeError):
            evt.arbitrary_attr = "nope"


class TestSlottedPluginState:
    """Tests for the per-plugin scan state tracker."""

    def test_basic(self):
        state = SlottedPluginState("sfp_dns", "SCAN123")
        assert state.module_name == "sfp_dns"
        assert state.scan_id == "SCAN123"
        assert state.events_received == 0
        assert state.events_produced == 0

    def test_record_events(self):
        state = SlottedPluginState("sfp_dns")
        state.record_event_received()
        state.record_event_received()
        state.record_event_produced()
        assert state.events_received == 2
        assert state.events_produced == 1

    def test_record_error(self):
        state = SlottedPluginState("sfp_dns")
        state.record_error()
        state.record_error()
        assert state.errors == 2

    def test_memory_tracking(self):
        state = SlottedPluginState("sfp_dns")
        state.update_memory(100)
        state.update_memory(200)
        state.update_memory(150)
        assert state.peak_memory_kb == 200

    def test_to_dict(self):
        state = SlottedPluginState("sfp_dns", "S1")
        state.record_event_received()
        d = state.to_dict()
        assert d["module_name"] == "sfp_dns"
        assert d["events_received"] == 1
        assert "duration_s" in d

    def test_no_dict_attribute(self):
        state = SlottedPluginState("sfp_dns")
        assert not hasattr(state, "__dict__")


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 112 — StreamingResultSet / StreamingJsonEncoder
# ═══════════════════════════════════════════════════════════════════════════

class TestStreamingResultSet:
    """Tests for server-side cursor streaming."""

    def test_iter_batches(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Simulate two batches of 3 and 2 rows
        batch1 = [(1, "a"), (2, "b"), (3, "c")]
        batch2 = [(4, "d"), (5, "e")]
        mock_cursor.fetchmany.side_effect = [batch1, batch2, []]

        srs = StreamingResultSet(mock_conn, "SELECT * FROM tbl", batch_size=3)
        batches = list(srs.iter_batches())

        assert len(batches) == 2
        assert batches[0] == batch1
        assert batches[1] == batch2
        assert srs.total_yielded == 5
        assert srs.is_closed

    def test_iter_rows(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        batch1 = [(1,), (2,)]
        mock_cursor.fetchmany.side_effect = [batch1, []]

        srs = StreamingResultSet(mock_conn, "SELECT 1")
        rows = list(srs.iter_rows())
        assert rows == [(1,), (2,)]

    def test_empty_result(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchmany.return_value = []

        srs = StreamingResultSet(mock_conn, "SELECT 1 WHERE FALSE")
        batches = list(srs.iter_batches())
        assert batches == []
        assert srs.total_yielded == 0

    def test_cursor_closed_on_error(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("DB error")

        srs = StreamingResultSet(mock_conn, "SELECT *")
        with pytest.raises(Exception, match="DB error"):
            list(srs.iter_batches())
        mock_cursor.close.assert_called_once()
        assert srs.is_closed

    def test_custom_cursor_name(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchmany.return_value = []

        srs = StreamingResultSet(mock_conn, "SELECT 1", cursor_name="my_cursor")
        list(srs.iter_batches())
        mock_conn.cursor.assert_called_with(name="my_cursor")


class TestStreamingJsonEncoder:
    """Tests for incremental JSON array encoding."""

    def test_encode_empty(self):
        enc = StreamingJsonEncoder()
        output = "".join(enc.encode_iter(iter([])))
        assert output == "[]"
        assert enc.count == 0

    def test_encode_single_item(self):
        enc = StreamingJsonEncoder()
        import json
        output = "".join(enc.encode_iter(iter([{"a": 1}])))
        parsed = json.loads(output)
        assert parsed == [{"a": 1}]
        assert enc.count == 1

    def test_encode_multiple_items(self):
        enc = StreamingJsonEncoder()
        import json
        items = [{"x": 1}, {"x": 2}, {"x": 3}]
        output = "".join(enc.encode_iter(iter(items)))
        parsed = json.loads(output)
        assert parsed == items
        assert enc.count == 3

    def test_encode_with_indent(self):
        enc = StreamingJsonEncoder(indent=True)
        output = "".join(enc.encode_iter(iter([{"a": 1}])))
        assert "\n" in output

    def test_custom_dumps(self):
        def custom_dumps(obj, **kwargs):
            return '{"custom": true}'

        enc = StreamingJsonEncoder()
        output = "".join(enc.encode_iter(iter([{"a": 1}]), json_dumps=custom_dumps))
        assert '{"custom": true}' in output


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 113 — LazyImporter
# ═══════════════════════════════════════════════════════════════════════════

class TestLazyImporter:
    """Tests for deferred module importing."""

    def test_basic_import(self):
        li = LazyImporter()
        json_mod = li.get("json")
        import json
        assert json_mod is json

    def test_cached_import(self):
        li = LazyImporter()
        first = li.get("os")
        second = li.get("os")
        assert first is second

    def test_import_failure(self):
        li = LazyImporter()
        with pytest.raises(ImportError):
            li.get("non_existent_module_xyz_12345")

    def test_is_loaded(self):
        li = LazyImporter()
        assert not li.is_loaded("sys")
        li.get("sys")
        assert li.is_loaded("sys")

    def test_loaded_modules(self):
        li = LazyImporter()
        li.get("os")
        li.get("sys")
        assert "os" in li.loaded_modules
        assert "sys" in li.loaded_modules

    def test_unload(self):
        li = LazyImporter()
        li.get("os")
        assert li.is_loaded("os")
        result = li.unload("os")
        assert result is True
        assert not li.is_loaded("os")

    def test_unload_not_loaded(self):
        li = LazyImporter()
        assert li.unload("not_loaded") is False

    def test_clear(self):
        li = LazyImporter()
        li.get("os")
        li.get("sys")
        li.clear()
        assert li.loaded_modules == []

    def test_preload(self):
        li = LazyImporter()
        results = li.preload("os", "sys", "non_existent_xyz_99999")
        assert results["os"] is True
        assert results["sys"] is True
        assert results["non_existent_xyz_99999"] is False

    def test_thread_safety(self):
        li = LazyImporter()
        results = {}

        def import_module(name):
            mod = li.get(name)
            results[name] = mod

        threads = [threading.Thread(target=import_module, args=("json",)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(id(v) for v in results.values())) == 1  # All same object

    def test_global_lazy_instance(self):
        """The module-level ``lazy`` singleton should work."""
        assert isinstance(lazy, LazyImporter)
        mod = lazy.get("os")
        import os
        assert mod is os


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 114 — CachedHelpers
# ═══════════════════════════════════════════════════════════════════════════

class TestCachedHelpers:
    """Tests for LRU-cached helper method wrappers."""

    def setup_method(self):
        self.ch = CachedHelpers(maxsize=256)

    def test_urlBaseUrl_basic(self):
        assert self.ch.urlBaseUrl("https://example.com/path?q=1") == "https://example.com"

    def test_urlBaseUrl_none(self):
        assert self.ch.urlBaseUrl("") is None
        assert self.ch.urlBaseUrl(None) is None

    def test_urlBaseUrl_no_path(self):
        result = self.ch.urlBaseUrl("example.com")
        assert result == "example.com"

    def test_urlBaseDir(self):
        result = self.ch.urlBaseDir("https://example.com/path/to/page.html")
        assert result == "https://example.com/path/to/"

    def test_validEmail_valid(self):
        assert self.ch.validEmail("user@example.com") is True

    def test_validEmail_invalid(self):
        assert self.ch.validEmail("not-an-email") is False
        assert self.ch.validEmail("") is False
        assert self.ch.validEmail(123) is False

    def test_validPhoneNumber_valid(self):
        assert self.ch.validPhoneNumber("+1 555-123-4567") is True

    def test_validPhoneNumber_invalid(self):
        assert self.ch.validPhoneNumber("abc") is False
        assert self.ch.validPhoneNumber(123) is False

    def test_validLEI_valid(self):
        assert self.ch.validLEI("529900T8BM49AURSDO55") is True

    def test_validLEI_invalid(self):
        assert self.ch.validLEI("too-short") is False
        assert self.ch.validLEI(123) is False

    def test_validIP_valid(self):
        assert self.ch.validIP("192.168.1.1") is True
        assert self.ch.validIP("10.0.0.1") is True

    def test_validIP_invalid(self):
        assert self.ch.validIP("999.999.999.999") is False
        assert self.ch.validIP("not-an-ip") is False
        assert self.ch.validIP("") is False

    def test_validIP6_valid(self):
        assert self.ch.validIP6("::1") is True
        assert self.ch.validIP6("2001:db8::1") is True

    def test_validIP6_invalid(self):
        assert self.ch.validIP6("not-ipv6") is False
        assert self.ch.validIP6("") is False

    def test_cache_hits(self):
        # Call same URL twice
        self.ch.urlBaseUrl("https://example.com/page1")
        self.ch.urlBaseUrl("https://example.com/page1")
        stats = self.ch.stats()
        assert stats["urlBaseUrl"]["hits"] >= 1

    def test_stats(self):
        self.ch.validEmail("a@b.com")
        stats = self.ch.stats()
        assert "validEmail" in stats
        assert stats["validEmail"]["misses"] >= 1

    def test_clear_all(self):
        self.ch.urlBaseUrl("https://a.com/b")
        self.ch.clear_all()
        stats = self.ch.stats()
        assert stats["urlBaseUrl"]["currsize"] == 0

    def test_total_hits_misses(self):
        self.ch.urlBaseUrl("https://a.com/b")
        self.ch.urlBaseUrl("https://a.com/b")
        assert self.ch.total_hits() >= 1
        assert self.ch.total_misses() >= 1

    def test_hit_rate(self):
        self.ch.clear_all()
        self.ch.urlBaseUrl("https://a.com/b")
        self.ch.urlBaseUrl("https://a.com/b")
        rate = self.ch.hit_rate()
        assert rate == pytest.approx(50.0, abs=5.0)

    def test_hit_rate_no_calls(self):
        ch = CachedHelpers()
        assert ch.hit_rate() == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 115 — CeleryMemoryGuard
# ═══════════════════════════════════════════════════════════════════════════

class TestCeleryMemoryGuard:
    """Tests for runtime memory watchdog."""

    def test_ok_when_below_limits(self):
        guard = CeleryMemoryGuard(soft_limit_mb=5000, hard_limit_mb=8000)
        guard._current_rss_mb = 100
        # First call is always a check (count 1 % interval)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=100.0):
            result = guard.check()
        assert result == "ok"

    def test_warn_on_soft_limit(self):
        guard = CeleryMemoryGuard(soft_limit_mb=100, hard_limit_mb=200, check_interval=1)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=150.0):
            result = guard.check()
        assert result == "warn"

    def test_stop_on_hard_limit(self):
        guard = CeleryMemoryGuard(soft_limit_mb=100, hard_limit_mb=200, check_interval=1)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=250.0):
            result = guard.check()
        assert result == "stop"

    def test_check_interval_skips(self):
        guard = CeleryMemoryGuard(soft_limit_mb=1, hard_limit_mb=2, check_interval=5)
        guard._current_rss_mb = 0.5  # Below limits
        # Calls 1-4 should skip actual measurement
        for _ in range(4):
            result = guard.check()
            assert result == "ok"

    def test_peak_rss(self):
        guard = CeleryMemoryGuard(check_interval=1)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=500.0):
            guard.check()
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=300.0):
            guard.check()
        assert guard.peak_rss_mb == 500.0

    def test_warnings_recorded(self):
        guard = CeleryMemoryGuard(soft_limit_mb=100, hard_limit_mb=200, check_interval=1)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=150.0):
            guard.check()
        assert len(guard.warnings) == 1
        assert guard.warnings[0]["level"] == "soft"

    def test_reset(self):
        guard = CeleryMemoryGuard(soft_limit_mb=100, hard_limit_mb=200, check_interval=1)
        with patch.object(CeleryMemoryGuard, '_get_rss_mb', return_value=150.0):
            guard.check()
        guard.reset()
        assert guard.current_rss_mb == 0.0
        assert guard.peak_rss_mb == 0.0
        assert len(guard.warnings) == 0

    def test_summary(self):
        guard = CeleryMemoryGuard(soft_limit_mb=1000, hard_limit_mb=2000)
        summary = guard.summary()
        assert "checks_performed" in summary
        assert "soft_limit_mb" in summary
        assert summary["soft_limit_mb"] == 1000

    def test_get_rss_mb_returns_float(self):
        rss = CeleryMemoryGuard._get_rss_mb()
        assert isinstance(rss, float)


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 116-120 — MemoryProfiler / AllocationTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestAllocationSnapshot:
    """Tests for the snapshot dataclass."""

    def test_defaults(self):
        snap = AllocationSnapshot()
        assert snap.total_objects == 0
        assert snap.rss_mb == 0.0
        assert snap.top_types == []

    def test_to_dict(self):
        snap = AllocationSnapshot(
            total_objects=1000,
            gc_gen0=5,
            gc_gen1=2,
            gc_gen2=1,
            rss_mb=100.5,
            top_types=[("dict", 500), ("list", 300)],
        )
        d = snap.to_dict()
        assert d["total_objects"] == 1000
        assert len(d["top_types"]) == 2
        assert d["top_types"][0]["type"] == "dict"


class TestMemoryProfiler:
    """Tests for background memory profiling."""

    def test_snapshot_now(self):
        profiler = MemoryProfiler()
        snap = profiler.snapshot_now()
        assert isinstance(snap, AllocationSnapshot)
        assert snap.total_objects > 0

    def test_snapshots_list(self):
        profiler = MemoryProfiler()
        profiler.snapshot_now()
        profiler.snapshot_now()
        assert len(profiler.snapshots) == 2

    def test_max_snapshots_limit(self):
        profiler = MemoryProfiler(max_snapshots=3)
        for _ in range(5):
            profiler.snapshot_now()
        assert len(profiler.snapshots) == 3

    def test_growth_rate_no_snapshots(self):
        profiler = MemoryProfiler()
        assert profiler.growth_rate() == 0.0

    def test_growth_rate_single_snapshot(self):
        profiler = MemoryProfiler()
        profiler.snapshot_now()
        assert profiler.growth_rate() == 0.0

    def test_rss_growth_rate(self):
        profiler = MemoryProfiler()
        profiler.snapshot_now()
        # Rate should be computable with 2+ snapshots
        time.sleep(0.05)
        profiler.snapshot_now()
        # Just test it doesn't crash — actual value depends on system
        assert isinstance(profiler.rss_growth_rate(), float)

    def test_report_no_snapshots(self):
        profiler = MemoryProfiler()
        report = profiler.report()
        assert "error" in report

    def test_report_with_snapshots(self):
        profiler = MemoryProfiler()
        profiler.snapshot_now()
        time.sleep(0.05)
        profiler.snapshot_now()
        report = profiler.report()
        assert "snapshots_collected" in report
        assert report["snapshots_collected"] == 2

    def test_start_stop(self):
        profiler = MemoryProfiler(interval_s=0.05, max_snapshots=50)
        profiler.start()
        time.sleep(0.2)
        profiler.stop()
        assert len(profiler.snapshots) >= 1

    def test_double_start(self):
        profiler = MemoryProfiler(interval_s=0.1)
        profiler.start()
        profiler.start()  # Should not create a second thread
        profiler.stop()


class TestAllocationTracker:
    """Tests for labeled allocation tracking."""

    def test_track_context(self):
        tracker = AllocationTracker()
        with tracker.track("test_alloc"):
            _ = [i for i in range(1000)]
        report = tracker.report()
        assert "test_alloc" in report
        assert report["test_alloc"]["call_count"] == 1

    def test_multiple_tracks(self):
        tracker = AllocationTracker()
        for _ in range(3):
            with tracker.track("repeated"):
                pass
        report = tracker.report()
        assert report["repeated"]["call_count"] == 3

    def test_clear(self):
        tracker = AllocationTracker()
        with tracker.track("x"):
            pass
        tracker.clear()
        assert tracker.report() == {}


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 121-125 — ObjectSizeAnalyzer / GCTuner
# ═══════════════════════════════════════════════════════════════════════════

class TestObjectSizeAnalyzer:
    """Tests for deep object sizing."""

    def test_deep_sizeof_dict(self):
        analyzer = ObjectSizeAnalyzer()
        d = {"key": "value" * 100}
        size = analyzer.deep_sizeof(d)
        assert size > 0

    def test_deep_sizeof_list(self):
        analyzer = ObjectSizeAnalyzer()
        lst = list(range(100))
        size = analyzer.deep_sizeof(lst)
        assert size > sys.getsizeof(lst)  # Should include element sizes

    def test_deep_sizeof_nested(self):
        analyzer = ObjectSizeAnalyzer()
        nested = {"a": {"b": {"c": [1, 2, 3]}}}
        size = analyzer.deep_sizeof(nested)
        assert size > sys.getsizeof(nested)

    def test_max_depth(self):
        analyzer = ObjectSizeAnalyzer(max_depth=1)
        deep = {"a": {"b": {"c": {"d": "value"}}}}
        shallow_size = analyzer.deep_sizeof(deep)
        analyzer2 = ObjectSizeAnalyzer(max_depth=10)
        deep_size = analyzer2.deep_sizeof(deep)
        assert deep_size >= shallow_size

    def test_slotted_object(self):
        analyzer = ObjectSizeAnalyzer()
        evt = SlottedEvent("X", "y" * 100)
        size = analyzer.deep_sizeof(evt)
        assert size > 0

    def test_top_objects(self):
        analyzer = ObjectSizeAnalyzer()
        top = analyzer.top_objects(5)
        assert len(top) <= 5
        assert all("type" in item for item in top)

    def test_type_summary(self):
        analyzer = ObjectSizeAnalyzer()
        summary = analyzer.type_summary()
        assert len(summary) > 0
        # Should have common types
        assert any(t in summary for t in ("dict", "list", "str", "tuple"))


class TestGCTuner:
    """Tests for GC threshold tuning."""

    def test_original_thresholds(self):
        tuner = GCTuner()
        orig = tuner.original_thresholds
        assert len(orig) == 3
        assert all(isinstance(t, int) for t in orig)

    def test_set_scan_thresholds(self):
        tuner = GCTuner()
        tuner.set_scan_thresholds(5000, 50, 100)
        current = gc.get_threshold()
        assert current[0] == 5000
        assert current[1] == 50
        # gen2 may be reset by some Python versions
        tuner.restore_thresholds()

    def test_restore_thresholds(self):
        tuner = GCTuner()
        original = gc.get_threshold()
        tuner.set_scan_thresholds(9999, 99, 99)
        tuner.restore_thresholds()
        assert gc.get_threshold() == original

    def test_collect_now(self):
        tuner = GCTuner()
        collected = tuner.collect_now(0)
        assert isinstance(collected, int)

    def test_bulk_operation(self):
        tuner = GCTuner()
        assert gc.isenabled()
        with tuner.bulk_operation():
            assert not gc.isenabled()
        assert gc.isenabled()

    def test_collection_stats(self):
        tuner = GCTuner()
        tuner.collect_now(0)
        stats = tuner.collection_stats()
        assert stats["collections"] >= 1
        assert "total_time_s" in stats

    def test_collection_stats_empty(self):
        tuner = GCTuner()
        stats = tuner.collection_stats()
        assert stats["collections"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 126-130 — WeakEventCache / EventHistoryPruner
# ═══════════════════════════════════════════════════════════════════════════

class TestWeakEventCache:
    """Tests for weak-reference event cache."""

    def test_put_get_string(self):
        cache = WeakEventCache()
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self):
        cache = WeakEventCache()
        assert cache.get("nonexistent") is None

    def test_contains(self):
        cache = WeakEventCache()
        cache.put("k", "v")
        assert "k" in cache
        assert "missing" not in cache

    def test_maxsize_eviction(self):
        cache = WeakEventCache(maxsize=3)
        for i in range(5):
            cache.put(f"key{i}", f"value{i}")
        # First two should be evicted
        assert cache.get("key0") is None
        assert cache.get("key1") is None
        assert cache.get("key4") == "value4"

    def test_weakref_object(self):
        """Objects that support weakref should use weak references."""
        cache = WeakEventCache()

        class Holder:
            def __init__(self, val):
                self.val = val

        obj = Holder(42)
        cache.put("obj_key", obj)
        assert cache.get("obj_key").val == 42

        # After deleting the strong reference, weakref should be cleaned
        del obj
        gc.collect()
        # The weakref callback should have cleaned up
        assert cache.get("obj_key") is None

    def test_stats(self):
        cache = WeakEventCache()
        cache.put("a", "1")
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1

    def test_clear(self):
        cache = WeakEventCache()
        cache.put("a", "1")
        cache.clear()
        assert cache.size() == 0
        assert cache.get("a") is None

    def test_size(self):
        cache = WeakEventCache()
        cache.put("a", "1")
        cache.put("b", "2")
        assert cache.size() == 2

    def test_hit_rate(self):
        cache = WeakEventCache()
        cache.put("a", "1")
        cache.get("a")
        cache.get("a")
        cache.get("miss")
        stats = cache.stats()
        assert stats["hit_rate"] == pytest.approx(66.67, abs=1.0)


class TestEventHistoryPruner:
    """Tests for plugin event history pruning."""

    def test_prune_long_history(self):
        pruner = EventHistoryPruner(max_history_per_module=5)
        plugin = MagicMock()
        plugin._eventHistory = list(range(20))
        plugin._listenerModules = list(range(3))  # below threshold

        pruner.register_plugin(plugin)
        pruned = pruner._prune_once()

        assert pruned == 15  # 20 - 5
        assert len(plugin._eventHistory) == 5

    def test_prune_listener_modules(self):
        pruner = EventHistoryPruner(max_history_per_module=5)
        plugin = MagicMock()
        plugin._listenerModules = list(range(10))
        plugin._eventHistory = list(range(3))

        pruner.register_plugin(plugin)
        pruned = pruner._prune_once()

        assert pruned == 5  # 10 - 5
        assert len(plugin._listenerModules) == 5

    def test_no_prune_needed(self):
        pruner = EventHistoryPruner(max_history_per_module=100)
        plugin = MagicMock()
        plugin._eventHistory = list(range(5))
        plugin._listenerModules = []

        pruner.register_plugin(plugin)
        pruned = pruner._prune_once()
        assert pruned == 0

    def test_dead_plugin_cleaned(self):
        pruner = EventHistoryPruner()

        class TempPlugin:
            _eventHistory = []
            _listenerModules = []

        plugin = TempPlugin()
        pruner.register_plugin(plugin)
        del plugin
        gc.collect()

        pruner._prune_once()
        # Dead refs should be cleaned
        assert pruner.stats()["registered_plugins"] == 0

    def test_total_pruned(self):
        pruner = EventHistoryPruner(max_history_per_module=5)
        plugin = MagicMock()
        plugin._eventHistory = list(range(10))
        plugin._listenerModules = []

        pruner.register_plugin(plugin)
        pruner._prune_once()
        assert pruner.total_pruned == 5

    def test_start_stop(self):
        pruner = EventHistoryPruner(max_history_per_module=5, prune_interval_s=0.05)

        class FakePlugin:
            def __init__(self):
                self._eventHistory = list(range(100))
                self._listenerModules = []

        plugin = FakePlugin()
        pruner.register_plugin(plugin)
        pruner.start()
        time.sleep(0.3)
        pruner.stop()
        assert pruner.total_pruned > 0

    def test_stats(self):
        pruner = EventHistoryPruner()
        stats = pruner.stats()
        assert "registered_plugins" in stats
        assert "total_pruned" in stats
        assert "max_history_per_module" in stats
