"""Tests for spiderfoot.result_aggregator."""

import time
import unittest

from spiderfoot.result_aggregator import (
    EventRecord,
    ScanResultAggregator,
    TypeStats,
)


class TestEventRecord(unittest.TestCase):
    """Tests for EventRecord dataclass."""

    def test_creation(self):
        r = EventRecord(
            event_type="IP_ADDRESS", data="1.2.3.4",
            module="sfp_dns", confidence=95, risk=20,
        )
        self.assertEqual(r.event_type, "IP_ADDRESS")
        self.assertEqual(r.data, "1.2.3.4")
        self.assertGreater(r.timestamp, 0)


class TestTypeStats(unittest.TestCase):
    """Tests for TypeStats."""

    def test_initial(self):
        s = TypeStats(event_type="IP_ADDRESS")
        self.assertEqual(s.count, 0)
        self.assertEqual(s.unique_values, 0)

    def test_record(self):
        s = TypeStats(event_type="IP_ADDRESS")
        s.record("1.2.3.4", "sfp_dns", confidence=100, risk=30)
        s.record("5.6.7.8", "sfp_dns", confidence=80, risk=50)
        s.record("1.2.3.4", "sfp_resolver", confidence=90, risk=30)

        self.assertEqual(s.count, 3)
        self.assertEqual(s.unique_values, 2)
        self.assertEqual(s.max_risk, 50)
        self.assertAlmostEqual(s.avg_confidence, 90.0)
        self.assertIn("sfp_dns", s.modules)
        self.assertIn("sfp_resolver", s.modules)

    def test_to_dict(self):
        s = TypeStats(event_type="IP_ADDRESS")
        s.record("1.2.3.4", "sfp_dns", confidence=100, risk=50)
        d = s.to_dict()
        self.assertEqual(d["event_type"], "IP_ADDRESS")
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["max_risk"], 50)


class TestScanResultAggregator(unittest.TestCase):
    """Tests for ScanResultAggregator."""

    def setUp(self):
        self.agg = ScanResultAggregator(scan_id="test-001")

    def test_empty_aggregator(self):
        self.assertEqual(self.agg.total_events, 0)
        self.assertEqual(self.agg.unique_types, 0)
        self.assertEqual(self.agg.unique_modules, 0)
        self.assertAlmostEqual(self.agg.overall_risk_score, 0.0)

    def test_add_event(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.assertEqual(self.agg.total_events, 1)
        self.assertEqual(self.agg.unique_types, 1)

    def test_multiple_events(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=10)
        self.agg.add_event("IP_ADDRESS", "5.6.7.8", "sfp_dns", risk=20)
        self.agg.add_event("INTERNET_NAME", "example.com", "sfp_spider")
        self.assertEqual(self.agg.total_events, 3)
        self.assertEqual(self.agg.unique_types, 2)
        self.assertEqual(self.agg.unique_modules, 2)

    def test_type_stats(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns",
                          confidence=100, risk=30)
        self.agg.add_event("IP_ADDRESS", "5.6.7.8", "sfp_resolver",
                          confidence=80, risk=60)
        stats = self.agg.get_type_stats()
        self.assertIn("IP_ADDRESS", stats)
        self.assertEqual(stats["IP_ADDRESS"]["count"], 2)
        self.assertEqual(stats["IP_ADDRESS"]["max_risk"], 60)

    def test_module_stats(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.agg.add_event("IP_ADDRESS", "5.6.7.8", "sfp_dns")
        self.agg.add_event("INTERNET_NAME", "x.com", "sfp_spider")
        stats = self.agg.get_module_stats()
        self.assertEqual(stats["sfp_dns"], 2)
        self.assertEqual(stats["sfp_spider"], 1)

    def test_category_breakdown(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.agg.add_event("MALICIOUS_IPADDR", "1.2.3.4", "sfp_vt", risk=80)
        self.agg.add_event("EMAILADDR", "a@b.com", "sfp_email")
        cats = self.agg.get_category_breakdown()
        self.assertIn("INFRASTRUCTURE", cats)
        self.assertIn("THREAT", cats)
        self.assertIn("IDENTITY", cats)

    def test_categorize_prefixes(self):
        test_cases = {
            "MALICIOUS_IPADDR": "THREAT",
            "BLACKLISTED_INTERNET_NAME": "THREAT",
            "VULNERABILITY_CVE_HIGH": "VULNERABILITY",
            "EMAILADDR": "IDENTITY",
            "IP_ADDRESS": "INFRASTRUCTURE",
            "SSL_CERTIFICATE_RAW": "CERTIFICATE",
            "URL_FORM": "WEB",
            "DNS_TEXT": "DNS",
            "SOCIAL_MEDIA": "SOCIAL",
            "CLOUD_STORAGE_BUCKET": "CLOUD",
            "UNKNOWN_TYPE": "OTHER",
        }
        for event_type, expected in test_cases.items():
            result = self.agg._categorize(event_type)
            self.assertEqual(result, expected,
                           f"{event_type} -> {result}, expected {expected}")

    def test_overall_risk_score_no_risk(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=0)
        self.assertAlmostEqual(self.agg.overall_risk_score, 0.0)

    def test_overall_risk_score_with_risk(self):
        self.agg.add_event("MALICIOUS_IPADDR", "1.2.3.4", "sfp_vt", risk=80)
        self.agg.add_event("VULNERABILITY_CVE_HIGH", "CVE-2024-0001",
                          "sfp_vuln", risk=90)
        score = self.agg.overall_risk_score
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_top_risk_events(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=10)
        self.agg.add_event("MALICIOUS_IPADDR", "1.2.3.4", "sfp_vt", risk=90)
        self.agg.add_event("VULNERABILITY_CVE_HIGH", "CVE-001", "sfp_v",
                          risk=80)
        top = self.agg.get_top_risk_events(limit=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["risk"], 90)
        self.assertEqual(top[1]["risk"], 80)

    def test_top_entities(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_resolver")
        self.agg.add_event("IP_ADDRESS", "5.6.7.8", "sfp_dns")
        top = self.agg.get_top_entities(limit=2)
        self.assertEqual(top[0][0], "1.2.3.4")
        self.assertEqual(top[0][1], 2)

    def test_timeline(self):
        base = time.time()
        for i in range(10):
            self.agg.add_event("IP_ADDRESS", f"1.2.3.{i}", "sfp_dns",
                              timestamp=base + i)
        timeline = self.agg.get_timeline(buckets=5)
        self.assertEqual(len(timeline), 5)
        total = sum(b["count"] for b in timeline)
        self.assertEqual(total, 10)

    def test_timeline_empty(self):
        self.assertEqual(self.agg.get_timeline(), [])

    def test_timeline_single_event(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        timeline = self.agg.get_timeline()
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["count"], 1)

    def test_get_summary(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=30)
        self.agg.add_event("MALICIOUS_IPADDR", "1.2.3.4", "sfp_vt", risk=80)
        summary = self.agg.get_summary()
        self.assertEqual(summary["scan_id"], "test-001")
        self.assertEqual(summary["total_events"], 2)
        self.assertIn("category_breakdown", summary)
        self.assertIn("top_risk_events", summary)
        self.assertIn("module_stats", summary)

    def test_reset(self):
        self.agg.add_event("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.agg.reset()
        self.assertEqual(self.agg.total_events, 0)
        self.assertEqual(self.agg.unique_types, 0)

    def test_duration(self):
        self.assertGreater(self.agg.duration, 0)


if __name__ == "__main__":
    unittest.main()
