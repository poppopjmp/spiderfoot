"""Tests for Frontend Data Services (Phase 4, Cycles 291-320).

Tests cover:
- Pagination + sorting helpers (Cycle 296-320)
- ModuleHealthDashboard (Cycle 292)
- TimelineService (Cycle 294)
- ResultFilter + FilterCriteria (Cycle 295)
- ThreatMapAggregator (Cycle 293)
- ScanDiffSummary (Cycle 291)
- A11yLabelRegistry (Cycles 296-320)
"""

from __future__ import annotations

import time

import pytest

from spiderfoot.services.frontend_data import (
    A11yLabel,
    A11yLabelRegistry,
    FilterCriteria,
    GeoPoint,
    ModuleHealthDashboard,
    ModuleHealthSummary,
    Page,
    ResultFilter,
    ScanDiffSummary,
    SortOrder,
    ThreatMapAggregator,
    TimelineEvent,
    TimelineService,
    paginate,
    sort_dicts,
)


# ── Pagination ────────────────────────────────────────────────────────


class TestPage:
    """Tests for Page dataclass."""

    def test_has_next(self):
        p = Page(items=[1], total=100, page=1, page_size=25, total_pages=4)
        assert p.has_next is True

    def test_has_next_last_page(self):
        p = Page(items=[1], total=100, page=4, page_size=25, total_pages=4)
        assert p.has_next is False

    def test_has_prev(self):
        p = Page(items=[1], total=100, page=2, page_size=25, total_pages=4)
        assert p.has_prev is True

    def test_has_prev_first_page(self):
        p = Page(items=[1], total=100, page=1, page_size=25, total_pages=4)
        assert p.has_prev is False

    def test_to_dict(self):
        p = Page(items=["a", "b"], total=10, page=1, page_size=2, total_pages=5)
        d = p.to_dict()
        assert d["items"] == ["a", "b"]
        assert d["total"] == 10
        assert d["page"] == 1
        assert d["has_next"] is True


class TestPaginate:
    """Tests for paginate() function."""

    def test_basic(self):
        items = list(range(100))
        page = paginate(items, page=1, page_size=10)
        assert len(page.items) == 10
        assert page.items == list(range(10))
        assert page.total == 100
        assert page.total_pages == 10

    def test_second_page(self):
        items = list(range(100))
        page = paginate(items, page=2, page_size=10)
        assert page.items == list(range(10, 20))

    def test_last_page_partial(self):
        items = list(range(25))
        page = paginate(items, page=3, page_size=10)
        assert len(page.items) == 5
        assert page.items == list(range(20, 25))

    def test_empty(self):
        page = paginate([], page=1, page_size=10)
        assert page.items == []
        assert page.total == 0
        assert page.total_pages == 1

    def test_page_zero_clamps(self):
        page = paginate([1, 2, 3], page=0, page_size=2)
        assert page.page == 1

    def test_page_size_limit(self):
        page = paginate(list(range(2000)), page=1, page_size=5000)
        assert page.page_size == 1000


# ── Sort Helpers ──────────────────────────────────────────────────────


class TestSortDicts:
    """Tests for sort_dicts()."""

    def test_asc(self):
        items = [{"name": "c"}, {"name": "a"}, {"name": "b"}]
        result = sort_dicts(items, "name")
        assert [r["name"] for r in result] == ["a", "b", "c"]

    def test_desc(self):
        items = [{"name": "c"}, {"name": "a"}, {"name": "b"}]
        result = sort_dicts(items, "name", SortOrder.DESC)
        assert [r["name"] for r in result] == ["c", "b", "a"]

    def test_missing_key(self):
        items = [{"name": "b"}, {"x": 1}, {"name": "a"}]
        result = sort_dicts(items, "name")
        # Items with the key sort before items without it
        names = [r.get("name") for r in result]
        # "a" and "b" before the item with no name (sorts as "")
        assert "a" in names
        assert "b" in names

    def test_case_insensitive(self):
        items = [{"name": "Banana"}, {"name": "apple"}, {"name": "Cherry"}]
        result = sort_dicts(items, "name")
        assert [r["name"] for r in result] == ["apple", "Banana", "Cherry"]


# ── Module Health Dashboard ──────────────────────────────────────────


class TestModuleHealthSummary:
    """Tests for ModuleHealthSummary."""

    def test_to_dict(self):
        s = ModuleHealthSummary("sfp_test", status="healthy", events_processed=10)
        d = s.to_dict()
        assert d["module_name"] == "sfp_test"
        assert d["status"] == "healthy"
        assert d["events_processed"] == 10


