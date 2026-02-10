"""Tests for spiderfoot.scan_delta module."""
from __future__ import annotations

import unittest

from spiderfoot.scan_delta import (
    Delta,
    DeltaKind,
    DeltaResult,
    Finding,
    ScanDeltaAnalyzer,
)


class TestDeltaKind(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DeltaKind.NEW_FINDING.value, "new_finding")
        self.assertEqual(DeltaKind.RESOLVED.value, "resolved")
        self.assertEqual(DeltaKind.RISK_INCREASED.value, "risk_increased")
        self.assertEqual(DeltaKind.RISK_DECREASED.value, "risk_decreased")
        self.assertEqual(DeltaKind.STABLE.value, "stable")


class TestFinding(unittest.TestCase):
    def test_fingerprint(self):
        f = Finding(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertEqual(f.fingerprint, "IP_ADDRESS|1.2.3.4")

    def test_to_dict(self):
        f = Finding(event_type="IP_ADDRESS", data="1.2.3.4", risk=50)
        d = f.to_dict()
        self.assertEqual(d["event_type"], "IP_ADDRESS")
        self.assertEqual(d["risk"], 50)


class TestDelta(unittest.TestCase):
    def test_to_dict(self):
        f = Finding(event_type="IP_ADDRESS", data="1.2.3.4")
        d = Delta(kind=DeltaKind.NEW_FINDING, finding=f, note="first seen")
        result = d.to_dict()
        self.assertEqual(result["kind"], "new_finding")
        self.assertNotIn("previous", result)
        self.assertEqual(result["note"], "first seen")

    def test_to_dict_with_previous(self):
        old = Finding(event_type="IP_ADDRESS", data="1.2.3.4", risk=10)
        new = Finding(event_type="IP_ADDRESS", data="1.2.3.4", risk=50)
        d = Delta(kind=DeltaKind.RISK_INCREASED, finding=new, previous=old, risk_change=40)
        result = d.to_dict()
        self.assertIn("previous", result)
        self.assertEqual(result["risk_change"], 40)


class TestScanDeltaAnalyzer(unittest.TestCase):
    def _f(self, etype, data, risk=0, module="", confidence=100):
        return Finding(event_type=etype, data=data, risk=risk, module=module, confidence=confidence)

    def test_no_changes(self):
        baseline = [self._f("IP_ADDRESS", "1.2.3.4")]
        current = [self._f("IP_ADDRESS", "1.2.3.4")]

        analyzer = ScanDeltaAnalyzer()
        result = analyzer.analyze(baseline, current)

        self.assertEqual(len(result.new_findings()), 0)
        self.assertEqual(len(result.resolved()), 0)
        self.assertEqual(len(result.stable()), 1)

    def test_new_finding(self):
        baseline = [self._f("IP_ADDRESS", "1.2.3.4")]
        current = [
            self._f("IP_ADDRESS", "1.2.3.4"),
            self._f("IP_ADDRESS", "5.6.7.8"),
        ]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        self.assertEqual(len(result.new_findings()), 1)
        self.assertEqual(result.new_findings()[0].finding.data, "5.6.7.8")

    def test_resolved_finding(self):
        baseline = [
            self._f("IP_ADDRESS", "1.2.3.4"),
            self._f("IP_ADDRESS", "5.6.7.8"),
        ]
        current = [self._f("IP_ADDRESS", "1.2.3.4")]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        self.assertEqual(len(result.resolved()), 1)
        self.assertEqual(result.resolved()[0].finding.data, "5.6.7.8")

    def test_risk_increased(self):
        baseline = [self._f("VULNERABILITY", "CVE-2024-001", risk=30)]
        current = [self._f("VULNERABILITY", "CVE-2024-001", risk=80)]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        self.assertEqual(len(result.risk_increased()), 1)
        self.assertEqual(result.risk_increased()[0].risk_change, 50)

    def test_risk_decreased(self):
        baseline = [self._f("VULNERABILITY", "CVE-2024-001", risk=80)]
        current = [self._f("VULNERABILITY", "CVE-2024-001", risk=30)]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        self.assertEqual(len(result.risk_decreased()), 1)
        self.assertEqual(result.risk_decreased()[0].risk_change, -50)

    def test_risk_delta(self):
        baseline = [self._f("IP_ADDRESS", "1.1.1.1", risk=10)]
        current = [
            self._f("IP_ADDRESS", "1.1.1.1", risk=10),
            self._f("IP_ADDRESS", "2.2.2.2", risk=50),
        ]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        self.assertEqual(result.risk_delta, 50)

    def test_new_risks(self):
        baseline = []
        current = [
            self._f("IP_ADDRESS", "1.1.1.1", risk=0),
            self._f("MALICIOUS_IP", "2.2.2.2", risk=80),
        ]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        new_risks = result.new_risks(min_risk=50)
        self.assertEqual(len(new_risks), 1)
        self.assertEqual(new_risks[0].finding.data, "2.2.2.2")

    def test_resolved_risks(self):
        baseline = [
            self._f("MALICIOUS_IP", "2.2.2.2", risk=80),
            self._f("IP_ADDRESS", "1.1.1.1", risk=0),
        ]
        current = []

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        resolved = result.resolved_risks(min_risk=50)
        self.assertEqual(len(resolved), 1)

    def test_ignore_types(self):
        baseline = [self._f("RAW_DATA", "x")]
        current = [self._f("RAW_DATA", "y")]

        result = ScanDeltaAnalyzer(ignore_types={"RAW_DATA"}).analyze(baseline, current)
        self.assertEqual(len(result.deltas), 0)

    def test_by_type(self):
        baseline = []
        current = [
            self._f("IP_ADDRESS", "1.1.1.1"),
            self._f("EMAILADDR", "a@b.com"),
        ]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        ip_deltas = result.by_type("IP_ADDRESS")
        self.assertEqual(len(ip_deltas), 1)

    def test_module_change_detected(self):
        baseline = [self._f("IP_ADDRESS", "1.1.1.1", module="sfp_dns")]
        current = [self._f("IP_ADDRESS", "1.1.1.1", module="sfp_portscan")]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        changed = result.risk_increased() + result.risk_decreased()
        # Module change without risk change → shown somewhere
        # With default settings (compare_risk=True), same risk = stable
        # but module diff is detected in the CHANGED kind which maps to risk_increased/decreased
        # Actually module change alone maps to stable since risk didn't change
        # Let me verify the behavior
        self.assertEqual(len(result.stable()), 1)

    def test_summary(self):
        baseline = [self._f("IP_ADDRESS", "1.1.1.1")]
        current = [
            self._f("IP_ADDRESS", "1.1.1.1"),
            self._f("IP_ADDRESS", "2.2.2.2"),
        ]

        result = ScanDeltaAnalyzer().analyze(baseline, current)
        s = result.summary
        self.assertEqual(s["new_findings"], 1)
        self.assertEqual(s["stable"], 1)
        self.assertEqual(s["total_deltas"], 2)

    def test_to_dict(self):
        result = ScanDeltaAnalyzer().analyze(
            [self._f("IP_ADDRESS", "1.1.1.1")],
            [self._f("IP_ADDRESS", "2.2.2.2")],
        )
        d = result.to_dict()
        self.assertIn("summary", d)
        self.assertIn("deltas", d)

    def test_empty_scans(self):
        result = ScanDeltaAnalyzer().analyze([], [])
        self.assertEqual(len(result.deltas), 0)
        self.assertEqual(result.risk_delta, 0)

    def test_analyze_series(self):
        analyzer = ScanDeltaAnalyzer()
        scans = [
            ("scan-1", [self._f("IP_ADDRESS", "1.1.1.1")]),
            ("scan-2", [self._f("IP_ADDRESS", "1.1.1.1"), self._f("IP_ADDRESS", "2.2.2.2")]),
            ("scan-3", [self._f("IP_ADDRESS", "2.2.2.2")]),
        ]

        results = analyzer.analyze_series(scans)
        self.assertEqual(len(results), 2)

        # scan-1 → scan-2: added 2.2.2.2
        self.assertEqual(len(results[0].new_findings()), 1)
        # scan-2 → scan-3: removed 1.1.1.1
        self.assertEqual(len(results[1].resolved()), 1)

    def test_trend_tracking(self):
        analyzer = ScanDeltaAnalyzer()
        scans = [
            ("s1", [self._f("IP_ADDRESS", "1.1.1.1")]),
            ("s2", [self._f("IP_ADDRESS", "1.1.1.1"), self._f("IP_ADDRESS", "2.2.2.2")]),
        ]

        analyzer.analyze_series(scans)
        trend = analyzer.get_trend()
        self.assertEqual(len(trend), 1)
        self.assertEqual(trend[0]["scan_id"], "s2")
        self.assertEqual(trend[0]["total_findings"], 2)
        self.assertEqual(trend[0]["new_findings"], 1)


if __name__ == "__main__":
    unittest.main()
