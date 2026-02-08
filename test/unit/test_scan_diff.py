"""Tests for spiderfoot.scan_diff."""

import pytest

from spiderfoot.scan_diff import (
    Change,
    ChangeType,
    DiffResult,
    Finding,
    ScanDiff,
    ScanSnapshot,
)


class TestFinding:
    def test_key(self):
        f = Finding(event_type="IP_ADDRESS", data="1.2.3.4")
        assert f.key == "IP_ADDRESS:1.2.3.4"

    def test_fingerprint_deterministic(self):
        f1 = Finding(event_type="IP_ADDRESS", data="1.2.3.4")
        f2 = Finding(event_type="IP_ADDRESS", data="1.2.3.4")
        assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_varies_with_confidence(self):
        f1 = Finding(event_type="IP_ADDRESS", data="1.2.3.4",
                    confidence=100)
        f2 = Finding(event_type="IP_ADDRESS", data="1.2.3.4",
                    confidence=50)
        assert f1.fingerprint != f2.fingerprint

    def test_to_dict(self):
        f = Finding(event_type="DOMAIN_NAME", data="example.com",
                   module="sfp_dns")
        d = f.to_dict()
        assert d["event_type"] == "DOMAIN_NAME"
        assert d["data"] == "example.com"
        assert d["module"] == "sfp_dns"


class TestScanSnapshot:
    def test_from_events(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "example.com"},
        ]
        snap = ScanSnapshot.from_events(events, scan_id="s1")
        assert snap.finding_count == 2
        assert snap.scan_id == "s1"

    def test_from_events_alt_key(self):
        events = [
            {"event_type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        snap = ScanSnapshot.from_events(events)
        assert snap.finding_count == 1

    def test_event_types(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "example.com"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        snap = ScanSnapshot.from_events(events)
        assert snap.event_types == {"IP_ADDRESS", "DOMAIN_NAME"}

    def test_by_type(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "example.com"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        snap = ScanSnapshot.from_events(events)
        ips = snap.by_type("IP_ADDRESS")
        assert len(ips) == 2

    def test_round_trip(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4",
             "module": "sfp_dns"},
        ]
        snap = ScanSnapshot.from_events(events, scan_id="s1",
                                         target="example.com")
        d = snap.to_dict()
        restored = ScanSnapshot.from_dict(d)
        assert restored.scan_id == "s1"
        assert restored.finding_count == 1
        assert restored.findings[0].data == "1.2.3.4"

    def test_skip_empty_events(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "", "data": ""},
            {"data": "no type"},
        ]
        snap = ScanSnapshot.from_events(events)
        assert snap.finding_count == 1


class TestScanDiff:
    def test_no_changes(self):
        events = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "example.com"},
        ]
        snap_a = ScanSnapshot.from_events(events, scan_id="s1")
        snap_b = ScanSnapshot.from_events(events, scan_id="s2")

        diff = ScanDiff.compare(snap_a, snap_b)
        assert diff.has_changes is False
        assert diff.unchanged_count == 2
        assert diff.total_changes == 0

    def test_added_findings(self):
        baseline = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
        ]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline, scan_id="s1"),
            ScanSnapshot.from_events(current, scan_id="s2"),
        )
        assert len(diff.added) == 1
        assert diff.added[0].finding.data == "5.6.7.8"
        assert diff.added[0].change_type == ChangeType.ADDED

    def test_removed_findings(self):
        baseline = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
        )
        assert len(diff.removed) == 1
        assert diff.removed[0].finding.data == "5.6.7.8"

    def test_changed_findings(self):
        baseline = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4",
             "confidence": 100},
        ]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4",
             "confidence": 50},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
        )
        assert len(diff.changed) == 1
        assert diff.changed[0].previous.confidence == 100
        assert diff.changed[0].finding.confidence == 50

    def test_mixed_changes(self):
        baseline = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "old.example.com"},
            {"type": "TCP_PORT_OPEN", "data": "80"},
        ]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "new.example.com"},
            {"type": "TCP_PORT_OPEN", "data": "80"},
            {"type": "TCP_PORT_OPEN", "data": "443"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
        )
        assert len(diff.added) == 2   # new.example.com + 443
        assert len(diff.removed) == 1  # old.example.com
        assert diff.unchanged_count == 2  # 1.2.3.4 + 80

    def test_ignore_types(self):
        baseline = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "INTERNAL_STATUS", "data": "active"},
        ]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "INTERNAL_STATUS", "data": "done"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
            ignore_types={"INTERNAL_STATUS"},
        )
        assert diff.has_changes is False

    def test_summary(self):
        baseline = [{"type": "IP_ADDRESS", "data": "1.2.3.4"}]
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline, scan_id="s1"),
            ScanSnapshot.from_events(current, scan_id="s2"),
        )
        s = diff.summary()
        assert "Added:     1" in s
        assert "5.6.7.8" in s

    def test_to_dict(self):
        baseline = [{"type": "IP_ADDRESS", "data": "1.2.3.4"}]
        current = [{"type": "IP_ADDRESS", "data": "5.6.7.8"}]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
        )
        d = diff.to_dict()
        assert d["summary"]["added"] == 1
        assert d["summary"]["removed"] == 1

    def test_changes_by_type(self):
        baseline = []
        current = [
            {"type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"type": "DOMAIN_NAME", "data": "example.com"},
            {"type": "IP_ADDRESS", "data": "5.6.7.8"},
        ]
        diff = ScanDiff.compare(
            ScanSnapshot.from_events(baseline),
            ScanSnapshot.from_events(current),
        )
        by_type = diff.changes_by_type()
        assert len(by_type["IP_ADDRESS"]) == 2
        assert len(by_type["DOMAIN_NAME"]) == 1

    def test_compare_event_lists(self):
        baseline = [{"type": "IP_ADDRESS", "data": "1.2.3.4"}]
        current = [{"type": "IP_ADDRESS", "data": "5.6.7.8"}]

        diff = ScanDiff.compare_event_lists(
            baseline, current,
            baseline_id="b1", current_id="c1",
            target="example.com")

        assert diff.baseline_id == "b1"
        assert diff.current_id == "c1"
        assert diff.target == "example.com"
        assert len(diff.added) == 1
        assert len(diff.removed) == 1

    def test_empty_scans(self):
        diff = ScanDiff.compare(
            ScanSnapshot(scan_id="empty1"),
            ScanSnapshot(scan_id="empty2"),
        )
        assert diff.has_changes is False
        assert diff.total_changes == 0