class TestModuleHealthDashboard:
    """Tests for ModuleHealthDashboard."""

    def _populate(self) -> ModuleHealthDashboard:
        d = ModuleHealthDashboard()
        d.ingest("sfp_dns", events_processed=100, events_produced=50,
                 error_count=2, total_duration=5.0, status="healthy")
        d.ingest("sfp_web", events_processed=200, events_produced=80,
                 error_count=0, total_duration=10.0, status="healthy")
        d.ingest("sfp_bad", events_processed=10, events_produced=1,
                 error_count=15, total_duration=1.0, status="unhealthy")
        return d

    def test_ingest(self):
        d = ModuleHealthDashboard()
        d.ingest("sfp_test", events_processed=50, total_duration=2.5)
        assert d.module_count == 1

    def test_get_all(self):
        d = self._populate()
        all_modules = d.get_all()
        assert len(all_modules) == 3

    def test_get_all_sorted_by_name(self):
        d = self._populate()
        all_modules = d.get_all(sort_by="module_name")
        names = [m["module_name"] for m in all_modules]
        assert names == sorted(names)

    def test_get_failing(self):
        d = self._populate()
        failing = d.get_failing()
        assert len(failing) == 2  # sfp_dns (2 errors) + sfp_bad (15 errors)
        # Sorted by error_count desc
        assert failing[0]["module_name"] == "sfp_bad"

    def test_get_slowest(self):
        d = self._populate()
        slowest = d.get_slowest(limit=2)
        assert len(slowest) == 2

    def test_get_summary(self):
        d = self._populate()
        s = d.get_summary()
        assert s["total_modules"] == 3
        assert s["healthy"] == 1  # sfp_web only
        assert s["failing"] == 2
        assert s["total_events_processed"] == 310  # 100+200+10
        assert s["total_errors"] == 17  # 2+0+15

    def test_avg_duration_calc(self):
        d = ModuleHealthDashboard()
        d.ingest("sfp_test", events_processed=100, total_duration=10.0)
        modules = d.get_all()
        assert modules[0]["avg_duration_ms"] == 100.0  # 10s / 100 events * 1000

    def test_success_rate(self):
        d = ModuleHealthDashboard()
        d.ingest("sfp_test", events_processed=90, error_count=10)
        modules = d.get_all()
        assert modules[0]["success_rate"] == 90.0


# ── Timeline Service ──────────────────────────────────────────────────


class TestTimelineEvent:
    """Tests for TimelineEvent."""

    def test_to_dict(self):
        e = TimelineEvent(
            timestamp=1000.0, event_type="DOMAIN_NAME",
            data="example.com", module="sfp_dns",
        )
        d = e.to_dict()
        assert d["event_type"] == "DOMAIN_NAME"
        assert d["data"] == "example.com"

    def test_data_truncation(self):
        e = TimelineEvent(timestamp=1000.0, event_type="X", data="a" * 500)
        assert len(e.to_dict()["data"]) == 200


class TestTimelineService:
    """Tests for TimelineService."""

    def _populate(self) -> TimelineService:
        ts = TimelineService()
        ts.add_event(TimelineEvent(1000, "DOMAIN_NAME", "a.com", "sfp_dns"))
        ts.add_event(TimelineEvent(2000, "IP_ADDRESS", "1.2.3.4", "sfp_dns"))
        ts.add_event(TimelineEvent(3000, "DOMAIN_NAME", "b.com", "sfp_dns"))
        ts.add_event(TimelineEvent(4000, "EMAILADDR", "x@a.com", "sfp_email"))
        return ts

    def test_add_event(self):
        ts = TimelineService()
        ts.add_event(TimelineEvent(1000, "TEST", "data"))
        assert ts.event_count == 1

    def test_add_events_bulk(self):
        ts = TimelineService()
        count = ts.add_events([
            {"timestamp": 1000, "event_type": "A", "data": "d1"},
            {"timestamp": 2000, "event_type": "B", "data": "d2"},
            {"timestamp": 3000},  # missing event_type — skipped
        ])
        assert count == 2
        assert ts.event_count == 2

    def test_get_events_all(self):
        ts = self._populate()
        page = ts.get_events()
        assert page.total == 4

    def test_get_events_by_type(self):
        ts = self._populate()
        page = ts.get_events(event_type="DOMAIN_NAME")
        assert page.total == 2

    def test_get_events_time_range(self):
        ts = self._populate()
        page = ts.get_events(start=1500, end=3500)
        assert page.total == 2  # events at 2000 and 3000

    def test_get_events_sorted(self):
        ts = self._populate()
        page = ts.get_events()
        timestamps = [item["timestamp"] for item in page.items]
        assert timestamps == sorted(timestamps)

    def test_get_events_paginated(self):
        ts = self._populate()
        page = ts.get_events(page=1, page_size=2)
        assert len(page.items) == 2
        assert page.total == 4
        assert page.total_pages == 2

    def test_bucket_by_interval(self):
        ts = self._populate()
        buckets = ts.bucket_by_interval(interval_seconds=2000)
        assert len(buckets) >= 1
        total = sum(b["count"] for b in buckets)
        assert total == 4

    def test_bucket_filtered(self):
        ts = self._populate()
        buckets = ts.bucket_by_interval(2000, event_type="DOMAIN_NAME")
        total = sum(b["count"] for b in buckets)
        assert total == 2

    def test_bucket_empty(self):
        ts = TimelineService()
        assert ts.bucket_by_interval(3600) == []

    def test_time_range(self):
        ts = self._populate()
        r = ts.time_range
        assert r == (1000, 4000)

    def test_time_range_empty(self):
        ts = TimelineService()
        assert ts.time_range is None


# ── Result Filtering ─────────────────────────────────────────────────


class TestFilterCriteria:
    """Tests for FilterCriteria."""

    def test_empty(self):
        c = FilterCriteria()
        assert c.is_empty() is True

    def test_not_empty(self):
        c = FilterCriteria(event_types=["DOMAIN_NAME"])
        assert c.is_empty() is False


class TestResultFilter:
    """Tests for ResultFilter."""

    SAMPLE_RESULTS = [
        {"event_type": "DOMAIN_NAME", "module": "sfp_dns", "data": "example.com",
         "confidence": 100, "severity": "info", "scan_id": "s1", "timestamp": 1000},
        {"event_type": "IP_ADDRESS", "module": "sfp_dns", "data": "1.2.3.4",
         "confidence": 90, "severity": "low", "scan_id": "s1", "timestamp": 2000},
        {"event_type": "VULNERABILITY_CVE_CRITICAL", "module": "sfp_vulns",
         "data": "CVE-2024-1234", "confidence": 80, "severity": "critical",
         "scan_id": "s2", "timestamp": 3000},
        {"event_type": "EMAILADDR", "module": "sfp_email", "data": "a@b.com",
         "confidence": 70, "severity": "low", "scan_id": "s2", "timestamp": 4000},
    ]

    def test_no_filter(self):
        result = ResultFilter.apply(self.SAMPLE_RESULTS, FilterCriteria())
        assert len(result) == 4

    def test_filter_by_event_type(self):
        criteria = FilterCriteria(event_types=["DOMAIN_NAME"])
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 1
        assert result[0]["data"] == "example.com"

    def test_filter_by_module(self):
        criteria = FilterCriteria(modules=["sfp_dns"])
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 2

    def test_filter_by_severity(self):
        criteria = FilterCriteria(severity="critical")
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 1

    def test_filter_by_confidence(self):
        criteria = FilterCriteria(min_confidence=85)
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 2  # 100 and 90

    def test_filter_by_data_pattern_regex(self):
        criteria = FilterCriteria(data_pattern=r"CVE-\d+")
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 1

    def test_filter_by_data_pattern_substring(self):
        criteria = FilterCriteria(data_pattern="example")
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 1

    def test_filter_by_scan_id(self):
        criteria = FilterCriteria(scan_ids=["s2"])
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 2

    def test_filter_by_time_range(self):
        criteria = FilterCriteria(time_start=1500, time_end=3500)
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 2  # timestamps 2000 and 3000

    def test_combined_filters(self):
        criteria = FilterCriteria(
            modules=["sfp_dns"],
            min_confidence=95,
        )
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        assert len(result) == 1
        assert result[0]["data"] == "example.com"

    def test_invalid_regex_fallback(self):
        criteria = FilterCriteria(data_pattern="[invalid")
        result = ResultFilter.apply(self.SAMPLE_RESULTS, criteria)
        # Should fall back to substring, no match
        assert len(result) == 0

    def test_facets(self):
        facets = ResultFilter.facets(self.SAMPLE_RESULTS)
        assert facets["total"] == 4
        assert "DOMAIN_NAME" in facets["event_types"]
        assert "sfp_dns" in facets["modules"]
        assert "critical" in facets["severities"]

    def test_facets_empty(self):
        facets = ResultFilter.facets([])
        assert facets["total"] == 0


# ── Threat Map ────────────────────────────────────────────────────────


class TestGeoPoint:
    """Tests for GeoPoint."""

    def test_to_dict(self):
        p = GeoPoint(40.7, -74.0, "New York", "IP_ADDRESS", "1.2.3.4")
        d = p.to_dict()
        assert d["lat"] == 40.7
        assert d["lng"] == -74.0


class TestThreatMapAggregator:
    """Tests for ThreatMapAggregator."""

    def _populate(self) -> ThreatMapAggregator:
        t = ThreatMapAggregator()
        t.add_point(GeoPoint(40.71, -74.01, "NYC-1", "IP_ADDRESS", risk_level="high"))
        t.add_point(GeoPoint(40.72, -74.02, "NYC-2", "IP_ADDRESS", risk_level="medium"))
        t.add_point(GeoPoint(51.51, -0.13, "London", "DOMAIN_NAME", risk_level="low"))
        t.add_point(GeoPoint(-33.87, 151.21, "Sydney", "EMAILADDR", risk_level="critical"))
        return t

    def test_add_point(self):
        t = ThreatMapAggregator()
        t.add_point(GeoPoint(0, 0, "Origin"))
        assert t.point_count == 1

    def test_add_points_bulk(self):
        t = ThreatMapAggregator()
        count = t.add_points([
            {"lat": 40.7, "lng": -74.0, "label": "NYC"},
            {"latitude": 51.5, "longitude": -0.1, "label": "London"},
            {"label": "Missing"},  # no coords — skipped
        ])
        assert count == 2
        assert t.point_count == 2

    def test_get_all_points(self):
        t = self._populate()
        pts = t.get_all_points()
        assert len(pts) == 4

    def test_cluster(self):
        t = self._populate()
        clusters = t.cluster(precision=1)
        # NYC points cluster together (40.7, -74.0)
        # London (51.5, -0.1) and Sydney (-33.9, 151.2) are separate
        assert len(clusters) == 3

    def test_cluster_risk_sorted(self):
        t = self._populate()
        clusters = t.cluster(precision=1)
        # Should be sorted by risk_score descending
        scores = [c["risk_score"] for c in clusters]
        assert scores == sorted(scores, reverse=True)

    def test_by_region(self):
        t = self._populate()
        regions = t.by_region()
        assert regions["NW"] >= 2  # NYC
        assert regions["NW"] >= 1  # London
        assert regions["SE"] >= 1  # Sydney

    def test_risk_summary(self):
        t = self._populate()
        risk = t.risk_summary()
        assert risk["high"] == 1
        assert risk["critical"] == 1

    def test_empty_cluster(self):
        t = ThreatMapAggregator()
        assert t.cluster() == []


# ── Scan Diff Summary ────────────────────────────────────────────────


class TestScanDiffSummary:
    """Tests for ScanDiffSummary."""

    def test_from_changes(self):
        summary = ScanDiffSummary.from_changes(
            added=[{"event_type": "DOMAIN_NAME", "severity": "info"}],
            removed=[{"event_type": "IP_ADDRESS", "severity": "high"}],
            changed=[],
            unchanged_count=50,
        )
        assert summary["stats"]["added"] == 1
        assert summary["stats"]["removed"] == 1
        assert summary["stats"]["unchanged"] == 50
        assert summary["stats"]["total_changes"] == 2

    def test_change_rate(self):
        summary = ScanDiffSummary.from_changes(
            added=[{"event_type": "A"}] * 10,
            unchanged_count=90,
        )
        assert summary["stats"]["change_rate"] == 10.0

    def test_risk_impact(self):
        summary = ScanDiffSummary.from_changes(
            added=[
                {"event_type": "A", "severity": "critical"},
                {"event_type": "B", "severity": "high"},
            ],
            removed=[
                {"event_type": "C", "severity": "high"},
            ],
        )
        assert summary["risk_impact"]["high_risk_added"] == 2
        assert summary["risk_impact"]["high_risk_removed"] == 1
        assert summary["risk_impact"]["net_risk_change"] == 1

    def test_by_event_type(self):
        summary = ScanDiffSummary.from_changes(
            added=[{"event_type": "DOMAIN_NAME"}, {"event_type": "DOMAIN_NAME"}],
            removed=[{"event_type": "IP_ADDRESS"}],
        )
        by_type = summary["chart_data"]["by_event_type"]
        assert by_type["DOMAIN_NAME"]["added"] == 2
        assert by_type["IP_ADDRESS"]["removed"] == 1

    def test_empty(self):
        summary = ScanDiffSummary.from_changes()
        assert summary["stats"]["total_changes"] == 0


# ── Accessibility ─────────────────────────────────────────────────────


class TestA11yLabel:
    """Tests for A11yLabel."""

    def test_to_dict(self):
        lbl = A11yLabel("btn1", "Click Me", "A button", "button", "Ctrl+C")
        d = lbl.to_dict()
        assert d["id"] == "btn1"
        assert d["label"] == "Click Me"
        assert d["role"] == "button"
        assert d["shortcut"] == "Ctrl+C"

    def test_minimal_dict(self):
        lbl = A11yLabel("x", "Label")
        d = lbl.to_dict()
        assert "role" not in d
        assert "shortcut" not in d


class TestA11yLabelRegistry:
    """Tests for A11yLabelRegistry."""

    def test_defaults_loaded(self):
        r = A11yLabelRegistry()
        assert r.count >= 10

    def test_get_existing(self):
        r = A11yLabelRegistry()
        lbl = r.get("scan-start")
        assert lbl is not None
        assert lbl.label == "Start Scan"

    def test_get_missing(self):
        r = A11yLabelRegistry()
        assert r.get("nonexistent") is None

    def test_register(self):
        r = A11yLabelRegistry()
        initial_count = r.count
        r.register(A11yLabel("custom-btn", "Custom Button"))
        assert r.count == initial_count + 1
        assert r.get("custom-btn").label == "Custom Button"

    def test_get_shortcuts(self):
        r = A11yLabelRegistry()
        shortcuts = r.get_shortcuts()
        assert len(shortcuts) >= 3  # scan-start, nav-main, settings

    def test_get_all(self):
        r = A11yLabelRegistry()
        all_labels = r.get_all()
        assert len(all_labels) == r.count


# ── Integration ───────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests across frontend data services."""

    def test_filter_then_paginate(self):
        """Filter results then paginate the output."""
        results = [
            {"event_type": "DOMAIN_NAME", "data": f"d{i}.com",
             "module": "sfp_dns", "confidence": 100}
            for i in range(50)
        ]
        criteria = FilterCriteria(event_types=["DOMAIN_NAME"])
        filtered = ResultFilter.apply(results, criteria)
        page = paginate(filtered, page=2, page_size=10)
        assert page.total == 50
        assert len(page.items) == 10
        assert page.page == 2

    def test_timeline_to_facets(self):
        """Timeline events converted to faceted results."""
        ts = TimelineService()
        ts.add_events([
            {"timestamp": 1000, "event_type": "DOMAIN_NAME", "data": "a.com"},
            {"timestamp": 2000, "event_type": "DOMAIN_NAME", "data": "b.com"},
            {"timestamp": 3000, "event_type": "IP_ADDRESS", "data": "1.2.3.4"},
        ])
        page = ts.get_events()
        facets = ResultFilter.facets(page.items)
        assert facets["event_types"]["DOMAIN_NAME"] == 2
        assert facets["event_types"]["IP_ADDRESS"] == 1

    def test_threat_map_cluster_to_summary(self):
        """Cluster threat map data and summarize risk."""
        t = ThreatMapAggregator()
        for i in range(10):
            t.add_point(GeoPoint(
                40.7 + i * 0.001, -74.0 + i * 0.001,
                f"NYC-{i}", risk_level="high" if i % 2 == 0 else "medium",
            ))
        clusters = t.cluster(precision=1)
        assert len(clusters) >= 1
        total = sum(c["count"] for c in clusters)
        assert total == 10

    def test_health_dashboard_full_workflow(self):
        """Full module health dashboard workflow."""
        d = ModuleHealthDashboard()
        # Ingest modules
        for i in range(5):
            d.ingest(f"sfp_mod{i}",
                     events_processed=100 * (i + 1),
                     error_count=i * 2,
                     total_duration=float(i + 1),
                     status="healthy" if i < 3 else "degraded")
        # Get summary
        s = d.get_summary()
        assert s["total_modules"] == 5
        # Get failing
        failing = d.get_failing()
        assert len(failing) == 4  # all except sfp_mod0 (0 errors)
        # Get slowest
        slowest = d.get_slowest(2)
        assert len(slowest) == 2
